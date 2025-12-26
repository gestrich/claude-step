"""Data models for ClaudeStep operations"""

from typing import Any, Dict, List, Optional


class ReviewerCapacityResult:
    """Result of reviewer capacity check with detailed information"""

    def __init__(self):
        self.reviewers_status = []  # List of dicts with reviewer details
        self.selected_reviewer = None
        self.all_at_capacity = False

    def add_reviewer(self, username: str, max_prs: int, open_prs: List[Dict], has_capacity: bool):
        """Add reviewer status information"""
        self.reviewers_status.append({
            "username": username,
            "max_prs": max_prs,
            "open_prs": open_prs,  # List of {pr_number, task_index, task_description}
            "open_count": len(open_prs),
            "has_capacity": has_capacity
        })

    def format_summary(self) -> str:
        """Generate formatted summary for GitHub Actions output"""
        lines = ["## Reviewer Capacity Check", ""]

        for reviewer in self.reviewers_status:
            username = reviewer["username"]
            max_prs = reviewer["max_prs"]
            open_count = reviewer["open_count"]
            open_prs = reviewer["open_prs"]
            has_capacity = reviewer["has_capacity"]

            # Reviewer header with status emoji
            status_emoji = "✅" if has_capacity else "❌"
            lines.append(f"### {status_emoji} **{username}**")
            lines.append("")

            # Capacity info
            lines.append(f"**Max PRs Allowed:** {max_prs}")
            lines.append(f"**Currently Open:** {open_count}/{max_prs}")
            lines.append("")

            # List open PRs with details
            if open_prs:
                lines.append("**Open PRs:**")
                for pr_info in open_prs:
                    pr_num = pr_info.get("pr_number", "?")
                    task_idx = pr_info.get("task_index", "?")
                    task_desc = pr_info.get("task_description", "Unknown task")
                    lines.append(f"- PR #{pr_num}: Task {task_idx} - {task_desc}")
                lines.append("")
            else:
                lines.append("**Open PRs:** None")
                lines.append("")

            # Availability status
            if has_capacity:
                available_slots = max_prs - open_count
                lines.append(f"**Status:** ✅ Available ({available_slots} slot(s) remaining)")
            else:
                lines.append(f"**Status:** ❌ At capacity")

            lines.append("")

        # Final decision
        lines.append("---")
        lines.append("")
        if self.selected_reviewer:
            lines.append(f"**Decision:** ✅ Selected **{self.selected_reviewer}** for next PR")
        else:
            lines.append(f"**Decision:** ❌ All reviewers at capacity - skipping PR creation")

        return "\n".join(lines)


class TeamMemberStats:
    """Statistics for a single team member"""

    def __init__(self, username: str):
        self.username = username
        self.merged_prs = []  # List of {pr_number, title, merged_at, project}
        self.open_prs = []    # List of {pr_number, title, created_at, project}

    @property
    def merged_count(self) -> int:
        """Number of merged PRs"""
        return len(self.merged_prs)

    @property
    def open_count(self) -> int:
        """Number of open PRs"""
        return len(self.open_prs)

    def format_summary(self) -> str:
        """Format for GitHub/Slack markdown output"""
        lines = []

        # Emoji status indicator
        if self.merged_count > 0 or self.open_count > 0:
            status_emoji = "✅"
        else:
            status_emoji = "💤"

        # Member header
        lines.append(f"{status_emoji} **@{self.username}**")

        # Activity summary
        lines.append(f"- Merged: {self.merged_count} PR(s)")
        lines.append(f"- Open: {self.open_count} PR(s)")

        return "\n".join(lines)


