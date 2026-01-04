"""Unit tests for hash-based task identification edge cases"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from claudechain.domain.project import Project
from claudechain.domain.spec_content import SpecTask, SpecContent, generate_task_hash
from claudechain.domain.github_models import GitHubPullRequest
from claudechain.services.core.task_service import TaskService


class TestGenerateTaskHash:
    """Test suite for generate_task_hash function"""

    def test_hash_is_stable_for_same_input(self):
        """Should generate identical hash for same input"""
        description = "Add user authentication"
        hash1 = generate_task_hash(description)
        hash2 = generate_task_hash(description)
        assert hash1 == hash2

    def test_hash_length_is_8_characters(self):
        """Should generate 8-character hash"""
        description = "Some task description"
        task_hash = generate_task_hash(description)
        assert len(task_hash) == 8

    def test_hash_is_hexadecimal(self):
        """Should generate hexadecimal hash (0-9, a-f)"""
        description = "Some task description"
        task_hash = generate_task_hash(description)
        assert all(c in "0123456789abcdef" for c in task_hash)

    def test_hash_normalizes_whitespace(self):
        """Should generate same hash regardless of whitespace"""
        description1 = "Add user authentication"
        description2 = "  Add user authentication  "
        description3 = "Add  user  authentication"

        hash1 = generate_task_hash(description1)
        hash2 = generate_task_hash(description2)
        hash3 = generate_task_hash(description3)

        # All whitespace is normalized (collapsed to single spaces)
        # Leading/trailing whitespace is stripped
        # Internal whitespace is collapsed
        assert hash1 == hash2
        assert hash1 == hash3  # Internal whitespace is also collapsed

    def test_hash_is_case_sensitive(self):
        """Should generate different hash for different cases"""
        description1 = "Add user authentication"
        description2 = "add user authentication"

        hash1 = generate_task_hash(description1)
        hash2 = generate_task_hash(description2)

        assert hash1 != hash2

    def test_hash_for_empty_string(self):
        """Should handle empty string"""
        task_hash = generate_task_hash("")
        assert len(task_hash) == 8
        assert all(c in "0123456789abcdef" for c in task_hash)

    def test_hash_for_very_long_description(self):
        """Should handle very long descriptions"""
        description = "A" * 1000  # Very long description
        task_hash = generate_task_hash(description)
        assert len(task_hash) == 8

    def test_hash_for_special_characters(self):
        """Should handle special characters in description"""
        description = "Update API endpoint `/users/{id}` to support PATCH"
        task_hash = generate_task_hash(description)
        assert len(task_hash) == 8
        assert all(c in "0123456789abcdef" for c in task_hash)

    def test_hash_for_unicode_characters(self):
        """Should handle unicode characters"""
        description = "Add support for emoji 🎉 and unicode 日本語"
        task_hash = generate_task_hash(description)
        assert len(task_hash) == 8


class TestTaskHashCollisions:
    """Test suite for hash collision scenarios (extremely rare but tested)"""

    def test_different_tasks_have_different_hashes(self):
        """Should generate different hashes for different tasks"""
        task1 = "Add user authentication"
        task2 = "Add user authorization"
        task3 = "Implement feature X"

        hash1 = generate_task_hash(task1)
        hash2 = generate_task_hash(task2)
        hash3 = generate_task_hash(task3)

        assert hash1 != hash2
        assert hash1 != hash3
        assert hash2 != hash3

    def test_similar_tasks_have_different_hashes(self):
        """Should generate different hashes for similar tasks"""
        task1 = "Fix bug in login"
        task2 = "Fix bug in logout"
        task3 = "Fix bug in signup"

        hash1 = generate_task_hash(task1)
        hash2 = generate_task_hash(task2)
        hash3 = generate_task_hash(task3)

        # All should be different
        assert len({hash1, hash2, hash3}) == 3

    def test_hash_distribution_for_many_tasks(self):
        """Should generate unique hashes for many similar tasks"""
        # Generate 100 similar tasks
        tasks = [f"Task number {i}" for i in range(100)]
        hashes = [generate_task_hash(task) for task in tasks]

        # All hashes should be unique (no collisions)
        assert len(set(hashes)) == len(hashes)


class TestTaskReorderingScenarios:
    """Test suite for task reordering scenarios"""

    def test_task_hash_remains_stable_after_reordering(self):
        """Task hash should remain stable even when position changes"""
        # Original order
        project = Project("my-project")
        content1 = "- [ ] First\n- [ ] Second\n- [ ] Third"
        spec1 = SpecContent(project, content1)

        original_first_hash = spec1.tasks[0].task_hash
        original_second_hash = spec1.tasks[1].task_hash
        original_third_hash = spec1.tasks[2].task_hash

        # Reordered content (Third moved to first position)
        content2 = "- [ ] Third\n- [ ] First\n- [ ] Second"
        spec2 = SpecContent(project, content2)

        # Verify hashes are stable despite position change
        assert spec2.tasks[0].task_hash == original_third_hash  # Third is now first
        assert spec2.tasks[1].task_hash == original_first_hash  # First is now second
        assert spec2.tasks[2].task_hash == original_second_hash  # Second is now third

        # Verify indices changed but hashes didn't
        assert spec2.tasks[0].index == 1
        assert spec2.tasks[1].index == 2
        assert spec2.tasks[2].index == 3

    def test_task_insertion_doesnt_affect_existing_hashes(self):
        """Inserting a new task shouldn't affect existing task hashes"""
        # Original tasks
        project = Project("my-project")
        content1 = "- [ ] First\n- [ ] Third"
        spec1 = SpecContent(project, content1)

        original_first_hash = spec1.tasks[0].task_hash
        original_third_hash = spec1.tasks[1].task_hash

        # New task inserted in the middle
        content2 = "- [ ] First\n- [ ] NEW TASK\n- [ ] Third"
        spec2 = SpecContent(project, content2)

        # Verify existing task hashes are unchanged
        assert spec2.tasks[0].task_hash == original_first_hash
        assert spec2.tasks[2].task_hash == original_third_hash

        # Verify new task has a different hash
        new_task_hash = spec2.tasks[1].task_hash
        assert new_task_hash != original_first_hash
        assert new_task_hash != original_third_hash

    def test_task_deletion_doesnt_affect_remaining_hashes(self):
        """Deleting a task shouldn't affect remaining task hashes"""
        # Original tasks
        project = Project("my-project")
        content1 = "- [ ] First\n- [ ] DELETE ME\n- [ ] Third"
        spec1 = SpecContent(project, content1)

        original_first_hash = spec1.tasks[0].task_hash
        original_third_hash = spec1.tasks[2].task_hash

        # Middle task deleted
        content2 = "- [ ] First\n- [ ] Third"
        spec2 = SpecContent(project, content2)

        # Verify remaining task hashes are unchanged
        assert spec2.tasks[0].task_hash == original_first_hash
        assert spec2.tasks[1].task_hash == original_third_hash


