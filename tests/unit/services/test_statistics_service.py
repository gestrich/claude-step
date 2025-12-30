"""Tests for statistics collection and formatting"""

import json
import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from claudestep.domain.models import TeamMemberStats, ProjectStats, StatisticsReport
from claudestep.domain.project import Project
from claudestep.domain.spec_content import SpecContent
from claudestep.services.statistics_service import StatisticsService

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
        stats.merged_prs = [
            {"pr_number": 1, "title": "Test 1"},
            {"pr_number": 2, "title": "Test 2"},
        ]
        assert stats.merged_count == 2

    def test_open_count(self):
        """Test open_count property"""
        stats = TeamMemberStats("charlie")
        stats.open_prs = [
            {"pr_number": 3, "title": "Test 3"},
        ]
        assert stats.open_count == 1

    def test_format_summary_with_activity(self):
        """Test summary formatting with activity"""
        stats = TeamMemberStats("alice")
        stats.merged_prs = [{"pr_number": 1, "title": "Test"}]
        stats.open_prs = [{"pr_number": 2, "title": "Test"}]

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

    def test_format_for_slack_empty(self):
        """Test Slack formatting with no data"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0)

        slack_msg = report.format_for_slack()
        assert "ClaudeStep Statistics Report" in slack_msg
        assert "No projects found" in slack_msg
        # Empty report doesn't show leaderboard section

    def test_format_for_slack_with_data(self):
        """Test Slack formatting with data"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0)

        # Add project
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        report.add_project(project)

        # Add team member
        member = TeamMemberStats("alice")
        member.merged_prs = [{"pr_number": 1, "title": "Test"}]
        report.add_team_member(member)

        slack_msg = report.format_for_slack()
        assert "ClaudeStep Statistics Report" in slack_msg
        assert "test-project" in slack_msg
        assert "alice" in slack_msg
        # Check for table format
        assert "```" in slack_msg  # Code block for table
        assert "Total" in slack_msg  # Table header
        assert "Merged" in slack_msg  # Leaderboard header
        assert "2025-01-01" in slack_msg

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

    def test_to_json(self):
        """Test JSON serialization"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0)

        # Add project
        project = ProjectStats("test-project", "/path/spec.md")
        project.total_tasks = 10
        project.completed_tasks = 5
        project.in_progress_tasks = 2
        project.pending_tasks = 3
        report.add_project(project)

        # Add team member
        member = TeamMemberStats("alice")
        member.merged_prs = [{"pr_number": 1, "title": "Test", "merged_at": "2025-01-01", "project": "test"}]
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

    def test_team_stats_sorting(self):
        """Test that team stats are sorted by activity"""
        report = StatisticsReport()

        # Add members with different activity levels
        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": i} for i in range(5)]
        report.add_team_member(alice)

        bob = TeamMemberStats("bob")
        bob.merged_prs = [{"pr_number": i} for i in range(2)]
        report.add_team_member(bob)

        charlie = TeamMemberStats("charlie")
        charlie.merged_prs = [{"pr_number": i} for i in range(10)]
        report.add_team_member(charlie)

        slack_msg = report.format_for_slack()

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
        alice.merged_prs = [{"pr_number": 1, "title": "Test"}]
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

        # Add 5 members with different activity levels
        for i, name in enumerate(["alice", "bob", "charlie", "david", "eve"]):
            member = TeamMemberStats(name)
            # alice: 5, bob: 4, charlie: 3, david: 2, eve: 1
            member.merged_prs = [{"pr_number": j} for j in range(5 - i)]
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

        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": i} for i in range(10)]
        report.add_team_member(alice)

        bob = TeamMemberStats("bob")
        bob.merged_prs = [{"pr_number": i} for i in range(3)]
        report.add_team_member(bob)

        leaderboard = report.format_leaderboard()

        assert "10 PR(s) merged" in leaderboard
        assert "3 PR(s) merged" in leaderboard

    def test_leaderboard_shows_open_prs(self):
        """Test leaderboard shows open PRs when present"""
        report = StatisticsReport()

        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": 1}]
        alice.open_prs = [{"pr_number": 2}, {"pr_number": 3}]
        report.add_team_member(alice)

        leaderboard = report.format_leaderboard()

        assert "(2 open PR(s))" in leaderboard

    def test_leaderboard_activity_bar(self):
        """Test leaderboard activity bar scales correctly"""
        report = StatisticsReport()

        # alice has 10 merged (should get full bar)
        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": i} for i in range(10)]
        report.add_team_member(alice)

        # bob has 5 merged (should get half bar)
        bob = TeamMemberStats("bob")
        bob.merged_prs = [{"pr_number": i} for i in range(5)]
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

        # Active member
        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": 1}]
        report.add_team_member(alice)

        # Inactive member (has open PRs but no merges)
        bob = TeamMemberStats("bob")
        bob.open_prs = [{"pr_number": 2}]
        report.add_team_member(bob)

        # Completely inactive member
        charlie = TeamMemberStats("charlie")
        report.add_team_member(charlie)

        leaderboard = report.format_leaderboard()

        assert "@alice" in leaderboard
        assert "@bob" not in leaderboard
        assert "@charlie" not in leaderboard

    def test_leaderboard_in_slack_output(self):
        """Test leaderboard appears in Slack formatted output"""
        report = StatisticsReport()
        report.generated_at = datetime(2025, 1, 1, 12, 0, 0)

        alice = TeamMemberStats("alice")
        alice.merged_prs = [{"pr_number": 1}]
        report.add_team_member(alice)

        slack_msg = report.format_for_slack()

        # Leaderboard should appear before project progress
        assert "🏆 Leaderboard" in slack_msg
        leaderboard_pos = slack_msg.find("🏆 Leaderboard")
        project_pos = slack_msg.find("📊 Project Progress")

        # Leaderboard should come first (most engaging)
        assert leaderboard_pos < project_pos

class TestCostExtraction:
    """Test cost extraction from PR comments"""

    def test_extract_cost_from_valid_comment(self):
        """Test extracting cost from a valid cost breakdown comment"""
        comment = """## 💰 Cost Breakdown

