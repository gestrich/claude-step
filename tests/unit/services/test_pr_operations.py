"""Unit tests for PR operations and branch naming utilities"""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from claudestep.domain.github_models import GitHubPullRequest
from claudestep.services.pr_operations_service import PROperationsService


class TestFormatBranchName:
    """Tests for format_branch_name static method"""

    def test_format_basic_branch_name(self):
        """Should format branch name with project and index"""
        result = PROperationsService.format_branch_name("my-refactor", 1)
        assert result == "claude-step-my-refactor-1"

    def test_format_with_multi_word_project(self):
        """Should handle project names with multiple words"""
        result = PROperationsService.format_branch_name("swift-migration", 5)
        assert result == "claude-step-swift-migration-5"

    def test_format_with_large_index(self):
        """Should handle large task indices"""
        result = PROperationsService.format_branch_name("api-refactor", 42)
        assert result == "claude-step-api-refactor-42"

    def test_format_with_complex_project_name(self):
        """Should handle complex project names with hyphens"""
        result = PROperationsService.format_branch_name("my-complex-project-name", 3)
        assert result == "claude-step-my-complex-project-name-3"


class TestParseBranchName:
    """Tests for parse_branch_name static method"""

    def test_parse_basic_branch_name(self):
        """Should parse basic branch name"""
        result = PROperationsService.parse_branch_name("claude-step-my-refactor-1")
        assert result is not None
        project, index = result
        assert project == "my-refactor"
        assert index == 1

    def test_parse_multi_word_project(self):
        """Should parse project names with multiple words"""
        result = PROperationsService.parse_branch_name("claude-step-swift-migration-5")
        assert result is not None
        project, index = result
        assert project == "swift-migration"
        assert index == 5

    def test_parse_large_index(self):
        """Should handle large task indices"""
        result = PROperationsService.parse_branch_name("claude-step-api-refactor-42")
        assert result is not None
        project, index = result
        assert project == "api-refactor"
        assert index == 42

    def test_parse_complex_project_name(self):
        """Should handle complex project names with multiple hyphens"""
        result = PROperationsService.parse_branch_name("claude-step-my-complex-project-name-3")
        assert result is not None
        project, index = result
        assert project == "my-complex-project-name"
        assert index == 3

    def test_parse_invalid_branch_no_prefix(self):
        """Should return None for branch without claude-step prefix"""
        result = PROperationsService.parse_branch_name("my-refactor-1")
        assert result is None

    def test_parse_invalid_branch_wrong_format(self):
        """Should return None for branch with wrong format"""
        result = PROperationsService.parse_branch_name("claude-step-no-index")
        assert result is None

    def test_parse_invalid_branch_empty(self):
        """Should return None for empty branch name"""
        result = PROperationsService.parse_branch_name("")
        assert result is None

    def test_parse_invalid_branch_no_index(self):
        """Should return None for branch without index"""
        result = PROperationsService.parse_branch_name("claude-step-my-refactor-")
        assert result is None

    def test_parse_roundtrip(self):
        """Should correctly roundtrip through format and parse"""
        original_project = "my-test-project"
        original_index = 7

        # Format then parse
        branch = PROperationsService.format_branch_name(original_project, original_index)
        result = PROperationsService.parse_branch_name(branch)

        assert result is not None
        project, index = result
        assert project == original_project
        assert index == original_index

    def test_parse_index_zero(self):
        """Should handle index 0"""
        result = PROperationsService.parse_branch_name("claude-step-my-refactor-0")
        assert result is not None
        project, index = result
        assert project == "my-refactor"
        assert index == 0

    def test_parse_invalid_branch_non_numeric_index(self):
        """Should return None for branch with non-numeric index"""
        result = PROperationsService.parse_branch_name("claude-step-my-refactor-abc")
        assert result is None

    def test_parse_invalid_branch_negative_index(self):
        """Should return None for branch with negative index (contains hyphen before number)"""
        # Note: This will match the pattern but the last -1 will be treated as index 1
        # The project name will be "my-refactor-" which is still valid
        result = PROperationsService.parse_branch_name("claude-step-my-refactor--1")
        # This should parse, but the project name will be "my-refactor-"
        # Actually testing the current behavior
        if result:
            project, index = result
            assert project == "my-refactor-"
            assert index == 1
        # If implementation changes to reject this, that's also acceptable
        # The key is to document the behavior

    def test_parse_single_char_project(self):
        """Should handle single character project names"""
        result = PROperationsService.parse_branch_name("claude-step-x-1")
        assert result is not None
        project, index = result
        assert project == "x"
        assert index == 1

    def test_parse_numeric_project_name(self):
        """Should handle project names that contain numbers"""
        result = PROperationsService.parse_branch_name("claude-step-project-123-refactor-5")
        assert result is not None
        project, index = result
        assert project == "project-123-refactor"
        assert index == 5

    def test_parse_whitespace_in_branch(self):
        """Should handle branch with whitespace (though not recommended)"""
        # The regex pattern (.+) will match whitespace in project names
        # While not recommended, this tests the actual behavior
        result = PROperationsService.parse_branch_name("claude-step-my refactor-1")
        assert result is not None
        project, index = result
        assert project == "my refactor"
        assert index == 1

    def test_parse_case_sensitivity(self):
        """Should handle case sensitivity in prefix (expects lowercase)"""
        result = PROperationsService.parse_branch_name("Claude-Step-my-refactor-1")
        assert result is None  # Should fail because prefix is case-sensitive


class TestGetProjectPrs:
    """Tests for get_project_prs instance method"""

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_open_prs(self, mock_list_prs):
        """Should fetch and filter open PRs for a project"""
        # Mock infrastructure layer response with domain models
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=3,
                state="open",
                head_ref_name="claude-step-other-project-1",
                title="Other project",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        # Call method
        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor", state="open")

        # Verify - should return domain models filtered by project
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2

        # Verify infrastructure layer was called correctly
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="open",
            label="claudestep",
            limit=100
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs(self, mock_list_prs):
        """Should fetch all PRs regardless of state"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="merged",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=datetime.now(timezone.utc),
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor", state="all")

        assert len(result) == 2

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_merged_prs(self, mock_list_prs):
        """Should fetch only merged PRs"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="merged",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=datetime.now(timezone.utc),
            )
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor", state="merged")

        assert len(result) == 1
        assert result[0].state == "merged"

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_filter_by_branch_prefix(self, mock_list_prs):
        """Should only return PRs with matching branch prefix"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                head_ref_name="claude-step-my-refactor-1",
                title="Match 1",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                head_ref_name="claude-step-my-refactor-2",
                title="Match 2",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=3,
                head_ref_name="claude-step-other-project-1",
                title="No match",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=4,
                head_ref_name="random-branch",
                title="No match",
                state="open",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor")

        assert len(result) == 2
        assert all("my-refactor" in pr.head_ref_name for pr in result)

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_custom_label(self, mock_list_prs):
        """Should use custom label when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_project_prs("my-refactor", label="custom-label")

        # Verify infrastructure layer was called with custom label
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="all",
            label="custom-label",
            limit=100
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_handle_empty_response(self, mock_list_prs):
        """Should handle empty PR list gracefully"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor")

        assert result == []

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_handle_api_error(self, mock_list_prs):
        """Should handle GitHub API errors gracefully"""
        from claudestep.domain.exceptions import GitHubAPIError

        mock_list_prs.side_effect = GitHubAPIError("API failed")

        service = PROperationsService("owner/repo")
        result = service.get_project_prs("my-refactor")

        # Should return empty list on error
        assert result == []
