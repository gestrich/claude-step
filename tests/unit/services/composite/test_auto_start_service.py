"""Tests for auto-start service orchestration"""

import pytest
from unittest.mock import Mock, patch

from claudestep.domain.auto_start import AutoStartProject, AutoStartDecision, ProjectChangeType
from claudestep.services.composite.auto_start_service import AutoStartService


class TestDetectChangedProjects:
    """Test detect_changed_projects() method"""

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_added_project(self, mock_deleted, mock_changed):
        """Test detecting a newly added project"""
        # Mock git operations
        mock_changed.return_value = ['claude-step/new-project/spec.md']
        mock_deleted.return_value = []

        # Create service and test
        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        assert len(projects) == 1
        assert projects[0].name == "new-project"
        assert projects[0].change_type == ProjectChangeType.MODIFIED
        assert projects[0].spec_path == "claude-step/new-project/spec.md"

        # Verify git operations were called correctly
        mock_changed.assert_called_once_with("abc123", "def456", "claude-step/*/spec.md")
        mock_deleted.assert_called_once_with("abc123", "def456", "claude-step/*/spec.md")

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_modified_project(self, mock_deleted, mock_changed):
        """Test detecting a modified project"""
        mock_changed.return_value = ['claude-step/existing-project/spec.md']
        mock_deleted.return_value = []

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        assert len(projects) == 1
        assert projects[0].name == "existing-project"
        assert projects[0].change_type == ProjectChangeType.MODIFIED

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_deleted_project(self, mock_deleted, mock_changed):
        """Test detecting a deleted project"""
        mock_changed.return_value = []
        mock_deleted.return_value = ['claude-step/old-project/spec.md']

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        assert len(projects) == 1
        assert projects[0].name == "old-project"
        assert projects[0].change_type == ProjectChangeType.DELETED
        assert projects[0].spec_path == "claude-step/old-project/spec.md"

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_multiple_projects(self, mock_deleted, mock_changed):
        """Test detecting multiple changed projects"""
        mock_changed.return_value = [
            'claude-step/project-a/spec.md',
            'claude-step/project-b/spec.md'
        ]
        mock_deleted.return_value = ['claude-step/project-c/spec.md']

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        assert len(projects) == 3

        # Check modified projects
        modified = [p for p in projects if p.change_type == ProjectChangeType.MODIFIED]
        assert len(modified) == 2
        assert {p.name for p in modified} == {"project-a", "project-b"}

        # Check deleted projects
        deleted = [p for p in projects if p.change_type == ProjectChangeType.DELETED]
        assert len(deleted) == 1
        assert deleted[0].name == "project-c"

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_no_changes(self, mock_deleted, mock_changed):
        """Test detecting no changes"""
        mock_changed.return_value = []
        mock_deleted.return_value = []

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        assert len(projects) == 0

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_invalid_path(self, mock_deleted, mock_changed):
        """Test detecting changes with invalid path (should be filtered out)"""
        # Invalid path that doesn't match claude-step/*/spec.md pattern
        mock_changed.return_value = ['invalid/path/spec.md']
        mock_deleted.return_value = []

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456")

        # parse_spec_path_to_project returns None for invalid paths
        assert len(projects) == 0

    @patch('claudestep.services.composite.auto_start_service.detect_changed_files')
    @patch('claudestep.services.composite.auto_start_service.detect_deleted_files')
    def test_detect_custom_pattern(self, mock_deleted, mock_changed):
        """Test detecting changes with custom pattern"""
        mock_changed.return_value = ['custom-path/project/spec.md']
        mock_deleted.return_value = []

        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        projects = service.detect_changed_projects("abc123", "def456", spec_pattern="custom-path/*/spec.md")

        # Verify custom pattern was passed to git operations
        mock_changed.assert_called_once_with("abc123", "def456", "custom-path/*/spec.md")


