"""
Tests for add_cost_comment.py - Cost comment posting command
"""

import os
import subprocess
import tempfile
from unittest.mock import Mock, patch, call

import pytest

from claudestep.cli.commands.add_cost_comment import cmd_add_cost_comment, format_cost_comment


class TestFormatCostComment:
    """Test suite for cost comment formatting functionality"""

    def test_format_cost_comment_creates_markdown_table(self):
        """Should format costs as a markdown table with proper structure"""
        # Arrange
        main_cost = 0.123456
        summary_cost = 0.045678
        total_cost = 0.169134
        repo = "owner/repo"
        run_id = "12345"

        # Act
        result = format_cost_comment(main_cost, summary_cost, total_cost, repo, run_id)

        # Assert
        assert "## 💰 Cost Breakdown" in result
        assert "| Component | Cost (USD) |" in result
        assert "| Main refactoring task | $0.123456 |" in result
        assert "| PR summary generation | $0.045678 |" in result
        assert "| **Total** | **$0.169134** |" in result

    def test_format_cost_comment_includes_workflow_url(self):
        """Should include clickable workflow run URL"""
        # Arrange
        repo = "owner/repo"
        run_id = "67890"

        # Act
        result = format_cost_comment(0.0, 0.0, 0.0, repo, run_id)

        # Assert
        expected_url = f"https://github.com/{repo}/actions/runs/{run_id}"
        assert f"[View workflow run]({expected_url})" in result

    def test_format_cost_comment_handles_zero_costs(self):
        """Should format zero costs correctly"""
        # Arrange
        main_cost = 0.0
        summary_cost = 0.0
        total_cost = 0.0

        # Act
        result = format_cost_comment(main_cost, summary_cost, total_cost, "owner/repo", "123")

        # Assert
        assert "$0.000000" in result
        assert "## 💰 Cost Breakdown" in result

    def test_format_cost_comment_handles_high_precision(self):
        """Should display 6 decimal places for all costs"""
        # Arrange
        main_cost = 0.000001
        summary_cost = 0.000002
        total_cost = 0.000003

        # Act
        result = format_cost_comment(main_cost, summary_cost, total_cost, "owner/repo", "123")

        # Assert
        assert "$0.000001" in result
        assert "$0.000002" in result
        assert "$0.000003" in result


