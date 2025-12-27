"""Tests for table formatting utilities"""

import pytest
from claudestep.application.formatters.table_formatter import TableFormatter, visual_width, pad_to_visual_width


class TestVisualWidth:
    """Test visual width calculation"""

    def test_ascii_text(self):
        """ASCII characters are single width"""
        assert visual_width("hello") == 5
        assert visual_width("test") == 4

    def test_emoji(self):
        """Emojis are double width"""
        assert visual_width("🥇") == 2
        assert visual_width("🥈") == 2
        assert visual_width("🥉") == 2

    def test_emoji_with_text(self):
        """Mixed emoji and text"""
        assert visual_width("🥇 alice") == 8  # 2 + 1 + 5

    def test_unicode_blocks(self):
        """Unicode block characters are single width in most terminals"""
        assert visual_width("█") == 1
        assert visual_width("░") == 1
        assert visual_width("█████") == 5

    def test_empty_string(self):
        """Empty string has zero width"""
        assert visual_width("") == 0


class TestPadToVisualWidth:
    """Test visual width padding"""

    def test_pad_left_ascii(self):
        """Pad ASCII text to the left"""
        result = pad_to_visual_width("hello", 10, 'left')
        assert result == "hello     "
        assert visual_width(result) == 10

    def test_pad_right_ascii(self):
        """Pad ASCII text to the right"""
        result = pad_to_visual_width("hello", 10, 'right')
        assert result == "     hello"
        assert visual_width(result) == 10

    def test_pad_center_ascii(self):
        """Pad ASCII text centered"""
        result = pad_to_visual_width("hello", 11, 'center')
        assert result == "   hello   "
        assert visual_width(result) == 11

    def test_pad_emoji(self):
        """Pad text with emoji"""
        # "🥇" is 2 chars wide, pad to 6 total
        result = pad_to_visual_width("🥇", 6, 'left')
        assert visual_width(result) == 6
        assert result == "🥇    "

    def test_pad_emoji_with_text(self):
        """Pad emoji and text combination"""
        # "🥇 alice" is 2 + 1 + 5 = 8 visual width
        result = pad_to_visual_width("🥇 alice", 15, 'left')
        assert visual_width(result) == 15

    def test_no_padding_needed(self):
        """No padding when already at target width"""
        result = pad_to_visual_width("hello", 5, 'left')
        assert result == "hello"

    def test_text_too_long(self):
        """Text longer than target width is not truncated"""
        result = pad_to_visual_width("hello world", 5, 'left')
        assert result == "hello world"


class TestTableFormatter:
    """Test table formatting"""

    def test_simple_table(self):
        """Format a simple ASCII table"""
        table = TableFormatter(["Name", "Age"])
        table.add_row(["Alice", "30"])
        table.add_row(["Bob", "25"])

        result = table.format()
        lines = result.split("\n")

        assert len(lines) == 6  # top, header, sep, 2 rows, bottom
        assert lines[0].startswith("┌")
        assert lines[0].endswith("┐")
        assert "Name" in lines[1]
        assert "Age" in lines[1]
        assert "Alice" in lines[3]
        assert "Bob" in lines[4]

    def test_table_with_emoji(self):
        """Format table with emoji characters"""
        table = TableFormatter(["Rank", "Name"], align=['left', 'left'])
        table.add_row(["🥇", "Alice"])
        table.add_row(["🥈", "Bob"])
        table.add_row(["🥉", "Charlie"])

        result = table.format()
        lines = result.split("\n")

        # Each emoji line should align properly
        assert "🥇" in lines[3]
        assert "🥈" in lines[4]
        assert "🥉" in lines[5]

        # Verify the columns align by checking border characters
        for line in lines:
            if line.startswith("│"):
                # Count the pipes - should be consistent
                assert line.count("│") == 3  # start, middle, end

    def test_table_with_unicode_blocks(self):
        """Format table with Unicode block characters"""
        table = TableFormatter(["Progress"], align=['left'])
        table.add_row(["█████░░░░░ 50%"])
        table.add_row(["███░░░░░░░ 30%"])

        result = table.format()
        assert "█████░░░░░ 50%" in result
        assert "███░░░░░░░ 30%" in result

    def test_alignment_right(self):
        """Test right alignment"""
        table = TableFormatter(["Name", "Score"], align=['left', 'right'])
        table.add_row(["Alice", "100"])
        table.add_row(["Bob", "5"])

        result = table.format()
        lines = result.split("\n")

        # The score column should be right-aligned
        # Find the row with "100" and verify it's right-aligned
        alice_line = [l for l in lines if "Alice" in l][0]
        assert "  100 │" in alice_line or " 100 │" in alice_line

    def test_varying_column_widths(self):
        """Table auto-sizes to widest content"""
        table = TableFormatter(["Short", "Long Column Name"])
        table.add_row(["A", "B"])
        table.add_row(["This is very long", "C"])

        result = table.format()
        lines = result.split("\n")

        # First column should be wide enough for "This is very long"
        # Verify by checking border alignment
        top_border = lines[0]
        bottom_border = lines[-1]
        assert len(top_border) == len(bottom_border)

    def test_empty_table(self):
        """Empty table returns empty string"""
        table = TableFormatter(["Col1", "Col2"])
        result = table.format()
        assert result == ""

    def test_mismatched_columns(self):
        """Adding row with wrong number of columns raises error"""
        table = TableFormatter(["Col1", "Col2"])
        with pytest.raises(ValueError, match="Row has 3 columns, expected 2"):
            table.add_row(["A", "B", "C"])

    def test_mismatched_align(self):
        """Alignment list must match headers"""
        with pytest.raises(ValueError, match="align list must match number of headers"):
            TableFormatter(["Col1", "Col2"], align=['left'])

    def test_number_formatting(self):
        """Numbers are converted to strings"""
        table = TableFormatter(["Name", "Count"], align=['left', 'right'])
        table.add_row(["Alice", 42])
        table.add_row(["Bob", 7])

        result = table.format()
        assert "42" in result
        assert "7" in result
