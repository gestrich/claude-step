"""
Tests for post_pr_comment.py - Unified PR comment posting command
"""

import os
import subprocess
import tempfile
import json
from unittest.mock import Mock, patch

import pytest

from claudechain.cli.commands.post_pr_comment import cmd_post_pr_comment


class TestCmdPostPrComment:
    """Test suite for post_pr_comment command functionality"""

    @pytest.fixture
    def mock_gh_actions(self):
        """Fixture providing mocked GitHub Actions helper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def create_execution_file(self, tmp_path):
        """Helper to create execution files with cost data.

        Creates files with modelUsage so calculated_cost works.
        Uses Haiku 3 rate ($0.25/MTok) and input tokens only.
        """
        counter = [0]  # Use list for mutable closure

        def _create(cost: float):
            counter[0] += 1
            exec_file = tmp_path / f"exec_{counter[0]}_{cost}.json"
            # Calculate input tokens needed for target cost at Haiku 3 rate
            # cost = input_tokens * 0.25 / 1_000_000
            # input_tokens = cost * 4_000_000
            input_tokens = int(cost * 4_000_000)
            exec_file.write_text(json.dumps({
                "total_cost_usd": cost,  # File cost (not used)
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": input_tokens,
                    }
                }
            }))
            return str(exec_file)
        return _create

    @pytest.fixture
    def base_env_vars(self):
        """Fixture providing standard environment variables"""
        return {
            "PR_NUMBER": "42",
            "MAIN_EXECUTION_FILE": "",
            "SUMMARY_EXECUTION_FILE": "",
            "GITHUB_REPOSITORY": "owner/repo",
            "GITHUB_RUN_ID": "12345"
        }

    def test_cmd_post_pr_comment_posts_combined_comment_with_summary(self, mock_gh_actions, base_env_vars, create_execution_file, tmp_path):
        """Should post unified comment when summary file exists"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("## AI-Generated Summary\n\nTest summary content")
            summary_file = f.name

        try:
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
                        result = cmd_post_pr_comment(
                            gh=mock_gh_actions,
                            pr_number="42",
                            summary_file_path=summary_file,
                            main_execution_file=create_execution_file(0.123456),
                            summary_execution_file=create_execution_file(0.045678),
                            repo="owner/repo",
                            run_id="12345"
                        )

            # Assert
            assert result == 0
            # Function outputs 2 values: cost_breakdown, comment_posted
            assert mock_gh_actions.write_output.call_count == 2
            # Verify the last call is comment_posted
            last_call = mock_gh_actions.write_output.call_args_list[-1]
            assert last_call[0] == ("comment_posted", "true")
            mock_run.assert_called_once()
        finally:
            # Clean up real summary file
            os.unlink(summary_file)

    def test_cmd_post_pr_comment_writes_combined_content_to_temp_file(self, mock_gh_actions, base_env_vars, create_execution_file, tmp_path):
        """Should write properly formatted markdown with summary and cost"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("## AI-Generated Summary\n\nTest summary")
            summary_file = f.name

        written_content = []

        def capture_write(content):
            written_content.append(content)

        try:
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
                        cmd_post_pr_comment(
                            gh=mock_gh_actions,
                            pr_number="42",
                            summary_file_path=summary_file,
                            main_execution_file=create_execution_file(0.123456),
                            summary_execution_file=create_execution_file(0.045678),
                            repo="owner/repo",
                            run_id="12345"
                        )

            # Assert
            assert len(written_content) == 1
            content = written_content[0]
            assert "## AI-Generated Summary" in content
            assert "Test summary" in content
            assert "## 💰 Cost Breakdown" in content
            assert "$0.12" in content
            assert "$0.05" in content
            assert "$0.17" in content
        finally:
            os.unlink(summary_file)

    def test_cmd_post_pr_comment_posts_cost_only_when_summary_missing(self, mock_gh_actions, base_env_vars, create_execution_file, tmp_path):
        """Should post cost-only comment when summary file doesn't exist"""
        # Arrange
        written_content = []

        def capture_write(content):
            written_content.append(content)

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
                    result = cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="/nonexistent/file.md",
                        main_execution_file=create_execution_file(0.123456),
                        summary_execution_file=create_execution_file(0.045678),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        assert result == 0
        content = written_content[0]
        assert "## AI-Generated Summary" not in content
        assert "## 💰 Cost Breakdown" in content
        assert content.startswith("## 💰 Cost Breakdown")

    def test_cmd_post_pr_comment_posts_cost_only_when_summary_empty(self, mock_gh_actions, base_env_vars, create_execution_file, tmp_path):
        """Should post cost-only comment when summary file is empty"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("   \n  \n")  # Only whitespace
            summary_file = f.name

        written_content = []

        def capture_write(content):
            written_content.append(content)

        try:
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
                        result = cmd_post_pr_comment(
                            gh=mock_gh_actions,
                            pr_number="42",
                            summary_file_path=summary_file,
                            main_execution_file=create_execution_file(0.123456),
                            summary_execution_file=create_execution_file(0.045678),
                            repo="owner/repo",
                            run_id="12345"
                        )

            # Assert
            assert result == 0
            content = written_content[0]
            assert "## AI-Generated Summary" not in content
            assert "## 💰 Cost Breakdown" in content
        finally:
            os.unlink(summary_file)

    def test_cmd_post_pr_comment_skips_when_no_pr_number(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should skip posting and return success when PR_NUMBER is not set"""
        # Act
        result = cmd_post_pr_comment(
            gh=mock_gh_actions,
            pr_number="",
            summary_file_path="",
            main_execution_file=create_execution_file(0.0),
            summary_execution_file=create_execution_file(0.0),
            repo="owner/repo",
            run_id="12345"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("comment_posted", "false")
        mock_gh_actions.set_error.assert_not_called()

    def test_cmd_post_pr_comment_skips_when_pr_number_is_empty(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should skip posting when PR_NUMBER is whitespace only"""
        # Act
        result = cmd_post_pr_comment(
            gh=mock_gh_actions,
            pr_number="   ",
            summary_file_path="",
            main_execution_file=create_execution_file(0.0),
            summary_execution_file=create_execution_file(0.0),
            repo="owner/repo",
            run_id="12345"
        )

        # Assert
        assert result == 0
        mock_gh_actions.write_output.assert_called_once_with("comment_posted", "false")

    def test_cmd_post_pr_comment_fails_when_repository_missing(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should return error when GITHUB_REPOSITORY is not set"""
        # Act
        result = cmd_post_pr_comment(
            gh=mock_gh_actions,
            pr_number="42",
            summary_file_path="",
            main_execution_file=create_execution_file(0.0),
            summary_execution_file=create_execution_file(0.0),
            repo="",
            run_id="12345"
        )

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once_with("GITHUB_REPOSITORY environment variable is required")

    def test_cmd_post_pr_comment_fails_when_run_id_missing(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should return error when GITHUB_RUN_ID is not set"""
        # Act
        result = cmd_post_pr_comment(
            gh=mock_gh_actions,
            pr_number="42",
            summary_file_path="",
            main_execution_file=create_execution_file(0.0),
            summary_execution_file=create_execution_file(0.0),
            repo="owner/repo",
            run_id=""
        )

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once_with("GITHUB_RUN_ID environment variable is required")

    def test_cmd_post_pr_comment_handles_zero_cost_values(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should handle zero cost values correctly"""
        # Arrange
        written_content = []

        def capture_write(content):
            written_content.append(content)

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
                    result = cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.0),
                        summary_execution_file=create_execution_file(0.0),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        assert result == 0
        content = written_content[0]
        assert "$0.00" in content

    def test_cmd_post_pr_comment_uses_provided_cost_values(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should use provided cost values in output"""
        # Arrange
        written_content = []

        def capture_write(content):
            written_content.append(content)

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
                    result = cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123),
                        summary_execution_file=create_execution_file(0.456),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        assert result == 0
        content = written_content[0]
        assert "$0.12" in content
        assert "$0.46" in content
        assert "$0.58" in content

    def test_cmd_post_pr_comment_handles_subprocess_error(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should return error when gh CLI command fails"""
        # Arrange
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
                    result = cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123456),
                        summary_execution_file=create_execution_file(0.045678),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        assert result == 1
        mock_gh_actions.set_error.assert_called_once()
        error_message = mock_gh_actions.set_error.call_args[0][0]
        assert "Failed to post comment" in error_message
        assert "API error: not found" in error_message
        mock_unlink.assert_called_once()

    def test_cmd_post_pr_comment_cleans_up_temp_file_on_success(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should delete temporary file after successful comment posting"""
        # Arrange
        temp_file_path = "/tmp/test_cleanup.md"

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
                    cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123456),
                        summary_execution_file=create_execution_file(0.045678),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        mock_unlink.assert_called_once_with(temp_file_path)

    def test_cmd_post_pr_comment_cleans_up_temp_file_on_error(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should delete temporary file even when comment posting fails"""
        # Arrange
        temp_file_path = "/tmp/test_cleanup_error.md"

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
                    cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123456),
                        summary_execution_file=create_execution_file(0.045678),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        mock_unlink.assert_called_once_with(temp_file_path)

    def test_cmd_post_pr_comment_handles_summary_file_read_error(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should continue with cost-only comment when summary file read fails"""
        # Arrange
        main_exec_file = create_execution_file(0.123456)
        summary_exec_file = create_execution_file(0.045678)

        written_content = []

        def capture_write(content):
            written_content.append(content)

        # Create a mock open that only fails for the summary file
        original_open = open
        protected_path = "/tmp/protected_file.md"

        def selective_open(path, *args, **kwargs):
            if path == protected_path:
                raise PermissionError("Access denied")
            return original_open(path, *args, **kwargs)

        with patch('subprocess.run') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                with patch('os.unlink'):
                    with patch('builtins.open', side_effect=selective_open):
                        mock_file = Mock()
                        mock_file.name = "/tmp/test.md"
                        mock_file.write = Mock(side_effect=capture_write)
                        mock_file.__enter__ = Mock(return_value=mock_file)
                        mock_file.__exit__ = Mock(return_value=False)
                        mock_tempfile.return_value = mock_file
                        mock_run.return_value = Mock(returncode=0)

                        # Act
                        result = cmd_post_pr_comment(
                            gh=mock_gh_actions,
                            pr_number="42",
                            summary_file_path=protected_path,
                            main_execution_file=main_exec_file,
                            summary_execution_file=summary_exec_file,
                            repo="owner/repo",
                            run_id="12345"
                        )

        # Assert
        assert result == 0
        content = written_content[0]
        assert "## AI-Generated Summary" not in content
        assert "## 💰 Cost Breakdown" in content

    def test_cmd_post_pr_comment_strips_whitespace_from_pr_number(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should handle PR number correctly when passed with whitespace"""
        # Note: whitespace stripping now happens in __main__.py adapter layer
        with patch('subprocess.run') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                with patch('os.unlink'):
                    mock_file = Mock()
                    mock_file.name = "/tmp/test.md"
                    mock_file.__enter__ = Mock(return_value=mock_file)
                    mock_file.__exit__ = Mock(return_value=False)
                    mock_tempfile.return_value = mock_file
                    mock_run.return_value = Mock(returncode=0)

                    # Act - simulate what __main__.py does after stripping
                    result = cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",  # Already stripped in adapter
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123456),
                        summary_execution_file=create_execution_file(0.045678),
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        assert result == 0
        call_args = mock_run.call_args[0][0]
        assert "42" in call_args

    def test_cmd_post_pr_comment_calculates_total_cost_from_components(self, mock_gh_actions, create_execution_file, tmp_path):
        """Should calculate total_cost from main_cost + summary_cost in domain model"""
        # Arrange
        written_content = []

        def capture_write(content):
            written_content.append(content)

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
                    cmd_post_pr_comment(
                        gh=mock_gh_actions,
                        pr_number="42",
                        summary_file_path="",
                        main_execution_file=create_execution_file(0.123),
                        summary_execution_file=create_execution_file(0.456),
                        # Passed but not used - domain model calculates it
                        repo="owner/repo",
                        run_id="12345"
                    )

        # Assert
        content = written_content[0]
        # Domain model calculates total as main_cost + summary_cost = 0.579
        assert "$0.58" in content
