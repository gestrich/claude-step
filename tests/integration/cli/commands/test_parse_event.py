"""Integration tests for the parse-event command"""

import json
from unittest.mock import Mock, patch

import pytest

from claudechain.cli.commands.parse_event import cmd_parse_event
from claudechain.domain.project import Project


class TestCmdParseEvent:
    """Test suite for cmd_parse_event functionality"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def pull_request_merged_event(self):
        """Fixture providing a merged PR event"""
        return json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": True,
                "labels": [{"name": "claudechain"}, {"name": "enhancement"}],
                "base": {"ref": "main"},
                "head": {"ref": "claude-chain-my-project-a1b2c3d4"}
            }
        })

    @pytest.fixture
    def pull_request_not_merged_event(self):
        """Fixture providing a closed but not merged PR event"""
        return json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": False,
                "labels": [{"name": "claudechain"}],
                "base": {"ref": "main"},
                "head": {"ref": "claude-chain-my-project-a1b2c3d4"}
            }
        })

    @pytest.fixture
    def push_event(self):
        """Fixture providing a push event"""
        return json.dumps({
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456"
        })

    @pytest.fixture
    def workflow_dispatch_event(self):
        """Fixture providing a workflow_dispatch event"""
        return json.dumps({
            "ref": "refs/heads/main",
            "inputs": {
                "project_name": "my-refactor"
            }
        })

    # =============================================================================
    # Tests for pull_request events with project detection from changed files
    # =============================================================================

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_merged_detects_project_from_spec_changes(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should detect project from changed spec.md files in merged PR"""
        mock_compare.return_value = ["claude-chain/my-project/spec.md", "README.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/some-branch"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            project_name=None,
            default_base_branch="main",
            repo="owner/repo"
        )

        assert result == 0
        mock_compare.assert_called_once_with("owner/repo", "main", "feature/some-branch")
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "my-project")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "main")
        mock_github_helper.write_output.assert_any_call("base_branch", "main")
        mock_github_helper.write_output.assert_any_call("merged_pr_number", "42")

        captured = capsys.readouterr()
        assert "Event parsing complete" in captured.out

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_merged_with_claudechain_branch_detects_project(
        self, mock_compare, mock_github_helper, pull_request_merged_event, capsys
    ):
        """Should detect project from ClaudeChain branch name in changed spec.md"""
        mock_compare.return_value = ["claude-chain/my-project/spec.md"]

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=pull_request_merged_event,
            project_name=None,
            default_base_branch="main",
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "my-project")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "main")
        mock_github_helper.write_output.assert_any_call("base_branch", "main")
        mock_github_helper.write_output.assert_any_call("merged_pr_number", "42")

        captured = capsys.readouterr()
        assert "Event parsing complete" in captured.out

    def test_pull_request_not_merged_skips(
        self, mock_github_helper, pull_request_not_merged_event, capsys
    ):
        """Should skip PR that was closed but not merged"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=pull_request_not_merged_event,
            project_name=None,
            default_base_branch="main"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "true")
        mock_github_helper.write_output.assert_any_call("skip_reason", "PR was closed but not merged")

        captured = capsys.readouterr()
        assert "Skipping" in captured.out

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_no_spec_changes_and_non_claudechain_branch_skips(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should skip PR when no spec.md files changed and branch is not ClaudeChain"""
        mock_compare.return_value = ["src/code.py", "README.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 123,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/some-feature"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            project_name=None,
            default_base_branch="main",
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "true")
        mock_github_helper.write_output.assert_any_call(
            "skip_reason", "No spec.md changes detected and branch name is not a ClaudeChain branch"
        )

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_no_spec_changes_but_claudechain_branch_detects_project(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should detect project from ClaudeChain branch when compare API returns 0 files.

        This is the key fallback behavior: when a ClaudeChain PR is merged, the
        compare API may return 0 files (because the head is now part of base).
        The fallback detects the project from the branch name pattern.
        """
        # Compare API returns 0 files (simulating post-merge state)
        mock_compare.return_value = []

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 123,
                "merged": True,
                "labels": [{"name": "claudechain"}],
                "base": {"ref": "main"},
                "head": {"ref": "claude-chain-my-project-a1b2c3d4"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            project_name=None,
            default_base_branch="main",
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "my-project")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "main")

        captured = capsys.readouterr()
        assert "Detected project from branch name: my-project" in captured.out

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_branch_fallback_with_hyphenated_project_name(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should correctly parse project names with hyphens from branch fallback"""
        mock_compare.return_value = []

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 9,
                "merged": True,
                "labels": [{"name": "claudechain"}],
                "base": {"ref": "source-clean-up"},
                "head": {"ref": "claude-chain-cleanup-7b6f699f"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            project_name=None,
            default_base_branch="source-clean-up",
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "cleanup")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "source-clean-up")

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_multiple_projects_processes_first(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should process first project when multiple projects have spec.md changes"""
        mock_compare.return_value = [
            "claude-chain/project-a/spec.md",
            "claude-chain/project-b/spec.md"
        ]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 123,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/multi-project"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            project_name=None,
            default_base_branch="main",
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        # First project alphabetically
        mock_github_helper.write_output.assert_any_call("project_name", "project-a")
        # Check detected_projects contains both
        detected_projects_call = [
            call for call in mock_github_helper.write_output.call_args_list
            if call[0][0] == "detected_projects"
        ][0]
        detected_json = json.loads(detected_projects_call[0][1])
        assert len(detected_json) == 2
        assert detected_json[0]["name"] == "project-a"
        assert detected_json[1]["name"] == "project-b"

        captured = capsys.readouterr()
        assert "Multiple projects detected" in captured.out

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_pull_request_detects_project_from_complex_path(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should detect project name from spec.md path with complex name"""
        mock_compare.return_value = ["claude-chain/my-very-long-project-name/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 123,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/update"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("project_name", "my-very-long-project-name")

    # =============================================================================
    # Tests for workflow_dispatch events
    # =============================================================================

    def test_workflow_dispatch_with_project_name_succeeds(
        self, mock_github_helper, workflow_dispatch_event, capsys
    ):
        """Should process workflow_dispatch with explicit project name"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json=workflow_dispatch_event,
            project_name="explicit-project",
            default_base_branch="main"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "explicit-project")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "main")
        mock_github_helper.write_output.assert_any_call("base_branch", "main")

    def test_workflow_dispatch_without_project_name_fails(
        self, mock_github_helper, workflow_dispatch_event, capsys
    ):
        """Should fail workflow_dispatch without project name"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json=workflow_dispatch_event,
            project_name=None,
            default_base_branch="main"
        )

        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_msg = mock_github_helper.set_error.call_args[0][0]
        assert "workflow_dispatch requires project_name input" in error_msg

    def test_workflow_dispatch_respects_custom_base_branch(
        self, mock_github_helper, capsys
    ):
        """Should use custom default base branch"""
        event = json.dumps({
            "ref": "refs/heads/develop",
            "inputs": {}
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json=event,
            project_name="my-project",
            default_base_branch="develop"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("checkout_ref", "develop")
        mock_github_helper.write_output.assert_any_call("base_branch", "develop")

    def test_workflow_dispatch_uses_configured_base_branch_for_checkout(
        self, mock_github_helper, capsys
    ):
        """Should checkout the configured base branch, not the trigger branch.

        For workflow_dispatch:
        - checkout_ref: The configured default_base_branch (where spec file lives)
        - base_branch: Same as checkout_ref (for PR targeting)

        The trigger branch (event.ref) is just where the user clicked "Run workflow"
        but we need to checkout where the spec file and code actually live.
        """
        # Workflow triggered from 'main' branch (where user clicked Run workflow)
        event = json.dumps({
            "ref": "refs/heads/main",
            "inputs": {}
        })

        # User configured default_base_branch to 'feature-branch' - this is where the spec lives
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json=event,
            project_name="my-project",
            default_base_branch="feature-branch"
        )

        assert result == 0
        # Both checkout_ref and base_branch should use the configured branch
        mock_github_helper.write_output.assert_any_call("checkout_ref", "feature-branch")
        mock_github_helper.write_output.assert_any_call("base_branch", "feature-branch")

    # =============================================================================
    # Tests for push events with project detection from changed files
    # =============================================================================

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_push_event_requires_spec_changes_for_detection(
        self, mock_compare, mock_github_helper, push_event, capsys
    ):
        """Push events require spec.md changes - project_name param is not used for push.

        Unlike workflow_dispatch which uses explicit project_name input,
        push events always detect projects from changed spec.md files.
        If no spec changes, the event is skipped.
        """
        # Push with no spec changes
        mock_compare.return_value = ["src/code.py", "README.md"]

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json=push_event,
            project_name="pushed-project",  # Ignored for push events
            default_base_branch="main",
            repo="owner/repo"
        )

        # Should skip because no spec.md changes detected
        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "true")
        mock_github_helper.write_output.assert_any_call("skip_reason", "No spec.md changes detected")

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_push_event_detects_project_from_spec_changes(
        self, mock_compare, mock_github_helper, push_event, capsys
    ):
        """Should detect project from spec.md changes in push event"""
        mock_compare.return_value = ["claude-chain/my-project/spec.md", "README.md"]

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json=push_event,
            project_name=None,
            repo="owner/repo"
        )

        assert result == 0
        mock_compare.assert_called_once_with("owner/repo", "abc123", "def456")
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "my-project")

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_push_event_without_spec_changes_skips(
        self, mock_compare, mock_github_helper, push_event, capsys
    ):
        """Should skip push event when no spec.md files changed"""
        mock_compare.return_value = ["src/code.py", "README.md"]

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json=push_event,
            project_name=None,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "true")
        mock_github_helper.write_output.assert_any_call("skip_reason", "No spec.md changes detected")

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_push_event_multiple_projects_processes_first(
        self, mock_compare, mock_github_helper, push_event, capsys
    ):
        """Should process first project when multiple projects modified in push"""
        mock_compare.return_value = [
            "claude-chain/project-a/spec.md",
            "claude-chain/project-b/spec.md"
        ]

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json=push_event,
            project_name=None,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "project-a")

        captured = capsys.readouterr()
        assert "Multiple projects detected" in captured.out

    def test_push_event_without_repo_skips(
        self, mock_github_helper, push_event, capsys
    ):
        """Should skip push event when repo is not provided (can't call API)"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json=push_event,
            project_name=None,
            repo=None  # No repo provided
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "true")
        mock_github_helper.write_output.assert_any_call("skip_reason", "No spec.md changes detected")

    # =============================================================================
    # Tests for error handling
    # =============================================================================

    def test_invalid_json_returns_error(
        self, mock_github_helper, capsys
    ):
        """Should handle invalid JSON gracefully"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="push",
            event_json="not valid json",
            project_name="test"
        )

        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_msg = mock_github_helper.set_error.call_args[0][0]
        assert "Event parsing failed" in error_msg

    def test_empty_event_json_handled(
        self, mock_github_helper, capsys
    ):
        """Should handle empty event JSON by failing for workflow_dispatch without project"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json="{}",
            project_name=None
        )

        # workflow_dispatch without project_name should error
        assert result == 1
        mock_github_helper.set_error.assert_called_once()

    def test_workflow_dispatch_empty_json_with_project_succeeds(
        self, mock_github_helper, capsys
    ):
        """Should handle workflow_dispatch with empty JSON when project and base_branch provided.

        Even with empty event JSON, workflow_dispatch uses default_base_branch for checkout,
        so it succeeds as long as both project_name and default_base_branch are provided.
        """
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json="{}",
            project_name="test-project",
            default_base_branch="main"
        )

        # Should succeed - we use default_base_branch for checkout, not event.ref
        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "main")
        mock_github_helper.write_output.assert_any_call("base_branch", "main")

    # =============================================================================
    # Tests for output consistency
    # =============================================================================

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_outputs_all_required_fields_on_success(
        self, mock_compare, mock_github_helper
    ):
        """Should output all required fields on success"""
        mock_compare.return_value = ["claude-chain/my-project/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/test"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        assert result == 0

        # Collect all output calls
        output_calls = {
            call[0][0]: call[0][1]
            for call in mock_github_helper.write_output.call_args_list
        }

        # Verify all required outputs are present
        assert "skip" in output_calls
        assert "project_name" in output_calls
        assert "checkout_ref" in output_calls
        assert "base_branch" in output_calls

    def test_outputs_all_required_fields_on_skip(
        self, mock_github_helper, pull_request_not_merged_event
    ):
        """Should output skip fields when skipping"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=pull_request_not_merged_event
        )

        assert result == 0

        # Collect all output calls
        output_calls = {
            call[0][0]: call[0][1]
            for call in mock_github_helper.write_output.call_args_list
        }

        # Verify skip outputs are present
        assert output_calls.get("skip") == "true"
        assert "skip_reason" in output_calls

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_console_output_includes_context(
        self, mock_compare, mock_github_helper, capsys
    ):
        """Should include helpful context in console output"""
        mock_compare.return_value = ["claude-chain/my-project/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/test"}
            }
        })

        cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        captured = capsys.readouterr()
        assert "ClaudeChain Event Parsing" in captured.out
        assert "Event name: pull_request" in captured.out
        assert "PR number: 42" in captured.out


