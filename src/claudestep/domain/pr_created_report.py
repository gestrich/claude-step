"""Domain model for PR creation reports.

PullRequestCreatedReport consolidates all PR-related formatting into a single
domain model that can be rendered for Slack notifications, PR comments,
and workflow summaries using the formatter pattern.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from claudestep.domain.formatters.report_elements import (
    Divider,
    Header,
    LabeledValue,
    Link,
    Section,
    Table,
    TableColumn,
    TableRow,
    TextBlock,
)
from claudestep.domain.formatting import format_usd

if TYPE_CHECKING:
    from claudestep.domain.cost_breakdown import CostBreakdown


@dataclass
class PullRequestCreatedReport:
    """Domain model for PR creation reports.

    Holds all data needed to generate PR notifications, comments, and summaries.
    Provides element-building methods for each output format.

    Attributes:
        pr_number: Pull request number
        pr_url: Full URL to the pull request
        project_name: Name of the project
        task: Task description
        cost_breakdown: Cost breakdown with per-model data
        repo: Repository in format owner/repo
        run_id: Workflow run ID
        summary_content: Optional AI-generated summary content
    """

    pr_number: str
    pr_url: str
    project_name: str
    task: str
    cost_breakdown: CostBreakdown
    repo: str
    run_id: str
    summary_content: Optional[str] = None

    @property
    def workflow_url(self) -> str:
        """Generate the workflow run URL."""
        return f"https://github.com/{self.repo}/actions/runs/{self.run_id}"

    # ============================================================
    # Element Building Methods
    # ============================================================

    def build_notification_elements(self) -> str:
        """Build formatted Slack notification message.

        Returns a pre-formatted string to match the exact Slack message format
        with specific blank line placement.

        Returns:
            Formatted Slack notification string.
        """
        from claudestep.domain.formatters import SlackReportFormatter

        formatter = SlackReportFormatter()

        # Build using formatter for individual elements to ensure correct syntax
        # Note: emoji is outside bold markers to match original format
        lines = [
            "🎉 " + formatter.format_text_block(TextBlock("New PR Created", style="bold")),
            "",
            formatter.format_labeled_value(
                LabeledValue("PR", Link(f"#{self.pr_number}", self.pr_url))
            ),
            formatter.format_labeled_value(
                LabeledValue("Project", TextBlock(self.project_name, style="code"))
            ),
            formatter.format_labeled_value(LabeledValue("Task", self.task)),
            "",
            formatter.format_labeled_value(
                LabeledValue("💰 Cost", format_usd(self.cost_breakdown.total_cost))
            ),
        ]

        return "\n".join(lines)

    def build_comment_elements(self) -> Section:
        """Build report elements for PR comment.

        Includes optional AI summary and detailed cost breakdown.

        Returns:
            Section containing elements for GitHub PR comment.
        """
        section = Section()

        # Include AI summary if present
        if self.summary_content:
            section.add(TextBlock(self.summary_content))
            section.add(Divider())

        # Cost breakdown header
        section.add(Header("💰 Cost Breakdown", level=2))
        section.add(
            TextBlock("This PR was generated using Claude Code with the following costs:")
        )

        # Cost summary table
        section.add(self._build_cost_summary_table())

        # Per-model breakdown if available
        model_table = self._build_model_breakdown_table()
        if model_table:
            section.add(model_table)

        # Footer
        section.add(Divider())
        section.add(
            TextBlock(f"*Cost tracking by ClaudeStep • [View workflow run]({self.workflow_url})*")
        )

        return section

    def build_workflow_summary_elements(self) -> Section:
        """Build report elements for GitHub Actions workflow summary.

        Returns:
            Section containing elements for step summary.
        """
        section = Section()

        # Header
        section.add(Header("✅ ClaudeStep Complete", level=2))

        # PR and task info
        section.add(LabeledValue("PR", Link(f"#{self.pr_number}", self.pr_url)))
        if self.task:
            section.add(LabeledValue("Task", self.task))

        # Cost summary section
        section.add(Header("💰 Cost Summary", level=3))
        section.add(self._build_cost_summary_table())

        # Per-model breakdown if available
        model_table = self._build_model_breakdown_table()
        if model_table:
            section.add(model_table)

        # Footer
        section.add(Divider())
        section.add(
            TextBlock(f"*[View workflow run]({self.workflow_url})*")
        )

        return section

    # ============================================================
    # Private Helper Methods
    # ============================================================

    def _build_cost_summary_table(self) -> Table:
        """Build the cost summary table.

        Returns:
            Table with component costs.
        """
        return Table(
            columns=(
                TableColumn("Component", align="left"),
                TableColumn("Cost (USD)", align="right"),
            ),
            rows=(
                TableRow(("Main refactoring task", format_usd(self.cost_breakdown.main_cost))),
                TableRow(("PR summary generation", format_usd(self.cost_breakdown.summary_cost))),
                TableRow((f"**Total**", f"**{format_usd(self.cost_breakdown.total_cost)}**")),
            ),
        )

    def _build_model_breakdown_table(self) -> Optional[Section]:
        """Build the per-model breakdown section if models are available.

        Returns:
            Section with header and table, or None if no models.
        """
        models = self.cost_breakdown.get_aggregated_models()
        if not models:
            return None

        section = Section()
        section.add(Header("Per-Model Breakdown", level=3))

        # Build rows for each model
        rows = []
        for model in models:
            calculated_cost = model.calculate_cost()
            rows.append(
                TableRow((
                    model.model,
                    f"{model.input_tokens:,}",
                    f"{model.output_tokens:,}",
                    f"{model.cache_read_tokens:,}",
                    f"{model.cache_write_tokens:,}",
                    format_usd(calculated_cost),
                ))
            )

        # Add totals row
        rows.append(
            TableRow((
                "**Total**",
                f"**{self.cost_breakdown.input_tokens:,}**",
                f"**{self.cost_breakdown.output_tokens:,}**",
                f"**{self.cost_breakdown.cache_read_tokens:,}**",
                f"**{self.cost_breakdown.cache_write_tokens:,}**",
                f"**{format_usd(self.cost_breakdown.total_cost)}**",
            ))
        )

        section.add(
            Table(
                columns=(
                    TableColumn("Model", align="left"),
                    TableColumn("Input", align="right"),
                    TableColumn("Output", align="right"),
                    TableColumn("Cache R", align="right"),
                    TableColumn("Cache W", align="right"),
                    TableColumn("Cost", align="right"),
                ),
                rows=tuple(rows),
            )
        )

        return section
