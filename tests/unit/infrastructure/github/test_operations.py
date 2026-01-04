"""Tests for GitHub CLI operations"""

import json
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, call, mock_open, patch

import pytest

from claudechain.domain.exceptions import GitHubAPIError
from claudechain.infrastructure.github.operations import (
    compare_commits,
    detect_project_from_diff,
    download_artifact_json,
    ensure_label_exists,
    file_exists_in_branch,
    get_file_from_branch,
    gh_api_call,
    list_merged_pull_requests,
    list_open_pull_requests,
    list_pull_requests,
    run_gh_command,
)


class TestRunGhCommand:
    """Test suite for run_gh_command function"""

    @patch('claudechain.infrastructure.github.operations.run_command')
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

    @patch('claudechain.infrastructure.github.operations.run_command')
    def test_run_gh_command_strips_whitespace(self, mock_run):
        """Should strip leading and trailing whitespace from output"""
        # Arrange
        mock_run.return_value = Mock(stdout="\n\n  PR #123  \n\n", stderr="")
        args = ["pr", "view", "123"]

        # Act
        result = run_gh_command(args)

        # Assert
        assert result == "PR #123"

    @patch('claudechain.infrastructure.github.operations.run_command')
    def test_run_gh_command_handles_empty_output(self, mock_run):
        """Should handle empty output correctly"""
        # Arrange
        mock_run.return_value = Mock(stdout="", stderr="")
        args = ["pr", "list"]

        # Act
        result = run_gh_command(args)

        # Assert
        assert result == ""

    @patch('claudechain.infrastructure.github.operations.run_command')
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

    @patch('claudechain.infrastructure.github.operations.run_command')
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

    @patch('claudechain.infrastructure.github.operations.run_command')
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

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
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

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
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

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_handles_empty_response(self, mock_run_gh):
        """Should return empty dict when response is empty"""
        # Arrange
        mock_run_gh.return_value = ""
        endpoint = "/repos/owner/repo/actions/runs"

        # Act
        result = gh_api_call(endpoint)

        # Assert
        assert result == {}

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_raises_error_on_invalid_json(self, mock_run_gh):
        """Should raise GitHubAPIError when response is invalid JSON"""
        # Arrange
        mock_run_gh.return_value = "not valid json {{"
        endpoint = "/repos/owner/repo/pulls"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Invalid JSON from API"):
            gh_api_call(endpoint)

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_gh_api_call_handles_nested_json(self, mock_run_gh):
        """Should correctly parse nested JSON structures"""
        # Arrange
        mock_run_gh.return_value = '{"data": {"nested": {"value": 42}}}'
        endpoint = "/repos/owner/repo/contents"

        # Act
        result = gh_api_call(endpoint)

        # Assert
        assert result == {"data": {"nested": {"value": 42}}}

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
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

    @patch('claudechain.infrastructure.github.operations.subprocess.run')
    @patch('claudechain.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudechain.infrastructure.github.operations.os.path.exists')
    @patch('claudechain.infrastructure.github.operations.os.remove')
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

    @patch('claudechain.infrastructure.github.operations.subprocess.run')
    @patch('claudechain.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudechain.infrastructure.github.operations.os.path.exists')
    @patch('claudechain.infrastructure.github.operations.os.remove')
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

    @patch('claudechain.infrastructure.github.operations.subprocess.run')
    @patch('claudechain.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudechain.infrastructure.github.operations.os.path.exists')
    @patch('claudechain.infrastructure.github.operations.os.remove')
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

    @patch('claudechain.infrastructure.github.operations.subprocess.run')
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

    @patch('claudechain.infrastructure.github.operations.subprocess.run')
    @patch('claudechain.infrastructure.github.operations.zipfile.ZipFile')
    @patch('claudechain.infrastructure.github.operations.os.path.exists')
    @patch('claudechain.infrastructure.github.operations.os.remove')
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

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_creates_new_label(self, mock_run_gh, mock_github_actions_helper):
        """Should create label when it doesn't exist"""
        # Arrange
        mock_run_gh.return_value = "Label created"
        label = "claude-chain"
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

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_handles_existing_label(self, mock_run_gh, mock_github_actions_helper):
        """Should handle label that already exists gracefully"""
        # Arrange
        mock_run_gh.side_effect = GitHubAPIError("label already exists on repository")
        label = "claude-chain"
        gh = mock_github_actions_helper

        # Act
        ensure_label_exists(label, gh)

        # Assert
        gh.write_step_summary.assert_called_once_with(f"- Label '{label}': ✅ Already exists")

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_ensure_label_reraises_other_errors(self, mock_run_gh, mock_github_actions_helper):
        """Should re-raise GitHubAPIError if not about existing label"""
        # Arrange
        mock_run_gh.side_effect = GitHubAPIError("API rate limit exceeded")
        label = "claude-chain"
        gh = mock_github_actions_helper

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="API rate limit exceeded"):
            ensure_label_exists(label, gh)

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
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
        assert "ClaudeChain automated refactoring" == args[desc_idx + 1]
        assert "--color" in args
        color_idx = args.index("--color")
        assert "0E8A16" == args[color_idx + 1]


