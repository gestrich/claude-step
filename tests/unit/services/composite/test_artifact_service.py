"""Tests for artifact operations module

This module tests the centralized artifact operations API that provides a unified
interface for working with GitHub workflow artifacts containing task metadata.
"""

import json
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest

from claudestep.services.composite.artifact_service import (
    ProjectArtifact,
    TaskMetadata,
    find_in_progress_tasks,
    find_project_artifacts,
    get_artifact_metadata,
    get_reviewer_assignments,
    parse_task_index_from_name,
)
from claudestep.domain.models import AITask
from claudestep.domain.exceptions import GitHubAPIError


class TestTaskMetadata:
    """Test suite for TaskMetadata model"""

    def test_from_dict_creates_metadata_with_all_fields(self):
        """Should parse all fields from artifact JSON dictionary"""
        # Arrange
        data = {
            "task_index": 5,
            "task_description": "Add authentication",
            "project": "my-project",
            "branch_name": "claude-step-my-project-5",
            "reviewer": "alice",
            "created_at": "2025-01-15T10:30:00Z",
            "workflow_run_id": 12345,
            "pr_number": 42,
            "main_task_cost_usd": 1.25,
            "pr_summary_cost_usd": 0.15,
            "total_cost_usd": 1.40,
        }

        # Act
        metadata = TaskMetadata.from_dict(data)

        # Assert
        assert metadata.task_index == 5
        assert metadata.task_description == "Add authentication"
        assert metadata.project == "my-project"
        assert metadata.branch_name == "claude-step-my-project-5"
        assert metadata.reviewer == "alice"
        assert metadata.workflow_run_id == 12345
        assert metadata.pr_number == 42
        assert metadata.main_task_cost_usd == 1.25
        assert metadata.pr_summary_cost_usd == 0.15
        assert metadata.total_cost_usd == 1.40

    def test_from_dict_parses_datetime_correctly(self):
        """Should convert ISO datetime string to datetime object"""
        # Arrange
        data = {
            "task_index": 1,
            "task_description": "Test",
            "project": "test",
            "branch_name": "test-branch",
            "reviewer": "alice",
            "created_at": "2025-12-27T15:30:00Z",
            "workflow_run_id": 123,
            "pr_number": 1,
        }

        # Act
        metadata = TaskMetadata.from_dict(data)

        # Assert
        assert isinstance(metadata.created_at, datetime)
        assert metadata.created_at.year == 2025
        assert metadata.created_at.month == 12
        assert metadata.created_at.day == 27

    def test_from_dict_uses_default_cost_values(self):
        """Should use 0.0 default for missing cost fields"""
        # Arrange
        data = {
            "task_index": 1,
            "task_description": "Test",
            "project": "test",
            "branch_name": "test-branch",
            "reviewer": "alice",
            "created_at": "2025-12-27T15:30:00Z",
            "workflow_run_id": 123,
            "pr_number": 1,
            # Cost fields omitted
        }

        # Act
        metadata = TaskMetadata.from_dict(data)

        # Assert
        assert metadata.main_task_cost_usd == 0.0
        assert metadata.pr_summary_cost_usd == 0.0
        assert metadata.total_cost_usd == 0.0

    def test_from_dict_parses_ai_tasks_list(self):
        """Should parse ai_tasks list from JSON dictionary"""
        # Arrange
        data = {
            "task_index": 1,
            "task_description": "Add feature",
            "project": "my-project",
            "branch_name": "claude-step-my-project-abc12345",
            "reviewer": "alice",
            "created_at": "2025-12-27T15:30:00Z",
            "workflow_run_id": 123,
            "pr_number": 42,
            "ai_tasks": [
                {
                    "type": "PRCreation",
                    "model": "claude-sonnet-4",
                    "cost_usd": 0.15,
                    "created_at": "2025-12-27T15:25:00Z",
                    "tokens_input": 5000,
                    "tokens_output": 2000,
                    "duration_seconds": 45.2
                },
                {
                    "type": "PRSummary",
                    "model": "claude-sonnet-4",
                    "cost_usd": 0.02,
                    "created_at": "2025-12-27T15:28:00Z",
                    "tokens_input": 1000,
                    "tokens_output": 500,
                    "duration_seconds": 8.1
                }
            ]
        }

        # Act
        metadata = TaskMetadata.from_dict(data)

        # Assert
        assert len(metadata.ai_tasks) == 2
        assert metadata.ai_tasks[0].type == "PRCreation"
        assert metadata.ai_tasks[0].model == "claude-sonnet-4"
        assert metadata.ai_tasks[0].cost_usd == 0.15
        assert metadata.ai_tasks[0].tokens_input == 5000
        assert metadata.ai_tasks[1].type == "PRSummary"
        assert metadata.ai_tasks[1].cost_usd == 0.02

    def test_get_total_cost_sums_ai_tasks(self):
        """Should calculate total cost from ai_tasks list"""
        # Arrange
        now = datetime.now(timezone.utc)
        metadata = TaskMetadata(
            task_index=1,
            task_description="Test",
            project="test",
            branch_name="test-branch",
            reviewer="alice",
            created_at=now,
            workflow_run_id=123,
            pr_number=1,
            ai_tasks=[
                AITask(type="PRCreation", model="claude-sonnet-4", cost_usd=0.15, created_at=now),
                AITask(type="PRSummary", model="claude-sonnet-4", cost_usd=0.02, created_at=now),
            ]
        )

        # Act
        total = metadata.get_total_cost()

        # Assert
        assert total == pytest.approx(0.17, rel=1e-6)

    def test_to_dict_includes_ai_tasks(self):
        """Should serialize ai_tasks to JSON dictionary"""
        # Arrange
        now = datetime.now(timezone.utc)
        metadata = TaskMetadata(
            task_index=1,
            task_description="Test",
            project="test",
            branch_name="test-branch",
            reviewer="alice",
            created_at=now,
            workflow_run_id=123,
            pr_number=42,
            ai_tasks=[
                AITask(type="PRCreation", model="claude-sonnet-4", cost_usd=0.25, created_at=now,
                       tokens_input=3000, tokens_output=1500, duration_seconds=30.5),
            ]
        )

        # Act
        data = metadata.to_dict()

        # Assert
        assert "ai_tasks" in data
        assert len(data["ai_tasks"]) == 1
        assert data["ai_tasks"][0]["type"] == "PRCreation"
        assert data["ai_tasks"][0]["model"] == "claude-sonnet-4"
        assert data["ai_tasks"][0]["cost_usd"] == 0.25
        assert data["ai_tasks"][0]["tokens_input"] == 3000
        assert data["total_cost_usd"] == 0.25

    def test_json_roundtrip_with_ai_tasks(self):
        """Should correctly roundtrip TaskMetadata with AITask list through JSON"""
        # Arrange
        now = datetime.now(timezone.utc)
        original = TaskMetadata(
            task_index=5,
            task_description="Implement authentication",
            project="auth-project",
            branch_name="claude-step-auth-project-a1b2c3d4",
            reviewer="bob",
            created_at=now,
            workflow_run_id=99999,
            pr_number=123,
            pr_state="open",
            ai_tasks=[
                AITask(type="PRCreation", model="claude-opus-4", cost_usd=0.50, created_at=now,
                       tokens_input=10000, tokens_output=5000, duration_seconds=120.0),
                AITask(type="PRSummary", model="claude-sonnet-4", cost_usd=0.05, created_at=now,
                       tokens_input=2000, tokens_output=800, duration_seconds=15.0),
            ]
        )

        # Act - serialize to JSON and back
        json_str = json.dumps(original.to_dict())
        parsed_data = json.loads(json_str)
        restored = TaskMetadata.from_dict(parsed_data)

        # Assert
        assert restored.task_index == original.task_index
        assert restored.task_description == original.task_description
        assert restored.project == original.project
        assert restored.pr_number == original.pr_number
        assert len(restored.ai_tasks) == 2
        assert restored.ai_tasks[0].type == "PRCreation"
        assert restored.ai_tasks[0].cost_usd == 0.50
        assert restored.ai_tasks[1].type == "PRSummary"
        assert restored.get_total_cost() == 0.55


