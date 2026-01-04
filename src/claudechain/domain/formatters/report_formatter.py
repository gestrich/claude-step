"""Base class for report formatters.

Defines the interface that all report formatters must implement.
Each formatter knows how to render report elements into a specific
output format (Slack mrkdwn, GitHub markdown, etc.).
"""

from abc import ABC, abstractmethod
from typing import List

from claudechain.domain.formatters.report_elements import (
    Header,
    TextBlock,
    Link,
    ListItem,
    ListBlock,
    Table,
    ProgressBar,
    LabeledValue,
    Divider,
    Section,
    ReportElement,
)


class ReportFormatter(ABC):
    """Abstract base class for report formatters.

    Subclasses implement format methods for each element type,
    producing strings in their target format (Slack, Markdown, etc.).
    """

    def format(self, element: ReportElement) -> str:
        """Format any report element by dispatching to the appropriate method.

        Args:
            element: Any report element

        Returns:
            Formatted string representation
        """
        if isinstance(element, Section):
            return self.format_section(element)
        elif isinstance(element, Header):
            return self.format_header(element)
        elif isinstance(element, TextBlock):
            return self.format_text_block(element)
        elif isinstance(element, Link):
            return self.format_link(element)
        elif isinstance(element, ListBlock):
            return self.format_list_block(element)
        elif isinstance(element, Table):
            return self.format_table(element)
        elif isinstance(element, ProgressBar):
            return self.format_progress_bar(element)
        elif isinstance(element, LabeledValue):
            return self.format_labeled_value(element)
        elif isinstance(element, Divider):
            return self.format_divider(element)
        else:
            raise ValueError(f"Unknown element type: {type(element)}")

    def format_section(self, section: Section) -> str:
        """Format a section containing multiple elements.

        Args:
            section: Section to format

        Returns:
            Formatted string with all elements
        """
        lines: List[str] = []

        # Add section header if present
        if section.header:
            lines.append(self.format_header(section.header))
            lines.append("")

        # Format each element
        for element in section.elements:
            formatted = self.format(element)
            if formatted:
                lines.append(formatted)
                lines.append("")

        # Remove trailing empty line
        while lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)

    @abstractmethod
    def format_header(self, header: Header) -> str:
        """Format a header element.

        Args:
            header: Header to format

        Returns:
            Formatted header string
        """
        pass

    @abstractmethod
    def format_text_block(self, text_block: TextBlock) -> str:
        """Format a text block element.

        Args:
            text_block: TextBlock to format

        Returns:
            Formatted text string
        """
        pass

    @abstractmethod
    def format_link(self, link: Link) -> str:
        """Format a link element.

        Args:
            link: Link to format

        Returns:
            Formatted link string
        """
        pass

    @abstractmethod
    def format_list_item(self, item: ListItem) -> str:
        """Format a single list item.

        Args:
            item: ListItem to format

        Returns:
            Formatted list item string
        """
        pass

    def format_list_block(self, list_block: ListBlock) -> str:
        """Format a list block containing multiple items.

        Args:
            list_block: ListBlock to format

        Returns:
            Formatted list string
        """
        lines = [self.format_list_item(item) for item in list_block.items]
        return "\n".join(lines)

    @abstractmethod
    def format_table(self, table: Table) -> str:
        """Format a table element.

        Args:
            table: Table to format

        Returns:
            Formatted table string
        """
        pass

    @abstractmethod
    def format_progress_bar(self, progress_bar: ProgressBar) -> str:
        """Format a progress bar element.

        Args:
            progress_bar: ProgressBar to format

        Returns:
            Formatted progress bar string
        """
        pass

    @abstractmethod
    def format_labeled_value(self, labeled_value: LabeledValue) -> str:
        """Format a labeled value element (e.g., "Label: value").

        Args:
            labeled_value: LabeledValue to format

        Returns:
            Formatted label-value string
        """
        pass

    @abstractmethod
    def format_divider(self, divider: Divider) -> str:
        """Format a horizontal divider element.

        Args:
            divider: Divider to format

        Returns:
            Formatted divider string
        """
        pass