class TestCmdParseEventEdgeCases:
    """Test edge cases and boundary conditions"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.set_error = Mock()
        return mock

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_project_name_with_multiple_hyphens(
        self, mock_compare, mock_github_helper
    ):
        """Should handle project names with multiple hyphens"""
        mock_compare.return_value = ["claude-chain/my-very-long-project-name/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 1,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/update"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call(
            "project_name", "my-very-long-project-name"
        )

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_different_base_branches(
        self, mock_compare, mock_github_helper
    ):
        """Should respect different base branches from event"""
        mock_compare.return_value = ["claude-chain/test/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 1,
                "merged": True,
                "labels": [],
                "base": {"ref": "develop"},
                "head": {"ref": "feature/test"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("project_name", "test")
        mock_github_helper.write_output.assert_any_call("base_branch", "develop")
        mock_github_helper.write_output.assert_any_call("checkout_ref", "develop")

    def test_project_name_override_takes_precedence(self, mock_github_helper):
        """Should use explicit project_name for workflow_dispatch"""
        event = json.dumps({
            "ref": "refs/heads/main",
            "inputs": {}
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="workflow_dispatch",
            event_json=event,
            project_name="override-project",
            default_base_branch="main"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("project_name", "override-project")

    @patch("claudechain.cli.commands.parse_event.compare_commits")
    def test_empty_labels_list_still_processes_with_spec_changes(
        self, mock_compare, mock_github_helper
    ):
        """Should process PR with no labels when spec.md changes detected"""
        mock_compare.return_value = ["claude-chain/test/spec.md"]

        event = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 1,
                "merged": True,
                "labels": [],
                "base": {"ref": "main"},
                "head": {"ref": "feature/test"}
            }
        })

        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="pull_request",
            event_json=event,
            repo="owner/repo"
        )

        assert result == 0
        mock_github_helper.write_output.assert_any_call("skip", "false")
        mock_github_helper.write_output.assert_any_call("project_name", "test")

    def test_unknown_event_type_fails(self, mock_github_helper):
        """Should fail for unknown event types"""
        result = cmd_parse_event(
            gh=mock_github_helper,
            event_name="unknown_event",
            event_json="{}",
            project_name="test"
        )

        # Unknown event types should error
        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_msg = mock_github_helper.set_error.call_args[0][0]
        assert "Unsupported event type" in error_msg
