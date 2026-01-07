"""Data models for ClaudeChain operations"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Literal, Optional
from claudechain.domain.formatters.report_elements import (
    Header,
    TextBlock,
    Link,
    ListItem,
    ListBlock,
    TableColumn,
    TableRow,
    Table,
    Section,
)
from claudechain.domain.formatters.slack_formatter import SlackReportFormatter
from claudechain.domain.formatters.markdown_formatter import MarkdownReportFormatter
from claudechain.domain.formatting import format_usd
from claudechain.domain.github_models import GitHubPullRequest, PRState


@dataclass(frozen=True)
class BranchInfo:
    """Parsed ClaudeChain branch information.

    Represents the components of a ClaudeChain branch name in the format:
    claude-chain-{project_name}-{task_hash}

    Attributes:
        project_name: Name of the project (e.g., "my-refactor", "auth-migration")
        task_hash: 8-character hexadecimal task identifier (e.g., "a3f2b891")
        format_version: Branch format version (currently always "hash")

    Examples:
        >>> info = BranchInfo.from_branch_name("claude-chain-my-refactor-a3f2b891")
        >>> info.project_name
        'my-refactor'
        >>> info.task_hash
        'a3f2b891'
        >>> info.format_version
        'hash'
    """

    project_name: str
    task_hash: str
    format_version: Literal["hash"] = "hash"

    @classmethod
    def from_branch_name(cls, branch: str) -> Optional["BranchInfo"]:
        """Parse a ClaudeChain branch name into its components.

        Expected format: claude-chain-{project_name}-{hash}

        The project name can contain hyphens, so we match greedily up to the
        last hyphen before the hash. The hash must be exactly 8 lowercase
        hexadecimal characters.

        Args:
            branch: Branch name to parse

        Returns:
            BranchInfo instance if branch matches pattern, None otherwise

        Examples:
            >>> BranchInfo.from_branch_name("claude-chain-my-refactor-a3f2b891")
            BranchInfo(project_name='my-refactor', task_hash='a3f2b891', format_version='hash')
            >>> BranchInfo.from_branch_name("invalid-branch")
            None
            >>> BranchInfo.from_branch_name("claude-chain-auth-api-migration-f7c4d3e2")
            BranchInfo(project_name='auth-api-migration', task_hash='f7c4d3e2', format_version='hash')
        """
        # Pattern: claude-chain-{project}-{hash}
        # Project name can contain hyphens, so we match greedily up to the last hyphen
        pattern = r"^claude-chain-(.+)-([a-z0-9]+)$"
        match = re.match(pattern, branch)

        if not match:
            return None

        project_name = match.group(1)
        identifier = match.group(2)

        # Hash format: 8 hexadecimal characters (lowercase)
        if len(identifier) == 8 and all(c in "0123456789abcdef" for c in identifier):
            return cls(
                project_name=project_name,
                task_hash=identifier,
                format_version="hash"
            )

        return None


class TaskStatus(Enum):
    """Status of a task in the spec.md file.

    Used to track whether a task is pending, in progress, or completed.
    """

    PENDING = "pending"  # Task not started, no PR
    IN_PROGRESS = "in_progress"  # Task has open PR
    COMPLETED = "completed"  # Task marked as done in spec (checkbox checked)


@dataclass
class TaskWithPR:
    """A task from spec.md linked to its associated PR (if any).

    This model represents the relationship between a task defined in spec.md
    and the GitHub PR that implements it. Used for detailed statistics reporting
    to show task-level progress and identify orphaned PRs.

    Attributes:
        task_hash: 8-character hash from spec task (stable identifier)
        description: Task description text from spec.md
        status: Current task status (PENDING, IN_PROGRESS, COMPLETED)
        pr: Associated GitHub PR if one exists, None otherwise

    Examples:
        >>> # Task with associated open PR
        >>> task = TaskWithPR(
        ...     task_hash="a3f2b891",
        ...     description="Add user authentication",
        ...     status=TaskStatus.IN_PROGRESS,
        ...     pr=some_pr
        ... )
        >>> task.has_pr
        True

        >>> # Task without PR
        >>> task = TaskWithPR(
        ...     task_hash="b4c3d2e1",
        ...     description="Add input validation",
        ...     status=TaskStatus.PENDING,
        ...     pr=None
        ... )
        >>> task.has_pr
        False
    """

    task_hash: str
    description: str
    status: TaskStatus
    pr: Optional[GitHubPullRequest] = None
    cost_usd: float = 0.0

    @property
    def has_pr(self) -> bool:
        """Check if this task has an associated PR.

        Returns:
            True if task has a PR, False otherwise
        """
        return self.pr is not None

    @property
    def pr_number(self) -> Optional[int]:
        """Get the PR number if available.

        Returns:
            PR number or None if no PR
        """
        return self.pr.number if self.pr else None

    @property
    def pr_state(self) -> Optional[PRState]:
        """Get the PR state if available.

        Returns:
            PRState enum value or None if no PR
        """
        if self.pr is None:
            return None
        return PRState.from_string(self.pr.state)


def parse_iso_timestamp(timestamp_str: str) -> datetime:
    """Parse ISO 8601 timestamp, ensuring timezone-aware result

    Handles both legacy format (naive) and new format (timezone-aware):
    - "2025-12-29T23:47:49.299060" → parsed with UTC timezone added
    - "2025-12-29T23:47:49.299060+00:00" → parsed as-is
    - "2025-12-29T23:47:49.299060Z" → parsed as-is

    Args:
        timestamp_str: ISO 8601 formatted timestamp string

    Returns:
        Timezone-aware datetime object (always has tzinfo)
    """
    dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Legacy format without timezone - assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass
class CapacityResult:
    """Result of project capacity check.

    ClaudeChain allows only 1 open PR per project at a time.
    """

    has_capacity: bool
    assignee: Optional[str]
    open_prs: List[Dict]
    project_name: str

    @property
    def open_count(self) -> int:
        """Number of currently open PRs"""
        return len(self.open_prs)

    def format_summary(self) -> str:
        """Generate formatted summary for GitHub Actions output"""
        lines = ["## Capacity Check", ""]

        # Project header with status emoji
        status_emoji = "✅" if self.has_capacity else "❌"
        lines.append(f"### {status_emoji} **{self.project_name}**")
        lines.append("")

        # Capacity info
        lines.append(f"**Max PRs Allowed:** 1")
        lines.append(f"**Currently Open:** {self.open_count}/1")
        lines.append("")

        # List open PRs with details
        if self.open_prs:
            lines.append("**Open PRs:**")
            for pr_info in self.open_prs:
                pr_num = pr_info.get("pr_number", "?")
                task_desc = pr_info.get("task_description", "Unknown task")
                lines.append(f"- PR #{pr_num}: {task_desc}")
            lines.append("")
        else:
            lines.append("**Open PRs:** None")
            lines.append("")

        # Final decision
        lines.append("---")
        lines.append("")
        if not self.has_capacity:
            lines.append("**Decision:** ⏸️ At capacity - waiting for PR to be reviewed")
        elif self.assignee:
            lines.append(f"**Decision:** ✅ Capacity available - assignee: **{self.assignee}**")
        else:
            lines.append("**Decision:** ✅ Capacity available - PR will be created without assignee")

        return "\n".join(lines)


@dataclass
class PRReference:
    """Reference to a pull request for statistics

    Lightweight model that stores just the information needed for
    statistics display, not the full PR details.
    """

    pr_number: int
    title: str
    project: str
    timestamp: datetime  # merged_at or created_at depending on context

    def __post_init__(self):
        """Validate that all datetimes are timezone-aware"""
        if self.timestamp.tzinfo is None:
            raise ValueError(f"timestamp must be timezone-aware, got: {self.timestamp}")


    def format_display(self) -> str:
        """Format for display: '[project] #123: Title'"""
        return f"[{self.project}] #{self.pr_number}: {self.title}"


class TeamMemberStats:
    """Statistics for a single team member"""

    def __init__(self, username: str):
        self.username = username
        self.merged_prs: List[PRReference] = []  # Type-safe list of PR references
        self.open_prs: List[PRReference] = []    # Type-safe list of PR references

    @property
    def merged_count(self) -> int:
        """Number of merged PRs"""
        return len(self.merged_prs)

    @property
    def open_count(self) -> int:
        """Number of open PRs"""
        return len(self.open_prs)

    def add_merged_pr(self, pr_ref: PRReference):
        """Add merged PR reference"""
        self.merged_prs.append(pr_ref)

    def add_open_pr(self, pr_ref: PRReference):
        """Add open PR reference"""
        self.open_prs.append(pr_ref)

    def get_prs_by_project(self, pr_list: List[PRReference]) -> Dict[str, List[PRReference]]:
        """Group PR references by project"""
        by_project: Dict[str, List[PRReference]] = {}
        for pr_ref in pr_list:
            if pr_ref.project not in by_project:
                by_project[pr_ref.project] = []
            by_project[pr_ref.project].append(pr_ref)
        return by_project

    def to_summary_section(self) -> Section:
        """Build summary section for this team member.

        Returns:
            Section containing team member summary
        """
        # Emoji status indicator
        if self.merged_count > 0 or self.open_count > 0:
            status_emoji = "✅"
        else:
            status_emoji = "💤"

        section = Section()
        section.add(TextBlock(f"{status_emoji} @{self.username}", style="bold"))
        section.add(ListBlock((
            ListItem(f"Merged: {self.merged_count} PR(s)"),
            ListItem(f"Open: {self.open_count} PR(s)"),
        )))
        return section

    def format_summary(self, for_slack: bool = False) -> str:
        """Format for GitHub/Slack markdown output

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown
        """
        formatter = SlackReportFormatter() if for_slack else MarkdownReportFormatter()
        return formatter.format_section(self.to_summary_section())

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
    """Statistics for a single project

    Attributes:
        project_name: Name of the project
        spec_path: Path to the spec.md file
        total_tasks: Total number of tasks in spec.md
        completed_tasks: Number of completed tasks (checked off)
        in_progress_tasks: Number of tasks with open PRs
        pending_tasks: Number of tasks without PRs
        total_cost_usd: Total AI cost for this project
        open_prs: List of open PRs for this project
        stale_pr_count: Number of PRs that are stale
        tasks: Detailed list of tasks with their PR associations
        orphaned_prs: PRs whose task hashes don't match any current spec task
    """

    def __init__(self, project_name: str, spec_path: str):
        self.project_name = project_name
        self.spec_path = spec_path
        self.total_tasks = 0
        self.completed_tasks = 0
        self.in_progress_tasks = 0
        self.pending_tasks = 0
        self.total_cost_usd = 0.0
        self.open_prs: List[GitHubPullRequest] = []
        self.stale_pr_count: int = 0
        # New: Detailed task-PR mapping
        self.tasks: List[TaskWithPR] = []
        self.orphaned_prs: List[GitHubPullRequest] = []

    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_tasks == 0:
            return 0.0
        return (self.completed_tasks / self.total_tasks) * 100

    @property
    def has_remaining_tasks(self) -> bool:
        """Check if project has remaining tasks but no open PRs.

        This indicates a project that may need attention - there's work
        to be done but no PRs in progress.

        Returns:
            True if pending_tasks > 0 and in_progress_tasks == 0
        """
        return self.pending_tasks > 0 and self.in_progress_tasks == 0

    def format_progress_bar(self, width: int = 10) -> str:
        """Generate Unicode progress bar

        Args:
            width: Number of characters for the bar

        Returns:
            String like "████████░░ 80%"
        """
        if self.total_tasks == 0:
            return "░" * width + " 0%"

        pct = self.completion_percentage
        filled = int((pct / 100) * width)
        # Show at least 1 filled block if there's any progress
        if pct > 0 and filled == 0:
            filled = 1
        empty = width - filled
        bar = "█" * filled + "░" * empty
        return f"{bar} {pct:.0f}%"

    def to_summary_section(self) -> Section:
        """Build summary section for this project.

        Returns:
            Section containing project summary with progress bar
        """
        section = Section(header=Header(f"📊 {self.project_name}", level=3))

        # Progress bar and completion info
        section.add(TextBlock(
            f"{self.format_progress_bar()} · {self.completed_tasks}/{self.total_tasks} complete"
        ))

        # Compact status breakdown - only show non-zero counts
        status_parts = [f"✅{self.completed_tasks}"]
        if self.in_progress_tasks > 0:
            status_parts.append(f"🔄{self.in_progress_tasks}")
        if self.pending_tasks > 0:
            status_parts.append(f"⏸️{self.pending_tasks}")
        if self.total_cost_usd > 0:
            status_parts.append(f"💰{format_usd(self.total_cost_usd)}")

        section.add(TextBlock(" · ".join(status_parts)))
        return section

    def format_summary(self, for_slack: bool = False) -> str:
        """Format for GitHub/Slack markdown with progress bar

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown
        """
        formatter = SlackReportFormatter() if for_slack else MarkdownReportFormatter()
        return formatter.format_section(self.to_summary_section())

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

    def __init__(self, repo: Optional[str] = None):
        self.team_stats = {}      # username -> TeamMemberStats
        self.project_stats = {}   # project_name -> ProjectStats
        self.generated_at = None  # datetime
        self.repo = repo  # GitHub repository (owner/name)
        self.generation_time_seconds: Optional[float] = None  # Time to generate report

    def add_team_member(self, stats: TeamMemberStats):
        """Add team member statistics"""
        self.team_stats[stats.username] = stats

    def add_project(self, stats: ProjectStats):
        """Add project statistics"""
        self.project_stats[stats.project_name] = stats

    def projects_needing_attention(self) -> List[ProjectStats]:
        """Get projects that need attention.

        A project needs attention if:
        - It has stale PRs (stale_pr_count > 0), OR
        - It has remaining tasks but no open PRs (has_remaining_tasks is True), OR
        - It has open orphaned PRs (PRs whose tasks were removed from spec)

        Note: Merged orphaned PRs don't require attention (shown in workflow report only).

        Returns:
            List of ProjectStats for projects needing attention, sorted by project name
        """
        needing_attention = []
        for stats in self.project_stats.values():
            has_open_orphaned_prs = any(pr.is_open() for pr in stats.orphaned_prs)
            if stats.stale_pr_count > 0 or stats.has_remaining_tasks or has_open_orphaned_prs:
                needing_attention.append(stats)
        return sorted(needing_attention, key=lambda s: s.project_name)

    def _build_pr_url(self, pr_number: int) -> Optional[str]:
        """Construct GitHub PR URL from repo and PR number.

        Args:
            pr_number: The pull request number

        Returns:
            Full GitHub PR URL, or None if repo is not set
        """
        if not self.repo:
            return None
        return f"https://github.com/{self.repo}/pull/{pr_number}"

    def _format_pr_duration(self, pr) -> str:
        """Format how long a PR was/is open with appropriate units.

        Uses days if ≥1 day, hours if ≥1 hour, otherwise minutes.

        Args:
            pr: GitHubPullRequest to get duration for

        Returns:
            Formatted duration string like "2d", "5h", or "30m"
        """
        if pr.state == "open":
            end_time = datetime.now(timezone.utc)
        else:
            end_time = pr.merged_at if pr.merged_at else datetime.now(timezone.utc)

        delta = end_time - pr.created_at
        total_minutes = int(delta.total_seconds() / 60)

        if delta.days >= 1:
            return f"{delta.days}d"
        elif total_minutes >= 60:
            return f"{total_minutes // 60}h"
        else:
            return f"{max(1, total_minutes)}m"

    def to_header_section(self) -> Section:
        """Build report header section with metadata.

        Note: The main title "ClaudeChain Statistics" is handled by the Slack
        notification title, so we don't duplicate it here.

        Returns:
            Section containing repo and branch metadata (if any)
        """
        section = Section()

        # Build metadata parts
        metadata_parts = []
        if self.repo:
            metadata_parts.append(self.repo)

        if metadata_parts:
            section.add(TextBlock(" · ".join(metadata_parts), style="italic"))

        return section

    def to_leaderboard_section(self) -> Section:
        """Build leaderboard section showing top contributors.

        Returns:
            Section containing the leaderboard table, or empty section if no active members
        """
        section = Section(header=Header("🏆 Leaderboard", level=2))

        if not self.team_stats:
            return section

        # Sort by activity level (merged PRs desc, then username)
        sorted_members = sorted(
            self.team_stats.items(),
            key=lambda x: (-x[1].merged_count, x[0])
        )

        # Filter to only members with activity
        active_members = [(username, stats) for username, stats in sorted_members
                         if stats.merged_count > 0]

        if not active_members:
            return section

        # Build table
        columns = (
            TableColumn("Rank", align="left"),
            TableColumn("Username", align="left"),
            TableColumn("Open", align="right"),
            TableColumn("Merged", align="right"),
        )

        medals = ["🥇", "🥈", "🥉"]
        rows = []
        for idx, (username, stats) in enumerate(active_members):
            rank_display = medals[idx] if idx < 3 else f"#{idx+1}"
            rows.append(TableRow((
                rank_display,
                username[:15],
                str(stats.open_count),
                str(stats.merged_count),
            )))

        section.add(Table(columns=columns, rows=tuple(rows), in_code_block=True))
        return section

    def to_project_progress_section(self) -> Section:
        """Build project progress section with statistics table.

        Returns:
            Section containing the project progress table
        """
        section = Section(header=Header("Project Progress", level=2))

        if not self.project_stats:
            section.add(TextBlock("No projects found", style="italic"))
            return section

        # Build table
        columns = (
            TableColumn("Project", align="left"),
            TableColumn("Open", align="right"),
            TableColumn("Merged", align="right"),
            TableColumn("Total", align="right"),
            TableColumn("Progress", align="left"),
            TableColumn("Cost", align="right"),
        )

        rows = []
        for project_name in sorted(self.project_stats.keys()):
            stats = self.project_stats[project_name]

            # Create progress bar data
            pct = stats.completion_percentage
            bar_width = 10
            filled = int((pct / 100) * bar_width)
            # Show at least 1 filled block if there's any progress
            if pct > 0 and filled == 0:
                filled = 1
            bar = "█" * filled + "░" * (bar_width - filled)
            progress_display = f"{bar} {pct:>3.0f}%"

            # Format cost
            cost_display = format_usd(stats.total_cost_usd) if stats.total_cost_usd > 0 else "-"

            rows.append(TableRow((
                project_name[:20],
                str(stats.in_progress_tasks),
                str(stats.completed_tasks),
                str(stats.total_tasks),
                progress_display,
                cost_display,
            )))

        section.add(Table(columns=columns, rows=tuple(rows), in_code_block=True))
        return section

    def to_warnings_section(self, stale_pr_days: int = 7) -> Section:
        """Build warnings section for projects needing attention.

        Args:
            stale_pr_days: Threshold for stale PRs

        Returns:
            Section containing warnings, or empty section if no warnings
        """
        section = Section(header=Header("⚠️ Needs Attention", level=2))

        projects = self.projects_needing_attention()
        if not projects:
            return section

        for stats in projects:
            project_items = []

            # Collect all open PRs with their status indicators
            for pr in stats.open_prs:
                indicators = []
                if pr.is_stale(stale_pr_days):
                    indicators.append("stale")
                assignee = pr.first_assignee or "unassigned"

                status_parts = [self._format_pr_duration(pr), assignee]
                if indicators:
                    status_parts.extend(indicators)

                status_text = ", ".join(status_parts)
                url = pr.url or self._build_pr_url(pr.number)
                if url:
                    project_items.append(ListItem(
                        Link(f"#{pr.number} ({status_text})", url),
                        bullet="•"
                    ))
                else:
                    project_items.append(ListItem(
                        f"#{pr.number} ({status_text})",
                        bullet="•"
                    ))

            # Add open orphaned PRs
            for pr in stats.orphaned_prs:
                if pr.is_open():
                    url = pr.url or self._build_pr_url(pr.number)
                    status_text = f"{self._format_pr_duration(pr)}, orphaned"
                    if url:
                        project_items.append(ListItem(
                            Link(f"#{pr.number} ({status_text})", url),
                            bullet="•"
                        ))
                    else:
                        project_items.append(ListItem(
                            f"#{pr.number} ({status_text})",
                            bullet="•"
                        ))

            # Add warning if no open PRs but tasks remain
            if stats.has_remaining_tasks:
                project_items.append(ListItem(
                    f"No open PRs ({stats.pending_tasks} tasks remaining)",
                    bullet="•"
                ))

            if project_items:
                # Add project header as bold text, then the list
                section.add(TextBlock(stats.project_name, style="bold"))
                section.add(ListBlock(tuple(project_items)))

        return section

    def to_project_details_section(self) -> Section:
        """Build detailed task view showing each task with its PR association.

        Returns:
            Section containing detailed task-PR mappings for all projects
        """
        section = Section()

        for project_name in sorted(self.project_stats.keys()):
            stats = self.project_stats[project_name]

            # Project header with completion count
            header_text = f"{project_name} ({stats.completed_tasks}/{stats.total_tasks} complete)"
            project_section = Section(header=Header(header_text, level=2))

            # Tasks section as a table
            if stats.tasks:
                project_section.add(Header("Tasks", level=3))

                # Build table with columns: Checkbox, Task, PR, Status, Cost
                columns = (
                    TableColumn(header="", align="center"),  # checkbox
                    TableColumn(header="Task", align="left"),
                    TableColumn(header="PR", align="left"),
                    TableColumn(header="Status", align="left"),
                    TableColumn(header="Cost", align="right"),
                )

                rows = []
                total_cost = 0.0
                for task in stats.tasks:
                    checkbox = "✓" if task.status == TaskStatus.COMPLETED else ""
                    # Truncate long descriptions
                    desc = task.description[:50] + "..." if len(task.description) > 50 else task.description

                    if task.has_pr:
                        pr = task.pr
                        pr_url = pr.url or self._build_pr_url(pr.number)
                        duration = self._format_pr_duration(pr)
                        if pr.is_merged():
                            status = f"Merged ({duration})"
                        elif pr.is_open():
                            status = f"Open ({duration})"
                        else:
                            status = "Closed"
                        # PR link in its own column, status separate
                        if pr_url:
                            pr_info = Link(f"#{pr.number}", pr_url)
                        else:
                            pr_info = f"#{pr.number}"
                    else:
                        pr_info = "-"
                        status = "-"

                    cost_str = f"${task.cost_usd:.2f}" if task.cost_usd > 0 else "-"
                    total_cost += task.cost_usd

                    rows.append(TableRow(cells=(checkbox, desc, pr_info, status, cost_str)))

                # Add total row if there are costs
                if total_cost > 0:
                    rows.append(TableRow(cells=("", "", "", "**Total**", f"**${total_cost:.2f}**")))

                project_section.add(Table(columns=columns, rows=tuple(rows)))

            # Orphaned PRs section
            if stats.orphaned_prs:
                orphan_items = []
                for pr in stats.orphaned_prs:
                    duration = self._format_pr_duration(pr)
                    if pr.is_merged():
                        state = f"Merged, {duration}"
                    elif pr.is_open():
                        state = f"Open, {duration}"
                    else:
                        state = "Closed"
                    orphan_items.append(ListItem(f"PR #{pr.number} ({state}) - Task removed from spec"))

                project_section.add(Header("Orphaned PRs", level=3))
                project_section.add(TextBlock(
                    "> **Note:** Orphaned PRs are pull requests whose associated tasks have been "
                    "removed from the spec file.\n"
                    "> These may need manual review to determine if they should be closed or "
                    "if the task should be restored."
                ))
                project_section.add(ListBlock(tuple(orphan_items)))

            section.add(project_section)

        return section

    def format_leaderboard(self, for_slack: bool = False) -> str:
        """Format leaderboard showing top contributors with rankings

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise use standard markdown

        Returns:
            Formatted leaderboard with medals and rankings
        """
        section = self.to_leaderboard_section()
        if section.is_empty():
            return ""

        formatter = SlackReportFormatter() if for_slack else MarkdownReportFormatter()
        return formatter.format_section(section)

    def format_warnings_section(self, for_slack: bool = False, stale_pr_days: int = 7) -> str:
        """Format actionable items section for projects needing attention.

        Shows all open PRs that need action, with clickable links and status indicators:
        - Stale PRs (open too long)
        - Orphaned PRs (task removed from spec)
        - Projects with no open PRs but pending tasks

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise GitHub markdown
            stale_pr_days: Threshold for stale PRs (used in descriptions)

        Returns:
            Formatted warnings section or empty string if no warnings
        """
        section = self.to_warnings_section(stale_pr_days)
        if section.is_empty():
            return ""

        formatter = SlackReportFormatter() if for_slack else MarkdownReportFormatter()
        return formatter.format_section(section)

    def format_for_slack(
        self,
        show_assignee_stats: bool = False,
        stale_pr_days: int = 7,
    ) -> str:
        """Complete report in Slack mrkdwn format with tables

        Args:
            show_assignee_stats: Whether to include the assignee leaderboard (default: False)
            stale_pr_days: Threshold for stale PR warnings (default: 7 days)
        """
        formatter = SlackReportFormatter()
        sections = []

        # Header section (branch info if specified)
        header = self.to_header_section()
        if not header.is_empty():
            sections.append(formatter.format_section(header))

        # Leaderboard section (only if enabled)
        if show_assignee_stats:
            leaderboard = self.to_leaderboard_section()
            if not leaderboard.is_empty():
                sections.append(formatter.format_section(leaderboard))

        # Project progress section
        sections.append(formatter.format_section(self.to_project_progress_section()))

        # Warnings section
        warnings = self.to_warnings_section(stale_pr_days)
        if not warnings.is_empty():
            sections.append(formatter.format_section(warnings))

        # Generation time footer
        if self.generation_time_seconds is not None:
            sections.append(f"_Elapsed time: {self.generation_time_seconds:.1f}s_")

        return "\n\n".join(sections)

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

    def format_project_details(self, for_slack: bool = False) -> str:
        """Format detailed task view showing each task with its PR association.

        Shows all tasks from spec.md with their status and associated PRs (if any),
        plus any orphaned PRs (PRs whose tasks were removed from spec).

        Args:
            for_slack: If True, use Slack mrkdwn format; otherwise GitHub markdown

        Returns:
            Formatted string with task details and orphaned PRs

        Example output:
            ## my-project (5/20 complete)

            ### Tasks
            - [x] `echo "Hello"` - PR #31 (Merged)
            - [ ] `echo "World"` - PR #32 (Open, 2d)
            - [ ] `echo "Foo"` - (no PR)

            ### Orphaned PRs
            - PR #25 (Merged) - Task removed from spec
        """
        section = self.to_project_details_section()
        formatter = SlackReportFormatter() if for_slack else MarkdownReportFormatter()
        return formatter.format_section(section)

    def to_json(self) -> str:
        """Export as JSON for programmatic access"""
        import json
        from datetime import datetime

        data = {
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "repo": self.repo,
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
                "merged_prs": [
                    {
                        "pr_number": pr.pr_number,
                        "title": pr.title,
                        "project": pr.project,
                        "timestamp": pr.timestamp.isoformat()
                    }
                    for pr in stats.merged_prs
                ],
                "open_prs": [
                    {
                        "pr_number": pr.pr_number,
                        "title": pr.title,
                        "project": pr.project,
                        "timestamp": pr.timestamp.isoformat()
                    }
                    for pr in stats.open_prs
                ],
                "merged_count": stats.merged_count,
                "open_count": stats.open_count
            }

        return json.dumps(data, indent=2)


@dataclass
class AITask:
    """Metadata for a single AI operation within a PR

    Represents one AI task (e.g., code generation, PR summary, refinement)
    that contributes to a pull request.
    """

    type: str  # Task type: "PRCreation", "PRRefinement", "PRSummary", etc.
    model: str  # AI model used (e.g., "claude-sonnet-4", "claude-opus-4")
    cost_usd: float  # Cost for this specific AI operation
    created_at: datetime  # When this AI task was executed
    tokens_input: int = 0  # Input tokens used
    tokens_output: int = 0  # Output tokens generated
    duration_seconds: float = 0.0  # Time taken for this operation

    def __post_init__(self):
        """Validate that all datetimes are timezone-aware"""
        if self.created_at.tzinfo is None:
            raise ValueError(f"created_at must be timezone-aware, got: {self.created_at}")

    @classmethod
    def from_dict(cls, data: dict) -> "AITask":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing AI task data

        Returns:
            AITask instance
        """
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = parse_iso_timestamp(created_at)

        return cls(
            type=data["type"],
            model=data["model"],
            cost_usd=data["cost_usd"],
            created_at=created_at,
            tokens_input=data.get("tokens_input", 0),
            tokens_output=data.get("tokens_output", 0),
            duration_seconds=data.get("duration_seconds", 0.0),
        )

    def to_dict(self) -> dict:
        """Serialize to JSON dictionary

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "type": self.type,
            "model": self.model,
            "cost_usd": self.cost_usd,
            "created_at": self.created_at.isoformat(),
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class TaskMetadata:
    """Metadata for a single task/PR in ClaudeChain

    This model represents the metadata stored for each pull request created by ClaudeChain.
    It is used by both the artifact-based (legacy) and branch-based metadata storage systems.
    """

    task_index: int
    task_description: str
    project: str
    branch_name: str
    assignee: str
    created_at: datetime
    workflow_run_id: int
    pr_number: int
    pr_state: str = "open"  # "open", "merged", or "closed"

    # New: List of AI tasks that contributed to this PR
    ai_tasks: List["AITask"] = None  # type: ignore

    # Deprecated: Legacy flat cost fields (maintained for backward compatibility)
    # These are auto-calculated from ai_tasks if not provided
    model: str = "claude-sonnet-4"  # Deprecated: Use ai_tasks instead
    main_task_cost_usd: float = 0.0  # Deprecated: Use ai_tasks instead
    pr_summary_cost_usd: float = 0.0  # Deprecated: Use ai_tasks instead
    total_cost_usd: float = 0.0  # Deprecated: Use ai_tasks instead

    def __post_init__(self):
        """Initialize ai_tasks list if not provided and validate timezone-aware datetimes"""
        if self.ai_tasks is None:
            self.ai_tasks = []
        if self.created_at.tzinfo is None:
            raise ValueError(f"created_at must be timezone-aware, got: {self.created_at}")

    @classmethod
    def from_dict(cls, data: dict) -> "TaskMetadata":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing task metadata

        Returns:
            TaskMetadata instance
        """
        # Handle datetime parsing
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = parse_iso_timestamp(created_at)

        # Parse AI tasks if present (new format)
        ai_tasks = []
        if "ai_tasks" in data:
            ai_tasks = [AITask.from_dict(task_data) for task_data in data["ai_tasks"]]

        return cls(
            task_index=data["task_index"],
            task_description=data["task_description"],
            project=data["project"],
            branch_name=data["branch_name"],
            assignee=data.get("assignee", ""),
            created_at=created_at,
            workflow_run_id=data["workflow_run_id"],
            pr_number=data["pr_number"],
            pr_state=data.get("pr_state", "open"),
            ai_tasks=ai_tasks,
            # Legacy fields for backward compatibility
            model=data.get("model", "claude-sonnet-4"),
            main_task_cost_usd=data.get("main_task_cost_usd", 0.0),
            pr_summary_cost_usd=data.get("pr_summary_cost_usd", 0.0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
        )

    def to_dict(self) -> dict:
        """Serialize to JSON dictionary

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        result = {
            "task_index": self.task_index,
            "task_description": self.task_description,
            "project": self.project,
            "branch_name": self.branch_name,
            "assignee": self.assignee,
            "created_at": self.created_at.isoformat(),
            "workflow_run_id": self.workflow_run_id,
            "pr_number": self.pr_number,
            "pr_state": self.pr_state,
        }

        # Include AI tasks array (new format)
        if self.ai_tasks:
            result["ai_tasks"] = [task.to_dict() for task in self.ai_tasks]

        # Include legacy fields for backward compatibility
        # Auto-calculate from ai_tasks if available
        if self.ai_tasks:
            result["total_cost_usd"] = sum(task.cost_usd for task in self.ai_tasks)
            # Find primary model (most common or first)
            if self.ai_tasks:
                result["model"] = self.ai_tasks[0].model
        else:
            result["model"] = self.model
            result["main_task_cost_usd"] = self.main_task_cost_usd
            result["pr_summary_cost_usd"] = self.pr_summary_cost_usd
            result["total_cost_usd"] = self.total_cost_usd

        return result

    def add_ai_task(
        self,
        task_type: str,
        model: str,
        cost_usd: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
        duration_seconds: float = 0.0,
    ) -> None:
        """Add an AI task to this PR metadata

        Args:
            task_type: Type of AI task (e.g., "PRCreation", "PRRefinement")
            model: AI model used (e.g., "claude-sonnet-4")
            cost_usd: Cost in USD for this operation
            tokens_input: Input tokens used
            tokens_output: Output tokens generated
            duration_seconds: Time taken for this operation
        """
        ai_task = AITask(
            type=task_type,
            model=model,
            cost_usd=cost_usd,
            created_at=datetime.now(timezone.utc),
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            duration_seconds=duration_seconds,
        )
        self.ai_tasks.append(ai_task)

    def get_total_cost(self) -> float:
        """Calculate total cost from all AI tasks

        Returns:
            Total cost in USD
        """
        if self.ai_tasks:
            return sum(task.cost_usd for task in self.ai_tasks)
        return self.total_cost_usd

    def get_primary_model(self) -> str:
        """Get the primary AI model used for this PR

        Returns:
            Model name (first AI task's model, or legacy model field)
        """
        if self.ai_tasks:
            return self.ai_tasks[0].model
        return self.model


@dataclass
class ProjectMetadata:
    """Metadata for all tasks in a ClaudeChain project

    This model represents the structure of project JSON files stored in the
    claudechain-metadata branch. Each project has its own JSON file containing
    all task metadata for that project.
    """

    schema_version: str
    project: str
    last_updated: datetime
    tasks: List[TaskMetadata]

    def __post_init__(self):
        """Validate that all datetimes are timezone-aware"""
        if self.last_updated.tzinfo is None:
            raise ValueError(f"last_updated must be timezone-aware, got: {self.last_updated}")

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectMetadata":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing project metadata

        Returns:
            ProjectMetadata instance
        """
        # Handle datetime parsing
        last_updated = data["last_updated"]
        if isinstance(last_updated, str):
            last_updated = parse_iso_timestamp(last_updated)

        # Parse tasks
        tasks = [TaskMetadata.from_dict(task_data) for task_data in data.get("tasks", [])]

        return cls(
            schema_version=data.get("schema_version", "1.0"),
            project=data["project"],
            last_updated=last_updated,
            tasks=tasks,
        )

    def to_dict(self) -> dict:
        """Serialize to JSON dictionary

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "schema_version": self.schema_version,
            "project": self.project,
            "last_updated": self.last_updated.isoformat(),
            "tasks": [task.to_dict() for task in self.tasks],
        }

    @classmethod
    def create_empty(cls, project: str) -> "ProjectMetadata":
        """Create an empty project metadata instance

        Args:
            project: Project name

        Returns:
            Empty ProjectMetadata instance with current timestamp
        """
        return cls(
            schema_version="1.0",
            project=project,
            last_updated=datetime.now(timezone.utc),
            tasks=[],
        )