class TestDetermineNewProjects:
    """Test determine_new_projects() method"""

    def test_all_new_projects(self, capsys):
        """Test determining all projects are new"""
        # Mock PRService to return no PRs
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        projects = [
            AutoStartProject("project-a", ProjectChangeType.MODIFIED, "claude-step/project-a/spec.md"),
            AutoStartProject("project-b", ProjectChangeType.MODIFIED, "claude-step/project-b/spec.md")
        ]

        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects(projects)

        assert len(new_projects) == 2
        assert {p.name for p in new_projects} == {"project-a", "project-b"}

        # Verify PRService was called for each project
        assert mock_pr_service.get_project_prs.call_count == 2

        # Check output messages
        captured = capsys.readouterr()
        assert "✓ project-a is a new project (no existing PRs)" in captured.out
        assert "✓ project-b is a new project (no existing PRs)" in captured.out

    def test_all_existing_projects(self, capsys):
        """Test determining all projects have existing PRs"""
        # Mock PRService to return existing PRs
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = [Mock(), Mock()]  # 2 existing PRs

        projects = [
            AutoStartProject("project-a", ProjectChangeType.MODIFIED, "claude-step/project-a/spec.md"),
        ]

        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects(projects)

        assert len(new_projects) == 0

        # Check output messages
        captured = capsys.readouterr()
        assert "✗ project-a has 2 existing PR(s), skipping" in captured.out

    def test_mixed_new_and_existing(self, capsys):
        """Test mix of new and existing projects"""
        # Mock PRService with different returns for each project
        mock_pr_service = Mock()

        def get_prs_side_effect(project_name, state="all"):
            if project_name == "new-project":
                return []  # No existing PRs
            else:
                return [Mock()]  # Has existing PRs

        mock_pr_service.get_project_prs.side_effect = get_prs_side_effect

        projects = [
            AutoStartProject("new-project", ProjectChangeType.MODIFIED, "claude-step/new-project/spec.md"),
            AutoStartProject("existing-project", ProjectChangeType.MODIFIED, "claude-step/existing-project/spec.md")
        ]

        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects(projects)

        assert len(new_projects) == 1
        assert new_projects[0].name == "new-project"

    def test_skip_deleted_projects(self):
        """Test deleted projects are skipped"""
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        projects = [
            AutoStartProject("deleted-project", ProjectChangeType.DELETED, "claude-step/deleted-project/spec.md"),
            AutoStartProject("modified-project", ProjectChangeType.MODIFIED, "claude-step/modified-project/spec.md")
        ]

        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects(projects)

        # Only modified project should be checked and returned
        assert len(new_projects) == 1
        assert new_projects[0].name == "modified-project"

        # PRService should only be called once (for modified project)
        mock_pr_service.get_project_prs.assert_called_once_with("modified-project", state="all")

    def test_github_api_error_handling(self, capsys):
        """Test handling of GitHub API errors"""
        # Mock PRService to raise exception
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.side_effect = Exception("GitHub API error")

        projects = [
            AutoStartProject("project-a", ProjectChangeType.MODIFIED, "claude-step/project-a/spec.md"),
        ]

        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects(projects)

        # Should skip project on error and not crash
        assert len(new_projects) == 0

        # Check error message was logged
        captured = capsys.readouterr()
        assert "⚠️  Error querying GitHub API for project-a" in captured.out
        assert "GitHub API error" in captured.out

    def test_empty_projects_list(self):
        """Test with empty projects list"""
        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)
        new_projects = service.determine_new_projects([])

        assert len(new_projects) == 0
        mock_pr_service.get_project_prs.assert_not_called()


