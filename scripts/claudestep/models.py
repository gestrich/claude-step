"""Data models for ClaudeStep operations"""

from typing import Any, Dict, List, Optional
from claudestep.application.formatters.table_formatter import TableFormatter


class MarkdownFormatter:
    """Helper class for formatting text in both Slack mrkdwn and GitHub markdown"""

    def __init__(self, for_slack: bool = False):
        self.for_slack = for_slack

    def bold(self, text: str) -> str:
        """Format text as bold"""
        if self.for_slack:
            return f"*{text}*"
        return f"**{text}**"

    def italic(self, text: str) -> str:
        """Format text as italic"""
        return f"_{text}_"

    def header(self, text: str, level: int = 2) -> str:
        """Format text as a header

        Args:
            text: Header text
            level: Header level (1-6 for GitHub, 1-2 for Slack)
        """
        if self.for_slack:
            # Slack only has bold for headers
            return f"*{text}*"
        return f"{'#' * level} {text}"

    def code(self, text: str) -> str:
        """Format text as inline code"""
        return f"`{text}`"

    def code_block(self, text: str, language: str = "") -> str:
        """Format text as code block"""
        if self.for_slack:
            return f"```{text}```"
        return f"```{language}\n{text}\n```"

    def link(self, text: str, url: str) -> str:
        """Format text as a link"""
        if self.for_slack:
            return f"<{url}|{text}>"
        return f"[{text}]({url})"

    def list_item(self, text: str, bullet: str = "-") -> str:
        """Format text as a list item"""
        return f"{bullet} {text}"


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

    def format_summary(self, for_slack: bool = False) -> str:
        """Format for GitHub/Slack markdown output

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown
        """
        fmt = MarkdownFormatter(for_slack)
        lines = []

        # Emoji status indicator
        if self.merged_count > 0 or self.open_count > 0:
            status_emoji = "✅"
        else:
            status_emoji = "💤"

        # Member header
        lines.append(f"{status_emoji} {fmt.bold(f'@{self.username}')}")

        # Activity summary
        lines.append(f"- Merged: {self.merged_count} PR(s)")
        lines.append(f"- Open: {self.open_count} PR(s)")

        return "\n".join(lines)

    def format_table_row(self, rank: int = 0) -> str:
        """Format team member as a table row for compact display

        Args:
            rank: Ranking position (1-based), 0 for no rank display

        Returns:
            Formatted string: "🥇 username     5    2" or "@username    5    2"
        """
        # Medal emojis for top 3
        medals = ["🥇", "🥈", "🥉"]

        # Format rank/medal
        if rank > 0 and rank <= 3:
            prefix = medals[rank - 1]
        elif rank > 0:
            prefix = f"#{rank}"
        else:
            prefix = " "

        # Truncate long usernames
        username = self.username[:15]

        return f"{prefix} {username:<15} {self.merged_count:>3} {self.open_count:>3}"