class TestGetFileFromBranch:
    """Test suite for get_file_from_branch function"""

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_success(self, mock_gh_api):
        """Should fetch and decode file content from branch"""
        # Arrange
        import base64
        file_content = "# Sample Spec File\n\nTask 1: Do something"
        encoded = base64.b64encode(file_content.encode()).decode()
        mock_gh_api.return_value = {"content": encoded, "encoding": "base64"}

        repo = "owner/repo"
        branch = "main"
        file_path = "claude-chain/project/spec.md"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result == file_content
        mock_gh_api.assert_called_once_with(
            f"/repos/{repo}/contents/{file_path}?ref={branch}",
            method="GET"
        )

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_handles_newlines_in_base64(self, mock_gh_api):
        """Should handle base64 content with newlines (GitHub adds them)"""
        # Arrange
        import base64
        file_content = "Line 1\nLine 2\nLine 3"
        encoded = base64.b64encode(file_content.encode()).decode()
        # Simulate GitHub adding newlines every 60 chars
        encoded_with_newlines = encoded[:20] + "\n" + encoded[20:40] + "\n" + encoded[40:]
        mock_gh_api.return_value = {"content": encoded_with_newlines, "encoding": "base64"}

        repo = "owner/repo"
        branch = "main"
        file_path = "test.txt"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result == file_content

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_returns_none_on_404(self, mock_gh_api):
        """Should return None when file not found (404 error)"""
        # Arrange
        mock_gh_api.side_effect = GitHubAPIError("404 Not Found")
        repo = "owner/repo"
        branch = "main"
        file_path = "missing/file.md"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result is None

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_returns_none_when_not_found_in_message(self, mock_gh_api):
        """Should return None when 'Not Found' in error message"""
        # Arrange
        mock_gh_api.side_effect = GitHubAPIError("HTTP 404: Not Found (cached)")
        repo = "owner/repo"
        branch = "develop"
        file_path = "nonexistent.yml"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result is None

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_reraises_other_errors(self, mock_gh_api):
        """Should re-raise GitHubAPIError for non-404 errors"""
        # Arrange
        mock_gh_api.side_effect = GitHubAPIError("API rate limit exceeded")
        repo = "owner/repo"
        branch = "main"
        file_path = "some/file.md"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="API rate limit exceeded"):
            get_file_from_branch(repo, branch, file_path)

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_returns_none_when_no_content_field(self, mock_gh_api):
        """Should return None when API response lacks content field"""
        # Arrange
        mock_gh_api.return_value = {"type": "dir", "name": "folder"}
        repo = "owner/repo"
        branch = "main"
        file_path = "directory"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result is None

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_get_file_from_branch_handles_unicode_content(self, mock_gh_api):
        """Should correctly decode unicode characters"""
        # Arrange
        import base64
        file_content = "Unicode test: 你好世界 🎉 café"
        encoded = base64.b64encode(file_content.encode('utf-8')).decode()
        mock_gh_api.return_value = {"content": encoded}

        repo = "owner/repo"
        branch = "main"
        file_path = "unicode.txt"

        # Act
        result = get_file_from_branch(repo, branch, file_path)

        # Assert
        assert result == file_content