class TestProjectArtifact:
    """Test suite for ProjectArtifact model"""

    def test_task_index_returns_metadata_task_index_when_available(self):
        """Should return task index from metadata when metadata is populated"""
        # Arrange
        metadata = TaskMetadata(
            task_index=7,
            task_description="Test",
            project="test",
            branch_name="test-branch",
            reviewer="alice",
            created_at=datetime.now(timezone.utc),
            workflow_run_id=123,
            pr_number=1,
        )
        artifact = ProjectArtifact(
            artifact_id=1,
            artifact_name="task-metadata-test-7.json",
            workflow_run_id=123,
            metadata=metadata,
        )

        # Act
        result = artifact.task_index

        # Assert
        assert result == 7

    def test_task_index_parses_from_name_when_metadata_missing(self):
        """Should fallback to parsing artifact name when metadata is None"""
        # Arrange
        artifact = ProjectArtifact(
            artifact_id=1,
            artifact_name="task-metadata-myproject-42.json",
            workflow_run_id=123,
            metadata=None,
        )

        # Act
        result = artifact.task_index

        # Assert
        assert result == 42


class TestParseTaskIndexFromName:
    """Test suite for parse_task_index_from_name utility"""

    @pytest.mark.parametrize(
        "artifact_name,expected_index",
        [
            ("task-metadata-myproject-1.json", 1),
            ("task-metadata-test-123.json", 123),
            ("task-metadata-a-999.json", 999),
        ],
    )
    def test_parse_task_index_extracts_index_correctly(
        self, artifact_name, expected_index
    ):
        """Should extract task index from standard artifact name format"""
        # Act
        result = parse_task_index_from_name(artifact_name)

        # Assert
        assert result == expected_index

    def test_parse_task_index_supports_hyphenated_project_names(self):
        """Should correctly parse task index from project names with hyphens

        Note: The regex pattern .+ supports project names with hyphens.
        """
        # Act
        result = parse_task_index_from_name("task-metadata-my-project-42.json")

        # Assert
        assert result == 42  # Regex now supports hyphenated project names

    @pytest.mark.parametrize(
        "invalid_name",
        [
            "task-metadata-project.json",  # Missing index
            "task-metadata-project-abc.json",  # Non-numeric index
            "random-artifact-5.json",  # Wrong prefix
            "task-metadata-5.json",  # Missing project separator
            "",  # Empty string
            "not-a-match",  # No pattern match
        ],
    )
    def test_parse_task_index_returns_none_for_invalid_names(self, invalid_name):
        """Should return None when artifact name doesn't match expected pattern"""
        # Act
        result = parse_task_index_from_name(invalid_name)

        # Assert
        assert result is None