class ProjectStats:
    """Statistics for a single project"""

    def __init__(self, project_name: str, spec_path: str):
        self.project_name = project_name
        self.spec_path = spec_path
        self.total_tasks = 0
        self.completed_tasks = 0
        self.in_progress_tasks = 0
        self.pending_tasks = 0
        self.total_cost_usd = 0.0

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

    def format_summary(self, for_slack: bool = False) -> str:
        """Format for GitHub/Slack markdown with progress bar

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown
        """
        fmt = MarkdownFormatter(for_slack)
        lines = []

        # Project header
        lines.append(fmt.header(f"📊 {self.project_name}", level=3))
        lines.append("")

        # Progress bar and tasks on same line for compactness
        lines.append(f"{self.format_progress_bar()} · {self.completed_tasks}/{self.total_tasks} complete")

        # Compact status breakdown - only show non-zero counts
        status_parts = []
        status_parts.append(f"✅{self.completed_tasks}")
        if self.in_progress_tasks > 0:
            status_parts.append(f"🔄{self.in_progress_tasks}")
        if self.pending_tasks > 0:
            status_parts.append(f"⏸️{self.pending_tasks}")

        lines.append(" · ".join(status_parts))

        return "\n".join(lines)

    def format_table_row(self) -> str:
        """Format project as a table row for compact display

        Returns:
            Formatted string: "project-name    5    3    1    1"
        """
        # Truncate long project names
        name = self.project_name[:20]
        return f"{name:<20} {self.total_tasks:>3} {self.completed_tasks:>3} {self.in_progress_tasks:>3} {self.pending_tasks:>3}"


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

    def format_leaderboard(self, for_slack: bool = False) -> str:
        """Format leaderboard showing top contributors with rankings

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown

        Returns:
            Formatted leaderboard with medals and rankings
        """
        fmt = MarkdownFormatter(for_slack)
        lines = []

        if not self.team_stats:
            return ""

        # Sort by activity level (merged PRs desc, then username)
        sorted_members = sorted(
            self.team_stats.items(),
            key=lambda x: (-x[1].merged_count, x[0])
        )

        # Filter to only members with activity
        active_members = [(username, stats) for username, stats in sorted_members
                         if stats.merged_count > 0]

        if not active_members:
            return ""

        # Header
        lines.append(fmt.header("🏆 Leaderboard", level=2))
        lines.append("")

        # Medal emojis for top 3
        medals = ["🥇", "🥈", "🥉"]

        for idx, (username, stats) in enumerate(active_members):
            rank = idx + 1

            # Get medal or rank number
            if rank <= 3:
                rank_display = medals[idx]
            else:
                rank_display = f"#{rank}"

            # Format the leaderboard entry
            merged = stats.merged_count
            open_prs = stats.open_count

            # Create activity bar (visual representation of merged PRs)
            max_merged = active_members[0][1].merged_count if active_members else 1
            bar_width = 10
            filled = int((merged / max_merged) * bar_width) if max_merged > 0 else 0

            # Use lighter squares for Slack, full blocks for GitHub
            if for_slack:
                bar = "▓" * filled + "░" * (bar_width - filled)
            else:
                bar = "█" * filled + "░" * (bar_width - filled)

            lines.append(f"{rank_display} {fmt.bold(f'@{username}')} - {merged} PR(s) merged")
            lines.append(f"   {bar}")
            if open_prs > 0:
                lines.append(f"   {fmt.italic(f'({open_prs} open PR(s))')}")
            lines.append("")

        return "\n".join(lines)

    def format_for_slack(self) -> str:
        """Complete report in Slack mrkdwn format with tables"""
        fmt = MarkdownFormatter(for_slack=True)
        lines = []

        # Header
        lines.append(fmt.header("🤖 ClaudeStep Statistics Report", level=1))
        lines.append("")

        if self.generated_at:
            from datetime import datetime
            timestamp = self.generated_at.strftime("%Y-%m-%d %H:%M UTC")
            lines.append(fmt.italic(f"Generated: {timestamp}"))
            lines.append("")

        # Leaderboard Table
        if self.team_stats:
            # Filter to active members only
            sorted_members = sorted(
                self.team_stats.items(),
                key=lambda x: (-x[1].merged_count, x[0])
            )
            active_members = [(username, stats) for username, stats in sorted_members
                             if stats.merged_count > 0]

            if active_members:
                lines.append(fmt.header("🏆 Leaderboard", level=2))
                lines.append("```")

                # Build table using TableFormatter
                table = TableFormatter(
                    headers=["Rank", "Username", "Open", "Merged"],
                    align=['left', 'left', 'right', 'right']
                )

                medals = ["🥇", "🥈", "🥉"]
                for idx, (username, stats) in enumerate(active_members):
                    rank_display = medals[idx] if idx < 3 else f"#{idx+1}"
                    table.add_row([
                        rank_display,
                        username[:15],
                        str(stats.open_count),
                        str(stats.merged_count)
                    ])

                lines.append(table.format())
                lines.append("```")
                lines.append("")

        # Project Statistics Table
        if self.project_stats:
            lines.append(fmt.header("📊 Project Progress", level=2))
            lines.append("```")

            # Build table using TableFormatter
            table = TableFormatter(
                headers=["Project", "Open", "Merged", "Total", "Progress", "Cost"],
                align=['left', 'right', 'right', 'right', 'left', 'right']
            )

            for project_name in sorted(self.project_stats.keys()):
                stats = self.project_stats[project_name]
                pct = stats.completion_percentage

                # Create progress bar
                bar_width = 10
                filled = int((pct / 100) * bar_width)
                bar = "█" * filled + "░" * (bar_width - filled)
                progress_display = f"{bar} {pct:>3.0f}%"

                # Format cost
                cost_display = f"${stats.total_cost_usd:.2f}" if stats.total_cost_usd > 0 else "-"

                table.add_row([
                    project_name[:20],
                    str(stats.in_progress_tasks),
                    str(stats.completed_tasks),
                    str(stats.total_tasks),
                    progress_display,
                    cost_display
                ])

            lines.append(table.format())
            lines.append("```")
            lines.append("")
        else:
            lines.append(fmt.header("📊 Project Progress", level=2))
            lines.append("")
            lines.append(fmt.italic("No projects found"))
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
