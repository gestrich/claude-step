"""Unit tests for Project domain model"""

import os
import pytest
from pathlib import Path

from claudechain.domain.project import Project


class TestProjectInitialization:
    """Test suite for Project initialization"""

    def test_create_project_with_default_base_path(self):
        """Should create project with default base path"""
        # Arrange & Act
        project = Project("my-project")

        # Assert
        assert project.name == "my-project"
        assert project.base_path == "claude-chain/my-project"

    def test_create_project_with_custom_base_path(self):
        """Should create project with custom base path"""
        # Arrange & Act
        project = Project("my-project", base_path="custom/path/my-project")

        # Assert
        assert project.name == "my-project"
        assert project.base_path == "custom/path/my-project"


class TestProjectPathProperties:
    """Test suite for Project path properties"""

    def test_config_path_property(self):
        """Should return correct config path"""
        # Arrange
        project = Project("my-project")

        # Act
        config_path = project.config_path

        # Assert
        assert config_path == "claude-chain/my-project/configuration.yml"

    def test_spec_path_property(self):
        """Should return correct spec path"""
        # Arrange
        project = Project("my-project")

        # Act
        spec_path = project.spec_path

        # Assert
        assert spec_path == "claude-chain/my-project/spec.md"

    def test_pr_template_path_property(self):
        """Should return correct PR template path"""
        # Arrange
        project = Project("my-project")

        # Act
        pr_template_path = project.pr_template_path

        # Assert
        assert pr_template_path == "claude-chain/my-project/pr-template.md"

    def test_metadata_file_path_property(self):
        """Should return correct metadata file path"""
        # Arrange
        project = Project("my-project")

        # Act
        metadata_path = project.metadata_file_path

        # Assert
        assert metadata_path == "my-project.json"

    def test_paths_with_custom_base_path(self):
        """Should construct correct paths with custom base path"""
        # Arrange
        project = Project("my-project", base_path="custom/path/my-project")

        # Assert
        assert project.config_path == "custom/path/my-project/configuration.yml"
        assert project.spec_path == "custom/path/my-project/spec.md"
        assert project.pr_template_path == "custom/path/my-project/pr-template.md"
        # metadata_file_path should still be just the project name
        assert project.metadata_file_path == "my-project.json"


class TestProjectFromConfigPath:
    """Test suite for Project.from_config_path factory method"""

    def test_from_config_path_standard_format(self):
        """Should extract project name from standard config path"""
        # Arrange
        config_path = "claude-chain/my-project/configuration.yml"

        # Act
        project = Project.from_config_path(config_path)

        # Assert
        assert project.name == "my-project"
        assert project.base_path == "claude-chain/my-project"

    def test_from_config_path_with_different_base_dir(self):
        """Should extract project name from config path with different base directory"""
        # Arrange
        config_path = "custom/my-project/configuration.yml"

        # Act
        project = Project.from_config_path(config_path)

        # Assert
        assert project.name == "my-project"
        # Note: from_config_path uses default base_path construction
        assert project.base_path == "claude-chain/my-project"

    def test_from_config_path_with_nested_directories(self):
        """Should extract project name from deeply nested config path"""
        # Arrange
        config_path = "deeply/nested/my-project/configuration.yml"

        # Act
        project = Project.from_config_path(config_path)

        # Assert
        assert project.name == "my-project"


