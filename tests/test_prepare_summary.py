"""Tests for prepare_summary command"""

import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
import argparse

from claudestep.commands.prepare_summary import cmd_prepare_summary
from claudestep.infrastructure.github.actions import GitHubActionsHelper


class TestPrepareSummary:
    """Test prepare_summary command handler"""

    def test_prepare_summary_with_valid_inputs(self, tmp_path):
        """Test prepare_summary with all required inputs"""
        # Create mock GitHub Actions helper
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        # Create a temporary prompt template
        template_content = """You are analyzing a pull request that was just created by ClaudeStep.

## Context
- Task completed: {TASK_DESCRIPTION}
- PR number: {PR_NUMBER}
- Workflow run: {WORKFLOW_URL}

## Your Task
Generate a summary of the changes.
"""
        template_path = tmp_path / "prompts" / "summary_prompt.md"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(template_content)

        # Set environment variables
        with patch.dict(os.environ, {
            "PR_NUMBER": "123",
            "TASK": "Add user authentication",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "456789",
            "ACTION_PATH": str(tmp_path)
        }):
            # Run command
            exit_code = cmd_prepare_summary(args, gh)

            # Assertions
            assert exit_code == 0
            gh.write_output.assert_called_once()

            # Verify output contains substituted values
            call_args = gh.write_output.call_args
            assert call_args[0][0] == "summary_prompt"
            prompt = call_args[0][1]
            assert "Add user authentication" in prompt
            assert "123" in prompt
            assert "https://github.com/owner/repo/actions/runs/456789" in prompt
            # Ensure placeholders were replaced
            assert "{TASK_DESCRIPTION}" not in prompt
            assert "{PR_NUMBER}" not in prompt
            assert "{WORKFLOW_URL}" not in prompt

    def test_prepare_summary_without_pr_number(self):
        """Test prepare_summary gracefully skips when no PR number"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        with patch.dict(os.environ, {
            "PR_NUMBER": "",
            "TASK": "Some task",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "123",
            "ACTION_PATH": "/tmp"
        }, clear=True):
            exit_code = cmd_prepare_summary(args, gh)

            # Should exit successfully without error
            assert exit_code == 0
            gh.set_notice.assert_called_once_with(
                "No PR number provided, skipping summary generation"
            )
            # Should not write output
            gh.write_output.assert_not_called()

    def test_prepare_summary_missing_task(self):
        """Test prepare_summary fails when TASK is missing"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        with patch.dict(os.environ, {
            "PR_NUMBER": "123",
            "TASK": "",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "456",
            "ACTION_PATH": "/tmp"
        }, clear=True):
            exit_code = cmd_prepare_summary(args, gh)

            # Should fail
            assert exit_code == 1
            gh.set_error.assert_called_once_with(
                "TASK environment variable is required"
            )

    def test_prepare_summary_missing_repo_and_run_id(self):
        """Test prepare_summary fails when GITHUB_REPOSITORY or GITHUB_RUN_ID is missing"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        with patch.dict(os.environ, {
            "PR_NUMBER": "123",
            "TASK": "Some task",
            "GITHUB_REPOSITORY": "",
            "GITHUB_RUN_ID": "",
            "ACTION_PATH": "/tmp"
        }, clear=True):
            exit_code = cmd_prepare_summary(args, gh)

            # Should fail
            assert exit_code == 1
            gh.set_error.assert_called_once_with(
                "GITHUB_REPOSITORY and GITHUB_RUN_ID are required"
            )

    def test_prepare_summary_template_not_found(self):
        """Test prepare_summary fails when template file not found"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        with patch.dict(os.environ, {
            "PR_NUMBER": "123",
            "TASK": "Some task",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "456",
            "ACTION_PATH": "/nonexistent/path"
        }):
            exit_code = cmd_prepare_summary(args, gh)

            # Should fail
            assert exit_code == 1
            # Check error was logged
            assert gh.set_error.called
            error_message = gh.set_error.call_args[0][0]
            assert "Prompt template not found" in error_message

    def test_prepare_summary_template_substitution(self, tmp_path):
        """Test that template variables are correctly substituted"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        # Create template with all placeholders
        template_content = """Task: {TASK_DESCRIPTION}
PR: {PR_NUMBER}
URL: {WORKFLOW_URL}
"""
        template_path = tmp_path / "prompts" / "summary_prompt.md"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(template_content)

        with patch.dict(os.environ, {
            "PR_NUMBER": "999",
            "TASK": "Fix critical bug",
            "GITHUB_REPOSITORY": "test/repo",
            "GITHUB_RUN_ID": "111222",
            "ACTION_PATH": str(tmp_path)
        }):
            exit_code = cmd_prepare_summary(args, gh)

            assert exit_code == 0
            call_args = gh.write_output.call_args
            prompt = call_args[0][1]

            # Verify exact substitutions
            assert "Task: Fix critical bug" in prompt
            assert "PR: 999" in prompt
            assert "URL: https://github.com/test/repo/actions/runs/111222" in prompt

    def test_prepare_summary_output_format(self, tmp_path):
        """Test that prompt format is correct"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        template_content = "Template with {PR_NUMBER}"
        template_path = tmp_path / "prompts" / "summary_prompt.md"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(template_content)

        with patch.dict(os.environ, {
            "PR_NUMBER": "42",
            "TASK": "Test task",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "789",
            "ACTION_PATH": str(tmp_path)
        }):
            exit_code = cmd_prepare_summary(args, gh)

            assert exit_code == 0
            # Verify write_output was called with correct key
            assert gh.write_output.call_args[0][0] == "summary_prompt"
            # Verify prompt is a non-empty string
            prompt = gh.write_output.call_args[0][1]
            assert isinstance(prompt, str)
            assert len(prompt) > 0

    def test_prepare_summary_workflow_url_construction(self, tmp_path):
        """Test that workflow URL is correctly constructed"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        template_content = "{WORKFLOW_URL}"
        template_path = tmp_path / "prompts" / "summary_prompt.md"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(template_content)

        with patch.dict(os.environ, {
            "PR_NUMBER": "1",
            "TASK": "Task",
            "GITHUB_REPOSITORY": "myorg/myrepo",
            "GITHUB_RUN_ID": "987654321",
            "ACTION_PATH": str(tmp_path)
        }):
            exit_code = cmd_prepare_summary(args, gh)

            assert exit_code == 0
            prompt = gh.write_output.call_args[0][1]
            assert prompt == "https://github.com/myorg/myrepo/actions/runs/987654321"

    def test_prepare_summary_handles_exception(self, tmp_path):
        """Test that exceptions are handled gracefully"""
        gh = MagicMock(spec=GitHubActionsHelper)
        args = argparse.Namespace()

        # Create template
        template_content = "Test"
        template_path = tmp_path / "prompts" / "summary_prompt.md"
        template_path.parent.mkdir(parents=True)
        template_path.write_text(template_content)

        # Mock write_output to raise an exception
        gh.write_output.side_effect = Exception("Write failed")

        with patch.dict(os.environ, {
            "PR_NUMBER": "1",
            "TASK": "Task",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "123",
            "ACTION_PATH": str(tmp_path)
        }):
            exit_code = cmd_prepare_summary(args, gh)

            # Should fail gracefully
            assert exit_code == 1
            assert gh.set_error.called
            error_message = gh.set_error.call_args[0][0]
            assert "Failed to prepare summary" in error_message
