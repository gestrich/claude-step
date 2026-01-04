"""Integration tests for the auto-start command"""

from unittest.mock import Mock, patch, call

import pytest

from claudechain.cli.commands.auto_start import cmd_auto_start, cmd_auto_start_summary
from claudechain.domain.auto_start import AutoStartProject, ProjectChangeType


class TestCmdAutoStart:
    """Test suite for cmd_auto_start functionality"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_output = Mock()
        mock.write_step_summary = Mock()
        mock.set_error = Mock()
        return mock

    @pytest.fixture
    def sample_changed_projects(self):
        """Fixture providing sample changed projects"""
        return [
            AutoStartProject("project-a", ProjectChangeType.ADDED, "claude-chain/project-a/spec.md"),
            AutoStartProject("project-b", ProjectChangeType.MODIFIED, "claude-chain/project-b/spec.md"),
        ]

    @pytest.fixture
    def sample_deleted_project(self):
        """Fixture providing sample deleted project"""
        return [
            AutoStartProject("project-deleted", ProjectChangeType.DELETED, "claude-chain/project-deleted/spec.md"),
        ]

    def test_cmd_auto_start_detects_and_triggers_new_projects(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should detect new projects and trigger workflows successfully"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.WorkflowService"
        ) as mock_workflow_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            # Mock AutoStartService
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = [sample_changed_projects[0]]

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                project=sample_changed_projects[0],
                should_trigger=True,
                reason="New project detected"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Mock WorkflowService
            mock_workflow_service = Mock()
            mock_workflow_service.batch_trigger_claudechain_workflows.return_value = (
                ["project-a"],  # triggered
                []  # failed
            )
            mock_workflow_service_class.return_value = mock_workflow_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0

        # Verify service calls
        mock_auto_start_service.detect_changed_projects.assert_called_once_with(
            ref_before="abc123",
            ref_after="def456",
            spec_pattern="claude-chain/*/spec.md"
        )
        mock_auto_start_service.determine_new_projects.assert_called_once()
        mock_auto_start_service.should_auto_trigger.assert_called_once()

        # Verify workflow triggering
        mock_workflow_service.batch_trigger_claudechain_workflows.assert_called_once_with(
            projects=["project-a"],
            base_branch="main",
            checkout_ref="def456"
        )

        # Verify outputs
        mock_github_helper.write_output.assert_any_call("triggered_projects", "project-a")
        mock_github_helper.write_output.assert_any_call("trigger_count", "1")
        mock_github_helper.write_output.assert_any_call("failed_projects", "")
        mock_github_helper.write_output.assert_any_call("projects_to_trigger", "project-a")
        mock_github_helper.write_output.assert_any_call("project_count", "1")

        # Verify console output
        captured = capsys.readouterr()
        assert "ClaudeChain Auto-Start Detection" in captured.out
        assert "Successfully triggered: 1 project(s)" in captured.out

    def test_cmd_auto_start_handles_no_changes(
        self, mock_github_helper, capsys
    ):
        """Should handle case when no spec.md changes are detected"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = []
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0
        mock_github_helper.write_output.assert_any_call("projects_to_trigger", "")
        mock_github_helper.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "No spec.md changes detected" in captured.out

    def test_cmd_auto_start_handles_existing_projects(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should handle case when all changed projects already have PRs"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = []  # All have existing PRs
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0
        mock_github_helper.write_output.assert_any_call("projects_to_trigger", "")
        mock_github_helper.write_output.assert_any_call("project_count", "0")

        captured = capsys.readouterr()
        assert "No new projects to trigger" in captured.out

    def test_cmd_auto_start_handles_deleted_projects(
        self, mock_github_helper, sample_deleted_project, capsys
    ):
        """Should skip deleted projects based on business logic"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_deleted_project
            mock_auto_start_service.determine_new_projects.return_value = sample_deleted_project

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                project=sample_deleted_project[0],
                should_trigger=False,
                reason="Project was deleted"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0

        # Verify no workflows were triggered (no WorkflowService instantiated)
        mock_github_helper.write_output.assert_any_call("triggered_projects", "")
        mock_github_helper.write_output.assert_any_call("trigger_count", "0")

        captured = capsys.readouterr()
        assert "SKIP - Project was deleted" in captured.out

    def test_cmd_auto_start_handles_partial_trigger_failure(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should handle partial failures when some workflows fail to trigger"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.WorkflowService"
        ) as mock_workflow_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            # Mock AutoStartService
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = sample_changed_projects

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.side_effect = [
                AutoStartDecision(sample_changed_projects[0], True, "New project"),
                AutoStartDecision(sample_changed_projects[1], True, "New project"),
            ]
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Mock WorkflowService with partial failure
            mock_workflow_service = Mock()
            mock_workflow_service.batch_trigger_claudechain_workflows.return_value = (
                ["project-a"],  # triggered
                ["project-b"]   # failed
            )
            mock_workflow_service_class.return_value = mock_workflow_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0

        # Verify outputs include both success and failure
        mock_github_helper.write_output.assert_any_call("triggered_projects", "project-a")
        mock_github_helper.write_output.assert_any_call("trigger_count", "1")
        mock_github_helper.write_output.assert_any_call("failed_projects", "project-b")

        captured = capsys.readouterr()
        assert "Successfully triggered: 1 project(s)" in captured.out
        assert "Failed triggers: 1 project(s)" in captured.out

    def test_cmd_auto_start_handles_all_trigger_failures(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should handle case when all workflow triggers fail"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.WorkflowService"
        ) as mock_workflow_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            # Mock AutoStartService
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = [sample_changed_projects[0]]

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                sample_changed_projects[0], True, "New project"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Mock WorkflowService with all failures
            mock_workflow_service = Mock()
            mock_workflow_service.batch_trigger_claudechain_workflows.return_value = (
                [],  # triggered
                ["project-a"]  # failed
            )
            mock_workflow_service_class.return_value = mock_workflow_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0

        # Verify outputs
        mock_github_helper.write_output.assert_any_call("triggered_projects", "")
        mock_github_helper.write_output.assert_any_call("trigger_count", "0")
        mock_github_helper.write_output.assert_any_call("failed_projects", "project-a")

        captured = capsys.readouterr()
        assert "Auto-start failed - all triggers failed" in captured.out

    def test_cmd_auto_start_handles_exception(
        self, mock_github_helper, capsys
    ):
        """Should handle exceptions and return error code"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.side_effect = Exception("Test error")
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_call = mock_github_helper.set_error.call_args[0][0]
        assert "Auto-start detection failed" in error_call
        assert "Test error" in error_call

    def test_cmd_auto_start_respects_disabled_configuration(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should skip all projects when auto-start is disabled"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = [sample_changed_projects[0]]

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                sample_changed_projects[0],
                should_trigger=False,
                reason="Auto-start is disabled via configuration"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456",
                auto_start_enabled=False
            )

        # Assert
        assert result == 0

        # Verify auto_start_enabled was passed to service
        mock_auto_start_service_class.assert_called_once()
        call_args = mock_auto_start_service_class.call_args
        # Check positional argument (third parameter is auto_start_enabled)
        assert call_args[0][2] is False

        captured = capsys.readouterr()
        assert "SKIP - Auto-start is disabled via configuration" in captured.out

    def test_cmd_auto_start_prints_progress_information(
        self, mock_github_helper, sample_changed_projects, capsys
    ):
        """Should print progress information to console"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.WorkflowService"
        ) as mock_workflow_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ):
            # Mock AutoStartService
            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = [sample_changed_projects[0]]

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                sample_changed_projects[0], True, "New project"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            # Mock WorkflowService
            mock_workflow_service = Mock()
            mock_workflow_service.batch_trigger_claudechain_workflows.return_value = (
                ["project-a"], []
            )
            mock_workflow_service_class.return_value = mock_workflow_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456"
            )

        # Assert
        assert result == 0
        captured = capsys.readouterr()
        assert "Step 1/3: Detecting changed projects" in captured.out
        assert "Step 2/3: Determining new projects" in captured.out
        assert "Step 3/4: Making auto-trigger decisions" in captured.out
        assert "Step 4/4: Triggering workflows" in captured.out
        assert "Repository: owner/repo" in captured.out
        assert "Base branch: main" in captured.out

    def test_cmd_auto_start_service_instantiation(
        self, mock_github_helper, sample_changed_projects
    ):
        """Should instantiate services with correct dependencies"""
        # Arrange
        with patch(
            "claudechain.cli.commands.auto_start.AutoStartService"
        ) as mock_auto_start_service_class, patch(
            "claudechain.cli.commands.auto_start.WorkflowService"
        ) as mock_workflow_service_class, patch(
            "claudechain.cli.commands.auto_start.PRService"
        ) as mock_pr_service_class:
            # Mock services
            mock_pr_service = Mock()
            mock_pr_service_class.return_value = mock_pr_service

            mock_auto_start_service = Mock()
            mock_auto_start_service.detect_changed_projects.return_value = sample_changed_projects
            mock_auto_start_service.determine_new_projects.return_value = [sample_changed_projects[0]]

            from claudechain.domain.auto_start import AutoStartDecision
            mock_auto_start_service.should_auto_trigger.return_value = AutoStartDecision(
                sample_changed_projects[0], True, "New project"
            )
            mock_auto_start_service_class.return_value = mock_auto_start_service

            mock_workflow_service = Mock()
            mock_workflow_service.batch_trigger_claudechain_workflows.return_value = (["project-a"], [])
            mock_workflow_service_class.return_value = mock_workflow_service

            # Act
            result = cmd_auto_start(
                gh=mock_github_helper,
                repo="owner/repo",
                base_branch="main",
                ref_before="abc123",
                ref_after="def456",
                auto_start_enabled=True
            )

        # Assert
        assert result == 0

        # Verify PRService instantiation
        mock_pr_service_class.assert_called_once_with("owner/repo")

        # Verify AutoStartService instantiation with dependencies
        mock_auto_start_service_class.assert_called_once_with(
            "owner/repo",
            mock_pr_service,
            True
        )

        # Verify WorkflowService instantiation
        mock_workflow_service_class.assert_called_once()


class TestCmdAutoStartSummary:
    """Test suite for cmd_auto_start_summary functionality"""

    @pytest.fixture
    def mock_github_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        mock = Mock()
        mock.write_step_summary = Mock()
        mock.set_error = Mock()
        return mock

    def test_cmd_auto_start_summary_all_succeeded(
        self, mock_github_helper, capsys
    ):
        """Should generate summary when all workflows triggered successfully"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="project-a project-b",
            failed_projects=""
        )

        # Assert
        assert result == 0

        # Verify summary content
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "ClaudeChain Auto-Start Summary" in summary_text
        assert "All workflows triggered successfully" in summary_text
        assert "project-a" in summary_text
        assert "project-b" in summary_text
        assert "Triggered Projects" in summary_text

        captured = capsys.readouterr()
        assert "Auto-start summary generated successfully" in captured.out

    def test_cmd_auto_start_summary_partial_success(
        self, mock_github_helper
    ):
        """Should generate summary when some workflows failed"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="project-a",
            failed_projects="project-b project-c"
        )

        # Assert
        assert result == 0

        # Verify summary content
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "Partial success" in summary_text
        assert "Successfully Triggered" in summary_text
        assert "project-a" in summary_text
        assert "Failed to Trigger" in summary_text
        assert "project-b" in summary_text
        assert "project-c" in summary_text

    def test_cmd_auto_start_summary_all_failed(
        self, mock_github_helper
    ):
        """Should generate summary when all workflows failed"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="",
            failed_projects="project-a project-b"
        )

        # Assert
        assert result == 0

        # Verify summary content
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "All workflow triggers failed" in summary_text
        assert "Failed Projects" in summary_text
        assert "project-a" in summary_text
        assert "project-b" in summary_text

    def test_cmd_auto_start_summary_no_projects(
        self, mock_github_helper
    ):
        """Should generate summary when no projects were detected"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="",
            failed_projects=""
        )

        # Assert
        assert result == 0

        # Verify summary content
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "No new projects detected" in summary_text
        assert "No spec.md changes found" in summary_text

    def test_cmd_auto_start_summary_includes_helpful_info(
        self, mock_github_helper
    ):
        """Should include helpful information about what happens next"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="project-a",
            failed_projects=""
        )

        # Assert
        assert result == 0

        # Verify summary content
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "What happens next?" in summary_text
        assert "Pull requests will be created automatically" in summary_text

    def test_cmd_auto_start_summary_handles_exception(
        self, mock_github_helper, capsys
    ):
        """Should handle exceptions and return error code"""
        # Arrange
        # Create a side effect that raises on second call but allows error summary to be written
        call_count = [0]
        def side_effect(text):
            call_count[0] += 1
            if call_count[0] == 2:  # Second call fails
                raise Exception("Test error")
            return None

        mock_github_helper.write_step_summary.side_effect = side_effect

        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="project-a",
            failed_projects=""
        )

        # Assert
        assert result == 1
        mock_github_helper.set_error.assert_called_once()
        error_call = mock_github_helper.set_error.call_args[0][0]
        assert "Auto-start summary generation failed" in error_call
        assert "Test error" in error_call

    def test_cmd_auto_start_summary_parses_project_lists(
        self, mock_github_helper
    ):
        """Should correctly parse space-separated project lists"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="  project-a   project-b  ",
            failed_projects="  project-c  "
        )

        # Assert
        assert result == 0

        # Verify all projects are included in summary
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])

        assert "project-a" in summary_text
        assert "project-b" in summary_text
        assert "project-c" in summary_text

    def test_cmd_auto_start_summary_handles_empty_strings(
        self, mock_github_helper
    ):
        """Should handle empty strings gracefully"""
        # Act
        result = cmd_auto_start_summary(
            gh=mock_github_helper,
            triggered_projects="",
            failed_projects=""
        )

        # Assert
        assert result == 0

        # Should show no projects detected
        summary_calls = mock_github_helper.write_step_summary.call_args_list
        summary_text = " ".join([str(c) for c in summary_calls])
        assert "No new projects detected" in summary_text
