"""Tests for git operations"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from claudechain.domain.exceptions import GitError
from claudechain.infrastructure.git.operations import run_command, run_git_command


class TestRunCommand:
    """Test suite for run_command function"""

    def test_run_command_success_with_output(self):
        """Should execute command and return completed process with output"""
        # Arrange
        cmd = ["echo", "test"]

        # Act
        result = run_command(cmd)

        # Assert
        assert result.returncode == 0
        assert "test" in result.stdout

    def test_run_command_captures_output_by_default(self):
        """Should capture stdout and stderr by default"""
        # Arrange
        cmd = ["echo", "test output"]

        # Act
        result = run_command(cmd)

        # Assert
        assert result.stdout is not None
        assert result.stderr is not None

    def test_run_command_without_output_capture(self):
        """Should not capture output when capture_output=False"""
        # Arrange
        cmd = ["echo", "test"]

        # Act
        result = run_command(cmd, capture_output=False)

        # Assert
        assert result.stdout is None
        assert result.stderr is None

    def test_run_command_raises_on_failure_when_check_true(self):
        """Should raise CalledProcessError on non-zero exit when check=True"""
        # Arrange
        cmd = ["false"]  # Command that always fails

        # Act & Assert
        with pytest.raises(subprocess.CalledProcessError):
            run_command(cmd, check=True)

    def test_run_command_does_not_raise_when_check_false(self):
        """Should not raise exception on failure when check=False"""
        # Arrange
        cmd = ["false"]

        # Act
        result = run_command(cmd, check=False)

        # Assert
        assert result.returncode != 0

    def test_run_command_returns_text_output(self):
        """Should return output as text strings not bytes"""
        # Arrange
        cmd = ["echo", "test"]

        # Act
        result = run_command(cmd)

        # Assert
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)


class TestRunGitCommand:
    """Test suite for run_git_command function"""

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_success(self, mock_run):
        """Should execute git command and return stdout"""
        # Arrange
        mock_run.return_value = Mock(stdout="  output text  \n", stderr="")
        args = ["status", "--short"]

        # Act
        result = run_git_command(args)

        # Assert
        assert result == "output text"
        mock_run.assert_called_once_with(["git", "status", "--short"])

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_strips_whitespace(self, mock_run):
        """Should strip leading and trailing whitespace from output"""
        # Arrange
        mock_run.return_value = Mock(stdout="\n\n  branch name  \n\n", stderr="")
        args = ["rev-parse", "--abbrev-ref", "HEAD"]

        # Act
        result = run_git_command(args)

        # Assert
        assert result == "branch name"

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_handles_empty_output(self, mock_run):
        """Should handle empty output correctly"""
        # Arrange
        mock_run.return_value = Mock(stdout="", stderr="")
        args = ["status"]

        # Act
        result = run_git_command(args)

        # Assert
        assert result == ""

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_raises_git_error_on_failure(self, mock_run):
        """Should raise GitError when git command fails"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "checkout", "nonexistent"],
            stderr="error: pathspec 'nonexistent' did not match any file(s)"
        )
        mock_run.side_effect = error
        args = ["checkout", "nonexistent"]

        # Act & Assert
        with pytest.raises(GitError, match="Git command failed"):
            run_git_command(args)

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_includes_stderr_in_error(self, mock_run):
        """Should include stderr output in GitError message"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "commit"],
            stderr="nothing to commit"
        )
        mock_run.side_effect = error
        args = ["commit", "-m", "message"]

        # Act & Assert
        with pytest.raises(GitError, match="nothing to commit"):
            run_git_command(args)

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_includes_command_in_error(self, mock_run):
        """Should include command arguments in error message"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["git", "push"],
            stderr="failed to push"
        )
        mock_run.side_effect = error
        args = ["push", "origin", "main"]

        # Act & Assert
        with pytest.raises(GitError, match="push origin main"):
            run_git_command(args)

    @patch('claudechain.infrastructure.git.operations.run_command')
    def test_run_git_command_with_multiple_arguments(self, mock_run):
        """Should handle git commands with multiple arguments"""
        # Arrange
        mock_run.return_value = Mock(stdout="success", stderr="")
        args = ["commit", "-m", "test message", "--author", "Test <test@example.com>"]

        # Act
        result = run_git_command(args)

        # Assert
        mock_run.assert_called_once_with([
            "git", "commit", "-m", "test message",
            "--author", "Test <test@example.com>"
        ])
        assert result == "success"
