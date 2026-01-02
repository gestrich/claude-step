"""Unit tests for ProjectRepository"""

import pytest
from unittest.mock import Mock, patch

from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.domain.spec_content import SpecContent
from claudestep.infrastructure.repositories.project_repository import ProjectRepository


class TestProjectRepositoryInitialization:
    """Test suite for ProjectRepository initialization"""

    def test_create_repository_with_repo_name(self):
        """Should create repository with GitHub repo name"""
        # Arrange & Act
        repo = ProjectRepository("owner/repo-name")

        # Assert
        assert repo.repo == "owner/repo-name"


class TestProjectRepositoryLoadConfiguration:
    """Test suite for ProjectRepository.load_configuration method"""

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_success(self, mock_get_file):
        """Should load and parse configuration successfully"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
"""
        mock_get_file.return_value = yaml_content

        # Act
        config = repo.load_configuration(project, "main")

        # Assert
        assert config is not None
        assert isinstance(config, ProjectConfiguration)
        assert config.project == project
        assert len(config.reviewers) == 2
        assert config.reviewers[0].username == "alice"
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "claude-step/my-project/configuration.yml"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_returns_default_when_file_not_found(self, mock_get_file):
        """Should return default config when configuration file doesn't exist"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        mock_get_file.return_value = None

        # Act
        config = repo.load_configuration(project, "main")

        # Assert - returns default config, not None
        assert config is not None
        assert config.project == project
        assert config.reviewers == []
        assert config.base_branch is None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "claude-step/my-project/configuration.yml"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_with_custom_branch(self, mock_get_file):
        """Should load configuration from custom branch"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        yaml_content = "reviewers: []"
        mock_get_file.return_value = yaml_content

        # Act
        config = repo.load_configuration(project, "develop")

        # Assert
        assert config is not None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "develop",
            "claude-step/my-project/configuration.yml"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_with_custom_project_base_path(self, mock_get_file):
        """Should use custom project base path"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project", base_path="custom/path/my-project")
        yaml_content = "reviewers: []"
        mock_get_file.return_value = yaml_content

        # Act
        config = repo.load_configuration(project, "main")

        # Assert
        assert config is not None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "custom/path/my-project/configuration.yml"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_handles_empty_reviewers(self, mock_get_file):
        """Should handle configuration with empty reviewers list"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        yaml_content = "reviewers: []"
        mock_get_file.return_value = yaml_content

        # Act
        config = repo.load_configuration(project, "main")

        # Assert
        assert config is not None
        assert config.reviewers == []


class TestProjectRepositoryLoadConfigurationIfExists:
    """Test suite for ProjectRepository.load_configuration_if_exists method"""

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_if_exists_returns_config_when_found(self, mock_get_file):
        """Should return parsed config when file exists"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
"""
        mock_get_file.return_value = yaml_content

        # Act
        config = repo.load_configuration_if_exists(project, "main")

        # Assert
        assert config is not None
        assert len(config.reviewers) == 1
        assert config.reviewers[0].username == "alice"

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_configuration_if_exists_returns_none_when_not_found(self, mock_get_file):
        """Should return None when file doesn't exist"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        mock_get_file.return_value = None

        # Act
        config = repo.load_configuration_if_exists(project, "main")

        # Assert
        assert config is None


class TestProjectRepositoryLoadSpec:
    """Test suite for ProjectRepository.load_spec method"""

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_success(self, mock_get_file):
        """Should load and parse spec.md successfully"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        spec_content = """# Project Spec
