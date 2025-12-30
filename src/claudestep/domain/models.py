"""Data models for ClaudeStep operations"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from claudestep.services.formatters.table_formatter import TableFormatter


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
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

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
    """Metadata for a single task/PR in ClaudeStep

    This model represents the metadata stored for each pull request created by ClaudeStep.
    It is used by both the artifact-based (legacy) and branch-based metadata storage systems.
    """

    task_index: int
    task_description: str
    project: str
    branch_name: str
    reviewer: str
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
        """Initialize ai_tasks list if not provided"""
        if self.ai_tasks is None:
            self.ai_tasks = []

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
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Parse AI tasks if present (new format)
        ai_tasks = []
        if "ai_tasks" in data:
            ai_tasks = [AITask.from_dict(task_data) for task_data in data["ai_tasks"]]

        return cls(
            task_index=data["task_index"],
            task_description=data["task_description"],
            project=data["project"],
            branch_name=data["branch_name"],
            reviewer=data["reviewer"],
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
            "reviewer": self.reviewer,
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
            created_at=datetime.now(),
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
    """Metadata for all tasks in a ClaudeStep project

    This model represents the structure of project JSON files stored in the
    claudestep-metadata branch. Each project has its own JSON file containing
    all task metadata for that project.
    """

    schema_version: str
    project: str
    last_updated: datetime
    tasks: List[TaskMetadata]

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
            last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))

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
            last_updated=datetime.now(),
            tasks=[],
        )


# ============================================================================
# Alternative Model 3: Hybrid Approach
# ============================================================================
# This is an alternative data model design that separates tasks (spec.md content)
# from pull requests (execution details). See docs/proposed/github-model-alternatives.md
# for full design rationale and comparison with other models.
#
# Key characteristics:
# - Task: Lightweight reference to spec.md with explicit status
# - PullRequest: Execution details that reference tasks by index
# - Clear separation: Task = "what" (spec), PR = "how" (execution)
# - Status enum: Explicit state machine (pending → in_progress → completed)
# ============================================================================


class TaskStatus(str, Enum):
    """Status of a task in ClaudeStep

    State machine:
    - PENDING: Not yet started (no PR created)
    - IN_PROGRESS: PR created but not merged
    - COMPLETED: PR merged
    """

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class Task:
    """Lightweight task reference from spec.md

    Represents a task definition from spec.md with its current status.
    Status is derived from associated PullRequest state.
    """

    index: int  # Position in spec.md (1-based)
    description: str  # Task description from spec.md
    status: TaskStatus  # Current task status (derived from PR state)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing task data

        Returns:
            Task instance
        """
        status_str = data.get("status", "pending")
        status = TaskStatus(status_str)

        return cls(
            index=data["index"],
            description=data["description"],
            status=status,
        )

    def to_dict(self) -> dict:
        """Serialize to JSON dictionary

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "index": self.index,
            "description": self.description,
            "status": self.status.value,
        }


@dataclass
class AIOperation:
    """Metadata for a single AI operation within a PR

    Represents one AI operation (e.g., code generation, PR summary, refinement)
    that contributes to a pull request.

    This is similar to AITask but renamed to clarify it's an operation
    within a PR execution.
    """

    type: str  # Operation type: "PRCreation", "PRRefinement", "PRSummary", etc.
    model: str  # AI model used (e.g., "claude-sonnet-4", "claude-opus-4")
    cost_usd: float  # Cost for this specific AI operation
    created_at: datetime  # When this AI operation was executed
    workflow_run_id: int  # GitHub Actions run that executed this operation
    tokens_input: int = 0  # Input tokens used
    tokens_output: int = 0  # Output tokens generated
    duration_seconds: float = 0.0  # Time taken for this operation

    @classmethod
    def from_dict(cls, data: dict) -> "AIOperation":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing AI operation data

        Returns:
            AIOperation instance
        """
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return cls(
            type=data["type"],
            model=data["model"],
            cost_usd=data["cost_usd"],
            created_at=created_at,
            workflow_run_id=data["workflow_run_id"],
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
            "workflow_run_id": self.workflow_run_id,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "duration_seconds": self.duration_seconds,
        }


