"""Tests for the discover command"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from claudechain.cli.commands.discover import find_all_projects, main


class TestFindAllProjects:
    """Test suite for find_all_projects functionality"""

    def test_find_projects_returns_projects_with_spec(self, tmp_path):
        """Should return projects that have spec.md files"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create valid projects with spec.md
        project1 = base_dir / "project1"
        project1.mkdir()
        (project1 / "spec.md").write_text("- [ ] Task 1")

        project2 = base_dir / "project2"
        project2.mkdir()
        (project2 / "spec.md").write_text("- [ ] Task 1")

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert len(result) == 2
        assert "project1" in result
        assert "project2" in result

    def test_find_projects_excludes_dirs_without_spec(self, tmp_path):
        """Should exclude directories that don't have spec.md"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Valid project with spec.md
        valid_project = base_dir / "valid-project"
        valid_project.mkdir()
        (valid_project / "spec.md").write_text("- [ ] Task 1")

        # Invalid project - missing spec.md
        invalid_project = base_dir / "invalid-project"
        invalid_project.mkdir()

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert len(result) == 1
        assert "valid-project" in result
        assert "invalid-project" not in result

    def test_find_projects_excludes_files_in_base_dir(self, tmp_path):
        """Should exclude files in base directory, only process directories"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create a file (not a directory)
        (base_dir / "README.md").write_text("readme content")

        # Create valid project with spec.md
        project = base_dir / "project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert len(result) == 1
        assert "project" in result

    def test_find_projects_returns_sorted_list(self, tmp_path):
        """Should return projects in alphabetical order"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Create projects in reverse alphabetical order
        for name in ["zebra", "alpha", "beta"]:
            project = base_dir / name
            project.mkdir()
            (project / "spec.md").write_text("- [ ] Task 1")

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert result == ["alpha", "beta", "zebra"]

    def test_find_projects_returns_empty_when_base_dir_missing(self, tmp_path, capsys):
        """Should return empty list when base directory doesn't exist"""
        # Arrange
        base_dir = tmp_path / "nonexistent"

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert result == []
        captured = capsys.readouterr()
        assert "not found" in captured.out

    def test_find_projects_returns_empty_when_no_projects(self, tmp_path):
        """Should return empty list when base directory has no projects"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert result == []

    def test_find_projects_uses_default_base_dir(self, tmp_path, monkeypatch):
        """Should use 'claude-chain' as default base directory"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        project = base_dir / "test-project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        # Act (no base_dir argument)
        result = find_all_projects()

        # Assert
        assert "test-project" in result

    def test_find_projects_uses_env_var_for_base_dir(self, tmp_path, monkeypatch):
        """Should use CLAUDECHAIN_PROJECT_DIR environment variable when set"""
        # Arrange
        custom_dir = tmp_path / "custom-projects"
        custom_dir.mkdir()

        project = custom_dir / "test-project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        monkeypatch.setenv("CLAUDECHAIN_PROJECT_DIR", str(custom_dir))

        # Act (no base_dir argument)
        result = find_all_projects()

        # Assert
        assert "test-project" in result

    def test_find_projects_explicit_arg_overrides_env_var(self, tmp_path, monkeypatch):
        """Should use explicit base_dir argument over environment variable"""
        # Arrange
        env_dir = tmp_path / "env-dir"
        env_dir.mkdir()

        arg_dir = tmp_path / "arg-dir"
        arg_dir.mkdir()

        project = arg_dir / "test-project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        monkeypatch.setenv("CLAUDECHAIN_PROJECT_DIR", str(env_dir))

        # Act (explicit base_dir argument)
        result = find_all_projects(str(arg_dir))

        # Assert
        assert "test-project" in result

    def test_find_projects_handles_nested_files(self, tmp_path):
        """Should only check for spec.md in immediate subdirectories"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Valid project at top level
        project = base_dir / "project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        # Nested directory with spec should not be found
        nested = project / "nested"
        nested.mkdir()
        (nested / "spec.md").write_text("- [ ] Task 1")

        # Act
        result = find_all_projects(str(base_dir))

        # Assert
        assert len(result) == 1
        assert "project" in result

    def test_find_projects_prints_found_projects(self, tmp_path, capsys):
        """Should print each project as it's found"""
        # Arrange
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        project = base_dir / "test-project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        # Act
        find_all_projects(str(base_dir))

        # Assert
        captured = capsys.readouterr()
        assert "Found project: test-project" in captured.out


class TestMain:
    """Test suite for main command function"""

    def test_main_discovers_projects_and_writes_output(self, tmp_path, monkeypatch, capsys):
        """Should discover projects and write JSON output to GitHub Actions"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        project1 = base_dir / "alpha"
        project1.mkdir()
        (project1 / "spec.md").write_text("- [ ] Task 1")

        project2 = base_dir / "beta"
        project2.mkdir()
        (project2 / "spec.md").write_text("- [ ] Task 1")

        # Mock GitHubActionsHelper
        with patch("claudechain.cli.commands.discover.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            # Act
            main()

            # Assert
            mock_gh.write_output.assert_any_call("projects", '["alpha", "beta"]')
            mock_gh.write_output.assert_any_call("project_count", "2")

        captured = capsys.readouterr()
        assert "Discovering refactor projects" in captured.out
        assert "Found 2 project(s)" in captured.out
        assert "alpha" in captured.out
        assert "beta" in captured.out

    def test_main_handles_no_projects_found(self, tmp_path, monkeypatch, capsys):
        """Should handle case when no projects are found"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        # Mock GitHubActionsHelper
        with patch("claudechain.cli.commands.discover.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            # Act
            main()

            # Assert
            mock_gh.write_output.assert_any_call("projects", "[]")
            mock_gh.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "No projects found" in captured.out
        assert 'Projects JSON: []' in captured.out

    def test_main_outputs_valid_json_array(self, tmp_path, monkeypatch):
        """Should output valid JSON array format"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        project = base_dir / "test-project"
        project.mkdir()
        (project / "spec.md").write_text("- [ ] Task 1")

        # Mock GitHubActionsHelper
        with patch("claudechain.cli.commands.discover.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            # Act
            main()

            # Assert
            # Verify the JSON output is valid
            call_args = mock_gh.write_output.call_args_list
            projects_output = next(
                call[0][1] for call in call_args if call[0][0] == "projects"
            )
            parsed = json.loads(projects_output)
            assert parsed == ["test-project"]

    def test_main_prints_project_list(self, tmp_path, monkeypatch, capsys):
        """Should print list of discovered projects"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        for name in ["project-a", "project-b"]:
            project = base_dir / name
            project.mkdir()
            (project / "spec.md").write_text("- [ ] Task 1")

        # Mock GitHubActionsHelper
        with patch("claudechain.cli.commands.discover.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            # Act
            main()

        # Assert
        captured = capsys.readouterr()
        assert "- project-a" in captured.out
        assert "- project-b" in captured.out

    def test_main_outputs_project_count(self, tmp_path, monkeypatch):
        """Should output correct project count"""
        # Arrange
        monkeypatch.chdir(tmp_path)
        base_dir = tmp_path / "claude-chain"
        base_dir.mkdir()

        for i in range(3):
            project = base_dir / f"project{i}"
            project.mkdir()
            (project / "spec.md").write_text("- [ ] Task 1")

        # Mock GitHubActionsHelper
        with patch("claudechain.cli.commands.discover.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            # Act
            main()

            # Assert
            mock_gh.write_output.assert_any_call("project_count", "3")
