"""Tests for assignee capacity checking

This module tests the AssigneeService's ability to check project capacity
and provide assignee information.
"""

import os
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from claudechain.services.core.assignee_service import AssigneeService
from claudechain.services.core.pr_service import PRService
from claudechain.domain.project import Project
from claudechain.domain.project_configuration import ProjectConfiguration
from claudechain.domain.github_models import GitHubPullRequest, GitHubUser


def create_github_pr(pr_number, task_hash, project="myproject", task_desc=None):
    """Helper to create a GitHubPullRequest for testing"""
    if task_desc is None:
        task_desc = f"Task {task_hash[:8]}"

    return GitHubPullRequest(
        number=pr_number,
        title=f"ClaudeChain: {task_desc}",
        state="open",
        created_at=datetime.now(timezone.utc),
        merged_at=None,
        assignees=[],
        labels=["claudechain"],
        head_ref_name=f"claude-chain-{project}-{task_hash}"
    )


class TestCheckCapacity:
    """Test suite for check_capacity functionality"""

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
    def assignee_service(self, mock_env, mock_pr_service):
        """Fixture providing AssigneeService instance"""
        return AssigneeService("owner/repo", mock_pr_service)

    @pytest.fixture
    def config_with_assignee(self):
        """Fixture providing configuration with assignee"""
        project = Project("test-project")
        return ProjectConfiguration(
            project=project,
            assignee="alice"
        )

    @pytest.fixture
    def config_without_assignee(self):
        """Fixture providing configuration without assignee"""
        project = Project("test-project")
        return ProjectConfiguration(
            project=project,
            assignee=None
        )

    def test_check_capacity_returns_true_when_no_open_prs(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should return has_capacity=True when no open PRs"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        result = assignee_service.check_capacity(
            config_with_assignee, "claudechain", "myproject"
        )

        # Assert
        assert result.has_capacity is True
        assert result.assignee == "alice"
        assert result.open_count == 0

    def test_check_capacity_returns_false_when_one_open_pr(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should return has_capacity=False when there is 1 open PR"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = [
            create_github_pr(101, "00000001")
        ]

        # Act
        result = assignee_service.check_capacity(
            config_with_assignee, "claudechain", "myproject"
        )

        # Assert
        assert result.has_capacity is False
        assert result.open_count == 1

    def test_check_capacity_returns_assignee_from_config(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should return assignee from configuration"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        result = assignee_service.check_capacity(
            config_with_assignee, "claudechain", "myproject"
        )

        # Assert
        assert result.assignee == "alice"

    def test_check_capacity_returns_none_assignee_when_not_configured(
        self, config_without_assignee, assignee_service, mock_pr_service
    ):
        """Should return None assignee when not configured"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        result = assignee_service.check_capacity(
            config_without_assignee, "claudechain", "myproject"
        )

        # Assert
        assert result.assignee is None
        assert result.has_capacity is True  # Still has capacity

    def test_check_capacity_includes_open_pr_info(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should include PR details in result"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = [
            create_github_pr(201, "00000005", task_desc="Update authentication flow")
        ]

        # Act
        result = assignee_service.check_capacity(
            config_with_assignee, "claudechain", "myproject"
        )

        # Assert
        assert len(result.open_prs) == 1
        pr_info = result.open_prs[0]
        assert pr_info["pr_number"] == 201
        assert pr_info["task_description"] == "Update authentication flow"

    def test_check_capacity_calls_get_open_prs_with_correct_params(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should call get_open_prs_for_project with correct parameters"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        assignee_service.check_capacity(config_with_assignee, "my-label", "test-project")

        # Assert
        mock_pr_service.get_open_prs_for_project.assert_called_once_with(
            "test-project", label="my-label"
        )

    def test_check_capacity_includes_project_name_in_result(
        self, config_with_assignee, assignee_service, mock_pr_service
    ):
        """Should include project name in result"""
        # Arrange
        mock_pr_service.get_open_prs_for_project.return_value = []

        # Act
        result = assignee_service.check_capacity(
            config_with_assignee, "claudechain", "test-project"
        )

        # Assert
        assert result.project_name == "test-project"


class TestCapacityResultFormatSummary:
    """Test suite for CapacityResult.format_summary()"""

    def test_format_summary_shows_capacity_available(self):
        """Should format summary correctly when capacity available"""
        from claudechain.domain.models import CapacityResult

        result = CapacityResult(
            has_capacity=True,
            assignee="alice",
            open_prs=[],
            project_name="test-project"
        )

        summary = result.format_summary()

        assert "✅" in summary
        assert "test-project" in summary
        assert "Capacity available" in summary
        assert "alice" in summary

    def test_format_summary_shows_at_capacity(self):
        """Should format summary correctly when at capacity"""
        from claudechain.domain.models import CapacityResult

        result = CapacityResult(
            has_capacity=False,
            assignee="alice",
            open_prs=[{"pr_number": 123, "task_description": "Some task"}],
            project_name="test-project"
        )

        summary = result.format_summary()

        assert "❌" in summary
        assert "At capacity" in summary
        assert "PR #123" in summary

    def test_format_summary_shows_no_assignee_message(self):
        """Should show appropriate message when no assignee configured"""
        from claudechain.domain.models import CapacityResult

        result = CapacityResult(
            has_capacity=True,
            assignee=None,
            open_prs=[],
            project_name="test-project"
        )

        summary = result.format_summary()

        assert "without assignee" in summary
