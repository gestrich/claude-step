"""GitHub-flavored Markdown formatter for report elements.

Formats report elements using standard markdown syntax:
- Bold: **text**
- Italic: _text_
- Links: [text](url)
- Code: `text`
- Headers: # ## ### etc.
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


class MarkdownReportFormatter(ReportFormatter):
    """Formatter that produces GitHub-flavored Markdown output."""

    def format_header(self, header: Header) -> str:
        """Format header with appropriate number of # symbols.

        Args:
            header: Header to format

        Returns:
            Markdown header string
        """
        hashes = "#" * header.level
        return f"{hashes} {header.text}"

    def format_text_block(self, text_block: TextBlock) -> str:
        """Format text block with appropriate markdown styling.

        Args:
            text_block: TextBlock to format

        Returns:
            Styled text for markdown
        """
        text = text_block.text
        if text_block.style == "bold":
            return f"**{text}**"
        elif text_block.style == "italic":
            return f"_{text}_"
        elif text_block.style == "code":
            return f"`{text}`"
        return text

    def format_link(self, link: Link) -> str:
        """Format link using markdown syntax.

        Args:
            link: Link to format

        Returns:
            Markdown-formatted link
        """
        return f"[{link.text}]({link.url})"

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

    def _format_cell(self, cell) -> str:
        """Format a table cell, handling different element types.

        Args:
            cell: Cell content (str, Link, or other element)

        Returns:
            Formatted string for the cell
        """
        if isinstance(cell, str):
            return cell
        elif isinstance(cell, Link):
            return self.format_link(cell)
        else:
            return str(cell)

    def format_table(self, table: Table) -> str:
        """Format table using GitHub-flavored markdown table syntax.

        Uses pipe-separated columns with proper alignment syntax.

        Args:
            table: Table to format

        Returns:
            Markdown table string
        """
        lines = []

        # Header row
        header_cells = [col.header for col in table.columns]
        lines.append("| " + " | ".join(header_cells) + " |")

        # Alignment row
        align_cells = []
        for col in table.columns:
            if col.align == "right":
                align_cells.append("-" * 10 + ":")
            elif col.align == "center":
                align_cells.append(":" + "-" * 9 + ":")
            else:  # left (default)
                align_cells.append("-" * 11)
        lines.append("|" + "|".join(align_cells) + "|")

        # Data rows
        for row in table.rows:
            formatted_cells = [self._format_cell(cell) for cell in row.cells]
            lines.append("| " + " | ".join(formatted_cells) + " |")

        return "\n".join(lines)

    def format_progress_bar(self, progress_bar: ProgressBar) -> str:
        """Format progress bar with filled/empty blocks.

        Args:
            progress_bar: ProgressBar to format

        Returns:
            Visual progress bar string
        """
        pct = progress_bar.percentage
        width = progress_bar.width
        filled = round((pct / 100) * width)
        # Use full blocks for markdown
        bar = "█" * filled + "░" * (width - filled)

        if progress_bar.label:
            return f"{bar} {progress_bar.label}"
        return f"{bar} {pct:.0f}%"

    def format_labeled_value(self, labeled_value: LabeledValue) -> str:
        """Format a labeled value as bold label with value.

        Args:
            labeled_value: LabeledValue to format

        Returns:
            Formatted string like "**Label:** value"
        """
        value = labeled_value.value
        if isinstance(value, Link):
            value = self.format_link(value)
        elif isinstance(value, TextBlock):
            value = self.format_text_block(value)
        return f"**{labeled_value.label}:** {value}"

    def format_divider(self, _divider: Divider) -> str:
        """Format a horizontal divider.

        Args:
            _divider: Divider to format (unused, dividers have no config)

        Returns:
            Markdown horizontal rule
        """
        return "---"