class TestFindProjectArtifacts:
    """Test suite for find_project_artifacts function"""

    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_with_open_prs(
        self, mock_pr_service_class, mock_gh_api_call
    ):
        """Should find artifacts for open PRs by querying workflow runs"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]

        # Mock workflow runs response
        mock_gh_api_call.side_effect = [
            {
                "workflow_runs": [
                    {"id": 100, "conclusion": "success"},
                ]
            },
            # Mock artifacts response
            {
                "artifacts": [
                    {
                        "id": 1,
                        "name": "task-metadata-test-1.json",
                    }
                ]
            },
        ]

        # Act
        result = find_project_artifacts(
            repo="owner/repo",
            project="test",
            pr_state="open",
            download_metadata=False,
        )

        # Assert
        assert len(result) == 1
        assert result[0].artifact_id == 1
        assert result[0].artifact_name == "task-metadata-test-1.json"
        assert result[0].workflow_run_id == 100
        assert result[0].metadata is None

    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_filters_by_project_name(
        self, mock_pr_service_class, mock_gh_api_call
    ):
        """Should only return artifacts matching the project name"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]

        mock_gh_api_call.side_effect = [
            {"workflow_runs": [{"id": 100, "conclusion": "success"}]},
            {
                "artifacts": [
                    {"id": 1, "name": "task-metadata-test-1.json"},
                    {"id": 2, "name": "task-metadata-other-1.json"},
                    {"id": 3, "name": "task-metadata-test-2.json"},
                ]
            },
        ]

        # Act
        result = find_project_artifacts(
            repo="owner/repo", project="test", pr_state="open"
        )

        # Assert
        assert len(result) == 2
        assert result[0].artifact_name == "task-metadata-test-1.json"
        assert result[1].artifact_name == "task-metadata-test-2.json"

    @patch("claudestep.services.composite.artifact_service.download_artifact_json")
    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_downloads_metadata_when_requested(
        self, mock_pr_service_class, mock_gh_api_call, mock_download
    ):
        """Should download and parse metadata when download_metadata=True"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]
        mock_gh_api_call.side_effect = [
            {"workflow_runs": [{"id": 100, "conclusion": "success"}]},
            {"artifacts": [{"id": 1, "name": "task-metadata-test-1.json"}]},
        ]
        mock_download.return_value = {
            "task_index": 1,
            "task_description": "Test task",
            "project": "test",
            "branch_name": "claude-step-test-1",
            "reviewer": "alice",
            "created_at": "2025-12-27T15:30:00Z",
            "workflow_run_id": 100,
            "pr_number": 42,
        }

        # Act
        result = find_project_artifacts(
            repo="owner/repo",
            project="test",
            pr_state="open",
            download_metadata=True,
        )

        # Assert
        assert len(result) == 1
        assert result[0].metadata is not None
        assert result[0].metadata.task_index == 1
        assert result[0].metadata.reviewer == "alice"
        mock_download.assert_called_once_with("owner/repo", 1)

    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_skips_failed_runs(
        self, mock_pr_service_class, mock_gh_api_call
    ):
        """Should only process workflow runs with success conclusion"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]
        mock_gh_api_call.return_value = {
            "workflow_runs": [
                {"id": 100, "conclusion": "failure"},
                {"id": 101, "conclusion": "success"},
                {"id": 102, "conclusion": "cancelled"},
            ]
        }

        # Act
        result = find_project_artifacts(
            repo="owner/repo", project="test", pr_state="all"
        )

        # Assert
        # Should only query artifacts for run 101 (success)
        # First call is for workflow runs, second should be for artifacts of run 101
        assert mock_gh_api_call.call_count == 2

    @patch(
        "claudestep.services.composite.artifact_service._get_artifacts_for_run"
    )
    @patch(
        "claudestep.services.composite.artifact_service.gh_api_call"
    )
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_deduplicates_artifacts(
        self, mock_pr_service_class, mock_gh_api_call, mock_get_artifacts
    ):
        """Should not return duplicate artifacts with same ID"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [
            {"headRefName": "claude-step-test-1"},
            {"headRefName": "claude-step-test-2"},
        ]
        # Return two workflow runs with same artifacts (to test deduplication)
        mock_gh_api_call.return_value = {
            "workflow_runs": [
                {"id": 100, "conclusion": "success"},
                {"id": 101, "conclusion": "success"},
            ]
        }
        # Return same artifact from both runs (same ID = duplicate)
        mock_get_artifacts.return_value = [
            {"id": 1, "name": "task-metadata-test-1.json"}
        ]

        # Act
        result = find_project_artifacts(
            repo="owner/repo", project="test", pr_state="open"
        )

        # Assert
        assert len(result) == 1  # Deduplicated by artifact ID
        assert mock_gh_api_call.call_count == 1  # Called once for workflow runs
        assert mock_get_artifacts.call_count == 2  # Called for each successful run

    @patch("claudestep.services.composite.artifact_service.download_artifact_json")
    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_handles_metadata_parsing_errors(
        self, mock_pr_service_class, mock_gh_api_call, mock_download, capsys
    ):
        """Should continue processing when metadata parsing fails"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]
        mock_gh_api_call.side_effect = [
            {"workflow_runs": [{"id": 100, "conclusion": "success"}]},
            {"artifacts": [{"id": 1, "name": "task-metadata-test-1.json"}]},
        ]
        mock_download.return_value = {"invalid": "data"}  # Missing required fields

        # Act
        result = find_project_artifacts(
            repo="owner/repo",
            project="test",
            pr_state="open",
            download_metadata=True,
        )

        # Assert
        assert len(result) == 1
        assert result[0].metadata is None  # Parsing failed
        captured = capsys.readouterr()
        assert "Warning: Failed to parse metadata" in captured.out

    @patch("claudestep.services.composite.artifact_service.gh_api_call")
    @patch("claudestep.services.core.pr_service.PRService")
    def test_find_project_artifacts_handles_api_errors(
        self, mock_pr_service_class, mock_gh_api_call, capsys
    ):
        """Should handle GitHub API errors gracefully"""
        # Arrange
        mock_pr_service = mock_pr_service_class.return_value
        mock_pr_service.get_project_prs.return_value = [{"headRefName": "claude-step-test-1"}]
        mock_gh_api_call.side_effect = GitHubAPIError("API rate limit exceeded")

        # Act
        result = find_project_artifacts(
            repo="owner/repo", project="test", pr_state="open"
        )

        # Assert
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "Warning: Failed to get workflow runs" in captured.out


