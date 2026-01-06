"""Integration tests for the prepare command - baseBranch, allowedTools, and merge target validation"""

from unittest.mock import Mock, patch

import pytest

from claudechain.cli.commands.prepare import cmd_prepare
from claudechain.domain.project import Project
from claudechain.domain.project_configuration import ProjectConfiguration
from claudechain.domain.spec_content import SpecContent


class TestPrepareMergeTargetValidation:
    """Test suite for merge target branch validation in prepare command"""

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
    def sample_config_with_develop_branch(self):
        """Fixture providing config with baseBranch set to develop"""
        return ProjectConfiguration(
            project=Project("test-project"),
            assignee="reviewer1",
            base_branch="develop"
        )

    @pytest.fixture
    def sample_config_with_main_branch(self):
        """Fixture providing config without baseBranch override (uses default main)"""
        return ProjectConfiguration(
            project=Project("test-project"),
            assignee="reviewer1",
            base_branch=None
        )

    def test_prepare_skips_when_merge_target_does_not_match_config_base_branch(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_develop_branch, capsys, monkeypatch
    ):
        """Should skip when PR merged into different branch than config specifies"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")  # Default from workflow
        monkeypatch.setenv("MERGE_TARGET_BRANCH", "main")  # PR was merged into main

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService"), \
             patch("claudechain.cli.commands.prepare.TaskService"), \
             patch("claudechain.cli.commands.prepare.AssigneeService"), \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"):

            # Mock ProjectRepository - config says develop, but PR merged into main
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_develop_branch
            mock_repo_class.return_value = mock_repo

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0  # Not an error, just skip

        # Verify skip message was set
        mock_github_helper.set_notice.assert_called_once()
        notice_msg = mock_github_helper.set_notice.call_args[0][0]
        assert "expects base branch 'develop'" in notice_msg
        assert "merged into 'main'" in notice_msg

        # Verify outputs indicate skip
        mock_github_helper.write_output.assert_any_call("has_capacity", "false")
        mock_github_helper.write_output.assert_any_call("has_task", "false")
        mock_github_helper.write_output.assert_any_call("base_branch_mismatch", "true")

        # Verify console output
        captured = capsys.readouterr()
        assert "Skipping" in captured.out
        assert "develop" in captured.out
        assert "main" in captured.out

    def test_prepare_continues_when_merge_target_matches_config_base_branch(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_develop_branch, monkeypatch
    ):
        """Should continue when PR merged into expected branch"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")  # Default from workflow
        monkeypatch.setenv("MERGE_TARGET_BRANCH", "develop")  # PR merged into develop (matches config)

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_develop_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert - should succeed
        assert result == 0

        # Verify no skip notice was set
        mock_github_helper.set_notice.assert_not_called()

        # Verify outputs indicate success
        mock_github_helper.write_output.assert_any_call("has_capacity", "true")
        mock_github_helper.write_output.assert_any_call("has_task", "true")

    def test_prepare_succeeds_when_workflow_dispatch_matches_config(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_develop_branch, monkeypatch
    ):
        """Should succeed when workflow_dispatch base_branch matches config baseBranch"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "develop")  # Matches config baseBranch
        # Note: MERGE_TARGET_BRANCH is NOT set (simulating workflow_dispatch)

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_develop_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert - should succeed (base branch matches config)
        assert result == 0
        mock_github_helper.write_output.assert_any_call("has_capacity", "true")
        mock_github_helper.write_output.assert_any_call("has_task", "true")

    def test_prepare_uses_default_base_branch_for_merge_target_comparison(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_main_branch, capsys, monkeypatch
    ):
        """Should compare merge target against default base branch when config has no override"""
        # Arrange - config has no baseBranch, default is main, PR merged into feature
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")  # Default
        monkeypatch.setenv("MERGE_TARGET_BRANCH", "feature")  # PR merged into feature branch

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService"), \
             patch("claudechain.cli.commands.prepare.TaskService"), \
             patch("claudechain.cli.commands.prepare.AssigneeService"), \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"):

            # Mock ProjectRepository - config has no baseBranch override
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_main_branch
            mock_repo_class.return_value = mock_repo

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert - should skip because feature != main
        assert result == 0

        mock_github_helper.set_notice.assert_called_once()
        notice_msg = mock_github_helper.set_notice.call_args[0][0]
        assert "expects base branch 'main'" in notice_msg
        assert "merged into 'feature'" in notice_msg


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
            assignee="reviewer1",
            base_branch="develop"
        )

    @pytest.fixture
    def sample_config_without_base_branch(self):
        """Fixture providing config without baseBranch"""
        return ProjectConfiguration(
            project=Project("test-project"),
            assignee="reviewer1",
            base_branch=None
        )

    def test_prepare_uses_config_base_branch_when_set(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_base_branch, capsys, monkeypatch
    ):
        """Should use baseBranch from config when it is set (PR merge scenario)"""
        # Arrange - PR merge scenario where config overrides default
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")  # Default from workflow
        # Set MERGE_TARGET_BRANCH to config's baseBranch (simulating PR merged to develop)
        monkeypatch.setenv("MERGE_TARGET_BRANCH", "develop")

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_base_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

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

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_without_base_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0

        # Verify base_branch output uses default (main)
        mock_github_helper.write_output.assert_any_call("base_branch", "main")

        # Verify console output shows default (no override message)
        captured = capsys.readouterr()
        assert "Base branch: main" in captured.out
        assert "overridden" not in captured.out

    def test_prepare_loads_config_and_spec_from_local_filesystem(
        self, mock_github_helper, mock_args, sample_spec, sample_config_without_base_branch, monkeypatch
    ):
        """Should load both config and spec from local filesystem after checkout"""
        # Arrange - use config without baseBranch to avoid validation mismatch
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_without_base_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0

        # Verify load_local_configuration was called (local filesystem loading)
        mock_repo.load_local_configuration.assert_called_once()

        # Verify load_local_spec was called (local filesystem loading)
        mock_repo.load_local_spec.assert_called_once()

    def test_prepare_outputs_base_branch_for_downstream_steps(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_base_branch, monkeypatch
    ):
        """Should output resolved base_branch for use by downstream workflow steps"""
        # Arrange - PR merge scenario
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")
        # Set MERGE_TARGET_BRANCH to match config baseBranch
        monkeypatch.setenv("MERGE_TARGET_BRANCH", "develop")

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_base_branch
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0

        # Verify base_branch is in the outputs
        output_calls = {call[0][0]: call[0][1] for call in mock_github_helper.write_output.call_args_list}
        assert "base_branch" in output_calls
        assert output_calls["base_branch"] == "develop"  # Config override value


class TestPrepareAllowedToolsResolution:
    """Test suite for allowedTools resolution in prepare command"""

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
    def sample_config_with_allowed_tools(self):
        """Fixture providing config with allowedTools override"""
        return ProjectConfiguration(
            project=Project("test-project"),
            assignee="reviewer1",
            allowed_tools="Read,Write,Edit,Bash(npm test:*)"
        )

    @pytest.fixture
    def sample_config_without_allowed_tools(self):
        """Fixture providing config without allowedTools"""
        return ProjectConfiguration(
            project=Project("test-project"),
            assignee="reviewer1",
            allowed_tools=None
        )

    def test_prepare_uses_config_allowed_tools_when_set(
        self, mock_github_helper, mock_args, sample_spec, sample_config_with_allowed_tools, capsys, monkeypatch
    ):
        """Should use allowedTools from config when it is set"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_with_allowed_tools
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act - pass workflow default, but config has override
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0

        # Verify allowed_tools output uses config override
        mock_github_helper.write_output.assert_any_call("allowed_tools", "Read,Write,Edit,Bash(npm test:*)")

        # Verify console output shows override
        captured = capsys.readouterr()
        assert "Allowed tools: Read,Write,Edit,Bash(npm test:*) (overridden from default)" in captured.out

    def test_prepare_uses_default_allowed_tools_when_config_not_set(
        self, mock_github_helper, mock_args, sample_spec, sample_config_without_allowed_tools, capsys, monkeypatch
    ):
        """Should use default allowedTools when config doesn't specify one"""
        # Arrange
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("PROJECT_NAME", "test-project")
        monkeypatch.setenv("BASE_BRANCH", "main")

        with patch("claudechain.cli.commands.prepare.ProjectRepository") as mock_repo_class, \
             patch("claudechain.cli.commands.prepare.PRService") as mock_pr_service_class, \
             patch("claudechain.cli.commands.prepare.TaskService") as mock_task_service_class, \
             patch("claudechain.cli.commands.prepare.AssigneeService") as mock_assignee_service_class, \
             patch("claudechain.cli.commands.prepare.ensure_label_exists"), \
             patch("claudechain.cli.commands.prepare.validate_spec_format_from_string"), \
             patch("claudechain.cli.commands.prepare.run_git_command"):

            # Mock ProjectRepository
            mock_repo = Mock()
            mock_repo.load_local_configuration.return_value = sample_config_without_allowed_tools
            mock_repo.load_local_spec.return_value = sample_spec
            mock_repo_class.return_value = mock_repo

            # Mock PRService
            mock_pr_service = Mock()
            mock_pr_service.format_branch_name.return_value = "claude-chain-test-project-abc123"
            mock_pr_service_class.return_value = mock_pr_service

            # Mock TaskService
            mock_task_service = Mock()
            mock_task_service.detect_orphaned_prs.return_value = []
            mock_task_service.get_in_progress_tasks.return_value = set()
            mock_task_service.find_next_available_task.return_value = (1, "Task 1", "abc123")
            mock_task_service_class.return_value = mock_task_service

            # Mock AssigneeService
            mock_assignee_service = Mock()
            mock_capacity_result = Mock()
            mock_capacity_result.format_summary.return_value = "## Capacity Check\n✅ test-project (0/1)"
            mock_capacity_result.has_capacity = True
            mock_capacity_result.assignee = "reviewer1"
            mock_assignee_service.check_capacity.return_value = mock_capacity_result
            mock_assignee_service_class.return_value = mock_assignee_service

            # Act
            result = cmd_prepare(mock_args, mock_github_helper, default_allowed_tools="Read,Write,Edit")

        # Assert
        assert result == 0

        # Verify allowed_tools output uses default
        mock_github_helper.write_output.assert_any_call("allowed_tools", "Read,Write,Edit")

        # Verify console output shows default (no override message)
        captured = capsys.readouterr()
        assert "Allowed tools: Read,Write,Edit" in captured.out
        assert "overridden" not in captured.out
