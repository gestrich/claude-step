"""Test suite for TaskStatus and TaskWithPR domain models"""

from datetime import datetime, timezone

import pytest

from claudechain.domain.github_models import GitHubPullRequest, GitHubUser, PRState
from claudechain.domain.models import ProjectStats, TaskStatus, TaskWithPR


class TestPRState:
    """Test suite for PRState enum"""

    def test_open_state_value(self):
        """Should have correct value for OPEN state"""
        assert PRState.OPEN.value == "open"

    def test_closed_state_value(self):
        """Should have correct value for CLOSED state"""
        assert PRState.CLOSED.value == "closed"

    def test_merged_state_value(self):
        """Should have correct value for MERGED state"""
        assert PRState.MERGED.value == "merged"

    def test_from_string_open(self):
        """Should parse 'open' string to OPEN state"""
        assert PRState.from_string("open") == PRState.OPEN
        assert PRState.from_string("OPEN") == PRState.OPEN

    def test_from_string_closed(self):
        """Should parse 'closed' string to CLOSED state"""
        assert PRState.from_string("closed") == PRState.CLOSED
        assert PRState.from_string("CLOSED") == PRState.CLOSED

    def test_from_string_merged(self):
        """Should parse 'merged' string to MERGED state"""
        assert PRState.from_string("merged") == PRState.MERGED
        assert PRState.from_string("MERGED") == PRState.MERGED

    def test_from_string_invalid_raises_error(self):
        """Should raise ValueError for invalid state string"""
        with pytest.raises(ValueError, match="Invalid PR state"):
            PRState.from_string("invalid")


class TestTaskStatus:
    """Test suite for TaskStatus enum"""

    def test_pending_status_value(self):
        """Should have correct value for PENDING status"""
        assert TaskStatus.PENDING.value == "pending"

    def test_in_progress_status_value(self):
        """Should have correct value for IN_PROGRESS status"""
        assert TaskStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_status_value(self):
        """Should have correct value for COMPLETED status"""
        assert TaskStatus.COMPLETED.value == "completed"

    def test_all_statuses_are_distinct(self):
        """Should have three distinct status values"""
        statuses = [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
        assert len(statuses) == 3
        assert len(set(s.value for s in statuses)) == 3


class TestTaskWithPR:
    """Test suite for TaskWithPR domain model"""

    @pytest.fixture
    def sample_pr(self):
        """Create a sample GitHubPullRequest for testing"""
        return GitHubPullRequest(
            number=42,
            title="ClaudeChain: Add user authentication",
            state="open",
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudechain"],
            head_ref_name="claude-chain-my-project-a3f2b891",
        )

    @pytest.fixture
    def merged_pr(self):
        """Create a merged GitHubPullRequest for testing"""
        return GitHubPullRequest(
            number=41,
            title="ClaudeChain: Add input validation",
            state="merged",
            created_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            merged_at=datetime(2025, 1, 2, 15, 0, 0, tzinfo=timezone.utc),
            assignees=[GitHubUser(login="bob")],
            labels=["claudechain"],
            head_ref_name="claude-chain-my-project-b4c3d2e1",
        )

    def test_task_with_pr_creation(self, sample_pr):
        """Should create TaskWithPR with all required fields"""
        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add user authentication",
            status=TaskStatus.IN_PROGRESS,
            pr=sample_pr,
        )

        assert task.task_hash == "a3f2b891"
        assert task.description == "Add user authentication"
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.pr == sample_pr

    def test_task_without_pr(self):
        """Should create TaskWithPR without PR (pending task)"""
        task = TaskWithPR(
            task_hash="c5d4e3f2",
            description="Add logging",
            status=TaskStatus.PENDING,
            pr=None,
        )

        assert task.task_hash == "c5d4e3f2"
        assert task.description == "Add logging"
        assert task.status == TaskStatus.PENDING
        assert task.pr is None

    def test_has_pr_returns_true_when_pr_exists(self, sample_pr):
        """Should return True for has_pr when PR is assigned"""
        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add user authentication",
            status=TaskStatus.IN_PROGRESS,
            pr=sample_pr,
        )

        assert task.has_pr is True

    def test_has_pr_returns_false_when_no_pr(self):
        """Should return False for has_pr when PR is None"""
        task = TaskWithPR(
            task_hash="c5d4e3f2",
            description="Add logging",
            status=TaskStatus.PENDING,
            pr=None,
        )

        assert task.has_pr is False

    def test_pr_number_returns_number_when_pr_exists(self, sample_pr):
        """Should return PR number when PR is assigned"""
        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add user authentication",
            status=TaskStatus.IN_PROGRESS,
            pr=sample_pr,
        )

        assert task.pr_number == 42

    def test_pr_number_returns_none_when_no_pr(self):
        """Should return None for pr_number when PR is None"""
        task = TaskWithPR(
            task_hash="c5d4e3f2",
            description="Add logging",
            status=TaskStatus.PENDING,
            pr=None,
        )

        assert task.pr_number is None

    def test_pr_state_returns_state_when_pr_exists(self, sample_pr):
        """Should return PR state when PR is assigned"""
        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add user authentication",
            status=TaskStatus.IN_PROGRESS,
            pr=sample_pr,
        )

        assert task.pr_state == PRState.OPEN

    def test_pr_state_returns_merged_for_merged_pr(self, merged_pr):
        """Should return PRState.MERGED for merged PR"""
        task = TaskWithPR(
            task_hash="b4c3d2e1",
            description="Add input validation",
            status=TaskStatus.COMPLETED,
            pr=merged_pr,
        )

        assert task.pr_state == PRState.MERGED

    def test_pr_state_returns_none_when_no_pr(self):
        """Should return None for pr_state when PR is None"""
        task = TaskWithPR(
            task_hash="c5d4e3f2",
            description="Add logging",
            status=TaskStatus.PENDING,
            pr=None,
        )

        assert task.pr_state is None

    def test_completed_task_with_merged_pr(self, merged_pr):
        """Should correctly represent completed task with merged PR"""
        task = TaskWithPR(
            task_hash="b4c3d2e1",
            description="Add input validation",
            status=TaskStatus.COMPLETED,
            pr=merged_pr,
        )

        assert task.status == TaskStatus.COMPLETED
        assert task.has_pr is True
        assert task.pr_number == 41
        assert task.pr_state == PRState.MERGED


