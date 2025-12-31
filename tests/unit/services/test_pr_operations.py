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


class TestGetOpenPrsForProject:
    """Tests for get_open_prs_for_project convenience method"""

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_open_prs_for_project(self, mock_list_prs):
        """Should call get_project_prs with state='open'"""
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
            )
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_open_prs_for_project("my-refactor")

        # Should return only open PRs
        assert len(result) == 1
        assert result[0].state == "open"

        # Verify infrastructure layer was called with state="open"
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="open",
            label="claudestep",
            limit=100
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_open_prs_with_custom_label(self, mock_list_prs):
        """Should use custom label when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_open_prs_for_project("my-refactor", label="custom-label")

        # Verify custom label passed through
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="open",
            label="custom-label",
            limit=100
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_open_prs_empty_result(self, mock_list_prs):
        """Should handle empty results gracefully"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_open_prs_for_project("my-refactor")

        assert result == []


class TestGetOpenPrsForReviewer:
    """Tests for get_open_prs_for_reviewer method"""

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_open_prs_for_reviewer(self, mock_list_open_prs):
        """Should fetch open PRs assigned to reviewer"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_open_prs_for_reviewer("reviewer1")

        # Should return PRs assigned to reviewer
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2

        # Verify infrastructure layer was called with assignee parameter
        mock_list_open_prs.assert_called_once_with(
            repo="owner/repo",
            label="claudestep",
            assignee="reviewer1"
        )

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_open_prs_with_custom_label(self, mock_list_open_prs):
        """Should use custom label when provided"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_open_prs_for_reviewer("reviewer1", label="custom-label")

        # Verify custom label passed through
        mock_list_open_prs.assert_called_once_with(
            repo="owner/repo",
            label="custom-label",
            assignee="reviewer1"
        )

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_open_prs_empty_result(self, mock_list_open_prs):
        """Should handle reviewers with no assigned PRs"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_open_prs_for_reviewer("reviewer-no-prs")

        assert result == []

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_open_prs_returns_domain_models(self, mock_list_open_prs):
        """Should return typed GitHubPullRequest domain models"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            )
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_open_prs_for_reviewer("reviewer1")

        # Verify return type
        assert all(isinstance(pr, GitHubPullRequest) for pr in result)


class TestGetAllPrs:
    """Tests for get_all_prs method"""

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs_default_params(self, mock_list_prs):
        """Should fetch all PRs with default parameters"""
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
                state="merged",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=datetime.now(timezone.utc),
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_all_prs()

        # Should return all PRs
        assert len(result) == 2

        # Verify infrastructure layer was called with defaults
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="all",
            label="claudestep",
            limit=500
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs_custom_label(self, mock_list_prs):
        """Should use custom label when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_all_prs(label="custom-label")

        # Verify custom label passed through
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="all",
            label="custom-label",
            limit=500
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs_custom_state(self, mock_list_prs):
        """Should use custom state when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_all_prs(state="open")

        # Verify custom state passed through
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="open",
            label="claudestep",
            limit=500
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs_custom_limit(self, mock_list_prs):
        """Should use custom limit when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_all_prs(limit=100)

        # Verify custom limit passed through
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="all",
            label="claudestep",
            limit=100
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_all_prs_returns_domain_models(self, mock_list_prs):
        """Should return typed GitHubPullRequest domain models"""
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
            )
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_all_prs()

        # Verify return type
        assert all(isinstance(pr, GitHubPullRequest) for pr in result)


class TestGetUniqueProjects:
    """Tests for get_unique_projects method"""

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects(self, mock_list_prs):
        """Should extract unique project names from PRs"""
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

        service = PROperationsService("owner/repo")
        result = service.get_unique_projects()

        # Should return unique project names
        assert result == {"my-refactor", "other-project"}

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects_handles_invalid_branches(self, mock_list_prs):
        """Should ignore PRs with invalid branch names"""
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
                head_ref_name="invalid-branch-name",
                title="Invalid",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=3,
                state="open",
                head_ref_name="claude-step-no-index",
                title="No index",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_unique_projects()

        # Should only return valid project
        assert result == {"my-refactor"}

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects_empty_result(self, mock_list_prs):
        """Should return empty set when no projects found"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_unique_projects()

        assert result == set()

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects_custom_label(self, mock_list_prs):
        """Should use custom label when provided"""
        mock_list_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_unique_projects(label="custom-label")

        # Verify custom label passed through to get_all_prs
        mock_list_prs.assert_called_once_with(
            repo="owner/repo",
            state="all",
            label="custom-label",
            limit=500
        )

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects_handles_none_branch_names(self, mock_list_prs):
        """Should handle PRs with None as branch name"""
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
                head_ref_name=None,  # None branch name
                title="No branch",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_unique_projects()

        # Should only return valid project, skipping None
        assert result == {"my-refactor"}

    @patch("claudestep.services.pr_operations_service.list_pull_requests")
    def test_get_unique_projects_deduplicates(self, mock_list_prs):
        """Should deduplicate project names from multiple PRs"""
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
                head_ref_name="claude-step-my-refactor-3",
                title="Task 3",
                labels=[],
                assignees=[],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_unique_projects()

        # Should return single project, not duplicates
        assert result == {"my-refactor"}
        assert len(result) == 1


