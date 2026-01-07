"""Slack Block Kit formatter for statistics reports.

Generates Slack Block Kit JSON structures instead of plain mrkdwn text.
Block Kit provides richer formatting with native Slack components:
- Header blocks for titles
- Section blocks for content with optional fields
- Context blocks for metadata
- Divider blocks for visual separation

Reference: https://api.slack.com/block-kit
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from claudechain.domain.formatting import format_usd


class SlackBlockKitFormatter:
    """Formatter that produces Slack Block Kit JSON structures.

    Unlike SlackReportFormatter which outputs mrkdwn strings, this formatter
    generates the JSON block structures needed for Block Kit messages.
    """

    def __init__(self, repo: str):
        """Initialize the formatter.

        Args:
            repo: GitHub repository (owner/name) for building PR URLs
        """
        self.repo = repo

    # ============================================================
    # Public API - Message Building
    # ============================================================

    def build_message(
        self,
        blocks: list[dict[str, Any]],
        fallback_text: str = "ClaudeChain Statistics",
    ) -> dict[str, Any]:
        """Build the complete Slack message payload.

        Args:
            blocks: List of Block Kit blocks
            fallback_text: Text shown in notifications/previews

        Returns:
            Complete Slack message payload with text and blocks
        """
        return {
            "text": fallback_text,
            "blocks": blocks
        }

    def format_header_blocks(
        self,
        title: str = "ClaudeChain Statistics",
        generated_at: datetime | None = None,
        branch: str | None = None,
    ) -> list[dict[str, Any]]:
        """Generate header blocks for the report.

        Args:
            title: Report title
            generated_at: Report generation timestamp (defaults to now UTC)
            branch: Optional branch name to display

        Returns:
            List of Block Kit blocks for the header
        """
        blocks: list[dict[str, Any]] = []

        blocks.append(header_block(title))

        if generated_at is None:
            generated_at = datetime.now(timezone.utc)

        date_str = generated_at.strftime("%Y-%m-%d")
        context_parts = [f"📅 {date_str}"]
        if branch:
            context_parts.append(f"Branch: {branch}")

        blocks.append(context_block("  •  ".join(context_parts)))
        blocks.append(divider_block())

        return blocks

    # ============================================================
    # Public API - Content Formatting
    # ============================================================

    def format_project_blocks(
        self,
        project_name: str,
        merged: int,
        total: int,
        cost_usd: float,
        open_prs: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Generate Block Kit blocks for a single project.

        Args:
            project_name: Name of the project
            merged: Number of merged PRs/tasks
            total: Total number of tasks
            cost_usd: Total cost for this project
            open_prs: List of open PRs with keys: number, title, url, age_days

        Returns:
            List of Block Kit blocks for the project
        """
        blocks: list[dict[str, Any]] = []

        percent_complete = (merged / total * 100) if total > 0 else 0
        is_complete = merged == total and total > 0

        name = f"*{project_name}*"
        if is_complete:
            name += " ✅"

        progress_bar = _generate_progress_bar(percent_complete)

        blocks.append(section_block(f"{name}\n{progress_bar}"))

        cost_str = format_usd(cost_usd) if cost_usd > 0 else "$0.00"
        blocks.append(context_block(f"{merged}/{total} merged  •  💰 {cost_str}"))

        if open_prs:
            pr_lines = []
            for pr in open_prs:
                url = pr.get("url")
                if not url and self.repo:
                    url = self._build_pr_url(pr["number"])
                title = pr.get("title", "")
                age_days = pr.get("age_days", 0)

                if url:
                    line = f"• <{url}|#{pr['number']} {title}> ({age_days}d)"
                else:
                    line = f"• #{pr['number']} {title} ({age_days}d)"

                if age_days >= 5:
                    line += " ⚠️"
                pr_lines.append(line)

            blocks.append(section_block("\n".join(pr_lines)))

        blocks.append(divider_block())
        return blocks

    def format_leaderboard_blocks(
        self,
        entries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate Block Kit blocks for the leaderboard.

        Args:
            entries: List of leaderboard entries with keys: username, merged

        Returns:
            List of Block Kit blocks for the leaderboard
        """
        if not entries:
            return []

        blocks: list[dict[str, Any]] = []
        medals = ["🥇", "🥈", "🥉"]

        blocks.append(section_block("*🏆 Leaderboard*"))

        fields = []
        for i, entry in enumerate(entries[:6]):
            medal = medals[i] if i < 3 else f"{i+1}."
            fields.append(f"{medal} *{entry['username']}*\n{entry['merged']} merged")

        if fields:
            blocks.append(section_fields_block(fields))

        return blocks

    def format_warnings_blocks(
        self,
        warnings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Generate Block Kit blocks for warnings/attention section.

        Args:
            warnings: List of warning items with keys:
                - project_name: str
                - items: list of warning strings (e.g., "PR #42 (5d, stale)")

        Returns:
            List of Block Kit blocks for warnings
        """
        if not warnings:
            return []

        blocks: list[dict[str, Any]] = []
        blocks.append(section_block("*⚠️ Needs Attention*"))

        for warning in warnings:
            project_name = warning.get("project_name", "")
            items = warning.get("items", [])

            if items:
                content = f"*{project_name}*\n" + "\n".join(f"• {item}" for item in items)
                blocks.append(section_block(content))

        return blocks

    # ============================================================
    # Private Helpers
    # ============================================================

    def _build_pr_url(self, pr_number: int) -> str:
        """Construct GitHub PR URL from repo and PR number.

        Args:
            pr_number: The pull request number

        Returns:
            Full GitHub PR URL
        """
        return f"https://github.com/{self.repo}/pull/{pr_number}"


# ============================================================
# Block Builder Functions
# ============================================================

def header_block(text: str) -> dict[str, Any]:
    """Create a header block.

    Args:
        text: Header text (plain text only, max 150 chars)

    Returns:
        Slack header block structure
    """
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": text[:150], "emoji": True}
    }


def context_block(text: str) -> dict[str, Any]:
    """Create a context block with mrkdwn text.

    Args:
        text: Context text (supports mrkdwn formatting)

    Returns:
        Slack context block structure
    """
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text}]
    }


def section_block(text: str, fields: list[str] | None = None) -> dict[str, Any]:
    """Create a section block with optional fields.

    Args:
        text: Main section text (supports mrkdwn)
        fields: Optional list of field texts (max 10, displayed in 2-column grid)

    Returns:
        Slack section block structure
    """
    block: dict[str, Any] = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": text}
    }

    if fields:
        block["fields"] = [
            {"type": "mrkdwn", "text": field}
            for field in fields[:10]
        ]

    return block


def section_fields_block(fields: list[str]) -> dict[str, Any]:
    """Create a section block with only fields (no main text).

    Args:
        fields: List of field texts (max 10, displayed in 2-column grid)

    Returns:
        Slack section block structure with fields only
    """
    return {
        "type": "section",
        "fields": [
            {"type": "mrkdwn", "text": field}
            for field in fields[:10]
        ]
    }


def divider_block() -> dict[str, Any]:
    """Create a divider block.

    Returns:
        Slack divider block structure
    """
    return {"type": "divider"}


# ============================================================
# Private Module Helpers
# ============================================================

def _generate_progress_bar(percentage: float, width: int = 10) -> str:
    """Generate Unicode progress bar string.

    Args:
        percentage: Completion percentage (0-100)
        width: Number of characters for the bar

    Returns:
        String like "████████░░ 80%"
    """
    filled = int((percentage / 100) * width)
    if percentage > 0 and filled == 0:
        filled = 1
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {percentage:.0f}%"
