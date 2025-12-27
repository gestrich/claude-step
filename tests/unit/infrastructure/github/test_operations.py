"""Tests for GitHub CLI operations"""

import json
import subprocess
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import Mock, call, mock_open, patch

import pytest

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.infrastructure.github.operations import (
    download_artifact_json,
    ensure_label_exists,
    gh_api_call,
    run_gh_command,
)


class TestRunGhCommand:
    """Test suite for run_gh_command function"""

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_success(self, mock_run):
        """Should execute gh command and return stdout"""
        # Arrange
        mock_run.return_value = Mock(stdout="  command output  \n", stderr="")
        args = ["pr", "list"]

        # Act
        result = run_gh_command(args)

        # Assert
        assert result == "command output"
        mock_run.assert_called_once_with(["gh", "pr", "list"])

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_strips_whitespace(self, mock_run):
        """Should strip leading and trailing whitespace from output"""
        # Arrange
        mock_run.return_value = Mock(stdout="\n\n  PR #123  \n\n", stderr="")
        args = ["pr", "view", "123"]

        # Act
        result = run_gh_command(args)

        # Assert
        assert result == "PR #123"

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_handles_empty_output(self, mock_run):
        """Should handle empty output correctly"""
        # Arrange
        mock_run.return_value = Mock(stdout="", stderr="")
        args = ["pr", "list"]

        # Act
        result = run_gh_command(args)

        # Assert
        assert result == ""

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_raises_github_error_on_failure(self, mock_run):
        """Should raise GitHubAPIError when gh command fails"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "view", "999"],
            stderr="could not resolve to a PullRequest"
        )
        mock_run.side_effect = error
        args = ["pr", "view", "999"]

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="GitHub CLI command failed"):
            run_gh_command(args)

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_includes_stderr_in_error(self, mock_run):
        """Should include stderr output in GitHubAPIError message"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "api"],
            stderr="HTTP 404: Not Found"
        )
        mock_run.side_effect = error
        args = ["api", "/invalid/endpoint"]

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="HTTP 404"):
            run_gh_command(args)

    @patch('claudestep.infrastructure.github.operations.run_command')
    def test_run_gh_command_includes_command_in_error(self, mock_run):
        """Should include command arguments in error message"""
        # Arrange
        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=["gh", "pr", "create"],
            stderr="title is required"
        )
        mock_run.side_effect = error
        args = ["pr", "create", "--body", "test"]

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="pr create --body test"):
            run_gh_command(args)


class TestGhApiCall:
    """Test suite for gh_api_call function"""

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_success(self, mock_run_gh):
        """Should execute API call and return parsed JSON"""
        # Arrange
        mock_run_gh.return_value = '{"key": "value", "number": 123}'
        endpoint = "/repos/owner/repo/pulls/1"

        # Act
        result = gh_api_call(endpoint)

        # Assert
        assert result == {"key": "value", "number": 123}
        mock_run_gh.assert_called_once_with(["api", endpoint, "--method", "GET"])

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_with_post_method(self, mock_run_gh):
        """Should execute POST request with correct method"""
        # Arrange
        mock_run_gh.return_value = '{"created": true}'
        endpoint = "/repos/owner/repo/issues"

        # Act
        result = gh_api_call(endpoint, method="POST")

        # Assert
        assert result == {"created": True}
        mock_run_gh.assert_called_once_with(["api", endpoint, "--method", "POST"])

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_handles_empty_response(self, mock_run_gh):
        """Should return empty dict when response is empty"""
        # Arrange
        mock_run_gh.return_value = ""
        endpoint = "/repos/owner/repo/actions/runs"

        # Act
        result = gh_api_call(endpoint)

        # Assert
        assert result == {}

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_raises_error_on_invalid_json(self, mock_run_gh):
        """Should raise GitHubAPIError when response is invalid JSON"""
        # Arrange
        mock_run_gh.return_value = "not valid json {{"
        endpoint = "/repos/owner/repo/pulls"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Invalid JSON from API"):
            gh_api_call(endpoint)

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_handles_nested_json(self, mock_run_gh):
        """Should correctly parse nested JSON structures"""
        # Arrange
        mock_run_gh.return_value = '{"data": {"nested": {"value": 42}}}'
        endpoint = "/repos/owner/repo/contents"

        # Act
        result = gh_api_call(endpoint)

        # Assert
        assert result == {"data": {"nested": {"value": 42}}}

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_propagates_gh_errors(self, mock_run_gh):
        """Should propagate GitHubAPIError from run_gh_command"""
        # Arrange
        mock_run_gh.side_effect = GitHubAPIError("API rate limit exceeded")
        endpoint = "/repos/owner/repo/pulls"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="API rate limit exceeded"):
            gh_api_call(endpoint)