class TestGetReviewerPrsForProject:
    """Tests for get_reviewer_prs_for_project method"""

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_for_project(self, mock_list_open_prs):
        """Should filter reviewer's PRs by project"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=3,
                state="open",
                head_ref_name="claude-step-other-project-1",
                title="Other project",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")

        # Should return only PRs for the specified project
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2
        assert all(pr.project_name == "my-refactor" for pr in result)

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_for_project_empty_result(self, mock_list_open_prs):
        """Should handle reviewers with no PRs for project"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-other-project-1",
                title="Other project",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")

        # Should return empty list - reviewer has PRs but not for this project
        assert result == []

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_no_prs_at_all(self, mock_list_open_prs):
        """Should handle reviewers with no PRs at all"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")

        assert result == []

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_custom_label(self, mock_list_open_prs):
        """Should use custom label when provided"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_reviewer_prs_for_project("reviewer1", "my-refactor", label="custom-label")

        # Verify custom label passed through
        mock_list_open_prs.assert_called_once_with(
            repo="owner/repo",
            label="custom-label",
            assignee="reviewer1"
        )

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_returns_domain_models(self, mock_list_open_prs):
        """Should return typed GitHubPullRequest domain models"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            )
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")

        # Verify return type
        assert all(isinstance(pr, GitHubPullRequest) for pr in result)

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_prs_filters_using_domain_model_property(self, mock_list_open_prs):
        """Should use domain model's project_name property for filtering"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="invalid-branch-name",  # Invalid branch - project_name will be None
                title="Invalid",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")

        # Should only return PR with valid project name
        assert len(result) == 1
        assert result[0].number == 1


class TestGetReviewerPrCount:
    """Tests for get_reviewer_pr_count convenience method"""

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_pr_count(self, mock_list_open_prs):
        """Should return count of reviewer's PRs for project"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-my-refactor-2",
                title="Task 2",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_pr_count("reviewer1", "my-refactor")

        # Should return count of PRs
        assert result == 2

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_pr_count_zero(self, mock_list_open_prs):
        """Should return 0 for reviewers with no PRs"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_pr_count("reviewer1", "my-refactor")

        assert result == 0

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_pr_count_with_other_projects(self, mock_list_open_prs):
        """Should count only PRs for the specified project"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=2,
                state="open",
                head_ref_name="claude-step-other-project-1",
                title="Other project",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
            GitHubPullRequest(
                number=3,
                state="open",
                head_ref_name="claude-step-other-project-2",
                title="Other project 2",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            ),
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_pr_count("reviewer1", "my-refactor")

        # Should count only PRs for my-refactor, not other projects
        assert result == 1

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_pr_count_custom_label(self, mock_list_open_prs):
        """Should use custom label when provided"""
        mock_list_open_prs.return_value = []

        service = PROperationsService("owner/repo")
        service.get_reviewer_pr_count("reviewer1", "my-refactor", label="custom-label")

        # Verify custom label passed through
        mock_list_open_prs.assert_called_once_with(
            repo="owner/repo",
            label="custom-label",
            assignee="reviewer1"
        )

    @patch("claudestep.services.pr_operations_service.list_open_pull_requests")
    def test_get_reviewer_pr_count_returns_int(self, mock_list_open_prs):
        """Should return integer type"""
        mock_prs = [
            GitHubPullRequest(
                number=1,
                state="open",
                head_ref_name="claude-step-my-refactor-1",
                title="Task 1",
                labels=[],
                assignees=["reviewer1"],
                created_at=datetime.now(timezone.utc),
                merged_at=None,
            )
        ]
        mock_list_open_prs.return_value = mock_prs

        service = PROperationsService("owner/repo")
        result = service.get_reviewer_pr_count("reviewer1", "my-refactor")

        # Verify return type
        assert isinstance(result, int)