@dataclass
class PullRequest:
    """Pull request execution details

    Represents a PR created for a task, with all execution metadata.
    References a Task by task_index.

    Multiple PRs can reference the same task_index (retry scenario).
    """

    task_index: int  # References Task.index
    pr_number: int  # GitHub PR number
    branch_name: str  # Git branch for this PR
    reviewer: str  # Assigned reviewer username
    pr_state: str  # "open", "merged", "closed"
    created_at: datetime  # When PR was created
    ai_operations: List[AIOperation]  # All AI work for this PR

    @classmethod
    def from_dict(cls, data: dict) -> "PullRequest":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing pull request data

        Returns:
            PullRequest instance
        """
        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        ai_operations = [
            AIOperation.from_dict(op_data) for op_data in data.get("ai_operations", [])
        ]

        return cls(
            task_index=data["task_index"],
            pr_number=data["pr_number"],
            branch_name=data["branch_name"],
            reviewer=data["reviewer"],
            pr_state=data["pr_state"],
            created_at=created_at,
            ai_operations=ai_operations,
        )

    def to_dict(self) -> dict:
        """Serialize to JSON dictionary

        Returns:
            Dictionary representation suitable for JSON serialization
        """
        return {
            "task_index": self.task_index,
            "pr_number": self.pr_number,
            "branch_name": self.branch_name,
            "reviewer": self.reviewer,
            "pr_state": self.pr_state,
            "created_at": self.created_at.isoformat(),
            "ai_operations": [op.to_dict() for op in self.ai_operations],
        }

    def get_total_cost(self) -> float:
        """Calculate total cost from all AI operations

        Returns:
            Total cost in USD
        """
        return sum(op.cost_usd for op in self.ai_operations)

    def get_total_tokens(self) -> tuple[int, int]:
        """Get total input and output tokens

        Returns:
            Tuple of (total_input_tokens, total_output_tokens)
        """
        total_input = sum(op.tokens_input for op in self.ai_operations)
        total_output = sum(op.tokens_output for op in self.ai_operations)
        return (total_input, total_output)

    def get_total_duration(self) -> float:
        """Calculate total duration of all AI operations in seconds

        Returns:
            Total duration in seconds
        """
        return sum(op.duration_seconds for op in self.ai_operations)


@dataclass
class HybridProjectMetadata:
    """Project metadata using Hybrid model (Alternative 3)

    This model separates tasks (spec.md content) from pull requests (execution).
    See docs/proposed/github-model-alternatives.md for design rationale.

    Key characteristics:
    - All tasks from spec.md are always present with explicit status
    - PRs are separate entities that reference tasks by index
    - Status is derived from PR state (single source of truth)
    - Supports multiple PRs per task (retry scenario)
    """

    schema_version: str  # Should be "2.0" for this model
    project: str  # Project name/identifier
    last_updated: datetime  # Last modification timestamp
    tasks: List[Task]  # All tasks from spec.md (always present)
    pull_requests: List[PullRequest]  # All PRs created (execution history)

    @classmethod
    def from_dict(cls, data: dict) -> "HybridProjectMetadata":
        """Parse from JSON dictionary

        Args:
            data: Dictionary containing project metadata

        Returns:
            HybridProjectMetadata instance
        """
        last_updated = data["last_updated"]
        if isinstance(last_updated, str):
            last_updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))

        tasks = [Task.from_dict(task_data) for task_data in data.get("tasks", [])]
        pull_requests = [
            PullRequest.from_dict(pr_data) for pr_data in data.get("pull_requests", [])
        ]

        return cls(
            schema_version=data.get("schema_version", "2.0"),
            project=data["project"],
            last_updated=last_updated,
            tasks=tasks,
            pull_requests=pull_requests,
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
            "pull_requests": [pr.to_dict() for pr in self.pull_requests],
        }

    def sync_task_statuses(self) -> None:
        """Synchronize task statuses with PR states

        Updates all task statuses based on their associated PRs.
        This ensures status is derived from PR state (single source of truth).

        For tasks with multiple PRs (retry scenario), uses the latest PR.
        """
        for task in self.tasks:
            # Find all PRs for this task
            prs_for_task = [pr for pr in self.pull_requests if pr.task_index == task.index]

            if not prs_for_task:
                task.status = TaskStatus.PENDING
                continue

            # Use latest PR to determine status
            latest_pr = max(prs_for_task, key=lambda pr: pr.created_at)

            if latest_pr.pr_state == "merged":
                task.status = TaskStatus.COMPLETED
            elif latest_pr.pr_state in ["open", "closed"]:
                task.status = TaskStatus.IN_PROGRESS
            else:
                task.status = TaskStatus.PENDING

    @classmethod
    def create_empty(cls, project: str) -> "HybridProjectMetadata":
        """Create an empty project metadata instance

        Args:
            project: Project name

        Returns:
            Empty HybridProjectMetadata instance with current timestamp
        """
        return cls(
            schema_version="2.0",
            project=project,
            last_updated=datetime.now(),
            tasks=[],
            pull_requests=[],
        )

    def get_task_by_index(self, index: int) -> Optional[Task]:
        """Get task by index

        Args:
            index: Task index (1-based)

        Returns:
            Task instance or None if not found
        """
        for task in self.tasks:
            if task.index == index:
                return task
        return None

    def get_prs_for_task(self, task_index: int) -> List[PullRequest]:
        """Get all PRs for a specific task

        Args:
            task_index: Task index (1-based)

        Returns:
            List of PullRequest instances (may be empty, or multiple for retries)
        """
        return [pr for pr in self.pull_requests if pr.task_index == task_index]

    def get_latest_pr_for_task(self, task_index: int) -> Optional[PullRequest]:
        """Get the latest PR for a specific task

        Args:
            task_index: Task index (1-based)

        Returns:
            Latest PullRequest instance or None if no PRs exist
        """
        prs = self.get_prs_for_task(task_index)
        if not prs:
            return None
        return max(prs, key=lambda pr: pr.created_at)

    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks

        Returns:
            List of Task instances with status PENDING
        """
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    def get_in_progress_tasks(self) -> List[Task]:
        """Get all in-progress tasks

        Returns:
            List of Task instances with status IN_PROGRESS
        """
        return [task for task in self.tasks if task.status == TaskStatus.IN_PROGRESS]

    def get_completed_tasks(self) -> List[Task]:
        """Get all completed tasks

        Returns:
            List of Task instances with status COMPLETED
        """
        return [task for task in self.tasks if task.status == TaskStatus.COMPLETED]

    def get_total_cost(self) -> float:
        """Calculate total cost across all PRs

        Returns:
            Total cost in USD
        """
        return sum(pr.get_total_cost() for pr in self.pull_requests)

    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by AI model

        Returns:
            Dictionary mapping model name to total cost
        """
        costs: Dict[str, float] = {}
        for pr in self.pull_requests:
            for op in pr.ai_operations:
                costs[op.model] = costs.get(op.model, 0.0) + op.cost_usd
        return costs

    def get_progress_stats(self) -> Dict[str, int]:
        """Get task counts by status

        Returns:
            Dictionary with total, pending, in_progress, and completed counts
        """
        stats = {
            "total": len(self.tasks),
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
        }
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                stats["pending"] += 1
            elif task.status == TaskStatus.IN_PROGRESS:
                stats["in_progress"] += 1
            elif task.status == TaskStatus.COMPLETED:
                stats["completed"] += 1
        return stats

    def get_completion_percentage(self) -> float:
        """Calculate project completion percentage

        Returns:
            Completion percentage (0-100)
        """
        if not self.tasks:
            return 0.0
        stats = self.get_progress_stats()
        return (stats["completed"] / stats["total"]) * 100.0

    def calculate_task_status(self, task_index: int) -> TaskStatus:
        """Calculate task status from PR state

        This is the core logic that derives task status:
        - No PR → pending
        - PR open → in_progress
        - PR merged → completed
        - Multiple PRs → use latest by created_at

        Args:
            task_index: Task index (1-based)

        Returns:
            TaskStatus enum value
        """
        latest_pr = self.get_latest_pr_for_task(task_index)

        if latest_pr is None:
            return TaskStatus.PENDING

        if latest_pr.pr_state == "merged":
            return TaskStatus.COMPLETED
        elif latest_pr.pr_state in ["open", "closed"]:
            return TaskStatus.IN_PROGRESS
        else:
            return TaskStatus.PENDING

    def update_all_task_statuses(self) -> None:
        """Update all task statuses based on current PR states

        Call this after loading from JSON to ensure consistency.
        This is an alias for sync_task_statuses() for API compatibility.
        """
        self.sync_task_statuses()