class TestCmdAddCostComment:
    """Test suite for add_cost_comment command functionality"""

    @pytest.fixture
    def mock_gh_actions(self):
        """Fixture providing mocked GitHub Actions helper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def cost_env_vars(self):
        """Fixture providing standard cost environment variables"""
        return {
            "PR_NUMBER": "42",
            "MAIN_COST": "0.123456",
            "SUMMARY_COST": "0.045678",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

    def test_cmd_add_cost_comment_posts_comment_successfully(self, mock_gh_actions, cost_env_vars):
        """Should post cost comment to PR when all inputs are valid"""
        # Arrange
        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink') as mock_unlink:
                        # Set up temp file mock
                        mock_file = Mock()
                        mock_file.name = "/tmp/test_comment.md"
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file

                        # Set up subprocess mock
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("comment_posted", "true")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args == ["gh", "pr", "comment", "42", "--body-file", "/tmp/test_comment.md"]
        mock_unlink.assert_called_once_with("/tmp/test_comment.md")

    def test_cmd_add_cost_comment_writes_formatted_content_to_temp_file(self, mock_gh_actions, cost_env_vars):
        """Should write properly formatted markdown to temporary file"""
        # Arrange
        written_content = []

        def capture_write(content):
            written_content.append(content)

        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink'):
                        # Set up temp file mock to capture writes
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.write = Mock(side_effect=capture_write)
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert len(written_content) == 1
        content = written_content[0]
        assert "## 💰 Cost Breakdown" in content
        assert "$0.123456" in content
        assert "$0.045678" in content
        assert "https://github.com/owner/repo/actions/runs/12345" in content

    def test_cmd_add_cost_comment_skips_when_no_pr_number(self, mock_gh_actions):
        """Should skip posting and return success when PR_NUMBER is not set"""
        # Arrange
        env = {
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        with patch.dict(os.environ, env, clear=True):
            # Act
            result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("comment_posted", "false")
        mock_gh_actions.set_error.assert_not_called()

    def test_cmd_add_cost_comment_skips_when_pr_number_is_empty_string(self, mock_gh_actions):
        """Should skip posting when PR_NUMBER is whitespace only"""
        # Arrange
        env = {
            "PR_NUMBER": "   ",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        with patch.dict(os.environ, env, clear=True):
            # Act
            result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("comment_posted", "false")

    def test_cmd_add_cost_comment_fails_when_repository_missing(self, mock_gh_actions):
        """Should return error when GITHUB_REPOSITORY is not set"""
        # Arrange
        env = {
            "PR_NUMBER": "42",
            "GITHUB_RUN_ID": "12345"
        }

        with patch.dict(os.environ, env, clear=True):
            # Act
            result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once_with("GITHUB_REPOSITORY environment variable is required")
        mock_gh_actions.write_output.assert_not_called()

    def test_cmd_add_cost_comment_fails_when_run_id_missing(self, mock_gh_actions):
        """Should return error when GITHUB_RUN_ID is not set"""
        # Arrange
        env = {
            "PR_NUMBER": "42",
            "GITHUB_REPOSITORY": "owner/repo"
        }

        with patch.dict(os.environ, env, clear=True):
            # Act
            result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once_with("GITHUB_RUN_ID environment variable is required")

    def test_cmd_add_cost_comment_handles_invalid_cost_values(self, mock_gh_actions):
        """Should treat invalid cost values as zero and continue"""
        # Arrange
        env = {
            "PR_NUMBER": "42",
            "MAIN_COST": "invalid",
            "SUMMARY_COST": "not-a-number",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        written_content = []

        def capture_write(content):
            written_content.append(content)

        with patch.dict(os.environ, env, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink'):
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.write = Mock(side_effect=capture_write)
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        content = written_content[0]
        assert "$0.000000" in content  # Should use 0.0 for invalid values

    def test_cmd_add_cost_comment_uses_default_zero_costs_when_missing(self, mock_gh_actions):
        """Should use 0 for costs when environment variables are not set"""
        # Arrange
        env = {
            "PR_NUMBER": "42",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        written_content = []

        def capture_write(content):
            written_content.append(content)

        with patch.dict(os.environ, env, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink'):
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.write = Mock(side_effect=capture_write)
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        content = written_content[0]
        assert "$0.000000" in content

    def test_cmd_add_cost_comment_handles_subprocess_error(self, mock_gh_actions, cost_env_vars):
        """Should return error when gh CLI command fails"""
        # Arrange
        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink') as mock_unlink:
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file

                        # Simulate gh CLI failure
                        mock_run.side_effect = subprocess.CalledProcessError(
                            returncode=1,
                            cmd=["gh", "pr", "comment"],
                            stderr="API error: not found"
                        )

                        # Act
                        result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once()
        error_message = mock_gh_actions.set_error.call_args[0][0]
        assert "Failed to post comment" in error_message
        assert "API error: not found" in error_message
        mock_unlink.assert_called_once()  # Cleanup should still happen

    def test_cmd_add_cost_comment_cleans_up_temp_file_on_success(self, mock_gh_actions, cost_env_vars):
        """Should delete temporary file after successful comment posting"""
        # Arrange
        temp_file_path = "/tmp/test_cleanup.md"

        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink') as mock_unlink:
                        mock_file = Mock()
                        mock_file.name = temp_file_path
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        mock_unlink.assert_called_once_with(temp_file_path)

    def test_cmd_add_cost_comment_cleans_up_temp_file_on_error(self, mock_gh_actions, cost_env_vars):
        """Should delete temporary file even when comment posting fails"""
        # Arrange
        temp_file_path = "/tmp/test_cleanup_error.md"

        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink') as mock_unlink:
                        mock_file = Mock()
                        mock_file.name = temp_file_path
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="error")

                        # Act
                        cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        mock_unlink.assert_called_once_with(temp_file_path)

    def test_cmd_add_cost_comment_handles_unexpected_exception(self, mock_gh_actions, cost_env_vars):
        """Should catch and report unexpected exceptions"""
        # Arrange
        with patch.dict(os.environ, cost_env_vars, clear=True):
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                # Simulate unexpected error during file creation
                mock_tempfile.side_effect = IOError("Disk full")

                # Act
                result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once()
        error_message = mock_gh_actions.set_error.call_args[0][0]
        assert "Error posting cost comment" in error_message
        assert "Disk full" in error_message

    def test_cmd_add_cost_comment_strips_whitespace_from_inputs(self, mock_gh_actions):
        """Should strip whitespace from environment variable values"""
        # Arrange
        env = {
            "PR_NUMBER": "  42  ",
            "MAIN_COST": "  0.123456  ",
            "SUMMARY_COST": "  0.045678  ",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        with patch.dict(os.environ, env, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink'):
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        result = cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        assert result == 0
        call_args = mock_run.call_args[0][0]
        assert "42" in call_args  # Verify trimmed PR number used

    def test_cmd_add_cost_comment_calculates_total_correctly(self, mock_gh_actions):
        """Should calculate total cost as sum of main and summary costs"""
        # Arrange
        env = {
            "PR_NUMBER": "42",
            "MAIN_COST": "0.123",
            "SUMMARY_COST": "0.456",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

        written_content = []

        def capture_write(content):
            written_content.append(content)

        with patch.dict(os.environ, env, clear=True):
            with patch('subprocess.run') as mock_run:
                with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                    with patch('os.unlink'):
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.write = Mock(side_effect=capture_write)
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        cmd_add_cost_comment(None, mock_gh_actions)

        # Assert
        content = written_content[0]
        assert "$0.123000" in content  # Main cost
        assert "$0.456000" in content  # Summary cost
        assert "$0.579000" in content  # Total cost (0.123 + 0.456)
