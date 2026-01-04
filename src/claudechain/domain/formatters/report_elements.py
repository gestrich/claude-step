"""Abstract report elements for format-agnostic report building.

These data classes represent the semantic structure of a report without
any formatting logic. Formatters (Slack, Markdown) know how to render
these elements into their respective output formats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Union


@dataclass(frozen=True)
class Header:
    """A header/title element.

    Attributes:
        text: The header text content
        level: Header level (1=h1, 2=h2, etc.)
    """

    text: str
    level: int = 2


@dataclass(frozen=True)
class TextBlock:
    """A block of text with optional styling.

    Attributes:
        text: The text content
        style: Text style (plain, bold, italic, code)
    """

    text: str
    style: Literal["plain", "bold", "italic", "code"] = "plain"


@dataclass(frozen=True)
class Link:
    """A hyperlink element.

    Attributes:
        text: Display text for the link
        url: Target URL
    """

    text: str
    url: str


@dataclass(frozen=True)
class ListItem:
    """A single item in a list.

    Attributes:
        content: The item content (can be text, link, or nested elements)
        bullet: Bullet character (e.g., "-", "*", "•", or number for ordered lists)
    """

    content: Union[str, Link, TextBlock]
    bullet: str = "-"


@dataclass(frozen=True)
class ListBlock:
    """A list of items.

    Attributes:
        items: List of ListItem elements
    """

    items: tuple  # tuple of ListItem for immutability


@dataclass(frozen=True)
class TableColumn:
    """Definition for a table column.

    Attributes:
        header: Column header text
        align: Column alignment
    """

    header: str
    align: Literal["left", "right", "center"] = "left"


@dataclass(frozen=True)
class TableRow:
    """A single row in a table.

    Attributes:
        cells: Tuple of cell values (strings)
    """

    cells: tuple  # tuple of str for immutability


@dataclass(frozen=True)
class Table:
    """A data table element.

    Attributes:
        columns: Column definitions with headers and alignment
        rows: Data rows
        in_code_block: Whether to wrap the table in a code block (for Slack)
    """

    columns: tuple  # tuple of TableColumn
    rows: tuple  # tuple of TableRow
    in_code_block: bool = False


@dataclass(frozen=True)
class ProgressBar:
    """A visual progress indicator.

    Attributes:
        percentage: Completion percentage (0-100)
        width: Number of characters for the bar
        label: Optional label text to show after the bar
    """

    percentage: float
    width: int = 10
    label: Optional[str] = None


@dataclass(frozen=True)
class LabeledValue:
    """A label-value pair element (e.g., "PR: #123", "Cost: $0.50").

    Commonly used for metadata display in notifications and summaries.

    Attributes:
        label: The label text (will be rendered bold)
        value: The value (can be plain text, Link, or styled TextBlock)
    """

    label: str
    value: Union[str, Link, TextBlock]


@dataclass(frozen=True)
class Divider:
    """A horizontal divider/separator element.

    Renders as --- in markdown, similar in Slack.
    """

    pass


@dataclass
class Section:
    """A container grouping multiple elements with an optional header.

    This is mutable to allow building sections incrementally.

    Attributes:
        elements: List of elements in this section
        header: Optional section header
    """

    elements: List[
        Union[Header, TextBlock, Link, ListBlock, Table, ProgressBar, LabeledValue, Divider, Section]
    ] = field(default_factory=list)
    header: Optional[Header] = None

    def add(
        self,
        element: Union[
            Header, TextBlock, Link, ListBlock, Table, ProgressBar, LabeledValue, Divider, Section
        ],
    ) -> Section:
        """Add an element to this section.

        Args:
            element: Element to add

        Returns:
            Self for method chaining
        """
        self.elements.append(element)
        return self

    def is_empty(self) -> bool:
        """Check if section has no elements.

        Returns:
            True if section has no elements
        """
        return len(self.elements) == 0


# Type alias for any report element
ReportElement = Union[Header, TextBlock, Link, ListBlock, Table, ProgressBar, LabeledValue, Divider, Section]