class TestGetArtifactMetadata:
    """Test suite for get_artifact_metadata function"""

    @patch("claudestep.services.composite.artifact_service.download_artifact_json")
    def test_get_artifact_metadata_returns_parsed_metadata(self, mock_download):
        """Should download artifact and parse metadata"""
        # Arrange
        mock_download.return_value = {
            "task_index": 5,
            "task_description": "Test task",
            "project": "test",
            "branch_name": "claude-step-test-5",
            "reviewer": "bob",
            "created_at": "2025-12-27T10:00:00Z",
            "workflow_run_id": 200,
            "pr_number": 10,
        }

        # Act
        result = get_artifact_metadata(repo="owner/repo", artifact_id=42)

        # Assert
        assert result is not None
        assert result.task_index == 5
        assert result.reviewer == "bob"
        mock_download.assert_called_once_with("owner/repo", 42)

    @patch("claudestep.services.composite.artifact_service.download_artifact_json")
    def test_get_artifact_metadata_returns_none_when_download_fails(
        self, mock_download
    ):
        """Should return None when artifact download fails"""
        # Arrange
        mock_download.return_value = None

        # Act
        result = get_artifact_metadata(repo="owner/repo", artifact_id=42)

        # Assert
        assert result is None

    @patch("claudestep.services.composite.artifact_service.download_artifact_json")
    def test_get_artifact_metadata_returns_none_when_parsing_fails(
        self, mock_download, capsys
    ):
        """Should return None when metadata parsing fails"""
        # Arrange
        mock_download.return_value = {"invalid": "data"}

        # Act
        result = get_artifact_metadata(repo="owner/repo", artifact_id=42)

        # Assert
        assert result is None
        captured = capsys.readouterr()
        assert "Warning: Failed to parse metadata" in captured.out


