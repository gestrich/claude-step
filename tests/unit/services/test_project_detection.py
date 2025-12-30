"""Tests for project detection logic"""

import json
import pytest
from unittest.mock import Mock, patch

from claudestep.services.project_detection_service import ProjectDetectionService
from claudestep.domain.exceptions import GitHubAPIError


class TestDetectProjectFromPR:
    """Test suite for detect_project_from_pr functionality"""

    @pytest.fixture
    def mock_run_gh_command(self):
        """Fixture providing mocked run_gh_command"""
        with patch('claudestep.services.project_detection_service.run_gh_command') as mock:
            yield mock

    def test_detect_project_from_pr_success(self, mock_run_gh_command):
        """Should successfully detect project from PR branch name"""
        # Arrange
        pr_number = "123"
        repo = "owner/repo"
        branch_name = "claude-step-my-project-5"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result == "my-project"
        mock_run_gh_command.assert_called_once_with([
            "pr", "view", "123",
            "--repo", "owner/repo",
            "--json", "headRefName"
        ])

    def test_detect_project_from_pr_with_complex_project_name(self, mock_run_gh_command):
        """Should handle project names with multiple hyphens"""
        # Arrange
        pr_number = "456"
        repo = "owner/repo"
        branch_name = "claude-step-my-complex-project-name-42"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result == "my-complex-project-name"

    def test_detect_project_from_pr_when_branch_name_missing(self, mock_run_gh_command):
        """Should return None when PR data has no headRefName"""
        # Arrange
        pr_number = "789"
        repo = "owner/repo"
        pr_data = {}  # No headRefName
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_when_branch_name_is_none(self, mock_run_gh_command):
        """Should return None when headRefName is explicitly None"""
        # Arrange
        pr_number = "789"
        repo = "owner/repo"
        pr_data = {"headRefName": None}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_with_invalid_branch_format(self, mock_run_gh_command):
        """Should return None when branch name doesn't match expected format"""
        # Arrange
        pr_number = "999"
        repo = "owner/repo"
        branch_name = "feature/some-random-branch"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_with_wrong_prefix(self, mock_run_gh_command):
        """Should return None when branch doesn't start with claude-step-"""
        # Arrange
        pr_number = "111"
        repo = "owner/repo"
        branch_name = "wrong-prefix-my-project-1"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_when_gh_command_fails(self, mock_run_gh_command):
        """Should return None when GitHub CLI command fails"""
        # Arrange
        pr_number = "123"
        repo = "owner/repo"
        mock_run_gh_command.side_effect = GitHubAPIError("API error")
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_when_json_invalid(self, mock_run_gh_command):
        """Should return None when GitHub CLI returns invalid JSON"""
        # Arrange
        pr_number = "123"
        repo = "owner/repo"
        mock_run_gh_command.return_value = "invalid json {{"
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result is None

    def test_detect_project_from_pr_with_minimum_valid_branch(self, mock_run_gh_command):
        """Should handle minimum valid branch name (single char project, index 1)"""
        # Arrange
        pr_number = "555"
        repo = "owner/repo"
        branch_name = "claude-step-x-1"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result == "x"

    def test_detect_project_from_pr_with_numeric_project_name(self, mock_run_gh_command):
        """Should handle project names that contain numbers"""
        # Arrange
        pr_number = "666"
        repo = "owner/repo"
        branch_name = "claude-step-project-123-test-99"
        pr_data = {"headRefName": branch_name}
        mock_run_gh_command.return_value = json.dumps(pr_data)
        service = ProjectDetectionService(repo)

        # Act
        result = service.detect_project_from_pr(pr_number)

        # Assert
        assert result == "project-123-test"


class TestDetectProjectPaths:
    """Test suite for detect_project_paths functionality"""

    def test_detect_project_paths_with_simple_name(self):
        """Should generate correct paths for simple project name"""
        # Arrange
        project_name = "my-project"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert config_path == "claude-step/my-project/configuration.yml"
        assert spec_path == "claude-step/my-project/spec.md"
        assert pr_template_path == "claude-step/my-project/pr-template.md"
        assert project_path == "claude-step/my-project"

    def test_detect_project_paths_with_complex_name(self):
        """Should generate correct paths for complex project name with hyphens"""
        # Arrange
        project_name = "my-complex-project-name"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert config_path == "claude-step/my-complex-project-name/configuration.yml"
        assert spec_path == "claude-step/my-complex-project-name/spec.md"
        assert pr_template_path == "claude-step/my-complex-project-name/pr-template.md"
        assert project_path == "claude-step/my-complex-project-name"

    def test_detect_project_paths_with_single_char_name(self):
        """Should generate correct paths for single character project name"""
        # Arrange
        project_name = "x"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert config_path == "claude-step/x/configuration.yml"
        assert spec_path == "claude-step/x/spec.md"
        assert pr_template_path == "claude-step/x/pr-template.md"
        assert project_path == "claude-step/x"

    def test_detect_project_paths_returns_tuple(self):
        """Should return a tuple of exactly 4 elements"""
        # Arrange
        project_name = "test-project"

        # Act
        result = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert isinstance(result, tuple)
        assert len(result) == 4

    def test_detect_project_paths_with_numeric_name(self):
        """Should handle project names with numbers"""
        # Arrange
        project_name = "project-123"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert config_path == "claude-step/project-123/configuration.yml"
        assert spec_path == "claude-step/project-123/spec.md"
        assert pr_template_path == "claude-step/project-123/pr-template.md"
        assert project_path == "claude-step/project-123"

    def test_detect_project_paths_all_paths_use_same_directory(self):
        """Should ensure all paths are in the same project directory"""
        # Arrange
        project_name = "consistency-test"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        expected_base = "claude-step/consistency-test"
        assert config_path.startswith(expected_base)
        assert spec_path.startswith(expected_base)
        assert pr_template_path.startswith(expected_base)
        assert project_path == expected_base

    def test_detect_project_paths_has_correct_file_extensions(self):
        """Should return paths with correct file extensions"""
        # Arrange
        project_name = "test"

        # Act
        config_path, spec_path, pr_template_path, project_path = ProjectDetectionService.detect_project_paths(project_name)

        # Assert
        assert config_path.endswith(".yml")
        assert spec_path.endswith(".md")
        assert pr_template_path.endswith(".md")
        assert not project_path.endswith((".yml", ".md"))  # Project path has no extension
