"""Table formatting utilities for consistent Slack/terminal output"""

from typing import List, Literal, Optional
import unicodedata


def visual_width(text: str) -> int:
    """Calculate the visual display width of a string.

    Handles double-width characters (emojis, CJK characters, box-drawing chars).

    Args:
        text: String to measure

    Returns:
        Visual width in terminal columns
    """
    width = 0
    for char in text:
        # Get the East Asian Width property
        ea_width = unicodedata.east_asian_width(char)

        # Check if it's an emoji or special character
        if ord(char) >= 0x1F300:  # Emoji range starts here
            width += 2
        # Wide (W) and Fullwidth (F) characters
        elif ea_width in ('W', 'F'):
            width += 2
        # Ambiguous (A) - treating as single width for now
        # Neutral (N), Narrow (Na), Halfwidth (H)
        else:
            width += 1

    return width


def pad_to_visual_width(text: str, target_width: int, align: Literal['left', 'right', 'center'] = 'left') -> str:
    """Pad a string to a target visual width.

    Args:
        text: String to pad
        target_width: Desired visual width
        align: Alignment direction

    Returns:
        Padded string
    """
    current_width = visual_width(text)
    padding_needed = target_width - current_width

    if padding_needed <= 0:
        return text

    if align == 'left':
        return text + ' ' * padding_needed
    elif align == 'right':
        return ' ' * padding_needed + text
    else:  # center
        left_pad = padding_needed // 2
        right_pad = padding_needed - left_pad
        return ' ' * left_pad + text + ' ' * right_pad


class TableFormatter:
    """Format data as a bordered table with box-drawing characters."""

    def __init__(self, headers: List[str], align: Optional[List[str]] = None):
        """Initialize table formatter.

        Args:
            headers: Column headers
            align: List of alignment per column ('left', 'right', 'center')
                   Defaults to 'left' for all columns
        """
        self.headers = headers
        self.rows: List[List[str]] = []
        self.align = align or ['left'] * len(headers)

        if len(self.align) != len(headers):
            raise ValueError("align list must match number of headers")

    def add_row(self, row: List[str]):
        """Add a data row to the table.

        Args:
            row: List of cell values (must match number of headers)
        """
        if len(row) != len(self.headers):
            raise ValueError(f"Row has {len(row)} columns, expected {len(self.headers)}")
        self.rows.append([str(cell) for cell in row])

    def _calculate_column_widths(self) -> List[int]:
        """Calculate the visual width needed for each column."""
        widths = [visual_width(h) for h in self.headers]

        for row in self.rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], visual_width(cell))

        return widths

    def format(self) -> str:
        """Format the table with box-drawing characters.

        Returns:
            Formatted table as a string
        """
        if not self.rows:
            return ""

        col_widths = self._calculate_column_widths()
        lines = []

        # Top border
        top = "┌" + "┬".join("─" * (w + 2) for w in col_widths) + "┐"
        lines.append(top)

        # Header row
        header_cells = []
        for i, header in enumerate(self.headers):
            padded = pad_to_visual_width(header, col_widths[i], self.align[i])
            header_cells.append(f" {padded} ")
        lines.append("│" + "│".join(header_cells) + "│")

        # Header separator
        sep = "├" + "┼".join("─" * (w + 2) for w in col_widths) + "┤"
        lines.append(sep)

        # Data rows
        for row in self.rows:
            row_cells = []
            for i, cell in enumerate(row):
                padded = pad_to_visual_width(cell, col_widths[i], self.align[i])
                row_cells.append(f" {padded} ")
            lines.append("│" + "│".join(row_cells) + "│")

        # Bottom border
        bottom = "└" + "┴".join("─" * (w + 2) for w in col_widths) + "┘"
        lines.append(bottom)

        return "\n".join(lines)
