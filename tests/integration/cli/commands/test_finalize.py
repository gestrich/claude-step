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

    @pytest.fixture
    def common_mocks(self):
        """Fixture providing commonly mocked objects for finalize tests"""
        with patch("claudestep.cli.commands.finalize.GitHubMetadataStore") as mock_metadata_store:
            with patch("claudestep.cli.commands.finalize.MetadataService") as mock_metadata_service:
                with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                    mock_get_file.return_value = "- [ ] Task 1\n- [ ] Task 2"
                    yield {
                        "metadata_store": mock_metadata_store,
                        "metadata_service": mock_metadata_service,
                        "get_file_from_branch": mock_get_file
                    }

    def test_successful_finalization_workflow(
        self, args, mock_gh, mock_env
    ):
        """Should complete full finalization workflow successfully"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                            with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                                with patch("claudestep.cli.commands.finalize.MetadataService"):
                                    with patch("os.path.exists") as mock_exists:
                                        with patch("builtins.open", mock_open()):
                                            with patch("os.getcwd") as mock_cwd:
                                                with patch("os.makedirs"):
                                                    # Setup mocks
                                                    mock_cwd.return_value = "/workspace"
                                                    mock_exists.return_value = False
                                                    mock_get_file.return_value = "- [ ] Task 1\n- [ ] Task 2"
                                                    mock_git.side_effect = [
                                                        None,  # config user.name
                                                        None,  # config user.email
                                                        "M  file.py",  # status --porcelain (has changes)
                                                        None,  # add -A
                                                        "file.py",  # diff --cached --name-only (has staged)
                                                        None,  # commit
                                                        None,  # remote set-url
                                                        None,  # add spec_path
                                                        "spec.md",  # diff --cached (spec changed)
                                                        None,  # commit spec
                                                        "2",  # rev-list --count (2 commits)
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
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete") as mock_mark:
                            with patch("os.path.exists") as mock_exists:
                                with patch("os.getcwd") as mock_cwd:
                                    with patch("builtins.open", mock_open()):
                                        with patch("os.makedirs"):
                                            # Setup mocks
                                            mock_cwd.return_value = "/workspace"
                                            mock_exists.return_value = False
                                            mock_get_file.return_value = "- [ ] Task 1\n- [ ] Implement feature X\n- [ ] Task 3"
                                            mock_git.side_effect = [
                                                None,  # config user.name
                                                None,  # config user.email
                                                "",  # status --porcelain
                                                None,  # remote set-url
                                                None,  # add spec
                                                "claude-step/my-project/spec.md",  # diff --cached (spec changed)
                                                None,  # commit spec
                                                "1",  # rev-list --count
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
                                            # Verify get_file_from_branch was called with correct parameters
                                            mock_get_file.assert_called_once_with("owner/repo", "main", "claude-step/my-project/spec.md")
                                            # Verify mark_task_complete was called
                                            mock_mark.assert_called_once_with("/workspace/claude-step/my-project/spec.md", "Implement feature X")
                                            # Verify spec.md was added and committed
                                            assert call(["add", "/workspace/claude-step/my-project/spec.md"]) in mock_git.call_args_list
                                            assert call(["commit", "-m", "Mark task 2 as complete in spec.md"]) in mock_git.call_args_list

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

    def test_finalization_creates_git_exclude_file_when_missing(self, args, mock_gh, mock_env):
        """Should create .git/info/exclude file when it doesn't exist"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("os.makedirs") as mock_makedirs:
                                    with patch("builtins.open", mock_open()) as mock_file:
                                        # Setup mocks
                                        mock_cwd.return_value = "/workspace"

                                        def exists_side_effect(path):
                                            if path == "/workspace/.action":
                                                return True
                                            if path.endswith(".git/info/exclude"):
                                                return False  # File doesn't exist, trigger FileNotFoundError
                                            return False

                                        mock_exists.side_effect = exists_side_effect

                                        # Configure mock_open to raise FileNotFoundError on read
                                        read_mock = mock_open()
                                        read_mock.side_effect = FileNotFoundError()

                                        def open_side_effect(path, mode="r"):
                                            if mode == "r" and path.endswith(".git/info/exclude"):
                                                raise FileNotFoundError()
                                            return mock_open()(path, mode)

                                        mock_file.side_effect = open_side_effect

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
                                        # Verify directory was created
                                        mock_makedirs.assert_called()
                                        # Verify file was opened for writing
                                        write_calls = [c for c in mock_file.call_args_list if len(c[0]) > 1 and c[0][1] == "w"]
                                        assert any(".git/info/exclude" in str(c) for c in write_calls)

    def test_finalization_handles_no_staged_changes_after_add(self, args, mock_gh, mock_env):
        """Should detect when no changes remain after git add"""
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
                                        "M  file.py",  # status --porcelain (has changes)
                                        None,  # add -A
                                        "",  # diff --cached --name-only (NO staged changes - already committed by Claude Code)
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
                                    # Should not create a commit since no staged changes
                                    commit_calls = [c for c in mock_git.call_args_list if "commit" in c[0][0]]
                                    assert len(commit_calls) == 0

    def test_finalization_handles_rev_list_value_error(self, args, mock_gh, mock_env):
        """Should handle ValueError when parsing commit count"""
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
                                        "invalid",  # rev-list --count (invalid value)
                                        None,  # remote set-url
                                        None,  # add spec
                                        "M  spec.md",  # status --porcelain (spec changed)
                                        None,  # commit for spec
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
                                    # Should treat as 0 commits and create a new commit for spec
                                    spec_commit_call = [c for c in mock_git.call_args_list
                                                       if "commit" in c[0][0] and "Mark task complete" in str(c)]
                                    assert len(spec_commit_call) > 0

    def test_finalization_amends_commit_when_spec_changed_with_existing_commit(self, args, mock_gh, mock_env):
        """Should amend existing commit when spec.md changes and commits exist"""
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
                                        "M  file.py",  # status --porcelain (has changes)
                                        None,  # add -A
                                        "file.py",  # diff --cached --name-only (has staged)
                                        None,  # commit
                                        "1",  # rev-list --count (1 commit exists)
                                        None,  # remote set-url
                                        None,  # add spec
                                        "M  spec.md",  # status --porcelain (spec changed)
                                        None,  # commit --amend --no-edit
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
                                    # Should amend the existing commit
                                    assert call(["commit", "--amend", "--no-edit"]) in mock_git.call_args_list

    def test_finalization_creates_separate_commit_when_amend_fails(self, args, mock_gh, mock_env):
        """Should create separate commit when amend fails"""
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

                                    git_calls = [
                                        None,  # config user.name
                                        None,  # config user.email
                                        "M  file.py",  # status --porcelain (has changes)
                                        None,  # add -A
                                        "file.py",  # diff --cached --name-only (has staged)
                                        None,  # commit
                                        "1",  # rev-list --count (1 commit exists)
                                        None,  # remote set-url
                                        None,  # add spec
                                        "M  spec.md",  # status --porcelain (spec changed)
                                    ]

                                    def git_side_effect(args_list):
                                        if args_list[0] == "commit" and "--amend" in args_list:
                                            raise GitError("Amend failed")
                                        if git_calls:
                                            return git_calls.pop(0)
                                        return None

                                    mock_git.side_effect = git_side_effect
                                    mock_gh_cmd.side_effect = [
                                        "https://github.com/owner/repo/pull/42",
                                        json.dumps({"number": 42})
                                    ]

                                    # Act
                                    result = cmd_finalize(args, mock_gh)

                                    # Assert
                                    assert result == 0
                                    # Should fall back to creating a separate commit
                                    separate_commit_call = [c for c in mock_git.call_args_list
                                                           if "commit" in c[0][0] and "Mark task complete" in str(c)]
                                    assert len(separate_commit_call) > 0

    def test_finalization_creates_commit_for_spec_when_no_prior_commits(self, args, mock_gh, mock_env):
        """Should create new commit for spec.md when no prior commits exist"""
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
                                        "",  # status --porcelain (no initial changes)
                                        "0",  # rev-list --count (no commits)
                                        None,  # remote set-url
                                        None,  # add spec
                                        "M  spec.md",  # status --porcelain (spec changed)
                                        None,  # commit for spec
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
                                    # Should create a new commit for spec (not amend)
                                    commit_call = [c for c in mock_git.call_args_list
                                                  if "commit" in c[0][0] and "Mark task complete" in str(c)]
                                    assert len(commit_call) > 0
                                    # Should not attempt amend
                                    amend_call = [c for c in mock_git.call_args_list if "--amend" in str(c)]
                                    assert len(amend_call) == 0

    def test_finalization_uses_default_pr_body_when_template_missing(self, args, mock_gh, mock_env):
        """Should use default PR body when template file doesn't exist"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                        with patch("os.path.exists") as mock_exists:
                            with patch("os.getcwd") as mock_cwd:
                                with patch("os.remove") as mock_remove:
                                    with patch("builtins.open", mock_open()) as mock_file:
                                        with patch("tempfile.NamedTemporaryFile") as mock_temp:
                                            # Setup mocks
                                            mock_cwd.return_value = "/workspace"

                                            def exists_side_effect(path):
                                                if path == "/workspace/.action":
                                                    return False
                                                if path == mock_env["PR_TEMPLATE_PATH"]:
                                                    return False  # Template doesn't exist
                                                if path.endswith("temp_pr_body") or path == "/tmp/temp_pr_body":
                                                    return True
                                                return False

                                            mock_exists.side_effect = exists_side_effect

                                            temp_file_mock = MagicMock()
                                            temp_file_mock.name = "/tmp/temp_pr_body"
                                            temp_file_mock.__enter__ = Mock(return_value=temp_file_mock)
                                            temp_file_mock.__exit__ = Mock(return_value=False)
                                            mock_temp.return_value = temp_file_mock

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
                                            # Verify default PR body was written
                                            write_calls = [c[0][0] for c in temp_file_mock.write.call_args_list]
                                            assert any("## Task" in str(c) for c in write_calls)
                                            # Verify temp file was removed
                                            mock_remove.assert_called_once_with("/tmp/temp_pr_body")

    def test_finalization_fetches_spec_from_base_branch(self, args, mock_gh, mock_env):
        """Should fetch spec.md from base branch via GitHub API"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                            with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                                with patch("claudestep.cli.commands.finalize.MetadataService"):
                                    with patch("os.path.exists") as mock_exists:
                                        with patch("os.getcwd") as mock_cwd:
                                            with patch("builtins.open", mock_open()):
                                                with patch("os.makedirs"):
                                                    # Setup mocks
                                                    mock_cwd.return_value = "/workspace"
                                                    mock_exists.return_value = False
                                                    mock_get_file.return_value = "- [ ] Task 1\n- [ ] Task 2"
                                                    mock_git.side_effect = [
                                                        None, None, "", None, None, "spec.md", None, "1", None
                                                    ]
                                                    mock_gh_cmd.side_effect = [
                                                        "https://github.com/owner/repo/pull/42",
                                                        json.dumps({"number": 42})
                                                    ]

                                                    # Act
                                                    result = cmd_finalize(args, mock_gh)

                                                    # Assert
                                                    assert result == 0
                                                    # Verify spec was fetched from base branch
                                                    mock_get_file.assert_called_once_with(
                                                        "owner/repo",
                                                        "main",
                                                        "claude-step/my-project/spec.md"
                                                    )

    def test_finalization_creates_separate_commit_for_spec(self, args, mock_gh, mock_env):
        """Should create a separate commit for spec.md changes"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                            with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                                with patch("claudestep.cli.commands.finalize.MetadataService"):
                                    with patch("os.path.exists") as mock_exists:
                                        with patch("os.getcwd") as mock_cwd:
                                            with patch("builtins.open", mock_open()):
                                                with patch("os.makedirs"):
                                                    # Setup mocks
                                                    mock_cwd.return_value = "/workspace"
                                                    mock_exists.return_value = False
                                                    mock_get_file.return_value = "- [ ] Task 1\n- [ ] Task 2"
                                                    mock_git.side_effect = [
                                                        None,  # config user.name
                                                        None,  # config user.email
                                                        "M  file.py",  # status --porcelain (has changes)
                                                        None,  # add -A
                                                        "file.py",  # diff --cached --name-only
                                                        None,  # commit
                                                        None,  # remote set-url
                                                        None,  # add spec
                                                        "spec.md",  # diff --cached (spec changed)
                                                        None,  # commit spec
                                                        "2",  # rev-list --count (2 commits)
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
                                                    # Verify separate commits were created
                                                    commit_calls = [c for c in mock_git.call_args_list if "commit" in c[0][0]]
                                                    assert len(commit_calls) == 2
                                                    # First commit for code changes
                                                    assert call(["commit", "-m", "Complete task: Implement feature X"]) in mock_git.call_args_list
                                                    # Second commit for spec.md
                                                    assert call(["commit", "-m", "Mark task 2 as complete in spec.md"]) in mock_git.call_args_list

    def test_finalization_handles_spec_fetch_failure_gracefully(self, args, mock_gh, mock_env):
        """Should continue PR creation when spec.md fetch fails"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                            with patch("claudestep.cli.commands.finalize.MetadataService"):
                                with patch("os.path.exists") as mock_exists:
                                    with patch("os.getcwd") as mock_cwd:
                                        with patch("builtins.open", mock_open()):
                                            # Setup mocks
                                            mock_cwd.return_value = "/workspace"
                                            mock_exists.return_value = False
                                            mock_get_file.return_value = None  # Failed to fetch
                                            mock_git.side_effect = [
                                                None, None, "", None, "1", None
                                            ]
                                            mock_gh_cmd.side_effect = [
                                                "https://github.com/owner/repo/pull/42",
                                                json.dumps({"number": 42})
                                            ]

                                            # Act
                                            result = cmd_finalize(args, mock_gh)

                                            # Assert
                                            assert result == 0
                                            # PR should still be created successfully
                                            mock_gh.write_output.assert_any_call("pr_number", "42")

    def test_finalization_handles_spec_fetch_exception_gracefully(self, args, mock_gh, mock_env):
        """Should continue PR creation when spec.md fetch raises exception"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                            with patch("claudestep.cli.commands.finalize.MetadataService"):
                                with patch("os.path.exists") as mock_exists:
                                    with patch("os.getcwd") as mock_cwd:
                                        # Setup mocks
                                        mock_cwd.return_value = "/workspace"
                                        mock_exists.return_value = False
                                        mock_get_file.side_effect = GitHubAPIError("File not found")
                                        mock_git.side_effect = [
                                            None, None, "", None, "1", None
                                        ]
                                        mock_gh_cmd.side_effect = [
                                            "https://github.com/owner/repo/pull/42",
                                            json.dumps({"number": 42})
                                        ]

                                        # Act
                                        result = cmd_finalize(args, mock_gh)

                                        # Assert
                                        assert result == 0
                                        # PR should still be created successfully
                                        mock_gh.write_output.assert_any_call("pr_number", "42")

    def test_finalization_writes_spec_to_correct_path(self, args, mock_gh, mock_env):
        """Should write spec.md content to the correct file path"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                            with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                                with patch("claudestep.cli.commands.finalize.MetadataService"):
                                    with patch("os.path.exists") as mock_exists:
                                        with patch("os.getcwd") as mock_cwd:
                                            with patch("builtins.open", mock_open()) as mock_file:
                                                with patch("os.makedirs") as mock_makedirs:
                                                    # Setup mocks
                                                    mock_cwd.return_value = "/workspace"
                                                    mock_exists.return_value = False
                                                    spec_content = "- [ ] Task 1\n- [ ] Task 2"
                                                    mock_get_file.return_value = spec_content
                                                    mock_git.side_effect = [
                                                        None, None, "", None, None, "spec.md", None, "1", None
                                                    ]
                                                    mock_gh_cmd.side_effect = [
                                                        "https://github.com/owner/repo/pull/42",
                                                        json.dumps({"number": 42})
                                                    ]

                                                    # Act
                                                    result = cmd_finalize(args, mock_gh)

                                                    # Assert
                                                    assert result == 0
                                                    # Verify directory was created
                                                    mock_makedirs.assert_called_once_with("/workspace/claude-step/my-project", exist_ok=True)
                                                    # Verify file was written with correct content
                                                    handle = mock_file()
                                                    handle.write.assert_any_call(spec_content)

    def test_finalization_skips_spec_commit_when_no_changes(self, args, mock_gh, mock_env):
        """Should skip spec.md commit when no changes after marking"""
        # Arrange
        with patch.dict("os.environ", mock_env):
            with patch("claudestep.cli.commands.finalize.run_git_command") as mock_git:
                with patch("claudestep.cli.commands.finalize.run_gh_command") as mock_gh_cmd:
                    with patch("claudestep.cli.commands.finalize.get_file_from_branch") as mock_get_file:
                        with patch("claudestep.cli.commands.finalize.mark_task_complete"):
                            with patch("claudestep.cli.commands.finalize.GitHubMetadataStore"):
                                with patch("claudestep.cli.commands.finalize.MetadataService"):
                                    with patch("os.path.exists") as mock_exists:
                                        with patch("os.getcwd") as mock_cwd:
                                            with patch("builtins.open", mock_open()):
                                                with patch("os.makedirs"):
                                                    # Setup mocks
                                                    mock_cwd.return_value = "/workspace"
                                                    mock_exists.return_value = False
                                                    mock_get_file.return_value = "- [x] Task 2 already complete"
                                                    mock_git.side_effect = [
                                                        None,  # config user.name
                                                        None,  # config user.email
                                                        "",  # status --porcelain
                                                        None,  # remote set-url
                                                        None,  # add spec
                                                        "",  # diff --cached (no spec changes)
                                                        "1",  # rev-list --count
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
                                                    # Should not create a commit for spec.md since it didn't change
                                                    spec_commit_calls = [c for c in mock_git.call_args_list
                                                                       if "commit" in c[0][0] and "Mark task" in str(c)]
                                                    assert len(spec_commit_calls) == 0