class TestProjectStatsTaskFields:
    """Test suite for ProjectStats tasks and orphaned_prs fields"""

    @pytest.fixture
    def sample_pr(self):
        """Create a sample GitHubPullRequest for testing"""
        return GitHubPullRequest(
            number=42,
            title="ClaudeChain: Add feature",
            state="open",
            created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudechain"],
            head_ref_name="claude-chain-my-project-a3f2b891",
        )

    def test_project_stats_initializes_empty_tasks_list(self):
        """Should initialize with empty tasks list"""
        stats = ProjectStats("my-project", "claude-chain/my-project/spec.md")

        assert stats.tasks == []
        assert isinstance(stats.tasks, list)

    def test_project_stats_initializes_empty_orphaned_prs_list(self):
        """Should initialize with empty orphaned_prs list"""
        stats = ProjectStats("my-project", "claude-chain/my-project/spec.md")

        assert stats.orphaned_prs == []
        assert isinstance(stats.orphaned_prs, list)

    def test_project_stats_can_add_tasks(self, sample_pr):
        """Should allow adding TaskWithPR to tasks list"""
        stats = ProjectStats("my-project", "claude-chain/my-project/spec.md")

        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add feature",
            status=TaskStatus.IN_PROGRESS,
            pr=sample_pr,
        )

        stats.tasks.append(task)

        assert len(stats.tasks) == 1
        assert stats.tasks[0].task_hash == "a3f2b891"

    def test_project_stats_can_add_orphaned_prs(self, sample_pr):
        """Should allow adding GitHubPullRequest to orphaned_prs list"""
        stats = ProjectStats("my-project", "claude-chain/my-project/spec.md")

        stats.orphaned_prs.append(sample_pr)

        assert len(stats.orphaned_prs) == 1
        assert stats.orphaned_prs[0].number == 42

    def test_project_stats_tasks_and_orphaned_prs_independent(self, sample_pr):
        """Should maintain tasks and orphaned_prs as independent lists"""
        stats = ProjectStats("my-project", "claude-chain/my-project/spec.md")

        task = TaskWithPR(
            task_hash="a3f2b891",
            description="Add feature",
            status=TaskStatus.PENDING,
            pr=None,
        )

        stats.tasks.append(task)
        stats.orphaned_prs.append(sample_pr)

        assert len(stats.tasks) == 1
        assert len(stats.orphaned_prs) == 1
        assert stats.tasks[0].pr is None
        assert stats.orphaned_prs[0].number == 42