This PR was generated using Claude Code with the following costs:

| Component | Cost (USD) |
|-----------|------------|
| Main refactoring task | $0.123456 |
| PR summary generation | $0.002345 |
| **Total** | **$0.125801** |

---
*Cost tracking by ClaudeStep • [View workflow run](https://example.com)*
"""
        cost = StatisticsService.extract_cost_from_comment(comment)
        assert cost == 0.125801

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


class TestCollectProjectCosts:
    """Test project cost collection"""

    def test_collect_costs_with_metadata(self):
        """Test collecting costs from metadata storage"""
        # Mock metadata service
        mock_metadata_service = Mock()

        # Create mock PullRequests with costs
        pr1 = Mock()
        pr1.pr_state = "merged"
        pr1.get_total_cost.return_value = 0.3

        pr2 = Mock()
        pr2.pr_state = "merged"
        pr2.get_total_cost.return_value = 0.2

        # Create mock project metadata
        project_metadata = Mock()
        project_metadata.pull_requests = [pr1, pr2]

        mock_metadata_service.get_project.return_value = project_metadata

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        cost = service.collect_project_costs("test-project", "claudestep")

        assert cost == 0.5
        mock_metadata_service.get_project.assert_called_once_with("test-project")

    def test_collect_costs_no_merged_prs(self):
        """Test collecting costs when no merged PRs found"""
        # Mock metadata service
        mock_metadata_service = Mock()

        # Create mock project with only open PRs
        pr1 = Mock()
        pr1.pr_state = "open"

        project_metadata = Mock()
        project_metadata.pull_requests = [pr1]

        mock_metadata_service.get_project.return_value = project_metadata

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        cost = service.collect_project_costs("test-project", "claudestep")

        assert cost == 0.0

    def test_collect_costs_no_project(self):
        """Test collecting costs when project not found"""
        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.get_project.return_value = None

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        cost = service.collect_project_costs("test-project", "claudestep")

        assert cost == 0.0

    def test_collect_costs_exception_handling(self):
        """Test that exceptions are handled gracefully"""
        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.get_project.side_effect = Exception("API error")

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        cost = service.collect_project_costs("test-project", "claudestep")

        assert cost == 0.0


class TestCollectTeamMemberStats:
    """Test team member statistics collection"""

    @patch("claudestep.services.statistics_service.run_gh_command")
    def test_collect_stats_basic(self, mock_run_gh):
        """Test basic team member stats collection"""
        merged_prs = [
            {
                "number": 1,
                "title": "Fix bug",
                "mergedAt": "2025-12-01T10:00:00Z",
                "assignees": [{"login": "alice"}]
            },
            {
                "number": 2,
                "title": "Add feature",
                "mergedAt": "2025-12-15T15:00:00Z",
                "assignees": [{"login": "bob"}]
            }
        ]

        open_prs = [
            {
                "number": 3,
                "title": "WIP",
                "createdAt": "2025-12-20T10:00:00Z",
                "assignees": [{"login": "alice"}]
            }
        ]

        # Mock gh commands
        mock_run_gh.side_effect = [json.dumps(merged_prs), json.dumps(open_prs)]

        # Create service and test
        mock_metadata_service = Mock()
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice", "bob"], days_back=30)

        assert "alice" in stats
        assert "bob" in stats
        assert stats["alice"].merged_count >= 1
        assert stats["alice"].open_count >= 1
        assert stats["bob"].merged_count >= 1

    @patch("claudestep.services.statistics_service.run_gh_command")
    def test_collect_stats_empty_prs(self, mock_run_gh):
        """Test stats collection with no PRs"""
        mock_run_gh.return_value = json.dumps([])

        # Create service and test
        mock_metadata_service = Mock()
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice"])

        assert "alice" in stats
        assert stats["alice"].merged_count == 0
        assert stats["alice"].open_count == 0

    @patch("claudestep.services.statistics_service.run_gh_command")
    def test_collect_stats_exception_handling(self, mock_run_gh):
        """Test that exceptions during collection are handled"""
        mock_run_gh.side_effect = Exception("API error")

        # Create service and test
        mock_metadata_service = Mock()
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        stats = service.collect_team_member_stats(["alice"])

        # Should return empty stats but not crash
        assert "alice" in stats
        assert stats["alice"].merged_count == 0


class TestCollectProjectStats:
    """Test project statistics collection"""

    def test_collect_stats_success(self):
        """Test successful project stats collection"""
        spec_content = """
- [x] Task 1
- [x] Task 2
- [ ] Task 3
- [ ] Task 4
        """

        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.find_in_progress_tasks.return_value = [2]

        # Mock get_project for cost collection
        pr1 = Mock()
        pr1.pr_state = "merged"
        pr1.get_total_cost.return_value = 1.5

        project_metadata = Mock()
        project_metadata.pull_requests = [pr1]
        mock_metadata_service.get_project.return_value = project_metadata

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main", project_repository=mock_repo)
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert stats.project_name == "test-project"
        assert stats.total_tasks == 4
        assert stats.completed_tasks == 2
        assert stats.in_progress_tasks == 1
        assert stats.pending_tasks == 1
        assert stats.total_cost_usd == 1.5

    def test_collect_stats_missing_spec(self):
        """Test stats collection with missing spec file"""
        # Create service and test
        mock_metadata_service = Mock()

        # Mock ProjectRepository to return None
        mock_repo = Mock()
        mock_repo.load_spec.return_value = None

        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main", project_repository=mock_repo)
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert stats is None

    def test_collect_stats_in_progress_error(self):
        """Test stats collection when in-progress task detection fails"""
        spec_content = "- [ ] Task 1\n- [x] Task 2"

        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.find_in_progress_tasks.side_effect = Exception("API error")
        mock_metadata_service.get_project.return_value = None

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main", project_repository=mock_repo)
        stats = service.collect_project_stats("test-project", "main", "claudestep")

        assert stats.in_progress_tasks == 0
        assert stats.pending_tasks == 1

    def test_collect_stats_custom_base_branch(self):
        """Test that custom base_branch value is used correctly"""
        spec_content = "- [x] Task 1\n- [ ] Task 2"

        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.find_in_progress_tasks.return_value = []
        mock_metadata_service.get_project.return_value = None

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.spec_content import SpecContent

        project = Project("test-project")
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service with custom base_branch
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="develop", project_repository=mock_repo)
        stats = service.collect_project_stats("test-project", "develop", "claudestep")

        # Verify the service uses the custom base_branch
        assert stats.project_name == "test-project"
        assert stats.total_tasks == 2
        assert stats.completed_tasks == 1

        # Verify repository was called with the custom branch
        mock_repo.load_spec.assert_called_with(project, "develop")


class TestCollectAllStatistics:
    """Test full statistics collection"""

    @patch("claudestep.services.statistics_service.run_gh_command")
    def test_collect_all_single_project(self, mock_run_gh):
        """Test collecting stats for a single project"""
        config_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 1
        """
        spec_content = "- [x] Task 1\n- [ ] Task 2"

        # Mock run_gh_command for team member stats
        mock_run_gh.return_value = json.dumps([])

        # Mock metadata service
        mock_metadata_service = Mock()
        mock_metadata_service.find_in_progress_tasks.return_value = []
        mock_metadata_service.get_project.return_value = None

        # Mock ProjectRepository
        mock_repo = Mock()
        from claudestep.domain.project import Project
        from claudestep.domain.project_configuration import ProjectConfiguration
        from claudestep.domain.spec_content import SpecContent

        project = Project("project1")
        mock_repo.load_configuration.return_value = ProjectConfiguration.from_yaml_string(project, config_content)
        mock_repo.load_spec.return_value = SpecContent(project, spec_content)

        # Create service and test
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main", project_repository=mock_repo)
        report = service.collect_all_statistics("claude-step/project1/configuration.yml")

        assert len(report.project_stats) == 1
        assert "project1" in report.project_stats
        assert len(report.team_stats) == 2
        assert "alice" in report.team_stats
        assert "bob" in report.team_stats

    def test_collect_all_no_repository(self):
        """Test that missing GITHUB_REPOSITORY returns empty report"""
        # Create service with empty repo
        mock_metadata_service = Mock()
        service = StatisticsService("", mock_metadata_service, base_branch="main")
        report = service.collect_all_statistics()

        assert len(report.project_stats) == 0
        assert len(report.team_stats) == 0

    @patch("claudestep.services.statistics_service.get_file_from_branch")
    def test_collect_all_config_error(self, mock_get_file):
        """Test handling of config loading errors"""
        # Mock get_file_from_branch to return None (config not found)
        mock_get_file.return_value = None

        # Create service and test
        mock_metadata_service = Mock()
        service = StatisticsService("owner/repo", mock_metadata_service, base_branch="main")
        report = service.collect_all_statistics("/nonexistent/config.yml")

        assert len(report.project_stats) == 0