- [ ] Task 1
- [ ] Task 2
- [x] Task 3"""
        mock_get_file.return_value = spec_content

        # Act
        spec = repo.load_spec(project, "main")

        # Assert
        assert spec is not None
        assert isinstance(spec, SpecContent)
        assert spec.project == project
        assert spec.total_tasks == 3
        assert spec.completed_tasks == 1
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "claude-step/my-project/spec.md"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_returns_none_when_file_not_found(self, mock_get_file):
        """Should return None when spec file doesn't exist"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        mock_get_file.return_value = None

        # Act
        spec = repo.load_spec(project, "main")

        # Assert
        assert spec is None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "claude-step/my-project/spec.md"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_with_custom_branch(self, mock_get_file):
        """Should load spec from custom branch"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        spec_content = "- [ ] Task 1"
        mock_get_file.return_value = spec_content

        # Act
        spec = repo.load_spec(project, "feature-branch")

        # Assert
        assert spec is not None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "feature-branch",
            "claude-step/my-project/spec.md"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_with_custom_project_base_path(self, mock_get_file):
        """Should use custom project base path"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project", base_path="custom/path/my-project")
        spec_content = "- [ ] Task 1"
        mock_get_file.return_value = spec_content

        # Act
        spec = repo.load_spec(project, "main")

        # Assert
        assert spec is not None
        mock_get_file.assert_called_once_with(
            "owner/repo",
            "main",
            "custom/path/my-project/spec.md"
        )

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_with_empty_content(self, mock_get_file):
        """Should return None for empty spec content (treated as not found)"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        spec_content = ""
        mock_get_file.return_value = spec_content

        # Act
        spec = repo.load_spec(project, "main")

        # Assert
        # Empty string is treated as falsy, so returns None
        assert spec is None

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_spec_with_no_tasks(self, mock_get_file):
        """Should handle spec with no task items"""
        # Arrange
        repo = ProjectRepository("owner/repo")
        project = Project("my-project")
        spec_content = """# Project Spec

This is just documentation without tasks.

## Notes
More text here."""
        mock_get_file.return_value = spec_content

        # Act
        spec = repo.load_spec(project, "main")

        # Assert
        assert spec is not None
        assert spec.total_tasks == 0


class TestProjectRepositoryLoadProjectFull:
    """Test suite for ProjectRepository.load_project_full method"""

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_project_full_success(self, mock_get_file):
        """Should load complete project data successfully"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        # Mock responses for config and spec
        def side_effect(repo_name, branch, path):
            if "configuration.yml" in path:
                return "reviewers:\n  - username: alice\n    maxOpenPRs: 2"
            elif "spec.md" in path:
                return "- [ ] Task 1\n- [x] Task 2"
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("my-project", "main")

        # Assert
        assert result is not None
        project, config, spec = result

        assert isinstance(project, Project)
        assert project.name == "my-project"

        assert isinstance(config, ProjectConfiguration)
        assert len(config.reviewers) == 1
        assert config.reviewers[0].username == "alice"

        assert isinstance(spec, SpecContent)
        assert spec.total_tasks == 2
        assert spec.completed_tasks == 1

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_project_full_uses_default_config_when_config_missing(self, mock_get_file):
        """Should use default config when configuration file is missing"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        # Mock: spec exists, config doesn't
        def side_effect(repo_name, branch, path):
            if "spec.md" in path:
                return "- [ ] Task 1\n- [x] Task 2"
            return None  # Config not found

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("my-project", "main")

        # Assert - returns project with default config
        assert result is not None
        project, config, spec = result

        assert project.name == "my-project"
        assert config.reviewers == []  # Default config has no reviewers
        assert config.base_branch is None
        assert spec.total_tasks == 2

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_project_full_returns_none_when_spec_missing(self, mock_get_file):
        """Should return None when spec file is missing"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        # Mock: config exists, spec doesn't
        def side_effect(repo_name, branch, path):
            if "configuration.yml" in path:
                return "reviewers: []"
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("my-project", "main")

        # Assert
        assert result is None

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_project_full_with_custom_branch(self, mock_get_file):
        """Should load from custom branch"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        def side_effect(repo_name, branch, path):
            if "configuration.yml" in path:
                return "reviewers: []"
            elif "spec.md" in path:
                return "- [ ] Task 1"
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("my-project", "develop")

        # Assert
        assert result is not None
        # Verify branch was used in calls
        assert mock_get_file.call_count == 2
        for call in mock_get_file.call_args_list:
            assert call[0][1] == "develop"  # Second argument is branch

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_load_project_full_creates_project_with_correct_name(self, mock_get_file):
        """Should create Project object with correct name"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        def side_effect(repo_name, branch, path):
            if "configuration.yml" in path:
                return "reviewers: []"
            elif "spec.md" in path:
                return "- [ ] Task 1"
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("custom-project-name", "main")

        # Assert
        assert result is not None
        project, _, _ = result
        assert project.name == "custom-project-name"
        assert project.base_path == "claude-step/custom-project-name"


