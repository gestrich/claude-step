"""Tests for finalize command - commit changes, create PR, and generate summary"""

import argparse
import json
import os
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, mock_open, call, MagicMock

from claudestep.cli.commands.finalize import cmd_finalize
from claudestep.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError


class TestCmdFinalize:
    """Test suite for cmd_finalize functionality"""

    @pytest.fixture
    def args(self):
        """Fixture providing command-line arguments"""
        args = argparse.Namespace()
        return args

    @pytest.fixture
    def mock_gh(self):
        """Fixture providing mocked GitHubActionsHelper"""
        return Mock()

    @pytest.fixture
    def mock_env(self):
        """Fixture providing standard environment variables"""
        return {
            "BRANCH_NAME": "claude-step-my-project-2",
            "TASK": "Implement feature X",
            "TASK_INDEX": "2",
            "REVIEWER": "alice",
            "PROJECT": "my-project",
            "SPEC_PATH": "claude-step/my-project/spec.md",
            "PR_TEMPLATE_PATH": "claude-step/my-project/pr_template.md",
            "GH_TOKEN": "ghp_test_token",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "123456789",
            "BASE_BRANCH": "main",
            "HAS_CAPACITY": "true",
            "HAS_TASK": "true",
            "LABEL": "claudestep",
            "MAIN_COST": "0.15",
            "SUMMARY_COST": "0.05"
        }

    @pytest.fixture
    def sample_pr_template(self):
        """Fixture providing sample PR template content"""
        return """## Summary
{TASK_DESCRIPTION}

## Testing
- [ ] Tested locally
"""

    def test_successful_finalization_workflow(
        self, args, mock_gh, mock_env
    ):
        """Should complete full finalization workflow successfully"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("builtins.open", mock_open()):
                                with patch("os.getcwd") as mock_cwd:
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "M  file.py",  # status --porcelain (has changes)
                                        None,  # add -A
                                        "file.py",  # diff --cached --name-only (has staged)
                                        None,  # commit
                                        "1",  # rev-list --count (1 commit)
                                        None,  # remote set-url
                                        None,  # add spec_path
                                        "",  # status --porcelain (no changes after spec)
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",  # pr create
                                        json.dumps({"number": 42})  # pr view
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    mock_gh.write_output.assert_any_call("pr_number", "42")
                                    mock_gh.write_output.assert_any_call("pr_url", "https://github.com/owner/repo/pull/42")
                                    mock_gh.write_step_summary.assert_any_call("✅ **Status**: PR created successfully")

    def test_finalization_skips_when_no_capacity(self, args, mock_gh, mock_env):
        """Should exit gracefully when HAS_CAPACITY is false"""
        # Arrange
        env = {**mock_env, "HAS_CAPACITY": "false"}

        with patch.dict("os.environ", env):
            # Act
            result = cmd_finalize(args, mock_gh)

            # Assert
            assert result == 0
            mock_gh.write_step_summary.assert_any_call("⏸️ **Status**: All reviewers at capacity")

    def test_finalization_skips_when_no_task(self, args, mock_gh, mock_env):
        """Should exit gracefully when HAS_TASK is false"""
        # Arrange
        env = {**mock_env, "HAS_TASK": "false"}

        with patch.dict("os.environ", env):
            # Act
            result = cmd_finalize(args, mock_gh)

            # Assert
            assert result == 0
            mock_gh.write_step_summary.assert_any_call("✅ **Status**: All tasks complete or in progress")

    def test_finalization_fails_when_missing_env_vars(self, args, mock_gh):
        """Should return error when required environment variables are missing"""
        # Arrange
        env = {
            "HAS_CAPACITY": "true",
            "HAS_TASK": "true",
            # Missing other required vars
        }

        with patch.dict("os.environ", env, clear=True):
            # Act
            result = cmd_finalize(args, mock_gh)

            # Assert
            assert result == 1
            mock_gh.set_error.assert_called_once()
            assert "Missing required environment variables" in mock_gh.set_error.call_args[0][0]

    def test_finalization_excludes_action_directory(self, args, mock_gh, mock_env):
        """Should add .action directory to git exclude list"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open(read_data="")) as mock_file:
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.side_effect = lambda path: (
                                        path == "/workspace/.action" or
                                        path.endswith(".git/info/exclude")
                                    )
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "",  # status --porcelain (no changes)
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    # Verify .action was written to exclude file
                                    handle = mock_file()
                                    handle.write.assert_any_call("\n.action\n")

    def test_finalization_configures_git_user(self, args, mock_gh, mock_env):
        """Should configure git user as github-actions bot"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "",  # status --porcelain
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    git_config_calls = [call for call in mock_git.call_args_list if "config" in call[0][0]]
                                    assert call(["config", "user.name", "github-actions[bot]"]) in git_config_calls
                                    assert call(["config", "user.email", "github-actions[bot]@users.noreply.github.com"]) in git_config_calls

    def test_finalization_commits_changes_when_present(self, args, mock_gh, mock_env):
        """Should stage and commit changes when present"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "M  file.py\n?? newfile.py",  # status --porcelain (has changes)
                                        None,  # add -A
                                        "file.py\nnewfile.py",  # diff --cached --name-only
                                        None,  # commit
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    assert call(["add", "-A"]) in mock_git.call_args_list
                                    assert call(["commit", "-m", "Complete task: Implement feature X"]) in mock_git.call_args_list

    def test_finalization_skips_commit_when_no_changes(self, args, mock_gh, mock_env):
        """Should skip commit when no changes are detected"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "",  # status --porcelain (no changes)
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    # Should not call commit for initial changes
                                    commit_calls = [call for call in mock_git.call_args_list
                                                  if "commit" in call[0][0] and "-m" in call[0][0]]
                                    assert len(commit_calls) == 0

    def test_finalization_marks_task_complete_in_spec(self, args, mock_gh, mock_env):
        """Should mark task as complete in spec.md"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete") as mock_mark:
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "",  # status --porcelain
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    mock_mark.assert_called_once_with("claude-step/my-project/spec.md", "Implement feature X")
                                    assert call(["add", "claude-step/my-project/spec.md"]) in mock_git.call_args_list

    def test_finalization_skips_pr_when_no_commits(self, args, mock_gh, mock_env):
        """Should skip PR creation when no commits to push"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                    with patch("os.path.exists") as mock_exists:
                        with patch("os.getcwd") as mock_cwd:
                            # Setup mocks
                            mock_cwd.return_value = "/workspace"
                            mock_exists.return_value = False
                            mock_git.side_effect = [
                                None,  # config user.name
                                None,  # config user.email
                                "",  # status --porcelain (no changes)
                                "0",  # rev-list --count (no commits)
                                None,  # remote set-url
                                None,  # add spec
                                "",  # status --porcelain (no spec changes)
                            ]

                            # Act
                            result = cmd_finalize(args, mock_gh)

                            # Assert
                            assert result == 0
                            mock_gh.set_warning.assert_called_once()
                            assert "No changes made" in mock_gh.set_warning.call_args[0][0]
                            mock_gh.write_output.assert_any_call("pr_number", "")
                            mock_gh.write_output.assert_any_call("pr_url", "")

    def test_finalization_pushes_branch(self, args, mock_gh, mock_env):
        """Should push branch with force flag"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "",  # status --porcelain
                                        "1",  # rev-list --count
                                        None,  # remote set-url
                                        None,  # add spec
                                        "",  # status --porcelain
                                        None,  # push
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    assert call(["push", "-u", "origin", "claude-step-my-project-2", "--force"]) in mock_git.call_args_list

    def test_finalization_creates_pr_with_correct_parameters(self, args, mock_gh, mock_env):
        """Should create PR with correct title, label, assignee, and branches"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    pr_create_call = mock_gh_cmd.call_args_list[0][0][0]
                                    assert "pr" in pr_create_call
                                    assert "create" in pr_create_call
                                    assert "--title" in pr_create_call
                                    assert "ClaudeStep: Implement feature X" in pr_create_call
                                    assert "--label" in pr_create_call
                                    assert "claudestep" in pr_create_call
                                    assert "--assignee" in pr_create_call
                                    assert "alice" in pr_create_call
                                    assert "--head" in pr_create_call
                                    assert "claude-step-my-project-2" in pr_create_call
                                    assert "--base" in pr_create_call
                                    assert "main" in pr_create_call

    def test_finalization_creates_artifact_metadata(self, args, mock_gh, mock_env):
        """Should create artifact metadata JSON file with all required fields"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()) as mock_file:
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0

                                    # Verify artifact file was opened for writing
                                    open_calls = [call[0] for call in mock_file.call_args_list]
                                    artifact_path = "/workspace/task-metadata-my-project-2.json"
                                    assert any(artifact_path in str(call) for call in open_calls)

                                    # Verify outputs include artifact information
                                    output_calls = {call[0][0]: call[0][1] for call in mock_gh.write_output.call_args_list}
                                    assert output_calls["artifact_name"] == "task-metadata-my-project-2.json"
                                    assert artifact_path in output_calls["artifact_path"]

    def test_finalization_writes_all_outputs(self, args, mock_gh, mock_env):
        """Should write all required output variables"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0

                                    output_calls = {call[0][0]: call[0][1] for call in mock_gh.write_output.call_args_list}
                                    assert output_calls["pr_number"] == "42"
                                    assert output_calls["pr_url"] == "https://github.com/owner/repo/pull/42"
                                    assert output_calls["artifact_name"] == "task-metadata-my-project-2.json"
                                    assert "/workspace/task-metadata-my-project-2.json" in output_calls["artifact_path"]

    def test_finalization_writes_step_summary(self, args, mock_gh, mock_env):
        """Should write step summary with PR information"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0

                                    summary_calls = [call[0][0] for call in mock_gh.write_step_summary.call_args_list]
                                    assert "✅ **Status**: PR created successfully" in summary_calls
                                    assert "- **PR**: #42" in summary_calls
                                    assert "- **Reviewer**: alice" in summary_calls
                                    assert "- **Task**: Implement feature X" in summary_calls

    def test_finalization_handles_git_error(self, args, mock_gh, mock_env):
        """Should handle GitError gracefully"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("os.getcwd") as mock_cwd:
                    # Setup mocks
                    mock_cwd.return_value = "/workspace"
                    mock_git.side_effect = GitError("Failed to push")

                    # Act
                    result = cmd_finalize(args, mock_gh)

                    # Assert
                    assert result == 1
                    mock_gh.set_error.assert_called_once()
                    assert "Finalization failed" in mock_gh.set_error.call_args[0][0]
                    mock_gh.write_step_summary.assert_any_call("❌ **Status**: Failed to create PR")

    def test_finalization_handles_github_api_error(self, args, mock_gh, mock_env):
        """Should handle GitHubAPIError gracefully"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = GitHubAPIError("API rate limit exceeded")

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 1
                                    mock_gh.set_error.assert_called_once()
                                    assert "Finalization failed" in mock_gh.set_error.call_args[0][0]

    def test_finalization_handles_unexpected_error(self, args, mock_gh, mock_env):
        """Should handle unexpected errors gracefully"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("os.getcwd") as mock_cwd:
                    # Setup mocks
                    mock_cwd.return_value = "/workspace"
                    mock_git.side_effect = RuntimeError("Unexpected error")

                    # Act
                    result = cmd_finalize(args, mock_gh)

                    # Assert
                    assert result == 1
                    mock_gh.set_error.assert_called_once()
                    assert "Unexpected error" in mock_gh.set_error.call_args[0][0]
                    mock_gh.write_step_summary.assert_any_call("❌ **Status**: Unexpected error")

    def test_finalization_handles_spec_marking_failure(self, args, mock_gh, mock_env):
        """Should continue when marking task in spec fails"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete") as mock_mark:
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_mark.side_effect = FileNotFoundError("Spec not found")
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0  # Should still succeed
                                    mock_gh.set_warning.assert_called()
                                    assert "Failed to mark task complete" in mock_gh.set_warning.call_args[0][0]

    def test_finalization_reconfigures_git_auth(self, args, mock_gh, mock_env):
        """Should reconfigure git remote URL with token"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("builtins.open", mock_open()):
                                    # Setup mocks
                                    mock_cwd.return_value = "/workspace"
                                    mock_exists.return_value = False
                                    mock_git.side_effect = [
                                        None, None, "", "1", None, None, "", None
                                    ]
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    expected_url = f"https://x-access-token:{mock_env['GH_TOKEN']}@github.com/{mock_env['GITHUB_REPOSITORY']}.git"
                                    assert call(["remote", "set-url", "origin", expected_url]) in mock_git.call_args_list
