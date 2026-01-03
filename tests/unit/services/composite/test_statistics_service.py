"""Tests for statistics collection and formatting"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

from claudestep.domain.models import TeamMemberStats, ProjectStats, StatisticsReport, PRReference, TaskStatus, TaskWithPR
from claudestep.domain.github_models import GitHubPullRequest, GitHubUser
from claudestep.domain.project import Project
from claudestep.domain.spec_content import SpecContent
from claudestep.services.composite.statistics_service import StatisticsService

from tests.builders import SpecFileBuilder


class TestProgressBar:
    """Test progress bar formatting"""

    def test_empty_progress(self):
        """Test progress bar with 0% completion"""
        stats = ProjectStats("test", "/fake/path")
        stats.total_tasks = 10
        stats.completed_tasks = 0
        bar = stats.format_progress_bar(10)
        assert "░░░░░░░░░░" in bar
        assert "0%" in bar

    def test_full_progress(self):
        """Test progress bar with 100% completion"""
        stats = ProjectStats("test", "/fake/path")
        stats.total_tasks = 10
        stats.completed_tasks = 10
        bar = stats.format_progress_bar(10)
        assert "██████████" in bar
        assert "100%" in bar

    def test_partial_progress(self):
        """Test progress bar with 50% completion"""
        stats = ProjectStats("test", "/fake/path")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        bar = stats.format_progress_bar(10)
        assert "█████░░░░░" in bar
        assert "50%" in bar

    def test_zero_tasks(self):
        """Test progress bar with zero total tasks"""
        stats = ProjectStats("test", "/fake/path")
        stats.total_tasks = 0
        stats.completed_tasks = 0
        bar = stats.format_progress_bar(10)
        assert "░░░░░░░░░░" in bar
        assert "0%" in bar

    def test_custom_width(self):
        """Test progress bar with custom width"""
        stats = ProjectStats("test", "/fake/path")
        stats.total_tasks = 20
        stats.completed_tasks = 10
        bar = stats.format_progress_bar(20)
        # 50% of 20 = 10 filled blocks
        assert "██████████░░░░░░░░░░" in bar
        assert "50%" in bar


class TestTaskCounting:
    """Test task counting from spec.md files using SpecContent domain model"""

    def test_count_tasks_all_pending(self, tmp_path):
        """Test counting with all tasks pending"""
        spec_path = (SpecFileBuilder()
                     .with_title("My Project")
                     .add_section("## Checklist")
                     .add_tasks("Task 1", "Task 2", "Task 3")
                     .write_to(tmp_path))

        content = spec_path.read_text()
        project = Project("test-project")
        spec = SpecContent(project, content)
        assert spec.total_tasks == 3
        assert spec.completed_tasks == 0

    def test_count_tasks_mixed(self, tmp_path):
        """Test counting with mixed completion status"""
        spec_path = (SpecFileBuilder()
                     .with_title("My Project")
                     .add_section("## Checklist")
                     .add_completed_task("Task 1 (done)")
                     .add_task("Task 2 (pending)")
                     .add_completed_task("Task 3 (done)")
                     .add_task("Task 4 (pending)")
                     .write_to(tmp_path))

        content = spec_path.read_text()
        project = Project("test-project")
        spec = SpecContent(project, content)
        assert spec.total_tasks == 4
        assert spec.completed_tasks == 2

    def test_count_tasks_case_insensitive(self, tmp_path):
        """Test counting with uppercase X for completed tasks"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
- [X] Task 1 (uppercase)
- [x] Task 2 (lowercase)
- [ ] Task 3 (pending)
        """)
        content = spec_file.read_text()
        project = Project("test-project")
        spec = SpecContent(project, content)
        assert spec.total_tasks == 3
        assert spec.completed_tasks == 2

    def test_count_tasks_with_indentation(self, tmp_path):
        """Test counting with indented tasks"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
## Main Tasks
  - [x] Indented completed task
  - [ ] Indented pending task
- [x] Non-indented completed
- [ ] Non-indented pending
        """)
        content = spec_file.read_text()
        project = Project("test-project")
        spec = SpecContent(project, content)
        assert spec.total_tasks == 4
        assert spec.completed_tasks == 2

    def test_count_tasks_empty_file(self, tmp_path):
        """Test counting with no tasks"""
        spec_path = (SpecFileBuilder()
                     .with_title("Project")
                     .add_section("No tasks yet!")
                     .write_to(tmp_path))

        content = spec_path.read_text()
        project = Project("test-project")
        spec = SpecContent(project, content)
        assert spec.total_tasks == 0
        assert spec.completed_tasks == 0


class TestTeamMemberStats:
    """Test TeamMemberStats model"""

    def test_initialization(self):
        """Test basic initialization"""
        stats = TeamMemberStats("alice")
        assert stats.username == "alice"
        assert stats.merged_count == 0
        assert stats.open_count == 0

    def test_merged_count(self):
        """Test merged_count property"""
        stats = TeamMemberStats("bob")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        stats.merged_prs = [
            PRReference(pr_number=1, title="Test 1", project="proj1", timestamp=timestamp),
            PRReference(pr_number=2, title="Test 2", project="proj1", timestamp=timestamp),
        ]
        assert stats.merged_count == 2

    def test_open_count(self):
        """Test open_count property"""
        stats = TeamMemberStats("charlie")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        stats.open_prs = [
            PRReference(pr_number=3, title="Test 3", project="proj1", timestamp=timestamp),
        ]
        assert stats.open_count == 1

    def test_format_summary_with_activity(self):
        """Test summary formatting with activity"""
        stats = TeamMemberStats("alice")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        stats.merged_prs = [PRReference(pr_number=1, title="Test", project="proj1", timestamp=timestamp)]
        stats.open_prs = [PRReference(pr_number=2, title="Test", project="proj1", timestamp=timestamp)]

        summary = stats.format_summary()
        assert "@alice" in summary
        assert "Merged: 1" in summary
        assert "Open: 1" in summary
        assert "✅" in summary

    def test_format_summary_no_activity(self):
        """Test summary formatting with no activity"""
        stats = TeamMemberStats("bob")

        summary = stats.format_summary()
        assert "@bob" in summary
        assert "Merged: 0" in summary
        assert "Open: 0" in summary
        assert "💤" in summary


class TestProjectStats:
    """Test ProjectStats model"""

    def test_completion_percentage(self):
        """Test completion percentage calculation"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 20
        stats.completed_tasks = 10
        assert stats.completion_percentage == 50.0

    def test_completion_percentage_zero_tasks(self):
        """Test completion percentage with zero tasks"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 0
        stats.completed_tasks = 0
        assert stats.completion_percentage == 0.0

    def test_completion_percentage_all_complete(self):
        """Test completion percentage at 100%"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 5
        stats.completed_tasks = 5
        assert stats.completion_percentage == 100.0

    def test_format_summary(self):
        """Test summary formatting"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 7
        stats.in_progress_tasks = 2
        stats.pending_tasks = 1

        summary = stats.format_summary()
        assert "my-project" in summary
        assert "7/10 complete" in summary
        # Check compact format with emojis
        assert "✅7" in summary
        assert "🔄2" in summary
        assert "⏸️1" in summary
        assert "█" in summary  # Progress bar
        assert "70%" in summary

    def test_has_remaining_tasks_true_when_pending_and_no_in_progress(self):
        """Should return True when there are pending tasks but no open PRs"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.in_progress_tasks = 0  # No open PRs
        stats.pending_tasks = 5      # Still have work to do

        assert stats.has_remaining_tasks is True

    def test_has_remaining_tasks_false_when_has_in_progress(self):
        """Should return False when there are open PRs in progress"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.in_progress_tasks = 2  # PRs are open
        stats.pending_tasks = 3

        assert stats.has_remaining_tasks is False

    def test_has_remaining_tasks_false_when_all_done(self):
        """Should return False when all tasks are complete"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 10
        stats.in_progress_tasks = 0
        stats.pending_tasks = 0

        assert stats.has_remaining_tasks is False

    def test_has_remaining_tasks_false_when_no_pending(self):
        """Should return False when there are no pending tasks"""
        stats = ProjectStats("my-project", "/path/to/spec.md")
        stats.total_tasks = 5
        stats.completed_tasks = 3
        stats.in_progress_tasks = 2  # All remaining tasks are in progress
        stats.pending_tasks = 0

        assert stats.has_remaining_tasks is False