class TestOrphanedPRDetection:
    """Test suite for orphaned PR detection"""

    def test_detect_orphaned_prs_with_hash_mismatch(self):
        """Should detect PRs whose task hash no longer matches any task"""
        # Setup spec with current tasks
        project = Project("my-project")
        content = "- [ ] Current task 1\n- [ ] Current task 2"
        spec = SpecContent(project, content)

        # Get hashes for current tasks
        valid_hash_1 = spec.tasks[0].task_hash
        valid_hash_2 = spec.tasks[1].task_hash

        # Create orphaned PR (hash doesn't match any current task)
        orphaned_hash = "deadbeef"  # This hash doesn't match any current task
        orphaned_pr = GitHubPullRequest(
            number=1,
            state="open",
            head_ref_name=f"claude-chain-my-project-{orphaned_hash}",
            title="Orphaned task",
            labels=[],
            assignees=[],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
        )

        # Create valid PR (hash matches a current task)
        valid_pr = GitHubPullRequest(
            number=2,
            state="open",
            head_ref_name=f"claude-chain-my-project-{valid_hash_1}",
            title="Valid task",
            labels=[],
            assignees=[],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
        )

        # Mock PR service to return both PRs
        mock_pr_service = MagicMock()
        mock_pr_service.get_open_prs_for_project.return_value = [orphaned_pr, valid_pr]

        # Create service and detect orphaned PRs
        service = TaskService("owner/repo", mock_pr_service)
        orphaned_prs = service.detect_orphaned_prs("claudechain", "my-project", spec)

        # Should detect only the orphaned PR
        assert len(orphaned_prs) == 1
        assert orphaned_prs[0].number == 1
        assert orphaned_prs[0].task_hash == orphaned_hash


    def test_detect_orphaned_prs_with_no_orphans(self):
        """Should return empty list when all PRs are valid"""
        # Setup spec with current tasks
        project = Project("my-project")
        content = "- [ ] Task 1\n- [ ] Task 2"
        spec = SpecContent(project, content)

        # Create PRs that match current tasks
        hash_1 = spec.tasks[0].task_hash
        pr1 = GitHubPullRequest(
            number=1,
            state="open",
            head_ref_name=f"claude-chain-my-project-{hash_1}",
            title="Task 1",
            labels=[],
            assignees=[],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
        )

        # Mock PR service
        mock_pr_service = MagicMock()
        mock_pr_service.get_open_prs_for_project.return_value = [pr1]

        # Create service and detect orphaned PRs
        service = TaskService("owner/repo", mock_pr_service)
        orphaned_prs = service.detect_orphaned_prs("claudechain", "my-project", spec)

        # Should find no orphaned PRs
        assert len(orphaned_prs) == 0


class TestGetInProgressTasks:
    """Test suite for get_in_progress_tasks dual-mode support"""

    def test_get_in_progress_tasks_with_hash_based_prs(self):
        """Should extract task hashes from hash-based PRs"""
        # Setup spec
        project = Project("my-project")
        content = "- [ ] Task 1\n- [ ] Task 2"
        spec = SpecContent(project, content)

        # Create hash-based PRs
        hash_1 = spec.tasks[0].task_hash
        hash_2 = spec.tasks[1].task_hash

        pr1 = GitHubPullRequest(
            number=1,
            state="open",
            head_ref_name=f"claude-chain-my-project-{hash_1}",
            title="Task 1",
            labels=[],
            assignees=[],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
        )

        pr2 = GitHubPullRequest(
            number=2,
            state="open",
            head_ref_name=f"claude-chain-my-project-{hash_2}",
            title="Task 2",
            labels=[],
            assignees=[],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
        )

        # Mock PR service
        mock_pr_service = MagicMock()
        mock_pr_service.get_open_prs_for_project.return_value = [pr1, pr2]

        # Create service and get in-progress tasks
        service = TaskService("owner/repo", mock_pr_service)
        hashes = service.get_in_progress_tasks("claudechain", "my-project")

        # Should return both hashes
        assert hashes == {hash_1, hash_2}


