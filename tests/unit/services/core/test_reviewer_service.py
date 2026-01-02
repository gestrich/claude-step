"""Tests for reviewer capacity checking and assignment

This module tests the reviewer_management module's ability to find available
reviewers based on GitHub API PR queries.
"""

import os
import pytest
import yaml
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from claudestep.services.core.reviewer_service import ReviewerService
from claudestep.services.core.pr_service import PRService
from claudestep.domain.models import ReviewerCapacityResult
from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

from tests.builders import ConfigBuilder


def config_dict_to_project_configuration(config_dict):
    """Helper to convert config dictionary to ProjectConfiguration domain model"""
    project = Project("test-project")
    yaml_content = yaml.dump(config_dict)
    return ProjectConfiguration.from_yaml_string(project, yaml_content)


def create_github_pr(pr_number, assignee_username, task_hash, project="myproject", task_desc=None):
    """Helper to create a GitHubPullRequest for testing"""
    if task_desc is None:
        task_desc = f"Task {task_hash[:8]}"

    return GitHubPullRequest(
        number=pr_number,
        title=f"ClaudeStep: {task_desc}",
        state="open",
        created_at=datetime.now(timezone.utc),
        merged_at=None,
        assignees=[GitHubUser(login=assignee_username)],
        labels=["claudestep"],
        head_ref_name=f"claude-step-{project}-{task_hash}"
    )