class TestDownloadArtifactJson:
    """Test suite for download_artifact_json function"""

    @patch('claudestep.infrastructure.github.operations.subprocess.run')
    @patch('claudestep.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudestep.infrastructure.github.operations.os.path.exists')
    @patch('claudestep.infrastructure.github.operations.os.remove')
    def test_download_artifact_json_success(self, mock_remove, mock_exists, mock_zipfile, mock_subprocess):
        """Should download, extract, and parse artifact JSON"""
        # Arrange
        repo = "owner/repo"
        artifact_id = 12345
        expected_data = {"cost": 1.23, "task": "test"}

        mock_subprocess.return_value = Mock(returncode=0)
        mock_exists.return_value = True

        mock_zip = Mock()
        mock_zip.namelist.return_value = ["metadata.json", "other.txt"]
        mock_zip.open.return_value.__enter__ = Mock(return_value=Mock(
            read=Mock(return_value=json.dumps(expected_data).encode())
        ))
        mock_zip.open.return_value.__exit__ = Mock(return_value=False)
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        mock_zipfile.return_value.__exit__ = Mock(return_value=False)

        # Act
        result = download_artifact_json(repo, artifact_id)

        # Assert
        assert result == expected_data
        mock_subprocess.assert_called_once()
        args = mock_subprocess.call_args[0][0]
        assert args[0] == "gh"
        assert args[1] == "api"
        assert f"/repos/{repo}/actions/artifacts/{artifact_id}/zip" in args

    @patch('claudestep.infrastructure.github.operations.subprocess.run')
    @patch('claudestep.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudestep.infrastructure.github.operations.os.path.exists')
    @patch('claudestep.infrastructure.github.operations.os.remove')
    def test_download_artifact_json_cleans_up_temp_file(self, mock_remove, mock_exists, mock_zipfile, mock_subprocess):
        """Should clean up temporary zip file after processing"""
        # Arrange
        repo = "owner/repo"
        artifact_id = 12345

        mock_subprocess.return_value = Mock(returncode=0)
        mock_exists.return_value = True

        mock_zip = Mock()
        mock_zip.namelist.return_value = ["data.json"]
        mock_zip.open.return_value.__enter__ = Mock(return_value=Mock(
            read=Mock(return_value=b'{"key": "value"}')
        ))
        mock_zip.open.return_value.__exit__ = Mock(return_value=False)
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        mock_zipfile.return_value.__exit__ = Mock(return_value=False)

        # Act
        download_artifact_json(repo, artifact_id)

        # Assert
        mock_remove.assert_called_once()

    @patch('claudestep.infrastructure.github.operations.subprocess.run')
    @patch('claudestep.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudestep.infrastructure.github.operations.os.path.exists')
    @patch('claudestep.infrastructure.github.operations.os.remove')
    def test_download_artifact_json_returns_none_when_no_json_in_zip(self, mock_remove, mock_exists, mock_zipfile, mock_subprocess, capsys):
        """Should return None when no JSON file found in artifact"""
        # Arrange
        repo = "owner/repo"
        artifact_id = 12345

        mock_subprocess.return_value = Mock(returncode=0)
        mock_exists.return_value = True

        mock_zip = Mock()
        mock_zip.namelist.return_value = ["readme.txt", "data.csv"]  # No JSON files
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        mock_zipfile.return_value.__exit__ = Mock(return_value=False)

        # Act
        result = download_artifact_json(repo, artifact_id)

        # Assert
        assert result is None
        captured = capsys.readouterr()
        assert "No JSON file found" in captured.out

    @patch('claudestep.infrastructure.github.operations.subprocess.run')
    def test_download_artifact_json_returns_none_on_download_failure(self, mock_subprocess, capsys):
        """Should return None and print warning when download fails"""
        # Arrange
        repo = "owner/repo"
        artifact_id = 12345
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ["gh"], stderr="Not found")

        # Act
        result = download_artifact_json(repo, artifact_id)

        # Assert
        assert result is None
        captured = capsys.readouterr()
        assert "Failed to download/parse artifact" in captured.out

    @patch('claudestep.infrastructure.github.operations.subprocess.run')
    @patch('claudestep.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudestep.infrastructure.github.operations.os.path.exists')
    @patch('claudestep.infrastructure.github.operations.os.remove')
    def test_download_artifact_json_returns_none_on_parse_error(self, mock_remove, mock_exists, mock_zipfile, mock_subprocess, capsys):
        """Should return None when JSON parsing fails"""
        # Arrange
        repo = "owner/repo"
        artifact_id = 12345

        mock_subprocess.return_value = Mock(returncode=0)
        mock_exists.return_value = True

        mock_zip = Mock()
        mock_zip.namelist.return_value = ["data.json"]
        mock_zip.open.return_value.__enter__ = Mock(return_value=Mock(
            read=Mock(return_value=b'invalid json {{')
        ))
        mock_zip.open.return_value.__exit__ = Mock(return_value=False)
        mock_zipfile.return_value.__enter__.return_value = mock_zip
        mock_zipfile.return_value.__exit__ = Mock(return_value=False)

        # Act
        result = download_artifact_json(repo, artifact_id)

        # Assert
        assert result is None
        captured = capsys.readouterr()
        assert "Failed to download/parse artifact" in captured.out


