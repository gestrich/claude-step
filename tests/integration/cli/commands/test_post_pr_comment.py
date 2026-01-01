"""
Tests for post_pr_comment.py - Unified PR comment posting command
"""

import os
import subprocess
import tempfile
import json
from unittest.mock import Mock, patch

import pytest

from claudestep.cli.commands.post_pr_comment import cmd_post_pr_comment
from claudestep.domain.cost_breakdown import CostBreakdown
from claudestep.domain.summary_file import SummaryFile


class TestFormatUnifiedComment:
    """Test suite for unified comment formatting functionality (using domain models)"""

    def test_format_unified_comment_with_summary_and_cost(self):
        """Should combine summary and cost breakdown into single comment"""
        # Arrange
        summary = SummaryFile(content="## AI-Generated Summary\n\nThis PR implements feature X.")
        cost_breakdown = CostBreakdown(main_cost=0.123456, summary_cost=0.045678)
        repo = "owner/repo"
        run_id = "12345"

        # Act
        result = summary.format_with_cost(cost_breakdown, repo, run_id)

        # Assert
        assert "## AI-Generated Summary" in result
        assert "This PR implements feature X." in result
        assert "---" in result
        assert "## 💰 Cost Breakdown" in result
        assert "| Main refactoring task | $0.123456 |" in result
        assert "| PR summary generation | $0.045678 |" in result
        assert "| **Total** | **$0.169134** |" in result

    def test_format_unified_comment_without_summary(self):
        """Should format cost-only comment when summary is not available"""
        # Arrange
        summary = SummaryFile(content=None)
        cost_breakdown = CostBreakdown(main_cost=0.123456, summary_cost=0.045678)
        repo = "owner/repo"
        run_id = "12345"

        # Act
        result = summary.format_with_cost(cost_breakdown, repo, run_id)

        # Assert
        assert "## AI-Generated Summary" not in result
        assert "## 💰 Cost Breakdown" in result
        assert result.startswith("## 💰 Cost Breakdown")

    def test_format_unified_comment_includes_workflow_url(self):
        """Should include clickable workflow run URL in cost section"""
        # Arrange
        summary = SummaryFile(content=None)
        cost_breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)
        repo = "owner/repo"
        run_id = "67890"

        # Act
        result = summary.format_with_cost(cost_breakdown, repo, run_id)

        # Assert
        expected_url = f"https://github.com/{repo}/actions/runs/{run_id}"
        assert f"[View workflow run]({expected_url})" in result

    def test_format_unified_comment_separates_summary_and_cost(self):
        """Should use divider between summary and cost sections"""
        # Arrange
        summary = SummaryFile(content="## AI-Generated Summary\n\nTest summary")
        cost_breakdown = CostBreakdown(main_cost=0.1, summary_cost=0.05)

        # Act
        result = summary.format_with_cost(cost_breakdown, "owner/repo", "123")

        # Assert
        assert "\n---\n" in result
        summary_index = result.index("Test summary")
        cost_index = result.index("## 💰 Cost Breakdown")
        divider_index = result.index("\n---\n")
        assert summary_index < divider_index < cost_index

    def test_format_unified_comment_handles_zero_costs(self):
        """Should format zero costs correctly"""
        # Arrange
        summary = SummaryFile(content=None)
        cost_breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)

        # Act
        result = summary.format_with_cost(cost_breakdown, "owner/repo", "123")

        # Assert
        assert "$0.000000" in result
        assert "## 💰 Cost Breakdown" in result


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
        """Helper to create execution files with cost data"""
        def _create(cost: float):
            if cost == 0.0 or not cost:
                return ""
            exec_file = tmp_path / f"exec_{cost}.json"
            exec_file.write_text(json.dumps({"total_cost_usd": cost}))
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
            # Function now outputs 4 values: main_cost, summary_cost, total_cost, comment_posted
            assert mock_gh_actions.write_output.call_count == 4
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
            assert "$0.123456" in content
            assert "$0.045678" in content
            assert "$0.169134" in content
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
        assert "$0.000000" in content

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
        assert "$0.123000" in content
        assert "$0.456000" in content
        assert "$0.579000" in content

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
        written_content = []

        def capture_write(content):
            written_content.append(content)

        with patch('subprocess.run') as mock_run:
            with patch('tempfile.NamedTemporaryFile') as mock_tempfile:
                with patch('os.unlink'):
                    with patch('os.path.exists', return_value=True):
                        with patch('builtins.open', side_effect=PermissionError("Access denied")):
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
                                summary_file_path="/tmp/protected_file.md",
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
        assert "$0.579000" in content