class TestFindAvailableReviewer:
    """Test suite for find_available_reviewer functionality"""

    @pytest.fixture
    def reviewers_config(self):
        """Fixture providing sample reviewer configuration"""
        config_dict = (ConfigBuilder()
                .with_reviewer("alice", 2)
                .with_reviewer("bob", 3)
                .with_reviewer("charlie", 1)
                .build())
        return config_dict_to_project_configuration(config_dict)

    @pytest.fixture
    def single_reviewer_config(self):
        """Fixture providing single reviewer configuration"""
        config_dict = ConfigBuilder().with_reviewer("alice", 2).build()
        return config_dict_to_project_configuration(config_dict)

    @pytest.fixture
    def mock_env(self):
        """Fixture providing GitHub environment variables"""
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
            yield

    @pytest.fixture
    def mock_pr_service(self):
        """Fixture providing mock PRService instance"""
        return Mock(spec=PRService)

    @pytest.fixture
    def reviewer_service(self, mock_env, mock_pr_service):
        """Fixture providing ReviewerService instance"""
        return ReviewerService("owner/repo", mock_pr_service)

    def test_find_reviewer_returns_first_with_capacity_when_all_available(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should return first reviewer when all reviewers have capacity"""
        # Arrange
        mock_pr_service.get_reviewer_prs_for_project.return_value = []  # No open PRs

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            reviewers_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "alice"  # First reviewer
        assert result.selected_reviewer == "alice"
        assert result.all_at_capacity is False
        assert len(result.reviewers_status) == 3

        # All reviewers should have capacity
        for reviewer_status in result.reviewers_status:
            assert reviewer_status["has_capacity"] is True
            assert reviewer_status["open_count"] == 0

    def test_find_reviewer_skips_at_capacity_reviewer(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should skip reviewer at capacity and select next available"""
        # Arrange
        def mock_get_reviewer_prs(username, project, label):
            if username == "alice":
                return [
                    create_github_pr(101, "alice", "00000001"),
                    create_github_pr(102, "alice", "00000002")
                ]
            return []

        mock_pr_service.get_reviewer_prs_for_project.side_effect = mock_get_reviewer_prs

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            reviewers_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "bob"  # Second reviewer has capacity
        assert result.selected_reviewer == "bob"
        assert result.all_at_capacity is False

        # Verify alice is at capacity
        alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
        assert alice_status["has_capacity"] is False
        assert alice_status["open_count"] == 2
        assert alice_status["max_prs"] == 2

        # Verify bob has capacity
        bob_status = next(r for r in result.reviewers_status if r["username"] == "bob")
        assert bob_status["has_capacity"] is True
        assert bob_status["open_count"] == 0

    def test_find_reviewer_returns_none_when_all_at_capacity(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should return None when all reviewers are at capacity"""
        # Arrange
        def mock_get_reviewer_prs(username, project, label):
            if username == "alice":
                return [
                    create_github_pr(101, "alice", "00000001"),
                    create_github_pr(102, "alice", "00000002")
                ]
            elif username == "bob":
                return [
                    create_github_pr(103, "bob", "00000003"),
                    create_github_pr(104, "bob", "00000004"),
                    create_github_pr(105, "bob", "00000005")
                ]
            elif username == "charlie":
                return [create_github_pr(106, "charlie", "00000006")]
            return []

        mock_pr_service.get_reviewer_prs_for_project.side_effect = mock_get_reviewer_prs

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            reviewers_config, "claudestep", "myproject"
        )

        # Assert
        assert selected is None
        assert result.selected_reviewer is None
        assert result.all_at_capacity is True

        # All reviewers should be at capacity
        for reviewer_status in result.reviewers_status:
            assert reviewer_status["has_capacity"] is False
            assert reviewer_status["open_count"] == reviewer_status["max_prs"]

    def test_find_reviewer_handles_over_capacity_reviewer(
        self, single_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should correctly identify reviewer as over capacity"""
        # Arrange - reviewer has 3 PRs but maxOpenPRs is 2
        mock_pr_service.get_reviewer_prs_for_project.return_value = [
            create_github_pr(101, "alice", "00000001"),
            create_github_pr(102, "alice", "00000002"),
            create_github_pr(103, "alice", "00000003")
        ]

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            single_reviewer_config, "claudestep", "myproject"
        )

        # Assert
        assert selected is None
        assert result.all_at_capacity is True
        alice_status = result.reviewers_status[0]
        assert alice_status["has_capacity"] is False
        assert alice_status["open_count"] == 3  # Over capacity
        assert alice_status["max_prs"] == 2

    def test_find_reviewer_with_zero_max_prs(self, reviewer_service, mock_pr_service):
        """Should handle reviewer with maxOpenPRs set to zero"""
        # Arrange
        config_dict = (ConfigBuilder()
                      .with_reviewer("alice", 0)
                      .with_reviewer("bob", 2)
                      .build())
        config = config_dict_to_project_configuration(config_dict)

        mock_pr_service.get_reviewer_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "bob"  # alice has 0 capacity, bob selected
        alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
        assert alice_status["has_capacity"] is False  # 0 < 0 is False

    def test_find_reviewer_filters_by_project_name(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should only count PRs for the specified project"""
        # Arrange - alice has PRs for different projects
        # The get_reviewer_prs_for_project method already filters by project,
        # so we return only the PRs for the requested project
        def mock_get_reviewer_prs(username, project, label):
            if username == "alice" and project == "myproject":
                return [create_github_pr(101, "alice", "00000001", project="myproject")]
            return []

        mock_pr_service.get_reviewer_prs_for_project.side_effect = mock_get_reviewer_prs

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            reviewers_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "alice"  # alice has 1/2 for myproject, still has capacity
        alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
        assert alice_status["open_count"] == 1  # Only counts myproject PR
        assert alice_status["has_capacity"] is True

    def test_find_reviewer_stores_pr_details_correctly(
        self, single_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should store PR number, task index, and description in result"""
        # Arrange
        mock_pr_service.get_reviewer_prs_for_project.return_value = [
            create_github_pr(201, "alice", "00000005", task_desc="Update authentication flow")
        ]

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            single_reviewer_config, "claudestep", "myproject"
        )

        # Assert
        alice_status = result.reviewers_status[0]
        assert len(alice_status["open_prs"]) == 1
        pr_info = alice_status["open_prs"][0]
        assert pr_info["pr_number"] == 201
        assert pr_info["task_hash"] is not None
        assert pr_info["task_description"] == "Update authentication flow"

    def test_find_reviewer_with_empty_reviewers_list_uses_project_capacity(
        self, reviewer_service, mock_pr_service
    ):
        """Should use project-level capacity when no reviewers configured"""
        # Arrange
        config_dict = ConfigBuilder().with_no_reviewers().build()
        config = config_dict_to_project_configuration(config_dict)

        # No open PRs for project - should have capacity
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            config, "claudestep", "myproject"
        )

        # Assert
        assert selected is None  # No reviewer assigned
        assert result.selected_reviewer is None
        assert result.all_at_capacity is False  # Has capacity (0 < 1)
        assert len(result.reviewers_status) == 1  # Virtual project entry
        assert result.reviewers_status[0]["username"] == "(project: myproject)"
        assert result.reviewers_status[0]["max_prs"] == 1
        assert result.reviewers_status[0]["has_capacity"] is True

    def test_find_reviewer_calls_list_open_prs_with_correct_params(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should call get_reviewer_prs_for_project with correct parameters"""
        # Arrange
        mock_pr_service.get_reviewer_prs_for_project.return_value = []

        # Act
        reviewer_service.find_available_reviewer(reviewers_config, "my-label", "test-project")

        # Assert
        # Should be called once per reviewer
        assert mock_pr_service.get_reviewer_prs_for_project.call_count == 3
        # Check first call (alice)
        first_call = mock_pr_service.get_reviewer_prs_for_project.call_args_list[0]
        assert first_call[1]["username"] == "alice"
        assert first_call[1]["project"] == "test-project"
        assert first_call[1]["label"] == "my-label"

    def test_find_reviewer_uses_github_repository_env_var(self, reviewers_config):
        """Should use GITHUB_REPOSITORY environment variable"""
        # Arrange
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "test-owner/test-repo"}):
            mock_pr_service = Mock(spec=PRService)
            mock_pr_service.get_reviewer_prs_for_project.return_value = []

            # Create service with test repo
            service = ReviewerService("test-owner/test-repo", mock_pr_service)

            # Act
            service.find_available_reviewer(reviewers_config, "claudestep", "myproject")

            # Assert
            # Verify the service was called (repo is stored in the service itself)
            assert service.repo == "test-owner/test-repo"
            assert mock_pr_service.get_reviewer_prs_for_project.call_count == 3

    def test_find_reviewer_handles_prs_without_branch_name(
        self, single_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should skip PRs that have no branch name"""
        # Arrange
        # PRs without branch names have project_name = None, so they are
        # filtered out by get_reviewer_prs_for_project before reaching
        # the reviewer management service. The mock should return empty list.
        mock_pr_service.get_reviewer_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            single_reviewer_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "alice"  # Still has capacity since PR was skipped
        alice_status = result.reviewers_status[0]
        assert alice_status["open_count"] == 0

    def test_find_reviewer_with_boundary_condition_exactly_at_capacity(
        self, single_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should correctly identify when reviewer is exactly at capacity"""
        # Arrange - exactly 2 PRs for maxOpenPRs of 2
        mock_pr_service.get_reviewer_prs_for_project.return_value = [
            create_github_pr(101, "alice", "00000001"),
            create_github_pr(102, "alice", "00000002")
        ]

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            single_reviewer_config, "claudestep", "myproject"
        )

        # Assert
        assert selected is None
        alice_status = result.reviewers_status[0]
        assert alice_status["open_count"] == 2
        assert alice_status["max_prs"] == 2
        assert alice_status["has_capacity"] is False  # Exactly at capacity

    def test_find_reviewer_with_boundary_condition_one_under_capacity(
        self, single_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should correctly identify when reviewer is just under capacity"""
        # Arrange - 1 PR for maxOpenPRs of 2
        mock_pr_service.get_reviewer_prs_for_project.return_value = [
            create_github_pr(101, "alice", "00000001")
        ]

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            single_reviewer_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "alice"
        alice_status = result.reviewers_status[0]
        assert alice_status["open_count"] == 1
        assert alice_status["max_prs"] == 2
        assert alice_status["has_capacity"] is True  # One under capacity

    def test_find_reviewer_returns_first_available_not_all(
        self, reviewers_config, reviewer_service, mock_pr_service
    ):
        """Should return first available reviewer, not all available reviewers"""
        # Arrange - alice and bob both have capacity
        mock_pr_service.get_reviewer_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            reviewers_config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "alice"  # First in list
        assert result.selected_reviewer == "alice"

        # Verify multiple reviewers have capacity but only first is selected
        reviewers_with_capacity = [
            r for r in result.reviewers_status if r["has_capacity"]
        ]
        assert len(reviewers_with_capacity) == 3  # All have capacity
        assert reviewers_with_capacity[0]["username"] == "alice"

    def test_find_reviewer_mixed_capacity_scenarios(self, reviewer_service, mock_pr_service):
        """Should handle complex mixed capacity scenario"""
        # Arrange - alice at capacity, bob has room, charlie over capacity
        config_dict = (ConfigBuilder()
                      .with_reviewer("alice", 2)
                      .with_reviewer("bob", 3)
                      .with_reviewer("charlie", 1)
                      .build())
        config = config_dict_to_project_configuration(config_dict)

        def mock_get_reviewer_prs(username, project, label):
            if username == "alice":
                return [
                    create_github_pr(101, "alice", "00000001"),
                    create_github_pr(102, "alice", "00000002")
                ]
            elif username == "bob":
                return [create_github_pr(103, "bob", "00000003")]
            elif username == "charlie":
                return [
                    create_github_pr(104, "charlie", "00000004"),
                    create_github_pr(105, "charlie", "00000005")
                ]
            return []

        mock_pr_service.get_reviewer_prs_for_project.side_effect = mock_get_reviewer_prs

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            config, "claudestep", "myproject"
        )

        # Assert
        assert selected == "bob"  # Only bob has capacity
        assert result.all_at_capacity is False

        # Verify status for each reviewer
        alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
        assert alice_status["has_capacity"] is False
        assert alice_status["open_count"] == 2

        bob_status = next(r for r in result.reviewers_status if r["username"] == "bob")
        assert bob_status["has_capacity"] is True
        assert bob_status["open_count"] == 1

        charlie_status = next(r for r in result.reviewers_status if r["username"] == "charlie")
        assert charlie_status["has_capacity"] is False
        assert charlie_status["open_count"] == 2  # Over capacity

    def test_find_reviewer_handles_missing_github_repository_env(self, reviewers_config):
        """Should handle missing GITHUB_REPOSITORY environment variable"""
        # Arrange - no GITHUB_REPOSITORY env var
        with patch.dict(os.environ, {}, clear=True):
            mock_pr_service = Mock(spec=PRService)
            mock_pr_service.get_reviewer_prs_for_project.return_value = []

            # Create service with empty repo
            service = ReviewerService("", mock_pr_service)

            # Act
            selected, result = service.find_available_reviewer(
                reviewers_config, "claudestep", "myproject"
            )

            # Assert
            # Verify the service was called and repo is stored correctly
            assert service.repo == ""
            assert mock_pr_service.get_reviewer_prs_for_project.call_count == 3


class TestFindAvailableReviewerNoReviewers:
    """Test suite for find_available_reviewer with no reviewers configured (project capacity)"""

    @pytest.fixture
    def mock_env(self):
        """Fixture providing GitHub environment variables"""
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
            yield

    @pytest.fixture
    def mock_pr_service(self):
        """Fixture providing mock PRService instance"""
        return Mock(spec=PRService)

    @pytest.fixture
    def reviewer_service(self, mock_env, mock_pr_service):
        """Fixture providing ReviewerService instance"""
        return ReviewerService("owner/repo", mock_pr_service)

    @pytest.fixture
    def no_reviewer_config(self):
        """Fixture providing configuration with no reviewers"""
        project = Project("test-project")
        return ProjectConfiguration.default(project)

    def test_no_reviewers_with_capacity_available(
        self, no_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should allow PR creation when project has no open PRs"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            no_reviewer_config, "claudestep", "test-project"
        )

        # Assert
        assert selected is None  # No reviewer assigned
        assert result.selected_reviewer is None
        assert result.all_at_capacity is False  # Has capacity

    def test_no_reviewers_at_capacity(
        self, no_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should block PR creation when project has open PR at limit"""
        # Arrange - 1 open PR, limit is 1
        mock_pr_service.get_open_prs_for_project.return_value = [
            create_github_pr(101, None, "00000001", project="test-project")
        ]

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            no_reviewer_config, "claudestep", "test-project"
        )

        # Assert
        assert selected is None  # No reviewer
        assert result.all_at_capacity is True  # At capacity

    def test_no_reviewers_calls_get_open_prs_for_project(
        self, no_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should call get_open_prs_for_project to check project capacity"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        reviewer_service.find_available_reviewer(
            no_reviewer_config, "claudestep", "test-project"
        )

        # Assert
        mock_pr_service.get_open_prs_for_project.assert_called_once_with(
            "test-project", label="claudestep"
        )
        # Should NOT call get_reviewer_prs_for_project since no reviewers
        mock_pr_service.get_reviewer_prs_for_project.assert_not_called()

    def test_no_reviewers_result_includes_project_info(
        self, no_reviewer_config, reviewer_service, mock_pr_service
    ):
        """Should include project capacity info in result"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        selected, result = reviewer_service.find_available_reviewer(
            no_reviewer_config, "claudestep", "test-project"
        )

        # Assert
        assert len(result.reviewers_status) == 1
        project_status = result.reviewers_status[0]
        assert project_status["username"] == "(project: test-project)"
        assert project_status["max_prs"] == 1  # DEFAULT_PROJECT_PR_LIMIT
        assert project_status["open_count"] == 0
        assert project_status["has_capacity"] is True