class TestProjectRepositoryIntegration:
    """Integration tests for ProjectRepository with realistic scenarios"""

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_full_workflow_with_realistic_data(self, mock_get_file):
        """Should handle complete workflow with realistic project data"""
        # Arrange
        repo = ProjectRepository("acme/web-app")

        realistic_config = """
reviewers:
  - username: dev1
    maxOpenPRs: 2
  - username: dev2
    maxOpenPRs: 3
  - username: dev3
    maxOpenPRs: 1
settings:
  auto_merge: true
  pr_template: standard
"""

        realistic_spec = """# Web Application Refactoring

## Overview
This project refactors the authentication system.

## Tasks

- [x] Analyze current authentication flow
- [x] Design new architecture
- [ ] Implement OAuth2 provider
- [ ] Add JWT token management
- [ ] Create user session service
- [ ] Write integration tests
- [ ] Update documentation

## Notes
Ensure backward compatibility with existing sessions.
"""

        def side_effect(repo_name, branch, path):
            if "configuration.yml" in path:
                return realistic_config
            elif "spec.md" in path:
                return realistic_spec
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result = repo.load_project_full("auth-refactor", "main")

        # Assert - Verify complete structure
        assert result is not None
        project, config, spec = result

        # Project assertions
        assert project.name == "auth-refactor"
        assert project.config_path == "claude-step/auth-refactor/configuration.yml"

        # Config assertions
        assert len(config.reviewers) == 3
        reviewer_names = config.get_reviewer_usernames()
        assert reviewer_names == ["dev1", "dev2", "dev3"]
        dev2 = config.get_reviewer("dev2")
        assert dev2.max_open_prs == 3

        # Spec assertions
        assert spec.total_tasks == 7
        assert spec.completed_tasks == 2
        assert spec.pending_tasks == 5

        next_task = spec.get_next_available_task()
        assert next_task.description == "Implement OAuth2 provider"
        assert next_task.index == 3

        pending_indices = spec.get_pending_task_indices()
        assert pending_indices == [3, 4, 5, 6, 7]

    @patch('claudestep.infrastructure.github.operations.get_file_from_branch')
    def test_repository_instance_can_load_multiple_projects(self, mock_get_file):
        """Should be able to load multiple different projects with same repository instance"""
        # Arrange
        repo = ProjectRepository("owner/repo")

        def side_effect(repo_name, branch, path):
            if "project-a" in path:
                if "configuration.yml" in path:
                    return "reviewers:\n  - username: alice"
                elif "spec.md" in path:
                    return "- [ ] Task A"
            elif "project-b" in path:
                if "configuration.yml" in path:
                    return "reviewers:\n  - username: bob"
                elif "spec.md" in path:
                    return "- [ ] Task B1\n- [ ] Task B2"
            return None

        mock_get_file.side_effect = side_effect

        # Act
        result_a = repo.load_project_full("project-a", "main")
        result_b = repo.load_project_full("project-b", "main")

        # Assert
        assert result_a is not None
        project_a, config_a, spec_a = result_a
        assert project_a.name == "project-a"
        assert config_a.reviewers[0].username == "alice"
        assert spec_a.total_tasks == 1

        assert result_b is not None
        project_b, config_b, spec_b = result_b
        assert project_b.name == "project-b"
        assert config_b.reviewers[0].username == "bob"
        assert spec_b.total_tasks == 2
