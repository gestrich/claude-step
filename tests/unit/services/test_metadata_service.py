"""Unit tests for MetadataService

Tests the application service layer for metadata operations
from src/claudestep/services/metadata_service.py
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from claudestep.domain.models import (
    Task,
    TaskStatus,
    PullRequest,
    AIOperation,
    HybridProjectMetadata,
)
from claudestep.services.metadata_service import MetadataService


class TestMetadataService:
    """Tests for MetadataService class"""

    @pytest.fixture
    def mock_store(self):
        """Create a mock MetadataStore"""
        return Mock()

    @pytest.fixture
    def service(self, mock_store):
        """Create a MetadataService with mock store"""
        return MetadataService(store=mock_store)

    @pytest.fixture
    def sample_project(self):
        """Create a sample project for testing"""
        created_at = datetime(2025, 12, 29, 10, 0, 0, tzinfo=timezone.utc)
        return HybridProjectMetadata(
            schema_version="2.0",
            project="test-project",
            last_updated=created_at,
            tasks=[
                Task(index=1, description="Task 1", status=TaskStatus.COMPLETED),
                Task(index=2, description="Task 2", status=TaskStatus.IN_PROGRESS),
                Task(index=3, description="Task 3", status=TaskStatus.PENDING)
            ],
            pull_requests=[
                PullRequest(
                    task_index=1,
                    pr_number=42,
                    branch_name="claudestep/test-project/step-1",
                    reviewer="alice",
                    pr_state="merged",
                    created_at=created_at,
                    ai_operations=[
                        AIOperation(
                            type="PRCreation",
                            model="claude-sonnet-4",
                            cost_usd=0.12,
                            created_at=created_at,
                            workflow_run_id=111
                        )
                    ]
                ),
                PullRequest(
                    task_index=2,
                    pr_number=43,
                    branch_name="claudestep/test-project/step-2",
                    reviewer="bob",
                    pr_state="open",
                    created_at=created_at,
                    ai_operations=[
                        AIOperation(
                            type="PRCreation",
                            model="claude-sonnet-4",
                            cost_usd=0.15,
                            created_at=created_at,
                            workflow_run_id=222
                        )
                    ]
                )
            ]
        )

    def test_get_project_success(self, service, mock_store, sample_project):
        """Should retrieve project from store"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.get_project("test-project")

        # Assert
        assert result == sample_project
        mock_store.get_project.assert_called_once_with("test-project")

    def test_get_project_not_found(self, service, mock_store):
        """Should return None when project not found"""
        # Arrange
        mock_store.get_project.return_value = None

        # Act
        result = service.get_project("nonexistent")

        # Assert
        assert result is None
        mock_store.get_project.assert_called_once_with("nonexistent")

    @patch('claudestep.services.metadata_service.datetime')
    def test_save_project_updates_timestamp_and_syncs(self, mock_datetime, service, mock_store, sample_project):
        """Should update timestamp and sync statuses before saving"""
        # Arrange
        now = datetime(2025, 12, 29, 15, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now

        # Act
        service.save_project(sample_project)

        # Assert
        assert sample_project.last_updated == now
        mock_store.save_project.assert_called_once_with(sample_project)

    def test_list_all_projects(self, service, mock_store, sample_project):
        """Should return all projects from store"""
        # Arrange
        projects = [sample_project]
        mock_store.get_all_projects.return_value = projects

        # Act
        result = service.list_all_projects()

        # Assert
        assert result == projects
        mock_store.get_all_projects.assert_called_once()

    @patch('claudestep.services.metadata_service.datetime')
    def test_get_or_create_project_existing(self, mock_datetime, service, mock_store, sample_project):
        """Should return existing project when it exists"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.get_or_create_project("test-project")

        # Assert
        assert result == sample_project
        mock_store.get_project.assert_called_once_with("test-project")
        mock_store.save_project.assert_not_called()

    @patch('claudestep.services.metadata_service.datetime')
    def test_get_or_create_project_new(self, mock_datetime, service, mock_store):
        """Should create and save new project when it doesn't exist"""
        # Arrange
        now = datetime(2025, 12, 29, 15, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_store.get_project.return_value = None

        # Act
        result = service.get_or_create_project("new-project")

        # Assert
        assert result.project == "new-project"
        assert result.schema_version == "2.0"
        assert len(result.tasks) == 0
        assert len(result.pull_requests) == 0
        mock_store.save_project.assert_called_once()

    @patch('claudestep.services.metadata_service.datetime')
    def test_get_or_create_project_with_tasks(self, mock_datetime, service, mock_store):
        """Should initialize new project with provided tasks"""
        # Arrange
        now = datetime(2025, 12, 29, 15, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_store.get_project.return_value = None

        tasks = [
            Task(index=1, description="Task 1", status=TaskStatus.PENDING),
            Task(index=2, description="Task 2", status=TaskStatus.PENDING)
        ]

        # Act
        result = service.get_or_create_project("new-project", tasks=tasks)

        # Assert
        assert len(result.tasks) == 2
        assert result.tasks == tasks
        mock_store.save_project.assert_called_once()

    def test_find_in_progress_tasks(self, service, mock_store, sample_project):
        """Should return task indices with open PRs"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.find_in_progress_tasks("test-project")

        # Assert
        assert result == {2}  # Only task 2 has open PR (returns set)

    def test_find_in_progress_tasks_no_project(self, service, mock_store):
        """Should return empty set when project doesn't exist"""
        # Arrange
        mock_store.get_project.return_value = None

        # Act
        result = service.find_in_progress_tasks("nonexistent")

        # Assert
        assert result == set()

    def test_get_reviewer_assignments(self, service, mock_store, sample_project):
        """Should map task indices to reviewers for open PRs only"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.get_reviewer_assignments("test-project")

        # Assert
        assert result == {2: "bob"}  # Only includes open PRs (PR 43 is open, PR 42 is merged)

    def test_get_reviewer_assignments_no_project(self, service, mock_store):
        """Should return empty dict when project doesn't exist"""
        # Arrange
        mock_store.get_project.return_value = None

        # Act
        result = service.get_reviewer_assignments("nonexistent")

        # Assert
        assert result == {}

    def test_get_open_prs_by_reviewer(self, service, mock_store, sample_project):
        """Should map reviewers to their open PR numbers"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.get_open_prs_by_reviewer("test-project")

        # Assert
        assert result == {"bob": [43]}  # Only bob has open PR

    def test_get_open_prs_by_reviewer_all_projects(self, service, mock_store, sample_project):
        """Should aggregate open PRs across all projects"""
        # Arrange
        created_at = datetime(2025, 12, 29, 10, 0, 0, tzinfo=timezone.utc)
        project2 = HybridProjectMetadata(
            schema_version="2.0",
            project="another-project",
            last_updated=created_at,
            tasks=[],
            pull_requests=[
                PullRequest(
                    task_index=1,
                    pr_number=50,
                    branch_name="claudestep/another/step-1",
                    reviewer="alice",
                    pr_state="open",
                    created_at=created_at,
                    ai_operations=[]
                )
            ]
        )
        mock_store.get_all_projects.return_value = [sample_project, project2]

        # Act
        result = service.get_open_prs_by_reviewer()

        # Assert
        assert result == {
            "bob": [43],
            "alice": [50]
        }

    @patch('claudestep.services.metadata_service.datetime')
    def test_add_pr_to_project(self, mock_datetime, service, mock_store, sample_project):
        """Should add new PR and sync task statuses"""
        # Arrange
        now = datetime(2025, 12, 29, 15, 30, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = now
        mock_store.get_project.return_value = sample_project

        new_pr = PullRequest(
            task_index=3,
            pr_number=44,
            branch_name="claudestep/test-project/step-3",
            reviewer="alice",
            pr_state="open",
            created_at=now,
            ai_operations=[]
        )

        # Act
        service.add_pr_to_project("test-project", task_index=3, pr=new_pr)

        # Assert
        assert len(sample_project.pull_requests) == 3
        assert sample_project.pull_requests[-1] == new_pr
        mock_store.save_project.assert_called_once()

    def test_update_pr_state(self, service, mock_store, sample_project):
        """Should update PR state and sync task statuses"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        service.update_pr_state("test-project", pr_number=43, new_state="merged")

        # Assert
        pr = next(pr for pr in sample_project.pull_requests if pr.pr_number == 43)
        assert pr.pr_state == "merged"
        mock_store.save_project.assert_called_once()

    def test_update_task_status(self, service, mock_store, sample_project):
        """Should update task status based on PRs"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        service.update_task_status("test-project", task_index=3)

        # Assert
        # Task 3 has no PRs, so should remain PENDING
        task = sample_project.get_task_by_index(3)
        assert task.status == TaskStatus.PENDING
        mock_store.save_project.assert_called_once()

    def test_get_projects_modified_since(self, service, mock_store):
        """Should filter projects by modification date"""
        # Arrange
        cutoff = datetime(2025, 12, 25, 0, 0, 0, tzinfo=timezone.utc)
        projects = [Mock(), Mock()]
        mock_store.get_projects_modified_since.return_value = projects

        # Act
        result = service.get_projects_modified_since(cutoff)

        # Assert
        assert result == projects
        mock_store.get_projects_modified_since.assert_called_once_with(cutoff)

    def test_get_project_stats(self, service, mock_store, sample_project):
        """Should return comprehensive project statistics"""
        # Arrange
        mock_store.get_project.return_value = sample_project

        # Act
        result = service.get_project_stats("test-project")

        # Assert
        assert result["project"] == "test-project"
        assert result["total_tasks"] == 3
        assert result["completed"] == 1
        assert result["in_progress"] == 1
        assert result["pending"] == 1
        assert result["completion_percentage"] == pytest.approx(33.33, 0.01)
        assert result["total_cost"] == 0.27  # 0.12 + 0.15

    def test_get_project_stats_no_project(self, service, mock_store):
        """Should return None when project doesn't exist"""
        # Arrange
        mock_store.get_project.return_value = None

        # Act
        result = service.get_project_stats("nonexistent")

        # Assert
        assert result is None

    def test_get_reviewer_capacity(self, service, mock_store, sample_project):
        """Should return reviewer capacity information"""
        # Arrange
        created_at = datetime(2025, 12, 29, 10, 0, 0, tzinfo=timezone.utc)
        project2 = HybridProjectMetadata(
            schema_version="2.0",
            project="another-project",
            last_updated=created_at,
            tasks=[],
            pull_requests=[
                PullRequest(
                    task_index=1,
                    pr_number=50,
                    branch_name="claudestep/another/step-1",
                    reviewer="alice",
                    pr_state="open",
                    created_at=created_at,
                    ai_operations=[]
                ),
                PullRequest(
                    task_index=2,
                    pr_number=51,
                    branch_name="claudestep/another/step-2",
                    reviewer="alice",
                    pr_state="open",
                    created_at=created_at,
                    ai_operations=[]
                )
            ]
        )
        mock_store.get_all_projects.return_value = [sample_project, project2]

        # Act
        result = service.get_reviewer_capacity()

        # Assert
        assert "alice" in result
        assert "bob" in result
        assert result["alice"]["open_prs"] == 2
        assert result["bob"]["open_prs"] == 1
        assert len(result["alice"]["pr_numbers"]) == 2
        assert len(result["bob"]["pr_numbers"]) == 1

    def test_project_exists_true(self, service, mock_store):
        """Should return True when project exists"""
        # Arrange
        mock_store.project_exists.return_value = True

        # Act
        result = service.project_exists("test-project")

        # Assert
        assert result is True
        mock_store.project_exists.assert_called_once_with("test-project")

    def test_project_exists_false(self, service, mock_store):
        """Should return False when project doesn't exist"""
        # Arrange
        mock_store.project_exists.return_value = False

        # Act
        result = service.project_exists("nonexistent")

        # Assert
        assert result is False
        mock_store.project_exists.assert_called_once_with("nonexistent")

    def test_list_project_names(self, service, mock_store):
        """Should return list of project names"""
        # Arrange
        mock_store.list_project_names.return_value = ["project1", "project2", "project3"]

        # Act
        result = service.list_project_names()

        # Assert
        assert result == ["project1", "project2", "project3"]
        mock_store.list_project_names.assert_called_once()