class ProjectStats:
    """Statistics for a single project"""

    def __init__(self, project_name: str, spec_path: str):
        self.project_name = project_name
        self.spec_path = spec_path
        self.total_tasks = 0
        self.completed_tasks = 0
        self.in_progress_tasks = 0
        self.pending_tasks = 0

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    def format_progress_bar(self, width: int = 10) -> str:
        """Generate Unicode progress bar

        Args:
            width: Number of characters for the bar

        Returns:
            String like "████████░░ 80%"
        """
        if self.total_tasks == 0:
            return "░" * width + " 0%"

        filled = int((self.completion_percentage / 100) * width)
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"{bar} {self.completion_percentage:.0f}%"

    def format_summary(self) -> str:
        """Format for GitHub/Slack markdown with progress bar"""
        lines = []

        # Project header
        lines.append(f"### 📊 **{self.project_name}**")
        lines.append("")

        # Progress bar
        lines.append(f"**Progress:** {self.format_progress_bar()}")
        lines.append(f"**Tasks:** {self.completed_tasks}/{self.total_tasks} complete")
        lines.append("")

        # Task breakdown
        lines.append("**Details:**")
        lines.append(f"- ✅ Completed: {self.completed_tasks}")
        lines.append(f"- 🔄 In Progress: {self.in_progress_tasks}")
        lines.append(f"- ⏸️ Pending: {self.pending_tasks}")

        return "\n".join(lines)


class StatisticsReport:
    """Aggregated statistics report for all projects and team members"""

    def __init__(self):
        self.team_stats = {}      # username -> TeamMemberStats
        self.project_stats = {}   # project_name -> ProjectStats
        self.generated_at = None  # datetime

    def add_team_member(self, stats: TeamMemberStats):
        """Add team member statistics"""
        self.team_stats[stats.username] = stats

    def add_project(self, stats: ProjectStats):
        """Add project statistics"""
        self.project_stats[stats.project_name] = stats

    def format_for_slack(self) -> str:
        """Complete report in Slack mrkdwn format"""
        lines = []

        # Header
        lines.append("# 🤖 ClaudeStep Statistics Report")
        lines.append("")

        if self.generated_at:
            from datetime import datetime
            timestamp = self.generated_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"*Generated: {timestamp}*")
            lines.append("")

        # Project Statistics
        if self.project_stats:
            lines.append("## 📊 Project Progress")
            lines.append("")
            for project_name in sorted(self.project_stats.keys()):
                stats = self.project_stats[project_name]
                lines.append(stats.format_summary())
                lines.append("")
        else:
            lines.append("## 📊 Project Progress")
            lines.append("")
            lines.append("*No projects found*")
            lines.append("")

        # Team Member Statistics
        if self.team_stats:
            lines.append("## 👥 Team Activity")
            lines.append("")
            # Sort by activity level (merged PRs desc, then username)
            sorted_members = sorted(
                self.team_stats.items(),
                key=lambda x: (-x[1].merged_count, x[0])
            )
            for username, stats in sorted_members:
                lines.append(stats.format_summary())
                lines.append("")
        else:
            lines.append("## 👥 Team Activity")
            lines.append("")
            lines.append("*No team member activity found*")
            lines.append("")

        return "\n".join(lines)

    def format_for_pr_comment(self) -> str:
        """Brief summary for PR notifications"""
        lines = []

        # Only include project progress, not full team stats
        if self.project_stats:
            # If single project, show details
            if len(self.project_stats) == 1:
                project_name = list(self.project_stats.keys())[0]
                stats = self.project_stats[project_name]
                lines.append(f"**{project_name}:** {stats.format_progress_bar()} ({stats.completed_tasks}/{stats.total_tasks})")
            else:
                # Multiple projects, show summary
                lines.append("**Project Progress:**")
                for project_name in sorted(self.project_stats.keys()):
                    stats = self.project_stats[project_name]
                    lines.append(f"- {project_name}: {stats.format_progress_bar()}")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export as JSON for programmatic access"""
        import json
        from datetime import datetime

        data = {
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "projects": {},
            "team_members": {}
        }

        # Serialize project stats
        for project_name, stats in self.project_stats.items():
            data["projects"][project_name] = {
                "total_tasks": stats.total_tasks,
                "completed_tasks": stats.completed_tasks,
                "in_progress_tasks": stats.in_progress_tasks,
                "pending_tasks": stats.pending_tasks,
                "completion_percentage": stats.completion_percentage
            }

        # Serialize team member stats
        for username, stats in self.team_stats.items():
            data["team_members"][username] = {
                "merged_prs": stats.merged_prs,
                "open_prs": stats.open_prs,
                "merged_count": stats.merged_count,
                "open_count": stats.open_count
            }

        return json.dumps(data, indent=2)