class TestFindInProgressTasks:
    """Test suite for find_in_progress_tasks convenience function"""

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_find_in_progress_tasks_returns_task_indices(self, mock_find_artifacts):
        """Should return set of task indices from open PR artifacts"""
        # Arrange
        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-1.json",
                workflow_run_id=100,
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="task-metadata-test-5.json",
                workflow_run_id=101,
            ),
            ProjectArtifact(
                artifact_id=3,
                artifact_name="task-metadata-test-10.json",
                workflow_run_id=102,
            ),
        ]

        # Act
        result = find_in_progress_tasks(repo="owner/repo", project="test")

        # Assert
        assert result == {1, 5, 10}
        mock_find_artifacts.assert_called_once_with(
            repo="owner/repo",
            project="test",
            label="claudestep",
            pr_state="open",
            download_metadata=False,
        )

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_find_in_progress_tasks_filters_none_indices(self, mock_find_artifacts):
        """Should exclude artifacts with unparseable task indices"""
        # Arrange
        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-1.json",
                workflow_run_id=100,
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="invalid-name.json",  # Won't parse
                workflow_run_id=101,
            ),
        ]

        # Act
        result = find_in_progress_tasks(repo="owner/repo", project="test")

        # Assert
        assert result == {1}  # Only valid index

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_find_in_progress_tasks_returns_empty_set_when_no_artifacts(
        self, mock_find_artifacts
    ):
        """Should return empty set when no artifacts found"""
        # Arrange
        mock_find_artifacts.return_value = []

        # Act
        result = find_in_progress_tasks(repo="owner/repo", project="test")

        # Assert
        assert result == set()