class TestFileExistsInBranch:
    """Test suite for file_exists_in_branch function"""

    @patch('claudechain.infrastructure.github.operations.get_file_from_branch')
    def test_file_exists_returns_true_when_file_found(self, mock_get_file):
        """Should return True when file content is returned"""
        # Arrange
        mock_get_file.return_value = "file content here"
        repo = "owner/repo"
        branch = "main"
        file_path = "existing/file.md"

        # Act
        result = file_exists_in_branch(repo, branch, file_path)

        # Assert
        assert result is True
        mock_get_file.assert_called_once_with(repo, branch, file_path)

    @patch('claudechain.infrastructure.github.operations.get_file_from_branch')
    def test_file_exists_returns_false_when_file_not_found(self, mock_get_file):
        """Should return False when get_file_from_branch returns None"""
        # Arrange
        mock_get_file.return_value = None
        repo = "owner/repo"
        branch = "main"
        file_path = "missing/file.md"

        # Act
        result = file_exists_in_branch(repo, branch, file_path)

        # Assert
        assert result is False

    @patch('claudechain.infrastructure.github.operations.get_file_from_branch')
    def test_file_exists_returns_true_for_empty_file(self, mock_get_file):
        """Should return True even for empty file content"""
        # Arrange
        mock_get_file.return_value = ""
        repo = "owner/repo"
        branch = "develop"
        file_path = "empty.txt"

        # Act
        result = file_exists_in_branch(repo, branch, file_path)

        # Assert
        assert result is True

    @patch('claudechain.infrastructure.github.operations.get_file_from_branch')
    def test_file_exists_propagates_errors(self, mock_get_file):
        """Should propagate GitHubAPIError from get_file_from_branch"""
        # Arrange
        mock_get_file.side_effect = GitHubAPIError("API error")
        repo = "owner/repo"
        branch = "main"
        file_path = "file.md"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="API error"):
            file_exists_in_branch(repo, branch, file_path)