class TestEnsureLabelExists:
    """Test suite for ensure_label_exists function"""

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_creates_new_label(self, mock_run_gh, mock_github_actions_helper):
        """Should create label when it doesn't exist"""
        # Arrange
        mock_run_gh.return_value = "Label created"
        label = "claude-step"
        gh = mock_github_actions_helper

        # Act
        ensure_label_exists(label, gh)

        # Assert
        mock_run_gh.assert_called_once()
        args = mock_run_gh.call_args[0][0]
        assert "label" in args
        assert "create" in args
        assert label in args
        assert "--color" in args
        gh.write_step_summary.assert_called_once_with(f"- Label '{label}': ✅ Created")
        gh.set_notice.assert_called_once_with(f"Created label '{label}'")

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_handles_existing_label(self, mock_run_gh, mock_github_actions_helper):
        """Should handle label that already exists gracefully"""
        # Arrange
        mock_run_gh.side_effect = GitHubAPIError("label already exists on repository")
        label = "claude-step"
        gh = mock_github_actions_helper

        # Act
        ensure_label_exists(label, gh)

        # Assert
        gh.write_step_summary.assert_called_once_with(f"- Label '{label}': ✅ Already exists")

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_reraises_other_errors(self, mock_run_gh, mock_github_actions_helper):
        """Should re-raise GitHubAPIError if not about existing label"""
        # Arrange
        mock_run_gh.side_effect = GitHubAPIError("API rate limit exceeded")
        label = "claude-step"
        gh = mock_github_actions_helper

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="API rate limit exceeded"):
            ensure_label_exists(label, gh)

    @patch('claudestep.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_uses_correct_color_and_description(self, mock_run_gh, mock_github_actions_helper):
        """Should create label with correct color and description"""
        # Arrange
        mock_run_gh.return_value = "success"
        label = "test-label"
        gh = mock_github_actions_helper

        # Act
        ensure_label_exists(label, gh)

        # Assert
        args = mock_run_gh.call_args[0][0]
        assert "--description" in args
        desc_idx = args.index("--description")
        assert "ClaudeStep automated refactoring" == args[desc_idx + 1]
        assert "--color" in args
        color_idx = args.index("--color")
        assert "0E8A16" == args[color_idx + 1]
