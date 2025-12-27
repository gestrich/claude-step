"""Tests for the discover_ready command"""

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch, call

import pytest

from claudestep.cli.commands.discover_ready import check_project_ready, main


class TestCheckProjectReady:
    """Test suite for check_project_ready functionality"""

    def test_check_project_ready_returns_true_when_all_conditions_met(
        self, tmp_path, capsys
    ):
        """Should return True when project has capacity and available tasks"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [x] Task 1\n- [ ] Task 2\n- [ ] Task 3")

        # Mock the dependencies
        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.find_available_reviewer") as mock_reviewer:
                mock_capacity_result = Mock()
                mock_capacity_result.format_summary.return_value = "Capacity info"
                mock_capacity_result.reviewer_status = [
                    {"username": "alice", "openPRs": 1, "maxPRs": 2}
                ]
                mock_reviewer.return_value = ({"username": "alice"}, mock_capacity_result)

                with patch("claudestep.cli.commands.discover_ready.get_in_progress_task_indices") as mock_progress:
                    mock_progress.return_value = set()

                    with patch("claudestep.cli.commands.discover_ready.find_next_available_task") as mock_task:
                        mock_task.return_value = {"index": 2, "description": "Task 2"}

                        # Act
                        result = check_project_ready(project_name, repo)

        # Assert
        assert result is True
        captured = capsys.readouterr()
        assert "✅ Ready for work" in captured.out
        assert "(1/2 PRs, 2 tasks remaining)" in captured.out

    def test_check_project_ready_returns_false_when_no_config(self, tmp_path, capsys):
        """Should return False when configuration file is missing"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(base_dir / "configuration.yml"),  # Doesn't exist
                str(base_dir / "spec.md"),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            # Act
            result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  No configuration file found" in captured.out

    def test_check_project_ready_returns_false_when_no_spec(self, tmp_path, capsys):
        """Should return False when spec.md file is missing"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(base_dir / "spec.md"),  # Doesn't exist
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            # Act
            result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  No spec.md found" in captured.out

    def test_check_project_ready_returns_false_when_no_reviewers(self, tmp_path, capsys):
        """Should return False when no reviewers are configured"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers: []")  # Empty reviewers

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [ ] Task 1")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            # Act
            result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  No reviewers configured" in captured.out

    def test_check_project_ready_returns_false_when_invalid_spec_format(
        self, tmp_path, capsys
    ):
        """Should return False when spec.md has invalid format"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("Invalid content without checkboxes")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.validate_spec_format") as mock_validate:
                mock_validate.side_effect = Exception("Invalid format")

                # Act
                result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  Invalid spec format: Invalid format" in captured.out

    def test_check_project_ready_returns_false_when_no_capacity(self, tmp_path, capsys):
        """Should return False when no reviewer has available capacity"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [ ] Task 1")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.find_available_reviewer") as mock_reviewer:
                mock_reviewer.return_value = (None, None)  # No capacity

                # Act
                result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  No reviewer capacity" in captured.out

    def test_check_project_ready_returns_false_when_no_tasks(self, tmp_path, capsys):
        """Should return False when no available tasks remain"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [x] Task 1\n- [x] Task 2")  # All completed

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.find_available_reviewer") as mock_reviewer:
                mock_capacity_result = Mock()
                mock_capacity_result.reviewer_status = []
                mock_reviewer.return_value = ({"username": "alice"}, mock_capacity_result)

                with patch("claudestep.cli.commands.discover_ready.get_in_progress_task_indices") as mock_progress:
                    mock_progress.return_value = set()

                    with patch("claudestep.cli.commands.discover_ready.find_next_available_task") as mock_task:
                        mock_task.return_value = None  # No tasks

                        # Act
                        result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "⏭️  No available tasks" in captured.out

    def test_check_project_ready_uses_claudestep_label(self, tmp_path):
        """Should use 'claudestep' label for all projects"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 2")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [ ] Task 1")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.find_available_reviewer") as mock_reviewer:
                mock_capacity_result = Mock()
                mock_capacity_result.format_summary.return_value = "Capacity info"
                mock_capacity_result.reviewer_status = [{"username": "alice", "openPRs": 0, "maxPRs": 2}]
                mock_reviewer.return_value = ({"username": "alice"}, mock_capacity_result)

                with patch("claudestep.cli.commands.discover_ready.get_in_progress_task_indices") as mock_progress:
                    mock_progress.return_value = set()

                    with patch("claudestep.cli.commands.discover_ready.find_next_available_task") as mock_task:
                        mock_task.return_value = {"index": 1}

                        # Act
                        check_project_ready(project_name, repo)

                        # Assert
                        mock_reviewer.assert_called_once()
                        _, call_kwargs = mock_reviewer.call_args
                        # Label is second positional arg
                        assert mock_reviewer.call_args[0][1] == "claudestep"

                        mock_progress.assert_called_once()
                        assert mock_progress.call_args[0][1] == "claudestep"

    def test_check_project_ready_handles_unexpected_errors(self, tmp_path, capsys):
        """Should return False and print error message on unexpected exceptions"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.side_effect = Exception("Unexpected error")

            # Act
            result = check_project_ready(project_name, repo)

        # Assert
        assert result is False
        captured = capsys.readouterr()
        assert "❌ Error checking project: Unexpected error" in captured.out

    def test_check_project_ready_counts_remaining_tasks(self, tmp_path, capsys):
        """Should correctly count remaining uncompleted tasks"""
        # Arrange
        project_name = "test-project"
        repo = "owner/repo"

        base_dir = tmp_path / "claude-step" / project_name
        base_dir.mkdir(parents=True)

        config_path = base_dir / "configuration.yml"
        config_path.write_text("reviewers:\n  - username: alice\n    maxOpenPRs: 5")

        spec_path = base_dir / "spec.md"
        spec_path.write_text("- [x] Task 1\n- [ ] Task 2\n- [ ] Task 3\n- [ ] Task 4\n- [x] Task 5")

        with patch("claudestep.cli.commands.discover_ready.detect_project_paths") as mock_paths:
            mock_paths.return_value = (
                str(config_path),
                str(spec_path),
                str(base_dir / "pr_template.md"),
                str(base_dir)
            )

            with patch("claudestep.cli.commands.discover_ready.find_available_reviewer") as mock_reviewer:
                mock_capacity_result = Mock()
                mock_capacity_result.format_summary.return_value = "Capacity info"
                mock_capacity_result.reviewer_status = [
                    {"username": "alice", "openPRs": 2, "maxPRs": 5}
                ]
                mock_reviewer.return_value = ({"username": "alice"}, mock_capacity_result)

                with patch("claudestep.cli.commands.discover_ready.get_in_progress_task_indices") as mock_progress:
                    mock_progress.return_value = set()

                    with patch("claudestep.cli.commands.discover_ready.find_next_available_task") as mock_task:
                        mock_task.return_value = {"index": 2}

                        # Act
                        result = check_project_ready(project_name, repo)

        # Assert
        assert result is True
        captured = capsys.readouterr()
        assert "3 tasks remaining" in captured.out  # 3 unchecked tasks


class TestMain:
    """Test suite for main command function"""

    def test_main_discovers_ready_projects_and_writes_output(self, capsys):
        """Should discover ready projects and write JSON output"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["project-a", "project-b"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        # Only project-a is ready
                        mock_check.side_effect = [True, False]

                        # Act
                        result = main()

        # Assert
        assert result == 0
        mock_gh.write_output.assert_any_call("projects", '["project-a"]')
        mock_gh.write_output.assert_any_call("project_count", "1")

        captured = capsys.readouterr()
        assert "ClaudeStep Discovery Mode" in captured.out
        assert "Finding all projects with capacity and available tasks" in captured.out
        assert "Found 1 project(s) ready for work" in captured.out
        assert "- project-a" in captured.out

    def test_main_handles_no_github_repository_env_var(self, capsys):
        """Should return error when GITHUB_REPOSITORY is not set"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch.dict(os.environ, {}, clear=True):
                # Act
                result = main()

        # Assert
        assert result == 1
        mock_gh.write_output.assert_any_call("projects", "[]")
        mock_gh.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "Error: GITHUB_REPOSITORY environment variable not set" in captured.out

    def test_main_handles_no_projects_found(self, capsys):
        """Should handle case when no projects exist"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = []  # No projects

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    # Act
                    result = main()

        # Assert
        assert result == 0
        mock_gh.write_output.assert_any_call("projects", "[]")
        mock_gh.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "No refactor projects found" in captured.out

    def test_main_handles_no_ready_projects(self, capsys):
        """Should handle case when projects exist but none are ready"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["project-a", "project-b"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        mock_check.return_value = False  # None ready

                        # Act
                        result = main()

        # Assert
        assert result == 0
        mock_gh.write_output.assert_any_call("projects", "[]")
        mock_gh.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "No projects have available capacity and tasks" in captured.out

    def test_main_checks_all_projects(self, capsys):
        """Should check readiness for all discovered projects"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["alpha", "beta", "gamma"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        mock_check.return_value = True

                        # Act
                        main()

                        # Assert
                        assert mock_check.call_count == 3
                        mock_check.assert_any_call("alpha", "owner/repo")
                        mock_check.assert_any_call("beta", "owner/repo")
                        mock_check.assert_any_call("gamma", "owner/repo")

    def test_main_outputs_valid_json_array(self):
        """Should output valid JSON array format"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["project-x", "project-y"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        mock_check.return_value = True

                        # Act
                        main()

        # Assert
        call_args = mock_gh.write_output.call_args_list
        projects_output = next(
            call[0][1] for call in call_args if call[0][0] == "projects"
        )
        parsed = json.loads(projects_output)
        assert parsed == ["project-x", "project-y"]

    def test_main_prints_checking_each_project(self, capsys):
        """Should print status message for each project being checked"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["my-project"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        mock_check.return_value = False

                        # Act
                        main()

        # Assert
        captured = capsys.readouterr()
        assert "Checking project: my-project" in captured.out

    def test_main_outputs_correct_project_count(self):
        """Should output correct count of ready projects"""
        # Arrange
        with patch("claudestep.cli.commands.discover_ready.GitHubActionsHelper") as mock_gh_class:
            mock_gh = Mock()
            mock_gh_class.return_value = mock_gh

            with patch("claudestep.cli.commands.discover_ready.find_all_projects") as mock_find:
                mock_find.return_value = ["a", "b", "c", "d", "e"]

                with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}):
                    with patch("claudestep.cli.commands.discover_ready.check_project_ready") as mock_check:
                        # 3 out of 5 are ready
                        mock_check.side_effect = [True, False, True, True, False]

                        # Act
                        main()

        # Assert
        mock_gh.write_output.assert_any_call("project_count", "3")