class TestListPullRequests:
    """Test suite for list_pull_requests function"""

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_success(self, mock_run_gh):
        """Should fetch PRs and return domain models"""
        # Arrange
        pr_data = [
            {
                "number": 123,
                "title": "Add feature",
                "state": "OPEN",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": None,
                "assignees": [{"login": "alice", "name": "Alice"}],
                "labels": [{"name": "claudechain"}]
            },
            {
                "number": 124,
                "title": "Fix bug",
                "state": "MERGED",
                "createdAt": "2024-01-02T12:00:00Z",
                "mergedAt": "2024-01-03T12:00:00Z",
                "assignees": [{"login": "bob"}],
                "labels": [{"name": "claudechain"}, {"name": "bug"}]
            }
        ]
        mock_run_gh.return_value = json.dumps(pr_data)
        repo = "owner/repo"

        # Act
        result = list_pull_requests(repo)

        # Assert
        assert len(result) == 2
        assert result[0].number == 123
        assert result[0].title == "Add feature"
        assert result[0].state == "open"
        assert result[1].number == 124
        assert result[1].is_merged()

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_with_filters(self, mock_run_gh):
        """Should build command with correct filters"""
        # Arrange
        mock_run_gh.return_value = "[]"
        repo = "owner/repo"

        # Act
        list_pull_requests(repo, state="merged", label="claudechain", limit=50)

        # Assert
        args = mock_run_gh.call_args[0][0]
        assert "pr" in args
        assert "list" in args
        assert "--repo" in args
        assert "owner/repo" in args
        assert "--state" in args
        assert "merged" in args
        assert "--label" in args
        assert "claudechain" in args
        assert "--limit" in args
        assert "50" in args

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_with_assignee_filter(self, mock_run_gh):
        """Should build command with assignee filter"""
        # Arrange
        mock_run_gh.return_value = "[]"
        repo = "owner/repo"

        # Act
        list_pull_requests(repo, state="open", assignee="reviewer1")

        # Assert
        args = mock_run_gh.call_args[0][0]
        assert "pr" in args
        assert "list" in args
        assert "--assignee" in args
        assert "reviewer1" in args
        assert "--state" in args
        assert "open" in args

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_filters_by_date(self, mock_run_gh):
        """Should filter PRs by date when since parameter provided"""
        # Arrange
        cutoff = datetime(2024, 1, 2, tzinfo=timezone.utc)
        pr_data = [
            {
                "number": 123,
                "title": "Old PR",
                "state": "MERGED",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": None,
                "assignees": [],
                "labels": []
            },
            {
                "number": 124,
                "title": "New PR",
                "state": "MERGED",
                "createdAt": "2024-01-03T12:00:00Z",
                "mergedAt": None,
                "assignees": [],
                "labels": []
            }
        ]
        mock_run_gh.return_value = json.dumps(pr_data)

        # Act
        result = list_pull_requests("owner/repo", since=cutoff)

        # Assert
        assert len(result) == 1
        assert result[0].number == 124

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_handles_empty_response(self, mock_run_gh):
        """Should handle empty PR list"""
        # Arrange
        mock_run_gh.return_value = "[]"

        # Act
        result = list_pull_requests("owner/repo")

        # Assert
        assert result == []

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_raises_on_invalid_json(self, mock_run_gh):
        """Should raise GitHubAPIError on invalid JSON"""
        # Arrange
        mock_run_gh.return_value = "invalid json {{"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="Invalid JSON"):
            list_pull_requests("owner/repo")

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_pull_requests_handles_empty_output(self, mock_run_gh):
        """Should handle empty string output"""
        # Arrange
        mock_run_gh.return_value = ""

        # Act
        result = list_pull_requests("owner/repo")

        # Assert
        assert result == []


class TestListMergedPullRequests:
    """Test suite for list_merged_pull_requests convenience function"""

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_merged_pull_requests_filters_by_merged_at(self, mock_run_gh):
        """Should filter merged PRs by merged_at date"""
        # Arrange
        cutoff = datetime(2024, 1, 2, tzinfo=timezone.utc)
        pr_data = [
            {
                "number": 123,
                "title": "Old merged PR",
                "state": "MERGED",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": "2024-01-01T13:00:00Z",
                "assignees": [],
                "labels": []
            },
            {
                "number": 124,
                "title": "New merged PR",
                "state": "MERGED",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": "2024-01-03T12:00:00Z",
                "assignees": [],
                "labels": []
            }
        ]
        mock_run_gh.return_value = json.dumps(pr_data)

        # Act
        result = list_merged_pull_requests("owner/repo", since=cutoff)

        # Assert
        assert len(result) == 1
        assert result[0].number == 124

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_merged_pull_requests_with_label(self, mock_run_gh):
        """Should pass label filter to list_pull_requests"""
        # Arrange
        mock_run_gh.return_value = "[]"
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Act
        list_merged_pull_requests("owner/repo", since=cutoff, label="claudechain")

        # Assert
        args = mock_run_gh.call_args[0][0]
        assert "--label" in args
        assert "claudechain" in args
        assert "--state" in args
        assert "merged" in args

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_merged_pull_requests_excludes_prs_without_merged_at(self, mock_run_gh):
        """Should exclude PRs that don't have merged_at timestamp"""
        # Arrange
        cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pr_data = [
            {
                "number": 123,
                "title": "Merged PR",
                "state": "MERGED",
                "createdAt": "2024-01-02T12:00:00Z",
                "mergedAt": "2024-01-03T12:00:00Z",
                "assignees": [],
                "labels": []
            },
            {
                "number": 124,
                "title": "No merge timestamp",
                "state": "MERGED",
                "createdAt": "2024-01-02T12:00:00Z",
                "mergedAt": None,
                "assignees": [],
                "labels": []
            }
        ]
        mock_run_gh.return_value = json.dumps(pr_data)

        # Act
        result = list_merged_pull_requests("owner/repo", since=cutoff)

        # Assert
        assert len(result) == 1
        assert result[0].number == 123