class TestGetReviewerAssignments:
    """Test suite for get_reviewer_assignments convenience function"""

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_get_reviewer_assignments_returns_pr_to_reviewer_mapping(
        self, mock_find_artifacts
    ):
        """Should return dictionary mapping PR numbers to reviewers"""
        # Arrange
        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-1.json",
                workflow_run_id=100,
                metadata=TaskMetadata(
                    task_index=1,
                    task_description="Task 1",
                    project="test",
                    branch_name="claude-step-test-1",
                    reviewer="alice",
                    created_at=datetime.now(timezone.utc),
                    workflow_run_id=100,
                    pr_number=10,
                ),
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="task-metadata-test-2.json",
                workflow_run_id=101,
                metadata=TaskMetadata(
                    task_index=2,
                    task_description="Task 2",
                    project="test",
                    branch_name="claude-step-test-2",
                    reviewer="bob",
                    created_at=datetime.now(timezone.utc),
                    workflow_run_id=101,
                    pr_number=11,
                ),
            ),
        ]

        # Act
        result = get_reviewer_assignments(repo="owner/repo", project="test")

        # Assert
        assert result == {10: "alice", 11: "bob"}
        mock_find_artifacts.assert_called_once_with(
            repo="owner/repo",
            project="test",
            label="claudestep",
            pr_state="open",
            download_metadata=True,
        )

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_get_reviewer_assignments_filters_artifacts_without_metadata(
        self, mock_find_artifacts
    ):
        """Should exclude artifacts where metadata download failed"""
        # Arrange
        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-1.json",
                workflow_run_id=100,
                metadata=TaskMetadata(
                    task_index=1,
                    task_description="Task 1",
                    project="test",
                    branch_name="claude-step-test-1",
                    reviewer="alice",
                    created_at=datetime.now(timezone.utc),
                    workflow_run_id=100,
                    pr_number=10,
                ),
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="task-metadata-test-2.json",
                workflow_run_id=101,
                metadata=None,  # Failed to download/parse
            ),
        ]

        # Act
        result = get_reviewer_assignments(repo="owner/repo", project="test")

        # Assert
        assert result == {10: "alice"}  # Only artifact with metadata

    @patch("claudestep.services.composite.artifact_service.find_project_artifacts")
    def test_get_reviewer_assignments_returns_empty_dict_when_no_artifacts(
        self, mock_find_artifacts
    ):
        """Should return empty dictionary when no artifacts found"""
        # Arrange
        mock_find_artifacts.return_value = []

        # Act
        result = get_reviewer_assignments(repo="owner/repo", project="test")

        # Assert
        assert result == {}
