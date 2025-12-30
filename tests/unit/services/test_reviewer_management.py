"""Tests for reviewer capacity checking and assignment

This module tests the reviewer_management module's ability to find available
reviewers based on artifact metadata tracking their assigned PRs.
"""

import os
import pytest
from unittest.mock import Mock, patch

from claudestep.services.reviewer_management_service import ReviewerManagementService
from claudestep.services.artifact_operations_service import ProjectArtifact, TaskMetadata
from claudestep.domain.models import ReviewerCapacityResult
from datetime import datetime

from tests.builders import ConfigBuilder, ArtifactBuilder, TaskMetadataBuilder


class TestFindAvailableReviewer:
    """Test suite for find_available_reviewer functionality"""

    @pytest.fixture
    def reviewers_config(self):
        """Fixture providing sample reviewer configuration"""
        return (ConfigBuilder()
                .with_reviewer("alice", 2)
                .with_reviewer("bob", 3)
                .with_reviewer("charlie", 1)
                .build()["reviewers"])

    @pytest.fixture
    def single_reviewer_config(self):
        """Fixture providing single reviewer configuration"""
        return ConfigBuilder().with_reviewer("alice", 2).build()["reviewers"]

    @pytest.fixture
    def mock_env(self):
        """Fixture providing GitHub environment variables"""
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
            yield

    @pytest.fixture
    def reviewer_service(self, mock_env):
        """Fixture providing ReviewerManagementService instance"""
        from claudestep.services.metadata_service import MetadataService
        from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
        metadata_store = GitHubMetadataStore("owner/repo")
        metadata_service = MetadataService(metadata_store)
        return ReviewerManagementService("owner/repo", metadata_service)

    def _create_artifact_with_metadata(
        self,
        artifact_id: int,
        task_index: int,
        pr_number: int,
        reviewer: str,
        project: str = "myproject"
    ) -> ProjectArtifact:
        """Helper to create a ProjectArtifact with metadata using builders"""
        metadata = (TaskMetadataBuilder()
                    .with_task(task_index, f"Task {task_index}")
                    .with_project(project)
                    .with_reviewer(reviewer)
                    .with_pr_number(pr_number)
                    .with_workflow_run_id(1000 + artifact_id)
                    .build())

        return (ArtifactBuilder()
                .with_id(artifact_id)
                .with_task(task_index, project=project)
                .with_workflow_run_id(1000 + artifact_id)
                .with_metadata(metadata)
                .build())

    def test_find_reviewer_returns_first_with_capacity_when_all_available(
        self, reviewers_config, reviewer_service
    ):
        """Should return first reviewer when all reviewers have capacity"""
        # Arrange
        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = []  # No open PRs

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
        self, reviewers_config, reviewer_service
    ):
        """Should skip reviewer at capacity and select next available"""
        # Arrange
        artifacts = [
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "alice"),  # alice at capacity (2/2)
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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
        self, reviewers_config, reviewer_service
    ):
        """Should return None when all reviewers are at capacity"""
        # Arrange
        artifacts = [
            # alice: 2/2
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "alice"),
            # bob: 3/3
            self._create_artifact_with_metadata(3, 3, 103, "bob"),
            self._create_artifact_with_metadata(4, 4, 104, "bob"),
            self._create_artifact_with_metadata(5, 5, 105, "bob"),
            # charlie: 1/1
            self._create_artifact_with_metadata(6, 6, 106, "charlie"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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
        self, single_reviewer_config, reviewer_service
    ):
        """Should correctly identify reviewer as over capacity"""
        # Arrange - reviewer has 3 PRs but maxOpenPRs is 2
        artifacts = [
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "alice"),
            self._create_artifact_with_metadata(3, 3, 103, "alice"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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

    def test_find_reviewer_with_zero_max_prs(self, reviewer_service):
        """Should handle reviewer with maxOpenPRs set to zero"""
        # Arrange
        reviewers = [
            {"username": "alice", "maxOpenPRs": 0},
            {"username": "bob", "maxOpenPRs": 2}
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = []

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                reviewers, "claudestep", "myproject"
            )

            # Assert
            assert selected == "bob"  # alice has 0 capacity, bob selected
            alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
            assert alice_status["has_capacity"] is False  # 0 < 0 is False

    def test_find_reviewer_ignores_unknown_reviewers_in_artifacts(
        self, reviewers_config, reviewer_service
    ):
        """Should ignore PRs assigned to reviewers not in config"""
        # Arrange
        artifacts = [
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "unknown-user"),  # Not in config
            self._create_artifact_with_metadata(3, 3, 103, "another-unknown"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                reviewers_config, "claudestep", "myproject"
            )

            # Assert
            assert selected == "alice"  # alice has 1/2, still has capacity
            alice_status = next(r for r in result.reviewers_status if r["username"] == "alice")
            assert alice_status["open_count"] == 1
            assert alice_status["has_capacity"] is True

            # bob and charlie should have no PRs
            bob_status = next(r for r in result.reviewers_status if r["username"] == "bob")
            assert bob_status["open_count"] == 0

    def test_find_reviewer_stores_pr_details_correctly(
        self, single_reviewer_config, reviewer_service
    ):
        """Should store PR number, task index, and description in result"""
        # Arrange
        artifacts = [
            self._create_artifact_with_metadata(1, 5, 201, "alice"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                single_reviewer_config, "claudestep", "myproject"
            )

            # Assert
            alice_status = result.reviewers_status[0]
            assert len(alice_status["open_prs"]) == 1
            pr_info = alice_status["open_prs"][0]
            assert pr_info["pr_number"] == 201
            assert pr_info["task_index"] == 5
            assert pr_info["task_description"] == "Task 5"

    def test_find_reviewer_with_empty_reviewers_list(self, reviewer_service):
        """Should handle empty reviewers list gracefully"""
        # Arrange
        reviewers = []

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = []

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                reviewers, "claudestep", "myproject"
            )

            # Assert
            assert selected is None
            assert result.selected_reviewer is None
            assert result.all_at_capacity is True  # Technically true - no one has capacity
            assert len(result.reviewers_status) == 0

    def test_find_reviewer_calls_find_project_artifacts_with_correct_params(
        self, reviewers_config, reviewer_service
    ):
        """Should call find_project_artifacts with correct parameters"""
        # Arrange
        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = []

            # Act
            reviewer_service.find_available_reviewer(reviewers_config, "my-label", "test-project")

            # Assert
            mock_find.assert_called_once_with(
                repo="owner/repo",
                project="test-project",
                label="my-label",
                pr_state="open",
                download_metadata=True
            )

    def test_find_reviewer_uses_github_repository_env_var(self, reviewers_config):
        """Should use GITHUB_REPOSITORY environment variable"""
        # Arrange
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "test-owner/test-repo"}):
            with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
                mock_find.return_value = []

                # Create service with test repo
                from claudestep.services.metadata_service import MetadataService
                from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
                metadata_store = GitHubMetadataStore("test-owner/test-repo")
                metadata_service = MetadataService(metadata_store)
                service = ReviewerManagementService("test-owner/test-repo", metadata_service)

                # Act
                service.find_available_reviewer(reviewers_config, "claudestep", "myproject")

                # Assert
                mock_find.assert_called_once()
                call_kwargs = mock_find.call_args[1]
                assert call_kwargs["repo"] == "test-owner/test-repo"

    def test_find_reviewer_handles_artifacts_without_metadata(
        self, single_reviewer_config, reviewer_service
    ):
        """Should skip artifacts that have no metadata"""
        # Arrange
        artifact_without_metadata = ProjectArtifact(
            artifact_id=1,
            artifact_name="task-metadata-myproject-1.json",
            workflow_run_id=1001,
            metadata=None  # No metadata
        )

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = [artifact_without_metadata]

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                single_reviewer_config, "claudestep", "myproject"
            )

            # Assert
            assert selected == "alice"  # Still has capacity since artifact was skipped
            alice_status = result.reviewers_status[0]
            assert alice_status["open_count"] == 0

    def test_find_reviewer_with_boundary_condition_exactly_at_capacity(
        self, single_reviewer_config, reviewer_service
    ):
        """Should correctly identify when reviewer is exactly at capacity"""
        # Arrange - exactly 2 PRs for maxOpenPRs of 2
        artifacts = [
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "alice"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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
        self, single_reviewer_config, reviewer_service
    ):
        """Should correctly identify when reviewer is just under capacity"""
        # Arrange - 1 PR for maxOpenPRs of 2
        artifacts = [
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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
        self, reviewers_config, reviewer_service
    ):
        """Should return first available reviewer, not all available reviewers"""
        # Arrange - alice and bob both have capacity
        artifacts = []

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

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

    def test_find_reviewer_mixed_capacity_scenarios(self, reviewer_service):
        """Should handle complex mixed capacity scenario"""
        # Arrange - alice at capacity, bob has room, charlie over capacity
        reviewers = [
            {"username": "alice", "maxOpenPRs": 2},
            {"username": "bob", "maxOpenPRs": 3},
            {"username": "charlie", "maxOpenPRs": 1}
        ]

        artifacts = [
            # alice: 2/2 (at capacity)
            self._create_artifact_with_metadata(1, 1, 101, "alice"),
            self._create_artifact_with_metadata(2, 2, 102, "alice"),
            # bob: 1/3 (has capacity)
            self._create_artifact_with_metadata(3, 3, 103, "bob"),
            # charlie: 2/1 (over capacity - shouldn't happen but test it)
            self._create_artifact_with_metadata(4, 4, 104, "charlie"),
            self._create_artifact_with_metadata(5, 5, 105, "charlie"),
        ]

        with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
            mock_find.return_value = artifacts

            # Act
            selected, result = reviewer_service.find_available_reviewer(
                reviewers, "claudestep", "myproject"
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
            with patch('claudestep.services.reviewer_management_service.find_project_artifacts') as mock_find:
                mock_find.return_value = []

                # Create service with empty repo
                from claudestep.services.metadata_service import MetadataService
                from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
                metadata_store = GitHubMetadataStore("")
                metadata_service = MetadataService(metadata_store)
                service = ReviewerManagementService("", metadata_service)

                # Act
                selected, result = service.find_available_reviewer(
                    reviewers_config, "claudestep", "myproject"
                )

                # Assert
                mock_find.assert_called_once()
                call_kwargs = mock_find.call_args[1]
                assert call_kwargs["repo"] == ""  # Empty string when env var not set