class TestListOpenPullRequests:
    """Test suite for list_open_pull_requests convenience function"""

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_open_pull_requests_success(self, mock_run_gh):
        """Should fetch open PRs"""
        # Arrange
        pr_data = [
            {
                "number": 123,
                "title": "Open PR",
                "state": "OPEN",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": None,
                "assignees": [],
                "labels": []
            }
        ]
        mock_run_gh.return_value = json.dumps(pr_data)

        # Act
        result = list_open_pull_requests("owner/repo")

        # Assert
        assert len(result) == 1
        assert result[0].is_open()

    @patch('claudechain.infrastructure.github.operations.run_gh_command')
    def test_list_open_pull_requests_with_label(self, mock_run_gh):
        """Should filter by label"""
        # Arrange
        mock_run_gh.return_value = "[]"

        # Act
        list_open_pull_requests("owner/repo", label="claudechain", limit=25)

        # Assert
        args = mock_run_gh.call_args[0][0]
        assert "--state" in args
        assert "open" in args
        assert "--label" in args
        assert "claudechain" in args
        assert "--limit" in args
        assert "25" in args


class TestCompareCommits:
    """Test suite for compare_commits function"""

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_success(self, mock_gh_api):
        """Should return list of changed file paths"""
        # Arrange
        mock_gh_api.return_value = {
            "files": [
                {"filename": "src/main.py", "status": "modified"},
                {"filename": "README.md", "status": "added"},
                {"filename": "old_file.txt", "status": "removed"}
            ]
        }
        repo = "owner/repo"
        base = "abc123"
        head = "def456"

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert result == ["src/main.py", "README.md", "old_file.txt"]
        mock_gh_api.assert_called_once_with(
            f"/repos/{repo}/compare/{base}...{head}",
            method="GET"
        )

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_with_branch_names(self, mock_gh_api):
        """Should work with branch names instead of SHAs"""
        # Arrange
        mock_gh_api.return_value = {
            "files": [
                {"filename": "feature.py", "status": "added"}
            ]
        }
        repo = "owner/repo"
        base = "main"
        head = "feature-branch"

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert result == ["feature.py"]
        mock_gh_api.assert_called_once_with(
            "/repos/owner/repo/compare/main...feature-branch",
            method="GET"
        )

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_empty_files_list(self, mock_gh_api):
        """Should return empty list when no files changed"""
        # Arrange
        mock_gh_api.return_value = {"files": []}
        repo = "owner/repo"
        base = "abc123"
        head = "abc123"  # Same commit

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert result == []

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_missing_files_key(self, mock_gh_api):
        """Should return empty list when files key is missing"""
        # Arrange
        mock_gh_api.return_value = {
            "status": "identical",
            "ahead_by": 0,
            "behind_by": 0
        }
        repo = "owner/repo"
        base = "abc123"
        head = "abc123"

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert result == []

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_propagates_api_error(self, mock_gh_api):
        """Should propagate GitHubAPIError from gh_api_call"""
        # Arrange
        mock_gh_api.side_effect = GitHubAPIError("404 Not Found: base commit not found")
        repo = "owner/repo"
        base = "nonexistent"
        head = "abc123"

        # Act & Assert
        with pytest.raises(GitHubAPIError, match="404 Not Found"):
            compare_commits(repo, base, head)

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_many_files(self, mock_gh_api):
        """Should handle response with many files"""
        # Arrange
        files = [{"filename": f"file_{i}.py", "status": "modified"} for i in range(100)]
        mock_gh_api.return_value = {"files": files}
        repo = "owner/repo"
        base = "abc123"
        head = "def456"

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert len(result) == 100
        assert result[0] == "file_0.py"
        assert result[99] == "file_99.py"

    @patch('claudechain.infrastructure.github.operations.gh_api_call')
    def test_compare_commits_spec_file_detection(self, mock_gh_api):
        """Should correctly return spec.md file paths for project detection"""
        # Arrange
        mock_gh_api.return_value = {
            "files": [
                {"filename": "claude-chain/my-project/spec.md", "status": "modified"},
                {"filename": "README.md", "status": "modified"},
                {"filename": "src/main.py", "status": "added"}
            ]
        }
        repo = "owner/repo"
        base = "abc123"
        head = "def456"

        # Act
        result = compare_commits(repo, base, head)

        # Assert
        assert "claude-chain/my-project/spec.md" in result
        assert len(result) == 3


