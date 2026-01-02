"""Integration tests for the prepare command - baseBranch configuration"""

from unittest.mock import Mock, patch

import pytest

from claudestep.cli.commands.prepare import cmd_prepare
from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration, Reviewer
from claudestep.domain.spec_content import SpecContent


class TestPrepareBaseBranchResolution:
    """Test suite for baseBranch resolution in prepare command"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.write_step_summary = Mock()
        mock.set_error = Mock()
        mock.set_notice = Mock()
        return mock

    @pytest.fixture
    def mock_args(self):
        """Fixture providing mocked argparse.Namespace"""
        return Mock()

    @pytest.fixture
    def sample_spec(self):
        """Fixture providing sample spec content"""
        return SpecContent(
            project=Project("test-project"),
            content="""# Test Spec

## Tasks
- [ ] Task 1
- [ ] Task 2
"""
        )

    @pytest.fixture
    def sample_config_with_base_branch(self):
        """Fixture providing config with baseBranch override"""
        return ProjectConfiguration(
            project=Project("test-project"),
            reviewers=[Reviewer(username="reviewer1", max_open_prs=3)],
            base_branch="develop"
        )

    @pytest.fixture
    def sample_config_without_base_branch(self):
        """Fixture providing config without baseBranch"""
        return ProjectConfiguration(
            project=Project("test-project"),
            reviewers=[Reviewer(username="reviewer1", max_open_prs=3)],
            base_branch=None
        )

    def test_prepare_uses_config_base_branch_when_set(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_base_branch, capsys, monkeypatch
    ):
        """Should use baseBranch from config when it is set"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")  # Default from workflow

        with patch("claudestep.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudestep.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudestep.cli.commands.prepare.ProjectService"), \
             patch("claudestep.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudestep.cli.commands.prepare.ReviewerService") as mock_reviewer_service_class, \
             patch("claudestep.cli.commands.prepare.file_exists_in_branch") as mock_file_exists, \
             patch("claudestep.cli.commands.prepare.ensure_label_exists"), \
             patch("claudestep.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudestep.cli.commands.prepare.run_git_command"):

            # Mock file existence checks
            mock_file_exists.return_value = True

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_configuration.return_value = sample_config_with_base_branch
            mock_repo.load_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-step-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock ReviewerService
            mock_reviewer_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Reviewer Capacity Check\n✅ reviewer1 (0/3)"
            mock_capacity_result.all_at_capacity = False  # Has capacity
            mock_reviewer_service.find_available_reviewer.return_value = ("reviewer1", mock_capacity_result)
            mock_reviewer_service_class.return_value = mock_reviewer_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper)

        # Assert
        assert result == 0

        # Verify base_branch output uses config override (develop, not main)
        mock_github_helper.write_output.assert_any_call("base_branch", "develop")

        # Verify console output shows override
        captured = capsys.readouterr()
        assert "Base branch: develop (overridden from default: main)" in captured.out

    def test_prepare_uses_default_base_branch_when_config_not_set(
        self, mock_github_helper, mock_args, sample_spec, sample_config_without_base_branch, capsys, monkeypatch
    ):
        """Should use default baseBranch when config doesn't specify one"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudestep.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudestep.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudestep.cli.commands.prepare.ProjectService"), \
             patch("claudestep.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudestep.cli.commands.prepare.ReviewerService") as mock_reviewer_service_class, \
             patch("claudestep.cli.commands.prepare.file_exists_in_branch") as mock_file_exists, \
             patch("claudestep.cli.commands.prepare.ensure_label_exists"), \
             patch("claudestep.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudestep.cli.commands.prepare.run_git_command"):

            # Mock file existence checks
            mock_file_exists.return_value = True

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_configuration.return_value = sample_config_without_base_branch
            mock_repo.load_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-step-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock ReviewerService
            mock_reviewer_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Reviewer Capacity Check\n✅ reviewer1 (0/3)"
            mock_capacity_result.all_at_capacity = False  # Has capacity
            mock_reviewer_service.find_available_reviewer.return_value = ("reviewer1", mock_capacity_result)
            mock_reviewer_service_class.return_value = mock_reviewer_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper)

        # Assert
        assert result == 0

        # Verify base_branch output uses default (main)
        mock_github_helper.write_output.assert_any_call("base_branch", "main")

        # Verify console output shows default (no override message)
        captured = capsys.readouterr()
        assert "Base branch: main" in captured.out
        assert "overridden" not in captured.out

    def test_prepare_uses_default_branch_to_load_config_files(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_base_branch, monkeypatch
    ):
        """Should use default base branch to locate and load config files"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudestep.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudestep.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudestep.cli.commands.prepare.ProjectService"), \
             patch("claudestep.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudestep.cli.commands.prepare.ReviewerService") as mock_reviewer_service_class, \
             patch("claudestep.cli.commands.prepare.file_exists_in_branch") as mock_file_exists, \
             patch("claudestep.cli.commands.prepare.ensure_label_exists"), \
             patch("claudestep.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudestep.cli.commands.prepare.run_git_command"):

            # Mock file existence checks
            mock_file_exists.return_value = True

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_configuration.return_value = sample_config_with_base_branch
            mock_repo.load_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-step-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock ReviewerService
            mock_reviewer_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Reviewer Capacity Check\n✅ reviewer1 (0/3)"
            mock_capacity_result.all_at_capacity = False  # Has capacity
            mock_reviewer_service.find_available_reviewer.return_value = ("reviewer1", mock_capacity_result)
            mock_reviewer_service_class.return_value = mock_reviewer_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper)

        # Assert
        assert result == 0

        # Verify file_exists_in_branch was called with default branch (main), not config branch (develop)
        file_exists_calls = mock_file_exists.call_args_list
        for call in file_exists_calls:
            branch_arg = call[0][1]  # Second positional arg is branch
            assert branch_arg == "main", f"Expected 'main' but got '{branch_arg}'"

        # Verify load_configuration was called with default branch
        mock_repo.load_configuration.assert_called_once()
        config_call = mock_repo.load_configuration.call_args
        assert config_call[0][1] == "main"

        # Verify load_spec was called with default branch
        mock_repo.load_spec.assert_called_once()
        spec_call = mock_repo.load_spec.call_args
        assert spec_call[0][1] == "main"

    def test_prepare_outputs_base_branch_for_downstream_steps(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_base_branch, monkeypatch
    ):
        """Should output resolved base_branch for use by downstream workflow steps"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudestep.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudestep.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudestep.cli.commands.prepare.ProjectService"), \
             patch("claudestep.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudestep.cli.commands.prepare.ReviewerService") as mock_reviewer_service_class, \
             patch("claudestep.cli.commands.prepare.file_exists_in_branch") as mock_file_exists, \
             patch("claudestep.cli.commands.prepare.ensure_label_exists"), \
             patch("claudestep.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudestep.cli.commands.prepare.run_git_command"):

            # Mock file existence checks
            mock_file_exists.return_value = True

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_configuration.return_value = sample_config_with_base_branch
            mock_repo.load_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-step-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock ReviewerService
            mock_reviewer_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Reviewer Capacity Check\n✅ reviewer1 (0/3)"
            mock_capacity_result.all_at_capacity = False  # Has capacity
            mock_reviewer_service.find_available_reviewer.return_value = ("reviewer1", mock_capacity_result)
            mock_reviewer_service_class.return_value = mock_reviewer_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper)

        # Assert
        assert result == 0

        # Verify base_branch is in the outputs
        output_calls = {call[0][0]: call[0][1] for call in mock_github_helper.write_output.call_args_list}
        assert "base_branch" in output_calls
        assert output_calls["base_branch"] == "develop"  # Config override value