class TestStatisticsReport:
    """Test StatisticsReport model"""

    def test_initialization(self):
        """Test basic initialization"""
        report = StatisticsReport()
        assert len(report.team_stats) == 0
        assert len(report.project_stats) == 0
        assert report.generated_at is None

    def test_add_team_member(self):
        """Test adding team member stats"""
        report = StatisticsReport()
        stats = TeamMemberStats("alice")
        report.add_team_member(stats)
        assert "alice" in report.team_stats
        assert report.team_stats["alice"] == stats

    def test_add_project(self):
        """Test adding project stats"""
        report = StatisticsReport()
        stats = ProjectStats("my-project", "/path/spec.md")
        report.add_project(stats)
        assert "my-project" in report.project_stats
        assert report.project_stats["my-project"] == stats

    def test_projects_needing_attention_empty(self):
        """Should return empty list when no projects need attention"""
        report = StatisticsReport()

        # Project with open PRs and no stale
        healthy = ProjectStats("healthy-project", "/path/spec.md")
        healthy.total_tasks = 10
        healthy.completed_tasks = 5
        healthy.in_progress_tasks = 2  # Has open PRs
        healthy.pending_tasks = 3
        healthy.stale_pr_count = 0
        report.add_project(healthy)

        result = report.projects_needing_attention()
        assert result == []

    def test_projects_needing_attention_stale_prs(self):
        """Should include projects with stale PRs"""
        report = StatisticsReport()

        # Project with stale PRs
        stale = ProjectStats("stale-project", "/path/spec.md")
        stale.total_tasks = 10
        stale.completed_tasks = 5
        stale.in_progress_tasks = 2
        stale.pending_tasks = 3
        stale.stale_pr_count = 1  # Has stale PR
        report.add_project(stale)

        result = report.projects_needing_attention()
        assert len(result) == 1
        assert result[0].project_name == "stale-project"

    def test_projects_needing_attention_no_open_prs(self):
        """Should include projects with remaining tasks but no open PRs"""
        report = StatisticsReport()

        # Project with no open PRs but pending tasks
        idle = ProjectStats("idle-project", "/path/spec.md")
        idle.total_tasks = 10
        idle.completed_tasks = 5
        idle.in_progress_tasks = 0  # No open PRs
        idle.pending_tasks = 5      # Tasks waiting
        idle.stale_pr_count = 0
        report.add_project(idle)

        result = report.projects_needing_attention()
        assert len(result) == 1
        assert result[0].project_name == "idle-project"

    def test_projects_needing_attention_both_conditions(self):
        """Should include projects that meet either stale or no-PRs condition"""
        report = StatisticsReport()

        # Healthy project
        healthy = ProjectStats("healthy", "/path/spec.md")
        healthy.total_tasks = 10
        healthy.completed_tasks = 5
        healthy.in_progress_tasks = 2
        healthy.pending_tasks = 3
        healthy.stale_pr_count = 0
        report.add_project(healthy)

        # Project with stale PRs
        stale = ProjectStats("stale", "/path/spec.md")
        stale.total_tasks = 10
        stale.completed_tasks = 5
        stale.in_progress_tasks = 2
        stale.pending_tasks = 3
        stale.stale_pr_count = 2
        report.add_project(stale)

        # Project with no open PRs
        idle = ProjectStats("idle", "/path/spec.md")
        idle.total_tasks = 10
        idle.completed_tasks = 5
        idle.in_progress_tasks = 0
        idle.pending_tasks = 5
        idle.stale_pr_count = 0
        report.add_project(idle)

        result = report.projects_needing_attention()
        assert len(result) == 2
        project_names = [p.project_name for p in result]
        assert "idle" in project_names
        assert "stale" in project_names
        assert "healthy" not in project_names

    def test_projects_needing_attention_sorted_by_name(self):
        """Should return projects sorted alphabetically by name"""
        report = StatisticsReport()

        # Add projects out of order
        for name in ["zebra", "alpha", "middle"]:
            project = ProjectStats(name, "/path/spec.md")
            project.pending_tasks = 5
            project.in_progress_tasks = 0  # No open PRs
            report.add_project(project)

        result = report.projects_needing_attention()
        assert len(result) == 3
        assert result[0].project_name == "alpha"
        assert result[1].project_name == "middle"
        assert result[2].project_name == "zebra"

    def test_projects_needing_attention_completed_projects_excluded(self):
        """Should not include completed projects even with no open PRs"""
        report = StatisticsReport()

        # Completed project
        complete = ProjectStats("complete", "/path/spec.md")
        complete.total_tasks = 10
        complete.completed_tasks = 10
        complete.in_progress_tasks = 0
        complete.pending_tasks = 0  # No pending tasks
        complete.stale_pr_count = 0
        report.add_project(complete)

        result = report.projects_needing_attention()
        assert result == []

    def test_projects_needing_attention_orphaned_prs(self):
        """Should include projects with orphaned PRs"""
        report = StatisticsReport()

        # Project with orphaned PRs but otherwise healthy
        project = ProjectStats("orphaned-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 2  # Has open PRs
        project.pending_tasks = 3
        project.stale_pr_count = 0

        # Add orphaned PR
        orphaned_pr = GitHubPullRequest(
            number=99,
            title="Orphaned PR",
            state="open",
            head_ref_name="claude-step-project-deadbeef",
            labels=["claudestep"],
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
        )
        project.orphaned_prs.append(orphaned_pr)
        report.add_project(project)

        result = report.projects_needing_attention()
        assert len(result) == 1
        assert result[0].project_name == "orphaned-project"

    def test_format_for_slack_empty(self):
        """Test Slack formatting with no data"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        slack_msg = report.format_for_slack()
        assert "ClaudeStep Statistics Report" in slack_msg
        assert "No projects found" in slack_msg
        # Empty report doesn't show leaderboard section

    def test_format_for_slack_with_data(self):
        """Test Slack formatting with data"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add project
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        report.add_project(project)

        # Add team member
        member = TeamMemberStats("alice")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        member.merged_prs = [PRReference(pr_number=1, title="Test", project="test", timestamp=timestamp)]
        report.add_team_member(member)

        # Without show_reviewer_stats, leaderboard is hidden
        slack_msg = report.format_for_slack()
        assert "ClaudeStep Statistics Report" in slack_msg
        assert "test-project" in slack_msg
        assert "alice" not in slack_msg  # Hidden by default
        assert "Leaderboard" not in slack_msg  # Hidden by default
        assert "```" in slack_msg  # Code block for table
        assert "Total" in slack_msg  # Table header
        assert "2025-01-01" in slack_msg

        # With show_reviewer_stats=True, leaderboard appears
        slack_msg_with_reviewers = report.format_for_slack(show_reviewer_stats=True)
        assert "alice" in slack_msg_with_reviewers
        assert "Merged" in slack_msg_with_reviewers  # Leaderboard header

    def test_format_for_slack_includes_base_branch(self):
        """Test Slack formatting includes base branch when set on report"""
        report = StatisticsReport(base_branch="dev")
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add a project
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        report.add_project(project)

        # With base_branch set on report
        slack_msg = report.format_for_slack()
        assert "Branch: dev" in slack_msg
        assert "2025-01-01" in slack_msg  # Timestamp still present

    def test_format_for_slack_orphaned_prs_in_warnings(self):
        """Test that orphaned PRs appear in the warnings section"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add project with orphaned PRs
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 2

        # Add orphaned PR (merged)
        orphaned_merged = GitHubPullRequest(
            number=42,
            title="Orphaned Merged PR",
            state="closed",
            merged_at=datetime.now(timezone.utc),
            head_ref_name="claude-step-project-deadbeef",
            labels=["claudestep"],
            created_at=datetime.now(timezone.utc),
            assignees=[],
        )
        # Add orphaned PR (open)
        orphaned_open = GitHubPullRequest(
            number=43,
            title="Orphaned Open PR",
            state="open",
            head_ref_name="claude-step-project-abcd1234",
            labels=["claudestep"],
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            merged_at=None,
            assignees=[],
        )
        project.orphaned_prs.append(orphaned_merged)
        project.orphaned_prs.append(orphaned_open)
        report.add_project(project)

        slack_msg = report.format_for_slack()
        assert "Needs Attention" in slack_msg
        # Only open orphaned PRs appear in Slack (merged ones don't need action)
        assert "#42" not in slack_msg  # Merged orphaned PR not shown
        assert "#43" in slack_msg  # Open orphaned PR shown
        assert "orphaned" in slack_msg

        # Without base_branch
        report_no_branch = StatisticsReport()
        report_no_branch.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        report_no_branch.add_project(project)
        slack_msg_no_branch = report_no_branch.format_for_slack()
        assert "Branch:" not in slack_msg_no_branch

    def test_format_for_pr_comment_single_project(self):
        """Test PR comment formatting with single project"""
        report = StatisticsReport()
        project = ProjectStats("my-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 8
        report.add_project(project)

        comment = report.format_for_pr_comment()
        assert "my-project" in comment
        assert "8/10" in comment
        assert "80%" in comment

    def test_format_for_pr_comment_multiple_projects(self):
        """Test PR comment formatting with multiple projects"""
        report = StatisticsReport()

        project1 = ProjectStats("project-a", "/path/a.md")
        project1.total_tasks = 10
        project1.completed_tasks = 5
        report.add_project(project1)

        project2 = ProjectStats("project-b", "/path/b.md")
        project2.total_tasks = 20
        project2.completed_tasks = 10
        report.add_project(project2)

        comment = report.format_for_pr_comment()
        assert "Project Progress" in comment
        assert "project-a" in comment
        assert "project-b" in comment

    def test_format_for_pr_comment_includes_base_branch(self):
        """Test PR comment formatting includes base branch when set"""
        report = StatisticsReport(base_branch="dev")
        project = ProjectStats("my-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 8
        report.add_project(project)

        comment = report.format_for_pr_comment()
        assert "Branch: dev" in comment

        # Without base_branch
        report_no_branch = StatisticsReport()
        report_no_branch.add_project(project)
        comment_no_branch = report_no_branch.format_for_pr_comment()
        assert "Branch:" not in comment_no_branch

    def test_to_json(self):
        """Test JSON serialization"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add project
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 2
        project.pending_tasks = 3
        report.add_project(project)

        # Add team member
        member = TeamMemberStats("alice")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        member.merged_prs = [PRReference(pr_number=1, title="Test", project="test", timestamp=timestamp)]
        member.open_prs = []
        report.add_team_member(member)

        json_str = report.to_json()
        data = json.loads(json_str)

        assert "generated_at" in data
        assert "projects" in data
        assert "team_members" in data
        assert "test-project" in data["projects"]
        assert data["projects"]["test-project"]["total_tasks"] == 10
        assert data["projects"]["test-project"]["completed_tasks"] == 5
        assert data["projects"]["test-project"]["completion_percentage"] == 50.0
        assert "alice" in data["team_members"]
        assert data["team_members"]["alice"]["merged_count"] == 1
        assert data["team_members"]["alice"]["open_count"] == 0

    def test_to_json_includes_base_branch(self):
        """Test JSON serialization includes base branch"""
        report = StatisticsReport(base_branch="dev")
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        json_str = report.to_json()
        data = json.loads(json_str)

        assert "base_branch" in data
        assert data["base_branch"] == "dev"

        # Without base_branch
        report_no_branch = StatisticsReport()
        report_no_branch.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        json_str_no_branch = report_no_branch.to_json()
        data_no_branch = json.loads(json_str_no_branch)
        assert data_no_branch["base_branch"] is None

    def test_team_stats_sorting(self):
        """Test that team stats are sorted by activity when enabled"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add members with different activity levels
        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(5)]
        report.add_team_member(alice)

        bob = TeamMemberStats("bob")
        bob.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(2)]
        report.add_team_member(bob)

        charlie = TeamMemberStats("charlie")
        charlie.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(10)]
        report.add_team_member(charlie)

        # Must enable show_reviewer_stats to see team stats in output
        slack_msg = report.format_for_slack(show_reviewer_stats=True)

        # Charlie should appear first (most active), then alice, then bob
        # Table format doesn't use @ prefix
        charlie_pos = slack_msg.find("charlie")
        alice_pos = slack_msg.find("alice")
        bob_pos = slack_msg.find("bob")

        assert charlie_pos < alice_pos < bob_pos


class TestLeaderboard:
    """Test leaderboard formatting"""

    def test_leaderboard_empty(self):
        """Test leaderboard with no team members"""
        report = StatisticsReport()
        leaderboard = report.format_leaderboard()
        assert leaderboard == ""

    def test_leaderboard_no_activity(self):
        """Test leaderboard with team members but no activity"""
        report = StatisticsReport()
        alice = TeamMemberStats("alice")
        bob = TeamMemberStats("bob")
        report.add_team_member(alice)
        report.add_team_member(bob)

        leaderboard = report.format_leaderboard()
        assert leaderboard == ""

    def test_leaderboard_single_member(self):
        """Test leaderboard with one active member"""
        report = StatisticsReport()
        alice = TeamMemberStats("alice")
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        alice.merged_prs = [PRReference(pr_number=1, title="Test", project="proj", timestamp=timestamp)]
        report.add_team_member(alice)

        leaderboard = report.format_leaderboard()
        assert "🏆 Leaderboard" in leaderboard
        assert "🥇" in leaderboard
        assert "@alice" in leaderboard
        assert "1 PR(s) merged" in leaderboard
        assert "██████████" in leaderboard  # Full bar for the only member

    def test_leaderboard_top_three_medals(self):
        """Test leaderboard shows medals for top 3"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Add 5 members with different activity levels
        for i, name in enumerate(["alice", "bob", "charlie", "david", "eve"]):
            member = TeamMemberStats(name)
            # alice: 5, bob: 4, charlie: 3, david: 2, eve: 1
            member.merged_prs = [PRReference(pr_number=j, title=f"PR {j}", project="proj", timestamp=timestamp) for j in range(5 - i)]
            report.add_team_member(member)

        leaderboard = report.format_leaderboard()

        # Check medals are present
        assert "🥇" in leaderboard
        assert "🥈" in leaderboard
        assert "🥉" in leaderboard
        assert "#4" in leaderboard
        assert "#5" in leaderboard

        # Check ordering
        alice_pos = leaderboard.find("@alice")
        bob_pos = leaderboard.find("@bob")
        charlie_pos = leaderboard.find("@charlie")
        david_pos = leaderboard.find("@david")
        eve_pos = leaderboard.find("@eve")

        assert alice_pos < bob_pos < charlie_pos < david_pos < eve_pos

    def test_leaderboard_shows_merged_counts(self):
        """Test leaderboard displays correct merged PR counts"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(10)]
        report.add_team_member(alice)

        bob = TeamMemberStats("bob")
        bob.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(3)]
        report.add_team_member(bob)

        leaderboard = report.format_leaderboard()

        assert "10 PR(s) merged" in leaderboard
        assert "3 PR(s) merged" in leaderboard

    def test_leaderboard_shows_open_prs(self):
        """Test leaderboard shows open PRs when present"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=1, title="PR 1", project="proj", timestamp=timestamp)]
        alice.open_prs = [
            PRReference(pr_number=2, title="PR 2", project="proj", timestamp=timestamp),
            PRReference(pr_number=3, title="PR 3", project="proj", timestamp=timestamp)
        ]
        report.add_team_member(alice)

        leaderboard = report.format_leaderboard()

        assert "(2 open PR(s))" in leaderboard

    def test_leaderboard_activity_bar(self):
        """Test leaderboard activity bar scales correctly"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # alice has 10 merged (should get full bar)
        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(10)]
        report.add_team_member(alice)

        # bob has 5 merged (should get half bar)
        bob = TeamMemberStats("bob")
        bob.merged_prs = [PRReference(pr_number=i, title=f"PR {i}", project="proj", timestamp=timestamp) for i in range(5)]
        report.add_team_member(bob)

        leaderboard = report.format_leaderboard()

        # alice should have full bar (10 filled blocks)
        lines = leaderboard.split("\n")
        alice_line_idx = next(i for i, line in enumerate(lines) if "@alice" in line)
        alice_bar = lines[alice_line_idx + 1].strip()
        assert alice_bar == "██████████"

        # bob should have half bar (5 filled, 5 empty)
        bob_line_idx = next(i for i, line in enumerate(lines) if "@bob" in line)
        bob_bar = lines[bob_line_idx + 1].strip()
        assert bob_bar == "█████░░░░░"

    def test_leaderboard_filters_inactive_members(self):
        """Test leaderboard only shows members with merged PRs"""
        report = StatisticsReport()
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Active member
        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=1, title="PR 1", project="proj", timestamp=timestamp)]
        report.add_team_member(alice)

        # Inactive member (has open PRs but no merges)
        bob = TeamMemberStats("bob")
        bob.open_prs = [PRReference(pr_number=2, title="PR 2", project="proj", timestamp=timestamp)]
        report.add_team_member(bob)

        # Completely inactive member
        charlie = TeamMemberStats("charlie")
        report.add_team_member(charlie)

        leaderboard = report.format_leaderboard()

        assert "@alice" in leaderboard
        assert "@bob" not in leaderboard
        assert "@charlie" not in leaderboard

    def test_leaderboard_in_slack_output(self):
        """Test leaderboard appears in Slack formatted output when enabled"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        timestamp = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        alice = TeamMemberStats("alice")
        alice.merged_prs = [PRReference(pr_number=1, title="PR 1", project="proj", timestamp=timestamp)]
        report.add_team_member(alice)

        # Leaderboard hidden by default
        slack_msg_default = report.format_for_slack()
        assert "🏆 Leaderboard" not in slack_msg_default

        # Leaderboard visible when enabled
        slack_msg = report.format_for_slack(show_reviewer_stats=True)

        # Leaderboard should appear before project progress
        assert "🏆 Leaderboard" in slack_msg
        leaderboard_pos = slack_msg.find("🏆 Leaderboard")
        project_pos = slack_msg.find("📊 Project Progress")

        # Leaderboard should come first (most engaging)
        assert leaderboard_pos < project_pos


class TestWarningsSection:
    """Test warnings section in Slack output"""

    def test_warnings_section_with_stale_prs(self):
        """Should show detailed warnings section with stale PR info"""
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser
        from datetime import timedelta

        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # Create a stale PR (10 days old)
        stale_pr = GitHubPullRequest(
            number=123,
            title="Stale PR",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-a1b2c3d4"
        )

        project = ProjectStats("api-cleanup", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 1
        project.pending_tasks = 4
        project.stale_pr_count = 1
        project.open_prs = [stale_pr]
        report.add_project(project)

        slack_msg = report.format_for_slack()
        assert "Needs Attention" in slack_msg
        assert "#123" in slack_msg
        assert "stale" in slack_msg
        assert "alice" in slack_msg

    def test_warnings_section_with_no_prs(self):
        """Should show warnings section for projects with no open PRs"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        project = ProjectStats("idle-project", "/path/spec.md")
        project.total_tasks = 20
        project.completed_tasks = 3
        project.in_progress_tasks = 0
        project.pending_tasks = 17
        project.stale_pr_count = 0
        report.add_project(project)

        slack_msg = report.format_for_slack()
        assert "Needs Attention" in slack_msg
        assert "No open PRs (17 tasks remaining)" in slack_msg

    def test_no_warnings_section_for_healthy_projects(self):
        """Should not show warnings section when all projects are healthy"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        project = ProjectStats("healthy-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 2
        project.pending_tasks = 3
        project.stale_pr_count = 0
        report.add_project(project)

        slack_msg = report.format_for_slack()
        assert "⚠️ Projects Needing Attention" not in slack_msg

    def test_stale_threshold_respected_in_warnings(self):
        """Should respect stale_pr_days threshold when formatting warnings"""
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser
        from datetime import timedelta

        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        # PR that's 5 days old
        pr = GitHubPullRequest(
            number=99,
            title="5 day old PR",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            merged_at=None,
            assignees=[GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-e5f6g7h8"
        )

        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 1
        project.pending_tasks = 4
        project.stale_pr_count = 1  # Marked as stale by statistics service
        project.open_prs = [pr]
        report.add_project(project)

        # With 7-day threshold: PR is not stale (5 < 7)
        slack_msg_7 = report.format_for_slack(stale_pr_days=7)
        # The PR appears but without "stale" indicator in the Needs Attention section
        # (Note: Status column in table may still show stale based on stale_pr_count)
        assert "#99 (5d, bob)" in slack_msg_7  # PR shown but no stale indicator

        # With 3-day threshold: PR is stale (5 >= 3)
        slack_msg_3 = report.format_for_slack(stale_pr_days=3)
        assert "#99 (5d, bob, stale)" in slack_msg_3  # PR shown with stale indicator


class TestCostExtraction:
    """Test cost extraction from PR comments"""

    def test_extract_cost_from_valid_comment(self):
        """Test extracting cost from a valid cost breakdown comment"""
        comment = """## 💰 Cost Breakdown

This PR was generated using Claude Code with the following costs:

| Component | Cost (USD) |
|-----------|------------|
| Main refactoring task | $0.12 |
| PR summary generation | $0.00 |
| **Total** | **$0.13** |

---
*Cost tracking by ClaudeStep • [View workflow run](https://example.com)*
"""
        cost = StatisticsService.extract_cost_from_comment(comment)
        assert cost == 0.13

    def test_extract_cost_no_cost_comment(self):
        """Test extracting cost from comment without cost breakdown"""
        comment = "This is a regular comment without cost information."
        cost = StatisticsService.extract_cost_from_comment(comment)
        assert cost is None

    def test_extract_cost_malformed_comment(self):
        """Test extracting cost from malformed cost comment"""
        comment = """## 💰 Cost Breakdown

| Component | Cost |
| Total | $invalid |
"""
        cost = StatisticsService.extract_cost_from_comment(comment)
        assert cost is None

    def test_project_stats_has_cost_field(self):
        """Test that ProjectStats has total_cost_usd field"""
        stats = ProjectStats("test-project", "/fake/spec.md")
        assert hasattr(stats, "total_cost_usd")
        assert stats.total_cost_usd == 0.0

    def test_slack_format_includes_cost(self):
        """Test that Slack format includes cost column"""
        report = StatisticsReport()

        # Add a project with cost data
        stats = ProjectStats("test-project", "/fake/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.in_progress_tasks = 2
        stats.pending_tasks = 3
        stats.total_cost_usd = 1.234567
        report.add_project(stats)

        slack_msg = report.format_for_slack()

        # Check that cost column header is present
        assert "Cost" in slack_msg

        # Check that cost value is formatted correctly
        assert "$1.23" in slack_msg

    def test_slack_format_zero_cost(self):
        """Test that Slack format shows '-' for zero cost"""
        report = StatisticsReport()

        # Add a project with no cost data
        stats = ProjectStats("test-project", "/fake/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.total_cost_usd = 0.0
        report.add_project(stats)

        slack_msg = report.format_for_slack()

        # Should show "-" for zero cost
        assert "Cost" in slack_msg

    def test_format_summary_includes_cost_when_present(self):
        """Test that format_summary includes cost when total_cost_usd > 0"""
        stats = ProjectStats("test-project", "/fake/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.in_progress_tasks = 2
        stats.pending_tasks = 3
        stats.total_cost_usd = 1.23

        summary = stats.format_summary()

        # Should include cost with money emoji
        assert "💰$1.23" in summary

    def test_format_summary_excludes_cost_when_zero(self):
        """Test that format_summary does not include cost when total_cost_usd is 0"""
        stats = ProjectStats("test-project", "/fake/spec.md")
        stats.total_tasks = 10
        stats.completed_tasks = 5
        stats.in_progress_tasks = 2
        stats.pending_tasks = 3
        stats.total_cost_usd = 0.0

        summary = stats.format_summary()

        # Should not include money emoji
        assert "💰" not in summary


class TestCostAggregationFromArtifacts:
    """Test cost aggregation from artifacts in statistics collection"""

    @patch("claudestep.services.composite.statistics_service.find_project_artifacts")
    def test_aggregate_costs_from_multiple_artifacts(self, mock_find_artifacts):
        """Should sum costs from all artifacts for a project"""
        from claudestep.services.composite.artifact_service import ProjectArtifact
        from claudestep.domain.models import TaskMetadata, AITask

        now = datetime.now(timezone.utc)

        # Create mock artifacts with different costs
        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-abc12345.json",
                workflow_run_id=100,
                metadata=TaskMetadata(
                    task_index=1,
                    task_description="Task 1",
                    project="test",
                    branch_name="claude-step-test-abc12345",
                    reviewer="alice",
                    created_at=now,
                    workflow_run_id=100,
                    pr_number=10,
                    ai_tasks=[
                        AITask(type="PRCreation", model="claude-sonnet-4", cost_usd=0.15, created_at=now),
                        AITask(type="PRSummary", model="claude-sonnet-4", cost_usd=0.02, created_at=now),
                    ]
                ),
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="task-metadata-test-def67890.json",
                workflow_run_id=101,
                metadata=TaskMetadata(
                    task_index=2,
                    task_description="Task 2",
                    project="test",
                    branch_name="claude-step-test-def67890",
                    reviewer="bob",
                    created_at=now,
                    workflow_run_id=101,
                    pr_number=11,
                    ai_tasks=[
                        AITask(type="PRCreation", model="claude-sonnet-4", cost_usd=0.25, created_at=now),
                    ]
                ),
            ),
            ProjectArtifact(
                artifact_id=3,
                artifact_name="task-metadata-test-ghi11111.json",
                workflow_run_id=102,
                metadata=TaskMetadata(
                    task_index=3,
                    task_description="Task 3",
                    project="test",
                    branch_name="claude-step-test-ghi11111",
                    reviewer="charlie",
                    created_at=now,
                    workflow_run_id=102,
                    pr_number=12,
                    ai_tasks=[
                        AITask(type="PRCreation", model="claude-opus-4", cost_usd=0.50, created_at=now),
                        AITask(type="PRSummary", model="claude-sonnet-4", cost_usd=0.03, created_at=now),
                    ]
                ),
            ),
        ]

        # Create service and test aggregation
        mock_repo = Mock()
        mock_pr_service = Mock()
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")

        total = service._aggregate_costs_from_artifacts("test", "claudestep")

        # Assert: 0.15 + 0.02 + 0.25 + 0.50 + 0.03 = 0.95
        assert total == pytest.approx(0.95, rel=1e-6)

    @patch("claudestep.services.composite.statistics_service.find_project_artifacts")
    def test_aggregate_costs_handles_missing_metadata(self, mock_find_artifacts):
        """Should skip artifacts without metadata (legacy PRs)"""
        from claudestep.services.composite.artifact_service import ProjectArtifact
        from claudestep.domain.models import TaskMetadata, AITask

        now = datetime.now(timezone.utc)

        mock_find_artifacts.return_value = [
            ProjectArtifact(
                artifact_id=1,
                artifact_name="task-metadata-test-abc12345.json",
                workflow_run_id=100,
                metadata=TaskMetadata(
                    task_index=1,
                    task_description="Task 1",
                    project="test",
                    branch_name="claude-step-test-abc12345",
                    reviewer="alice",
                    created_at=now,
                    workflow_run_id=100,
                    pr_number=10,
                    ai_tasks=[
                        AITask(type="PRCreation", model="claude-sonnet-4", cost_usd=0.20, created_at=now),
                    ]
                ),
            ),
            ProjectArtifact(
                artifact_id=2,
                artifact_name="task-metadata-test-def67890.json",
                workflow_run_id=101,
                metadata=None,  # Failed to download/parse - legacy PR
            ),
        ]

        mock_repo = Mock()
        mock_pr_service = Mock()
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")

        total = service._aggregate_costs_from_artifacts("test", "claudestep")

        # Should only count the first artifact
        assert total == pytest.approx(0.20, rel=1e-6)

    @patch("claudestep.services.composite.statistics_service.find_project_artifacts")
    def test_aggregate_costs_returns_zero_when_no_artifacts(self, mock_find_artifacts):
        """Should return 0.0 when no artifacts are found"""
        mock_find_artifacts.return_value = []

        mock_repo = Mock()
        mock_pr_service = Mock()
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")

        total = service._aggregate_costs_from_artifacts("test", "claudestep")

        assert total == 0.0


class TestCollectTeamMemberStats:
    """Test team member statistics collection from GitHub API"""

    def test_collect_stats_basic(self):
        """Test basic team member stats collection from GitHub"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest

        # Create mock GitHub PRs with valid 8-char hex hashes
        pr1 = GitHubPullRequest(
            number=1,
            title="Fix bug",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            merged_at=datetime.now(timezone.utc) - timedelta(days=4),
            assignees=["alice"],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-a3f2b891"
        )

        pr2 = GitHubPullRequest(
            number=2,
            title="Add feature",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            merged_at=datetime.now(timezone.utc) - timedelta(days=2),
            assignees=["bob"],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-f7c4d3e2"
        )

        pr3 = GitHubPullRequest(
            number=3,
            title="WIP",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
            merged_at=None,
            assignees=["alice"],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-1a2b3c4d"
        )

        # Mock PROperationsService
        mock_repo = Mock()
        mock_pr_service = Mock()
        mock_pr_service.get_all_prs.return_value = [pr1, pr2, pr3]

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice", "bob"], days_back=30)

        assert "alice" in stats
        assert "bob" in stats
        assert stats["alice"].merged_count == 1
        assert stats["alice"].open_count == 1
        assert stats["bob"].merged_count == 1
        assert stats["bob"].open_count == 0

    def test_collect_stats_empty_prs(self):
        """Test stats collection with no PRs from GitHub"""
        # Mock PROperationsService
        mock_repo = Mock()
        mock_pr_service = Mock()
        mock_pr_service.get_all_prs.return_value = []

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice"])

        assert "alice" in stats
        assert stats["alice"].merged_count == 0
        assert stats["alice"].open_count == 0

    def test_collect_stats_exception_handling(self):
        """Test that exceptions during collection are handled"""
        # Mock PROperationsService to raise exception
        mock_repo = Mock()
        mock_pr_service = Mock()
        mock_pr_service.get_all_prs.side_effect = Exception("GitHub API error")

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice"])

        # Should return empty stats but not crash
        assert "alice" in stats
        assert stats["alice"].merged_count == 0


class TestCollectProjectStats:
    """Test project statistics collection"""

    def test_collect_stats_success(self):
        """Test successful project stats collection"""
        from datetime import datetime, timezone
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        spec_content = """
- [x] Task 1
- [x] Task 2
- [ ] Task 3
- [ ] Task 4
        """

        # Mock open PRs from GitHub (one in-progress task)
        pr1 = GitHubPullRequest(
            number=3,
            title="Task 3",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-1a2b3c4d"
        )

        # Mock PROperationsService
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [pr1]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert stats.project_name == "test-project"
        assert stats.total_tasks == 4
        assert stats.completed_tasks == 2
        assert stats.in_progress_tasks == 1
        assert stats.pending_tasks == 1
        # Cost tracking disabled in Phase 4
        assert stats.total_cost_usd == 0.0

    def test_collect_stats_missing_spec(self):
        """Test stats collection with missing spec file"""
        # Mock ProjectRepository to return None
        mock_repo = Mock()
        mock_repo.load_spec.return_value = None

        # Mock PROperationsService
        mock_pr_service = Mock()

        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert stats is None

    def test_collect_stats_pr_error_propagates(self):
        """Test that PR fetch errors propagate to fail the workflow"""
        spec_content = "- [ ] Task 1\n- [x] Task 2"

        # Mock PROperationsService to raise exception on open PRs
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.side_effect = Exception("API error")

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test - exception should propagate
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        with pytest.raises(Exception, match="API error"):
            service.collect_project_stats("test-project", "main", "claudestep")

    def test_collect_stats_custom_base_branch(self):
        """Test that custom base_branch value is used correctly"""
        spec_content = "- [x] Task 1\n- [ ] Task 2"

        # Mock PROperationsService with no open PRs
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = []

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service with custom base_branch
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="develop")
        stats = service.collect_project_stats("test-project", "develop", "claudestep")

        # Verify the service uses the custom base_branch
        assert stats.project_name == "test-project"
        assert stats.total_tasks == 2
        assert stats.completed_tasks == 1

        # Verify repository was called with the custom branch
        mock_repo.load_spec.assert_called_with(project, "develop")


class TestCollectAllStatistics:
    """Test full statistics collection"""

    def test_collect_all_single_project(self):
        """Test collecting stats for a single project"""
        config_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 1
        """
        spec_content = "- [x] Task 1\n- [ ] Task 2"

        # Mock PROperationsService
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = []
        mock_pr_service.get_all_prs.return_value = []

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.project_configuration import ProjectConfiguration
        from claudestep.domain.spec_content import SpecContent

        project = Project("project1")
        mock_repo.load_configuration.return_value = ProjectConfiguration.from_yaml_string(project, config_content)
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")

        # Default: show_reviewer_stats=False, so team stats not collected
        report = service.collect_all_statistics("claude-step/project1/configuration.yml")
        assert len(report.project_stats) == 1
        assert "project1" in report.project_stats
        assert len(report.team_stats) == 0  # Not collected by default

        # With show_reviewer_stats=True, team stats are collected
        report_with_reviewers = service.collect_all_statistics(
            "claude-step/project1/configuration.yml",
            show_reviewer_stats=True
        )
        assert len(report_with_reviewers.project_stats) == 1
        assert "project1" in report_with_reviewers.project_stats
        assert len(report_with_reviewers.team_stats) == 2
        assert "alice" in report_with_reviewers.team_stats
        assert "bob" in report_with_reviewers.team_stats

    def test_collect_all_no_repository(self):
        """Test that missing GITHUB_REPOSITORY returns empty report"""
        # Create service with empty repo
        mock_repo = Mock()
        mock_pr_service = Mock()
        service = StatisticsService("", mock_repo, mock_pr_service, base_branch="main")
        report = service.collect_all_statistics()

        assert len(report.project_stats) == 0
        assert len(report.team_stats) == 0

    def test_collect_all_config_error(self):
        """Test handling of config loading errors"""
        # Mock ProjectRepository to return None (config not found)
        mock_repo = Mock()
        mock_repo.load_configuration.return_value = None

        # Mock PROperationsService
        mock_pr_service = Mock()

        # Create service and test
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        report = service.collect_all_statistics("/nonexistent/config.yml")

        assert len(report.project_stats) == 0


class TestGitHubPullRequestStaleness:
    """Tests for GitHubPullRequest days_open and is_stale methods"""

    def test_days_open_for_open_pr(self):
        """Should calculate days_open from created_at to now for open PRs"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        # Arrange - PR created 3 days ago
        created_at = datetime.now(timezone.utc) - timedelta(days=3)
        pr = GitHubPullRequest(
            number=42,
            title="Add new feature",
            state="open",
            created_at=created_at,
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-1a2b3c4d"
        )

        # Assert
        assert pr.number == 42
        assert pr.title == "Add new feature"
        assert pr.state == "open"
        assert pr.first_assignee == "alice"
        assert pr.created_at == created_at
        assert pr.days_open == 3
        assert pr.is_stale(stale_pr_days=7) is False  # 3 < 7 days

    def test_is_stale_when_old_enough(self):
        """Should mark PR as stale when days_open >= stale_pr_days"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        # Arrange - PR created 10 days ago
        created_at = datetime.now(timezone.utc) - timedelta(days=10)
        pr = GitHubPullRequest(
            number=123,
            title="Old PR",
            state="open",
            created_at=created_at,
            merged_at=None,
            assignees=[GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-5e6f7a8b"
        )

        # Assert
        assert pr.days_open == 10
        assert pr.is_stale(stale_pr_days=7) is True

    def test_first_assignee_with_no_assignees(self):
        """Should return None when no assignees"""
        from datetime import datetime, timezone
        from claudestep.domain.github_models import GitHubPullRequest

        # Arrange - PR with no assignees
        pr = GitHubPullRequest(
            number=99,
            title="Unassigned PR",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            labels=["claudestep"],
            head_ref_name="claude-step-test-9c0d1e2f"
        )

        # Assert
        assert pr.first_assignee is None

    def test_first_assignee_uses_first_when_multiple(self):
        """Should use first assignee when multiple are present"""
        from datetime import datetime, timezone
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        # Arrange - PR with multiple assignees
        pr = GitHubPullRequest(
            number=77,
            title="Multi-assignee PR",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="alice"), GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-3g4h5i6j"
        )

        # Assert
        assert pr.first_assignee == "alice"

    def test_days_open_for_merged_pr(self):
        """Should calculate days_open from created_at to merged_at for merged PRs"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        # Arrange - PR created 10 days ago, merged 5 days ago
        created_at = datetime.now(timezone.utc) - timedelta(days=10)
        merged_at = datetime.now(timezone.utc) - timedelta(days=5)
        pr = GitHubPullRequest(
            number=88,
            title="Merged PR",
            state="merged",
            created_at=created_at,
            merged_at=merged_at,
            assignees=[GitHubUser(login="charlie")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-m1n2o3p4"
        )

        # Assert - days_open should be 5 (created to merged), not 10 (created to now)
        assert pr.state == "merged"
        assert pr.days_open == 5


class TestStalePRTracking:
    """Tests for stale PR tracking in collect_project_stats"""

    def test_collect_stats_tracks_stale_prs(self):
        """Should track stale PRs and populate open_prs list"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        spec_content = "- [ ] Task 1\n- [ ] Task 2\n- [ ] Task 3"

        # Create PRs with different ages
        pr_fresh = GitHubPullRequest(
            number=1,
            title="Fresh PR",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-a1b2c3d4"
        )
        pr_stale = GitHubPullRequest(
            number=2,
            title="Stale PR",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            merged_at=None,
            assignees=[GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-e5f6g7h8"
        )

        # Mock PROperationsService
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [pr_fresh, pr_stale]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test with 7-day stale threshold
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep", stale_pr_days=7)

        # Assert
        assert len(stats.open_prs) == 2
        assert stats.stale_pr_count == 1
        assert stats.in_progress_tasks == 2

        # Verify PR info - now directly using GitHubPullRequest
        fresh_pr = next(p for p in stats.open_prs if p.number == 1)
        stale_pr = next(p for p in stats.open_prs if p.number == 2)

        assert fresh_pr.is_stale(7) is False
        assert fresh_pr.first_assignee == "alice"
        assert stale_pr.is_stale(7) is True
        assert stale_pr.first_assignee == "bob"

    def test_collect_stats_custom_stale_threshold(self):
        """Should respect custom stale_pr_days threshold"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.github_models import GitHubPullRequest, GitHubUser

        spec_content = "- [ ] Task 1"

        # PR that's 5 days old
        pr = GitHubPullRequest(
            number=1,
            title="5 day old PR",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            merged_at=None,
            assignees=[GitHubUser(login="charlie")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-i9j0k1l2"
        )

        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [pr]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")

        # With 7-day threshold: not stale
        stats_7 = service.collect_project_stats("test-project", "main", "claudestep", stale_pr_days=7)
        assert stats_7.stale_pr_count == 0
        # GitHubPullRequest.is_stale() uses the threshold passed to it
        assert stats_7.open_prs[0].is_stale(7) is False

        # With 3-day threshold: stale
        stats_3 = service.collect_project_stats("test-project", "main", "claudestep", stale_pr_days=3)
        assert stats_3.stale_pr_count == 1
        assert stats_3.open_prs[0].is_stale(3) is True

    def test_collect_stats_no_open_prs(self):
        """Should handle case with no open PRs"""
        spec_content = "- [x] Task 1\n- [ ] Task 2"

        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert len(stats.open_prs) == 0
        assert stats.stale_pr_count == 0
        assert stats.in_progress_tasks == 0


class TestTaskPRMappings:
    """Test task-PR mapping logic in _build_task_pr_mappings"""

    def test_task_matched_to_open_pr_is_in_progress(self):
        """Task with matching open PR should be IN_PROGRESS"""
        from datetime import datetime, timezone
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [ ] Implement feature X"

        # Create open PR with matching task hash
        project = Project("test-project")
        spec = SpecContent(project, spec_content)
        task_hash = spec.tasks[0].task_hash

        open_pr = GitHubPullRequest(
            number=42,
            title="Implement feature X",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name=f"claude-step-test-project-{task_hash}"
        )

        # Mock services
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [open_pr]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert
        assert len(stats.tasks) == 1
        assert stats.tasks[0].status == TaskStatus.IN_PROGRESS
        assert stats.tasks[0].pr is not None
        assert stats.tasks[0].pr.number == 42

    def test_task_matched_to_merged_pr_and_completed(self):
        """Completed task with merged PR should be COMPLETED with PR reference"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [x] Implement feature X"

        # Create merged PR with matching task hash
        project = Project("test-project")
        spec = SpecContent(project, spec_content)
        task_hash = spec.tasks[0].task_hash

        merged_pr = GitHubPullRequest(
            number=99,
            title="Implement feature X",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
            merged_at=datetime.now(timezone.utc) - timedelta(days=1),
            assignees=[GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name=f"claude-step-test-project-{task_hash}"
        )

        # Mock services
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = [merged_pr]

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert
        assert len(stats.tasks) == 1
        assert stats.tasks[0].status == TaskStatus.COMPLETED
        assert stats.tasks[0].pr is not None
        assert stats.tasks[0].pr.number == 99

    def test_task_with_no_pr_is_pending(self):
        """Task with no matching PR should be PENDING"""
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [ ] Implement feature X"

        project = Project("test-project")
        spec = SpecContent(project, spec_content)

        # Mock services - no PRs
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert
        assert len(stats.tasks) == 1
        assert stats.tasks[0].status == TaskStatus.PENDING
        assert stats.tasks[0].pr is None

    def test_orphaned_pr_detected(self):
        """PR with no matching task in spec should be orphaned"""
        from datetime import datetime, timezone
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [ ] Task A"

        project = Project("test-project")
        spec = SpecContent(project, spec_content)

        # Create PR with a different task hash (orphaned)
        orphaned_pr = GitHubPullRequest(
            number=55,
            title="Old removed task",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="charlie")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-deadbeef"  # Hash not in spec
        )

        # Mock services
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [orphaned_pr]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert - task A has no PR, orphaned PR detected
        assert len(stats.tasks) == 1
        assert stats.tasks[0].status == TaskStatus.PENDING
        assert stats.tasks[0].pr is None

        assert len(stats.orphaned_prs) == 1
        assert stats.orphaned_prs[0].number == 55

    def test_mixed_tasks_and_prs(self):
        """Test scenario with completed, in-progress, pending tasks and orphaned PR"""
        from datetime import datetime, timezone, timedelta
        from claudestep.domain.spec_content import SpecContent

        spec_content = """- [x] Task completed
- [ ] Task in progress
- [ ] Task pending"""

        project = Project("test-project")
        spec = SpecContent(project, spec_content)

        # Get task hashes
        completed_hash = spec.tasks[0].task_hash
        in_progress_hash = spec.tasks[1].task_hash
        # pending_hash = spec.tasks[2].task_hash (no PR for this one)

        # Create matching PRs
        merged_pr = GitHubPullRequest(
            number=1,
            title="Task completed",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=5),
            merged_at=datetime.now(timezone.utc) - timedelta(days=3),
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name=f"claude-step-test-project-{completed_hash}"
        )

        open_pr = GitHubPullRequest(
            number=2,
            title="Task in progress",
            state="open",
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
            merged_at=None,
            assignees=[GitHubUser(login="bob")],
            labels=["claudestep"],
            head_ref_name=f"claude-step-test-project-{in_progress_hash}"
        )

        orphaned_pr = GitHubPullRequest(
            number=3,
            title="Removed task",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
            merged_at=datetime.now(timezone.utc) - timedelta(days=8),
            assignees=[GitHubUser(login="charlie")],
            labels=["claudestep"],
            head_ref_name="claude-step-test-project-abcd1234"  # Not in spec
        )

        # Mock services
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [open_pr]
        mock_pr_service.get_merged_prs_for_project.return_value = [merged_pr, orphaned_pr]

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert task statuses
        assert len(stats.tasks) == 3

        completed_task = next(t for t in stats.tasks if t.description == "Task completed")
        assert completed_task.status == TaskStatus.COMPLETED
        assert completed_task.pr is not None
        assert completed_task.pr.number == 1

        in_progress_task = next(t for t in stats.tasks if t.description == "Task in progress")
        assert in_progress_task.status == TaskStatus.IN_PROGRESS
        assert in_progress_task.pr is not None
        assert in_progress_task.pr.number == 2

        pending_task = next(t for t in stats.tasks if t.description == "Task pending")
        assert pending_task.status == TaskStatus.PENDING
        assert pending_task.pr is None

        # Assert orphaned PR
        assert len(stats.orphaned_prs) == 1
        assert stats.orphaned_prs[0].number == 3

    def test_completed_task_without_pr(self):
        """Completed task without PR should still be COMPLETED"""
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [x] Manually completed task"

        project = Project("test-project")
        spec = SpecContent(project, spec_content)

        # Mock services - no PRs
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = []
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert - status comes from spec checkbox, not PR
        assert len(stats.tasks) == 1
        assert stats.tasks[0].status == TaskStatus.COMPLETED
        assert stats.tasks[0].pr is None

    def test_pr_without_task_hash_not_orphaned(self):
        """PR without parseable task hash should not appear in orphaned list"""
        from datetime import datetime, timezone
        from claudestep.domain.spec_content import SpecContent

        spec_content = "- [ ] Task A"

        project = Project("test-project")
        spec = SpecContent(project, spec_content)

        # Create PR with non-ClaudeStep branch name
        non_claudestep_pr = GitHubPullRequest(
            number=77,
            title="Manual PR",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[GitHubUser(login="dave")],
            labels=["claudestep"],
            head_ref_name="feature/manual-work"  # Not a ClaudeStep branch
        )

        # Mock services
        mock_pr_service = Mock()
        mock_pr_service.get_open_prs_for_project.return_value = [non_claudestep_pr]
        mock_pr_service.get_merged_prs_for_project.return_value = []

        mock_repo = Mock()
        mock_repo.load_spec.return_value = spec

        # Collect stats
        service = StatisticsService("owner/repo", mock_repo, mock_pr_service, base_branch="main")
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        # Assert - PR has no task hash, so it's not tracked as orphaned
        assert len(stats.orphaned_prs) == 0


class TestFormatProjectDetails:
    """Test format_project_details() method on StatisticsReport"""

    def test_format_empty_report(self):
        """Should return empty string for report with no projects"""
        report = StatisticsReport()
        result = report.format_project_details()
        assert result == ""

    def test_format_single_project_with_tasks(self):
        """Should format project with tasks and their statuses"""
        report = StatisticsReport()

        # Create project stats with tasks
        stats = ProjectStats("my-project", "/path/spec.md")
        stats.total_tasks = 3
        stats.completed_tasks = 1

        # Add tasks with different statuses
        stats.tasks = [
            TaskWithPR(
                task_hash="a1b2c3d4",
                description="Implement feature A",
                status=TaskStatus.COMPLETED,
                pr=None
            ),
            TaskWithPR(
                task_hash="e5f6g7h8",
                description="Implement feature B",
                status=TaskStatus.IN_PROGRESS,
                pr=GitHubPullRequest(
                    number=42,
                    title="Implement feature B",
                    state="open",
                    created_at=datetime.now(timezone.utc) - timedelta(days=2),
                    merged_at=None,
                    assignees=[GitHubUser(login="alice")],
                    labels=["claudestep"],
                    head_ref_name="claude-step-my-project-e5f6g7h8"
                )
            ),
            TaskWithPR(
                task_hash="i9j0k1l2",
                description="Implement feature C",
                status=TaskStatus.PENDING,
                pr=None
            )
        ]
        report.add_project(stats)

        result = report.format_project_details()

        # Check project header
        assert "my-project (1/3 complete)" in result
        # Check tasks section
        assert "### Tasks" in result
        # Check completed task
        assert "[x]" in result
        assert "`Implement feature A`" in result
        assert "(no PR)" in result
        # Check in-progress task
        assert "[ ]" in result
        assert "`Implement feature B`" in result
        assert "PR #42" in result
        assert "Open" in result
        # Check pending task
        assert "`Implement feature C`" in result

    def test_format_project_with_orphaned_prs(self):
        """Should include orphaned PRs section when present"""
        report = StatisticsReport()

        stats = ProjectStats("my-project", "/path/spec.md")
        stats.total_tasks = 1
        stats.completed_tasks = 1
        stats.tasks = [
            TaskWithPR(
                task_hash="a1b2c3d4",
                description="Only task",
                status=TaskStatus.COMPLETED,
                pr=None
            )
        ]

        # Add orphaned PRs
        stats.orphaned_prs = [
            GitHubPullRequest(
                number=25,
                title="Old task removed",
                state="merged",
                created_at=datetime.now(timezone.utc) - timedelta(days=10),
                merged_at=datetime.now(timezone.utc) - timedelta(days=5),
                assignees=[GitHubUser(login="bob")],
                labels=["claudestep"],
                head_ref_name="claude-step-my-project-x9y8z7w6"
            ),
            GitHubPullRequest(
                number=28,
                title="Another removed task",
                state="open",
                created_at=datetime.now(timezone.utc) - timedelta(days=5),
                merged_at=None,
                assignees=[GitHubUser(login="alice")],
                labels=["claudestep"],
                head_ref_name="claude-step-my-project-m3n4o5p6"
            )
        ]
        report.add_project(stats)

        result = report.format_project_details()

        # Check orphaned PRs section
        assert "### Orphaned PRs" in result
        assert "PR #25 (Merged)" in result
        assert "Task removed from spec" in result
        assert "PR #28 (Open" in result

    def test_format_project_with_merged_pr(self):
        """Should show Merged state for merged PRs"""
        report = StatisticsReport()

        stats = ProjectStats("my-project", "/path/spec.md")
        stats.total_tasks = 1
        stats.completed_tasks = 1

        merged_pr = GitHubPullRequest(
            number=31,
            title="Completed task",
            state="merged",
            created_at=datetime.now(timezone.utc) - timedelta(days=3),
            merged_at=datetime.now(timezone.utc) - timedelta(days=1),
            assignees=[GitHubUser(login="alice")],
            labels=["claudestep"],
            head_ref_name="claude-step-my-project-a1b2c3d4"
        )

        stats.tasks = [
            TaskWithPR(
                task_hash="a1b2c3d4",
                description="echo 'Hello World!'",
                status=TaskStatus.COMPLETED,
                pr=merged_pr
            )
        ]
        report.add_project(stats)

        result = report.format_project_details()

        assert "[x]" in result
        assert "PR #31 (Merged)" in result

    def test_format_truncates_long_descriptions(self):
        """Should truncate task descriptions longer than 60 chars"""
        report = StatisticsReport()

        stats = ProjectStats("my-project", "/path/spec.md")
        stats.total_tasks = 1
        stats.completed_tasks = 0

        long_desc = "A" * 100  # 100 character description

        stats.tasks = [
            TaskWithPR(
                task_hash="a1b2c3d4",
                description=long_desc,
                status=TaskStatus.PENDING,
                pr=None
            )
        ]
        report.add_project(stats)

        result = report.format_project_details()

        # Should be truncated to 60 chars + "..."
        assert "A" * 60 + "..." in result
        assert "A" * 61 not in result

    def test_format_multiple_projects_sorted(self):
        """Should format multiple projects in sorted order"""
        report = StatisticsReport()

        # Add projects out of order
        stats_b = ProjectStats("project-b", "/path/b.md")
        stats_b.total_tasks = 5
        stats_b.completed_tasks = 2
        stats_b.tasks = []
        report.add_project(stats_b)

        stats_a = ProjectStats("project-a", "/path/a.md")
        stats_a.total_tasks = 3
        stats_a.completed_tasks = 1
        stats_a.tasks = []
        report.add_project(stats_a)

        result = report.format_project_details()

        # Projects should be sorted alphabetically
        pos_a = result.find("project-a")
        pos_b = result.find("project-b")
        assert pos_a < pos_b

    def test_format_for_slack(self):
        """Should use Slack mrkdwn format when for_slack=True"""
        report = StatisticsReport()

        stats = ProjectStats("my-project", "/path/spec.md")
        stats.total_tasks = 1
        stats.completed_tasks = 1
        stats.tasks = [
            TaskWithPR(
                task_hash="a1b2c3d4",
                description="Task 1",
                status=TaskStatus.COMPLETED,
                pr=None
            )
        ]
        report.add_project(stats)

        result_github = report.format_project_details(for_slack=False)
        result_slack = report.format_project_details(for_slack=True)

        # GitHub uses ## for headers, Slack uses *bold*
        assert "## my-project" in result_github
        assert "*my-project" in result_slack
        assert "##" not in result_slack