class TestDetectProjectFromDiff:
    """Test suite for detect_project_from_diff function"""

    def test_single_spec_file_changed(self):
        """Should return project name when single spec.md changed"""
        # Arrange
        changed_files = [
            "claude-chain/my-project/spec.md",
            "README.md",
            "src/main.py"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result == "my-project"

    def test_no_spec_files_changed(self):
        """Should return None when no spec.md files changed"""
        # Arrange
        changed_files = [
            "src/main.py",
            "README.md",
            "tests/test_main.py"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result is None

    def test_multiple_spec_files_raises_error(self):
        """Should raise ValueError when multiple spec.md files changed"""
        # Arrange
        changed_files = [
            "claude-chain/project-a/spec.md",
            "claude-chain/project-b/spec.md",
            "README.md"
        ]

        # Act & Assert
        with pytest.raises(ValueError, match="Multiple projects modified"):
            detect_project_from_diff(changed_files)

    def test_multiple_spec_files_error_message_contains_projects(self):
        """Should include project names in error message"""
        # Arrange
        changed_files = [
            "claude-chain/alpha/spec.md",
            "claude-chain/beta/spec.md"
        ]

        # Act & Assert
        with pytest.raises(ValueError, match="alpha") as exc_info:
            detect_project_from_diff(changed_files)
        assert "beta" in str(exc_info.value)
        assert "Push changes to one project at a time" in str(exc_info.value)

    def test_spec_in_wrong_directory_structure(self):
        """Should return None for spec.md in wrong directory structure"""
        # Arrange
        changed_files = [
            "specs/project/spec.md",  # Wrong parent directory
            "claude-chain/spec.md",  # Missing project subdirectory
            "claude-chain/project/nested/spec.md",  # Too deeply nested
            "other-step/project/spec.md"  # Different prefix
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result is None

    def test_empty_file_list(self):
        """Should return None for empty file list"""
        # Arrange
        changed_files = []

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result is None

    def test_project_name_with_hyphens(self):
        """Should handle project names with hyphens"""
        # Arrange
        changed_files = [
            "claude-chain/my-awesome-project/spec.md"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result == "my-awesome-project"

    def test_project_name_with_underscores(self):
        """Should handle project names with underscores"""
        # Arrange
        changed_files = [
            "claude-chain/my_project_v2/spec.md"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result == "my_project_v2"

    def test_ignores_other_files_in_project_directory(self):
        """Should only detect spec.md, not other files in project directory"""
        # Arrange
        changed_files = [
            "claude-chain/project/README.md",
            "claude-chain/project/metadata.json",
            "claude-chain/project/tasks/task1.md"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result is None

    def test_multiple_files_same_project(self):
        """Should return project name even with multiple files from same project"""
        # Arrange
        changed_files = [
            "claude-chain/my-project/spec.md",
            "claude-chain/my-project/README.md",
            "src/related.py"
        ]

        # Act
        result = detect_project_from_diff(changed_files)

        # Assert
        assert result == "my-project"