class TestShouldAutoTrigger:
    """Test should_auto_trigger() decision logic"""

    def test_trigger_new_project(self):
        """Test triggering for new project"""
        # Mock PRService to return no PRs
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        project = AutoStartProject("new-project", ProjectChangeType.MODIFIED, "claude-step/new-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is True
        assert decision.reason == "New project detected"
        assert decision.project == project

    def test_skip_existing_project(self):
        """Test skipping project with existing PRs"""
        # Mock PRService to return existing PRs
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = [Mock(), Mock(), Mock()]  # 3 PRs

        project = AutoStartProject("existing-project", ProjectChangeType.MODIFIED, "claude-step/existing-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert decision.reason == "Project has 3 existing PR(s)"
        assert decision.project == project

    def test_skip_deleted_project(self):
        """Test skipping deleted project"""
        mock_pr_service = Mock()

        project = AutoStartProject("deleted-project", ProjectChangeType.DELETED, "claude-step/deleted-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert decision.reason == "Project spec was deleted"
        assert decision.project == project

        # Should not query PRs for deleted projects
        mock_pr_service.get_project_prs.assert_not_called()

    def test_github_api_error(self):
        """Test error handling when GitHub API fails"""
        # Mock PRService to raise exception
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.side_effect = Exception("API timeout")

        project = AutoStartProject("project-a", ProjectChangeType.MODIFIED, "claude-step/project-a/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert "Error checking PRs: API timeout" in decision.reason

    def test_single_existing_pr(self):
        """Test project with single existing PR"""
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = [Mock()]  # 1 PR

        project = AutoStartProject("project-a", ProjectChangeType.MODIFIED, "claude-step/project-a/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert decision.reason == "Project has 1 existing PR(s)"


class TestAutoStartDisabledConfiguration:
    """Test disabled auto-start configuration"""

    def test_disabled_auto_start_new_project(self):
        """Test that new projects are skipped when auto-start is disabled"""
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        project = AutoStartProject("new-project", ProjectChangeType.MODIFIED, "claude-step/new-project/spec.md")

        # Create service with auto_start_enabled=False
        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=False)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert decision.reason == "Auto-start is disabled via configuration"

        # Should not query PRs when auto-start is disabled
        mock_pr_service.get_project_prs.assert_not_called()

    def test_disabled_auto_start_existing_project(self):
        """Test that existing projects are also skipped when disabled"""
        mock_pr_service = Mock()

        project = AutoStartProject("existing-project", ProjectChangeType.MODIFIED, "claude-step/existing-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=False)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        assert decision.reason == "Auto-start is disabled via configuration"

    def test_disabled_auto_start_deleted_project(self):
        """Test that deleted projects show disabled message (not deleted message)"""
        mock_pr_service = Mock()

        project = AutoStartProject("deleted-project", ProjectChangeType.DELETED, "claude-step/deleted-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=False)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is False
        # Disabled check happens first, before deleted check
        assert decision.reason == "Auto-start is disabled via configuration"

    def test_enabled_auto_start_default(self):
        """Test that auto-start is enabled by default"""
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        project = AutoStartProject("new-project", ProjectChangeType.MODIFIED, "claude-step/new-project/spec.md")

        # Create service without specifying auto_start_enabled (should default to True)
        service = AutoStartService("owner/repo", mock_pr_service)
        decision = service.should_auto_trigger(project)

        # Should trigger since auto-start is enabled by default
        assert decision.should_trigger is True
        assert decision.reason == "New project detected"

    def test_enabled_auto_start_explicit(self):
        """Test explicitly enabling auto-start"""
        mock_pr_service = Mock()
        mock_pr_service.get_project_prs.return_value = []

        project = AutoStartProject("new-project", ProjectChangeType.MODIFIED, "claude-step/new-project/spec.md")

        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=True)
        decision = service.should_auto_trigger(project)

        assert decision.should_trigger is True
        assert decision.reason == "New project detected"


class TestServiceInitialization:
    """Test service initialization"""

    def test_basic_initialization(self):
        """Test basic service initialization"""
        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service)

        assert service.repo == "owner/repo"
        assert service.pr_service == mock_pr_service
        assert service.auto_start_enabled is True

    def test_initialization_with_disabled_auto_start(self):
        """Test initialization with auto-start disabled"""
        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=False)

        assert service.repo == "owner/repo"
        assert service.pr_service == mock_pr_service
        assert service.auto_start_enabled is False

    def test_initialization_with_enabled_auto_start(self):
        """Test initialization with auto-start explicitly enabled"""
        mock_pr_service = Mock()
        service = AutoStartService("owner/repo", mock_pr_service, auto_start_enabled=True)

        assert service.repo == "owner/repo"
        assert service.pr_service == mock_pr_service
        assert service.auto_start_enabled is True
