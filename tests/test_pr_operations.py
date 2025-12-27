"""Unit tests for PR operations and branch naming utilities"""

import json
from unittest.mock import MagicMock, patch

import pytest

from claudestep.application.services.pr_operations import (
    format_branch_name,
    get_project_prs,
    parse_branch_name,
)


class TestFormatBranchName:
    """Tests for format_branch_name function"""

    def test_format_basic_branch_name(self):
        """Should format branch name with project and index"""
        result = format_branch_name("my-refactor", 1)
        assert result == "claude-step-my-refactor-1"

    def test_format_with_multi_word_project(self):
        """Should handle project names with multiple words"""
        result = format_branch_name("swift-migration", 5)
        assert result == "claude-step-swift-migration-5"

    def test_format_with_large_index(self):
        """Should handle large task indices"""
        result = format_branch_name("api-refactor", 42)
        assert result == "claude-step-api-refactor-42"

    def test_format_with_complex_project_name(self):
        """Should handle complex project names with hyphens"""
        result = format_branch_name("my-complex-project-name", 3)
        assert result == "claude-step-my-complex-project-name-3"


class TestParseBranchName:
    """Tests for parse_branch_name function"""

    def test_parse_basic_branch_name(self):
        """Should parse basic branch name"""
        result = parse_branch_name("claude-step-my-refactor-1")
        assert result is not None
        project, index = result
        assert project == "my-refactor"
        assert index == 1

    def test_parse_multi_word_project(self):
        """Should parse project names with multiple words"""
        result = parse_branch_name("claude-step-swift-migration-5")
        assert result is not None
        project, index = result
        assert project == "swift-migration"
        assert index == 5

    def test_parse_large_index(self):
        """Should handle large task indices"""
        result = parse_branch_name("claude-step-api-refactor-42")
        assert result is not None
        project, index = result
        assert project == "api-refactor"
        assert index == 42

    def test_parse_complex_project_name(self):
        """Should handle complex project names with multiple hyphens"""
        result = parse_branch_name("claude-step-my-complex-project-name-3")
        assert result is not None
        project, index = result
        assert project == "my-complex-project-name"
        assert index == 3

    def test_parse_invalid_branch_no_prefix(self):
        """Should return None for branch without claude-step prefix"""
        result = parse_branch_name("my-refactor-1")
        assert result is None

    def test_parse_invalid_branch_wrong_format(self):
        """Should return None for branch with wrong format"""
        result = parse_branch_name("claude-step-no-index")
        assert result is None

    def test_parse_invalid_branch_empty(self):
        """Should return None for empty branch name"""
        result = parse_branch_name("")
        assert result is None

    def test_parse_invalid_branch_no_index(self):
        """Should return None for branch without index"""
        result = parse_branch_name("claude-step-my-refactor-")
        assert result is None

    def test_parse_roundtrip(self):
        """Should correctly roundtrip through format and parse"""
        original_project = "my-test-project"
        original_index = 7

        # Format then parse
        branch = format_branch_name(original_project, original_index)
        result = parse_branch_name(branch)

        assert result is not None
        project, index = result
        assert project == original_project
        assert index == original_index


class TestGetProjectPrs:
    """Tests for get_project_prs function"""

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_get_open_prs(self, mock_gh_command):
        """Should fetch and filter open PRs for a project"""
        # Mock GitHub API response
        mock_prs = [
            {
                "number": 1,
                "state": "open",
                "headRefName": "claude-step-my-refactor-1",
                "title": "Task 1",
                "labels": [],
                "assignees": [],
            },
            {
                "number": 2,
                "state": "open",
                "headRefName": "claude-step-my-refactor-2",
                "title": "Task 2",
                "labels": [],
                "assignees": [],
            },
            {
                "number": 3,
                "state": "open",
                "headRefName": "claude-step-other-project-1",
                "title": "Other project",
                "labels": [],
                "assignees": [],
            },
        ]
        mock_gh_command.return_value = json.dumps(mock_prs)

        # Call function
        result = get_project_prs("my-refactor", "owner/repo", state="open")

        # Verify
        assert len(result) == 2
        assert result[0]["number"] == 1
        assert result[1]["number"] == 2

        # Verify GitHub CLI was called correctly
        mock_gh_command.assert_called_once()
        call_args = mock_gh_command.call_args[0][0]
        assert "pr" in call_args
        assert "list" in call_args
        assert "--state" in call_args
        assert "open" in call_args

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_get_all_prs(self, mock_gh_command):
        """Should fetch all PRs regardless of state"""
        mock_prs = [
            {
                "number": 1,
                "state": "merged",
                "headRefName": "claude-step-my-refactor-1",
                "title": "Task 1",
            },
            {
                "number": 2,
                "state": "open",
                "headRefName": "claude-step-my-refactor-2",
                "title": "Task 2",
            },
        ]
        mock_gh_command.return_value = json.dumps(mock_prs)

        result = get_project_prs("my-refactor", "owner/repo", state="all")

        assert len(result) == 2

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_get_merged_prs(self, mock_gh_command):
        """Should fetch only merged PRs"""
        mock_prs = [
            {
                "number": 1,
                "state": "merged",
                "headRefName": "claude-step-my-refactor-1",
                "title": "Task 1",
                "mergedAt": "2025-12-27T10:00:00Z",
            }
        ]
        mock_gh_command.return_value = json.dumps(mock_prs)

        result = get_project_prs("my-refactor", "owner/repo", state="merged")

        assert len(result) == 1
        assert result[0]["state"] == "merged"

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_filter_by_branch_prefix(self, mock_gh_command):
        """Should only return PRs with matching branch prefix"""
        mock_prs = [
            {
                "number": 1,
                "headRefName": "claude-step-my-refactor-1",
                "title": "Match 1",
            },
            {
                "number": 2,
                "headRefName": "claude-step-my-refactor-2",
                "title": "Match 2",
            },
            {
                "number": 3,
                "headRefName": "claude-step-other-project-1",
                "title": "No match",
            },
            {"number": 4, "headRefName": "random-branch", "title": "No match"},
        ]
        mock_gh_command.return_value = json.dumps(mock_prs)

        result = get_project_prs("my-refactor", "owner/repo")

        assert len(result) == 2
        assert all("my-refactor" in pr["headRefName"] for pr in result)

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_custom_label(self, mock_gh_command):
        """Should use custom label when provided"""
        mock_gh_command.return_value = "[]"

        get_project_prs("my-refactor", "owner/repo", label="custom-label")

        call_args = mock_gh_command.call_args[0][0]
        assert "--label" in call_args
        assert "custom-label" in call_args

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_handle_empty_response(self, mock_gh_command):
        """Should handle empty PR list gracefully"""
        mock_gh_command.return_value = "[]"

        result = get_project_prs("my-refactor", "owner/repo")

        assert result == []

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_handle_api_error(self, mock_gh_command):
        """Should handle GitHub API errors gracefully"""
        from claudestep.domain.exceptions import GitHubAPIError

        mock_gh_command.side_effect = GitHubAPIError("API failed")

        result = get_project_prs("my-refactor", "owner/repo")

        # Should return empty list on error
        assert result == []

    @patch("claudestep.application.services.pr_operations.run_gh_command")
    def test_handle_invalid_json(self, mock_gh_command):
        """Should handle invalid JSON response gracefully"""
        mock_gh_command.return_value = "invalid json"

        result = get_project_prs("my-refactor", "owner/repo")

        # Should return empty list on parse error
        assert result == []
