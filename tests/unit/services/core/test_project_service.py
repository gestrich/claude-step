"""Tests for project detection logic"""

import pytest

from claudechain.services.core.project_service import ProjectService


class TestDetectProjectsFromMerge:
    """Test suite for detect_projects_from_merge functionality"""

    def test_detect_single_project_from_spec_change(self):
        """Should detect a single project when one spec.md is changed"""
        # Arrange
        changed_files = [
            "claude-chain/my-project/spec.md",
            "README.md",
            "src/main.py"
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "my-project"

    def test_detect_multiple_projects_from_spec_changes(self):
        """Should detect multiple projects when multiple spec.md files are changed"""
        # Arrange
        changed_files = [
            "claude-chain/project-a/spec.md",
            "claude-chain/project-b/spec.md",
            "README.md"
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 2
        project_names = [p.name for p in projects]
        assert "project-a" in project_names
        assert "project-b" in project_names

    def test_returns_empty_list_when_no_spec_files_changed(self):
        """Should return empty list when no spec.md files are changed"""
        # Arrange
        changed_files = [
            "src/main.py",
            "README.md",
            "claude-chain/my-project/configuration.yml"  # Not spec.md
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert projects == []

    def test_returns_empty_list_for_empty_file_list(self):
        """Should return empty list when file list is empty"""
        # Arrange
        changed_files = []

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert projects == []

    def test_ignores_spec_files_not_in_claude_chain_directory(self):
        """Should ignore spec.md files outside claude-chain directory"""
        # Arrange
        changed_files = [
            "docs/spec.md",  # Not in claude-chain/
            "other-project/spec.md",  # Not in claude-chain/
            "spec.md"  # Root level
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert projects == []

    def test_ignores_nested_spec_files(self):
        """Should ignore spec.md files nested too deeply"""
        # Arrange
        changed_files = [
            "claude-chain/project/subdir/spec.md",  # Too deep
            "claude-chain/project/docs/spec.md"  # Too deep
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert projects == []

    def test_returns_sorted_projects(self):
        """Should return projects sorted by name"""
        # Arrange
        changed_files = [
            "claude-chain/zebra-project/spec.md",
            "claude-chain/alpha-project/spec.md",
            "claude-chain/middle-project/spec.md"
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 3
        assert projects[0].name == "alpha-project"
        assert projects[1].name == "middle-project"
        assert projects[2].name == "zebra-project"

    def test_handles_project_names_with_hyphens(self):
        """Should correctly extract project names containing hyphens"""
        # Arrange
        changed_files = ["claude-chain/my-complex-project-name/spec.md"]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "my-complex-project-name"

    def test_returns_project_objects_with_correct_paths(self):
        """Should return Project objects with correct path properties"""
        # Arrange
        changed_files = ["claude-chain/test-project/spec.md"]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 1
        project = projects[0]
        assert project.name == "test-project"
        assert project.spec_path == "claude-chain/test-project/spec.md"
        assert project.config_path == "claude-chain/test-project/configuration.yml"
        assert project.base_path == "claude-chain/test-project"

    def test_deduplicates_same_project(self):
        """Should not duplicate projects even if multiple files for same project changed"""
        # Arrange - Same project, spec appears twice (shouldn't happen but test robustness)
        changed_files = [
            "claude-chain/my-project/spec.md",
            "claude-chain/my-project/spec.md"  # Duplicate
        ]

        # Act
        projects = ProjectService.detect_projects_from_merge(changed_files)

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "my-project"