class TestProjectFromBranchName:
    """Test suite for Project.from_branch_name factory method"""

    def test_from_branch_name_valid_hash_based_branch(self):
        """Should extract project from valid hash-based branch name"""
        # Arrange
        branch_name = "claude-chain-my-project-a1b2c3d4"

        # Act
        project = Project.from_branch_name(branch_name)

        # Assert
        assert project is not None
        assert project.name == "my-project"
        assert project.base_path == "claude-chain/my-project"

    def test_from_branch_name_with_hyphenated_project_name(self):
        """Should extract project with hyphens from hash-based branch name"""
        # Arrange
        branch_name = "claude-chain-my-complex-project-name-12345678"

        # Act
        project = Project.from_branch_name(branch_name)

        # Assert
        assert project is not None
        assert project.name == "my-complex-project-name"

    def test_from_branch_name_invalid_format_returns_none(self):
        """Should return None for invalid branch name format"""
        # Arrange
        invalid_branches = [
            "invalid-branch-name",
            "claude-chain-project",  # Missing hash
            "claude-chain-abc",  # Missing project name
            "main",
            "feature/something",
            "claude-chain-project-5",  # Index instead of hash
            "claude-chain-project-123",  # Index instead of hash
            "claude-chain-project-abcdefg",  # Hash too short (7 chars)
            "claude-chain-project-abcdefghi",  # Hash too long (9 chars)
            "claude-chain-project-ABCDEF12",  # Uppercase not allowed
            "claude-chain-project-xyz12345",  # Invalid hex chars (x, y, z)
        ]

        # Act & Assert
        for branch_name in invalid_branches:
            project = Project.from_branch_name(branch_name)
            assert project is None, f"Should return None for: {branch_name}"

    def test_from_branch_name_various_hex_hashes(self):
        """Should extract project from branch with various valid hex hashes"""
        # Arrange - Test multiple valid 8-char hex hashes
        test_cases = [
            ("claude-chain-my-project-00000000", "my-project"),
            ("claude-chain-my-project-ffffffff", "my-project"),
            ("claude-chain-my-project-12abcdef", "my-project"),
            ("claude-chain-other-proj-a1b2c3d4", "other-proj"),
        ]

        # Act & Assert
        for branch_name, expected_name in test_cases:
            project = Project.from_branch_name(branch_name)
            assert project is not None, f"Should parse: {branch_name}"
            assert project.name == expected_name


class TestProjectFindAll:
    """Test suite for Project.find_all factory method"""

    def test_find_all_discovers_multiple_projects(self, tmp_path):
        """Should discover all valid projects in directory"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create valid projects (projects are discovered by spec.md)
        for project_name in ["project-a", "project-b", "project-c"]:
            project_dir = base_dir / project_name
            project_dir.mkdir()
            (project_dir / "spec.md").write_text("- [ ] Task 1")

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 3
        project_names = [p.name for p in projects]
        assert "project-a" in project_names
        assert "project-b" in project_names
        assert "project-c" in project_names

    def test_find_all_returns_sorted_projects(self, tmp_path):
        """Should return projects sorted by name"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create projects in non-alphabetical order
        for project_name in ["zebra", "alpha", "middle"]:
            project_dir = base_dir / project_name
            project_dir.mkdir()
            (project_dir / "spec.md").write_text("- [ ] Task 1")

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 3
        assert [p.name for p in projects] == ["alpha", "middle", "zebra"]

    def test_find_all_ignores_directories_without_spec(self, tmp_path):
        """Should ignore directories without spec.md"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Valid project (has spec.md)
        valid_project = base_dir / "valid-project"
        valid_project.mkdir()
        (valid_project / "spec.md").write_text("- [ ] Task 1")

        # Invalid projects (no spec.md file)
        (base_dir / "invalid-project-1").mkdir()
        (base_dir / "invalid-project-2").mkdir()

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "valid-project"

    def test_find_all_discovers_projects_without_config(self, tmp_path):
        """Should discover projects that have spec.md but no configuration.yml"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Project with spec.md only (no configuration.yml)
        project_dir = base_dir / "spec-only-project"
        project_dir.mkdir()
        (project_dir / "spec.md").write_text("- [ ] Task 1")

        # Project with both spec.md and configuration.yml
        full_project_dir = base_dir / "full-project"
        full_project_dir.mkdir()
        (full_project_dir / "spec.md").write_text("- [ ] Task 1")
        (full_project_dir / "configuration.yml").write_text("reviewers: []")

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 2
        project_names = [p.name for p in projects]
        assert "spec-only-project" in project_names
        assert "full-project" in project_names

    def test_find_all_ignores_directories_with_only_config(self, tmp_path):
        """Should ignore directories that have configuration.yml but no spec.md"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Directory with only configuration.yml (not a valid project)
        config_only_dir = base_dir / "config-only"
        config_only_dir.mkdir()
        (config_only_dir / "configuration.yml").write_text("reviewers: []")

        # Valid project with spec.md
        valid_project = base_dir / "valid-project"
        valid_project.mkdir()
        (valid_project / "spec.md").write_text("- [ ] Task 1")

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "valid-project"

    def test_find_all_ignores_files_in_base_dir(self, tmp_path):
        """Should ignore files (not directories) in base directory"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create a valid project
        project_dir = base_dir / "my-project"
        project_dir.mkdir()
        (project_dir / "spec.md").write_text("- [ ] Task 1")

        # Create some files that should be ignored
        (base_dir / "README.md").write_text("# Readme")
        (base_dir / "some-file.txt").write_text("content")

        # Act
        projects = Project.find_all(str(base_dir))

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "my-project"

    def test_find_all_returns_empty_list_when_directory_not_exists(self, tmp_path):
        """Should return empty list when base directory doesn't exist"""
        # Arrange
        non_existent_dir = tmp_path / "non-existent"

        # Act
        projects = Project.find_all(str(non_existent_dir))

        # Assert
        assert projects == []

    def test_find_all_with_custom_base_dir(self, tmp_path):
        """Should discover projects in custom base directory"""
        # Arrange
        custom_dir = tmp_path / "custom-projects"
        custom_dir.mkdir()

        project_dir = custom_dir / "my-project"
        project_dir.mkdir()
        (project_dir / "spec.md").write_text("- [ ] Task 1")

        # Act
        projects = Project.find_all(str(custom_dir))

        # Assert
        assert len(projects) == 1
        assert projects[0].name == "my-project"


