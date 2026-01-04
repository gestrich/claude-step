"""Slack mrkdwn formatter for report elements.

Formats report elements using Slack's mrkdwn syntax:
- Bold: *text*
- Italic: _text_
- Links: <url|text>
- Code: `text`
"""

from claudechain.domain.formatters.report_elements import (
    Header,
    TextBlock,
    Link,
    ListItem,
    Table,
    ProgressBar,
    LabeledValue,
    Divider,
)
from claudechain.domain.formatters.report_formatter import ReportFormatter
from claudechain.domain.formatters.table_formatter import TableFormatter


class SlackReportFormatter(ReportFormatter):
    """Formatter that produces Slack mrkdwn output."""

    def format_header(self, header: Header) -> str:
        """Format header as bold text (Slack doesn't have header syntax).

        Args:
            header: Header to format

        Returns:
            Bold text for Slack
        """
        return f"*{header.text}*"

    def format_text_block(self, text_block: TextBlock) -> str:
        """Format text block with appropriate Slack styling.

        Args:
            text_block: TextBlock to format

        Returns:
            Styled text for Slack
        """
        text = text_block.text
        if text_block.style == "bold":
            return f"*{text}*"
        elif text_block.style == "italic":
            return f"_{text}_"
        elif text_block.style == "code":
            return f"`{text}`"
        return text

    def format_link(self, link: Link) -> str:
        """Format link using Slack syntax.

        Args:
            link: Link to format

        Returns:
            Slack-formatted link
        """
        return f"<{link.url}|{link.text}>"

    def format_list_item(self, item: ListItem) -> str:
        """Format a single list item.

        Args:
            item: ListItem to format

        Returns:
            Formatted list item
        """
        content = item.content
        if isinstance(content, Link):
            content = self.format_link(content)
        elif isinstance(content, TextBlock):
            content = self.format_text_block(content)
        return f"{item.bullet} {content}"

    def format_table(self, table: Table) -> str:
        """Format table using TableFormatter with optional code block.

        Args:
            table: Table to format

        Returns:
            Formatted table string
        """
        # Build table using existing TableFormatter
        formatter = TableFormatter(
            headers=[col.header for col in table.columns],
            align=[col.align for col in table.columns],
        )

        for row in table.rows:
            formatter.add_row(list(row.cells))

        table_str = formatter.format()

        if table.in_code_block:
            return f"```\n{table_str}\n```"
        return table_str

    def format_progress_bar(self, progress_bar: ProgressBar) -> str:
        """Format progress bar with filled/empty blocks.

        Args:
            progress_bar: ProgressBar to format

        Returns:
            Visual progress bar string
        """
        pct = progress_bar.percentage
        width = progress_bar.width
        filled = int((pct / 100) * width)
        # Use lighter blocks for Slack
        bar = "▓" * filled + "░" * (width - filled)

        if progress_bar.label:
            return f"{bar} {progress_bar.label}"
        return f"{bar} {pct:.0f}%"

    def format_labeled_value(self, labeled_value: LabeledValue) -> str:
        """Format a labeled value as bold label with value.

        Args:
            labeled_value: LabeledValue to format

        Returns:
            Formatted string like "*Label:* value"
        """
        value = labeled_value.value
        if isinstance(value, Link):
            value = self.format_link(value)
        elif isinstance(value, TextBlock):
            value = self.format_text_block(value)
        return f"*{labeled_value.label}:* {value}"

    def format_divider(self, _divider: Divider) -> str:
        """Format a horizontal divider.

        Args:
            divider: Divider to format

        Returns:
            Divider string (dashes work in Slack)
        """
        return "---"