class TestProjectEquality:
    """Test suite for Project equality and hashing"""

    def test_equality_same_name_and_base_path(self):
        """Should be equal when name and base_path match"""
        # Arrange
        project1 = Project("my-project")
        project2 = Project("my-project")

        # Act & Assert
        assert project1 == project2

    def test_equality_different_names(self):
        """Should not be equal when names differ"""
        # Arrange
        project1 = Project("project-a")
        project2 = Project("project-b")

        # Act & Assert
        assert project1 != project2

    def test_equality_different_base_paths(self):
        """Should not be equal when base paths differ"""
        # Arrange
        project1 = Project("my-project", base_path="claude-chain/my-project")
        project2 = Project("my-project", base_path="custom/my-project")

        # Act & Assert
        assert project1 != project2

    def test_equality_with_non_project_object(self):
        """Should not be equal to non-Project objects"""
        # Arrange
        project = Project("my-project")

        # Act & Assert
        assert project != "my-project"
        assert project != 123
        assert project != None
        assert project != {"name": "my-project"}

    def test_hash_same_for_equal_projects(self):
        """Should have same hash for equal projects"""
        # Arrange
        project1 = Project("my-project")
        project2 = Project("my-project")

        # Act & Assert
        assert hash(project1) == hash(project2)

    def test_hash_different_for_different_projects(self):
        """Should have different hash for different projects"""
        # Arrange
        project1 = Project("project-a")
        project2 = Project("project-b")

        # Act & Assert
        assert hash(project1) != hash(project2)

    def test_can_use_in_set(self):
        """Should be usable in sets"""
        # Arrange
        project1 = Project("project-a")
        project2 = Project("project-b")
        project3 = Project("project-a")  # Duplicate of project1

        # Act
        project_set = {project1, project2, project3}

        # Assert
        assert len(project_set) == 2  # Only unique projects
        assert project1 in project_set
        assert project2 in project_set

    def test_can_use_as_dict_key(self):
        """Should be usable as dictionary keys"""
        # Arrange
        project1 = Project("project-a")
        project2 = Project("project-b")

        # Act
        project_dict = {
            project1: "data-a",
            project2: "data-b"
        }

        # Assert
        assert project_dict[project1] == "data-a"
        assert project_dict[project2] == "data-b"


class TestProjectRepr:
    """Test suite for Project string representation"""

    def test_repr_contains_name_and_base_path(self):
        """Should have readable string representation"""
        # Arrange
        project = Project("my-project")

        # Act
        repr_str = repr(project)

        # Assert
        assert "Project" in repr_str
        assert "my-project" in repr_str
        assert "claude-chain/my-project" in repr_str

    def test_repr_with_custom_base_path(self):
        """Should include custom base path in representation"""
        # Arrange
        project = Project("my-project", base_path="custom/path")

        # Act
        repr_str = repr(project)

        # Assert
        assert "my-project" in repr_str
        assert "custom/path" in repr_str
