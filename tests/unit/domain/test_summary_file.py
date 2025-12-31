"""Unit tests for SummaryFile domain model"""

import os
import tempfile
from pathlib import Path

import pytest

from claudestep.domain.cost_breakdown import CostBreakdown
from claudestep.domain.summary_file import SummaryFile


class TestSummaryFileConstruction:
    """Test suite for SummaryFile construction and basic properties"""

    def test_can_create_summary_file_with_content(self):
        """Should be able to create SummaryFile with content"""
        # Act
        summary = SummaryFile(content="This is a summary")

        # Assert
        assert summary.content == "This is a summary"

    def test_can_create_summary_file_with_none_content(self):
        """Should be able to create SummaryFile with None content"""
        # Act
        summary = SummaryFile(content=None)

        # Assert
        assert summary.content is None

    def test_has_content_property_with_content(self):
        """Should return True when content exists"""
        # Arrange
        summary = SummaryFile(content="Some content")

        # Act
        has_content = summary.has_content

        # Assert
        assert has_content is True

    def test_has_content_property_with_none(self):
        """Should return False when content is None"""
        # Arrange
        summary = SummaryFile(content=None)

        # Act
        has_content = summary.has_content

        # Assert
        assert has_content is False

    def test_has_content_property_with_empty_string(self):
        """Should return False when content is empty string"""
        # Arrange
        summary = SummaryFile(content="")

        # Act
        has_content = summary.has_content

        # Assert
        assert has_content is False

    def test_has_content_property_with_whitespace(self):
        """Should return False when content is only whitespace"""
        # Arrange
        summary = SummaryFile(content="   \n\t  ")

        # Act
        has_content = summary.has_content

        # Assert
        assert has_content is False


class TestSummaryFileFromFile:
    """Test suite for SummaryFile.from_file() class method"""

    def test_from_file_with_valid_content(self):
        """Should read content from valid file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("# PR Summary\n\nThis is the content.")
            filepath = f.name

        try:
            # Act
            summary = SummaryFile.from_file(filepath)

            # Assert
            assert summary.content == "# PR Summary\n\nThis is the content."
            assert summary.has_content is True
        finally:
            os.unlink(filepath)

    def test_from_file_strips_whitespace(self):
        """Should strip leading and trailing whitespace"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("\n\n  Content here  \n\n")
            filepath = f.name

        try:
            # Act
            summary = SummaryFile.from_file(filepath)

            # Assert
            assert summary.content == "Content here"
            assert summary.has_content is True
        finally:
            os.unlink(filepath)

    def test_from_file_with_empty_file(self):
        """Should return None content for empty file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            filepath = f.name  # Empty file

        try:
            # Act
            summary = SummaryFile.from_file(filepath)

            # Assert
            assert summary.content is None
            assert summary.has_content is False
        finally:
            os.unlink(filepath)

    def test_from_file_with_whitespace_only_file(self):
        """Should return None content for file with only whitespace"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("   \n\t\n   ")
            filepath = f.name

        try:
            # Act
            summary = SummaryFile.from_file(filepath)

            # Assert
            assert summary.content is None
            assert summary.has_content is False
        finally:
            os.unlink(filepath)

    def test_from_file_with_nonexistent_file(self):
        """Should return None content for nonexistent file"""
        # Act
        summary = SummaryFile.from_file("/nonexistent/file.md")

        # Assert
        assert summary.content is None
        assert summary.has_content is False

    def test_from_file_with_empty_path(self):
        """Should return None content for empty path"""
        # Act
        summary = SummaryFile.from_file("")

        # Assert
        assert summary.content is None
        assert summary.has_content is False

    def test_from_file_with_multiline_content(self):
        """Should preserve multiline content"""
        # Arrange
        content = """# Summary

## Changes
- Change 1
- Change 2

## Impact
This affects the system."""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(content)
            filepath = f.name

        try:
            # Act
            summary = SummaryFile.from_file(filepath)

            # Assert
            assert summary.content == content
            assert summary.has_content is True
        finally:
            os.unlink(filepath)

    def test_from_file_handles_read_error_gracefully(self):
        """Should return None content on read error"""
        # Arrange - Create a directory, not a file (will cause read error)
        with tempfile.TemporaryDirectory() as tmpdir:
            # Act
            summary = SummaryFile.from_file(tmpdir)

            # Assert
            assert summary.content is None
            assert summary.has_content is False


class TestFormatWithCost:
    """Test suite for SummaryFile.format_with_cost() method"""

    def test_format_with_summary_and_cost(self):
        """Should combine summary content with cost breakdown"""
        # Arrange
        summary = SummaryFile(content="# PR Summary\n\nChanges made here.")
        cost = CostBreakdown(main_cost=1.5, summary_cost=0.5)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "12345")

        # Assert
        assert "# PR Summary" in result
        assert "Changes made here." in result
        assert "\n---\n" in result  # Separator
        assert "## 💰 Cost Breakdown" in result
        assert "$1.500000" in result
        assert "$0.500000" in result

    def test_format_without_summary_only_cost(self):
        """Should show only cost breakdown when no summary"""
        # Arrange
        summary = SummaryFile(content=None)
        cost = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "12345")

        # Assert
        assert "## 💰 Cost Breakdown" in result
        assert "$1.000000" in result
        assert "$0.500000" in result
        # Should start with cost breakdown (no summary content before it)
        assert result.startswith("## 💰 Cost Breakdown")

    def test_format_with_empty_summary_only_cost(self):
        """Should show only cost breakdown when summary is empty string"""
        # Arrange
        summary = SummaryFile(content="")
        cost = CostBreakdown(main_cost=2.0, summary_cost=1.0)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "99999")

        # Assert
        assert "## 💰 Cost Breakdown" in result
        assert "$2.000000" in result
        assert "$1.000000" in result
        # Should start with cost breakdown (no summary content before it)
        assert result.startswith("## 💰 Cost Breakdown")

    def test_format_includes_workflow_url_from_cost(self):
        """Should include workflow URL from cost breakdown"""
        # Arrange
        summary = SummaryFile(content="Summary content")
        cost = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = summary.format_with_cost(cost, "test/repo", "54321")

        # Assert
        assert "https://github.com/test/repo/actions/runs/54321" in result
        assert "[View workflow run]" in result

    def test_format_preserves_summary_formatting(self):
        """Should preserve markdown formatting in summary"""
        # Arrange
        summary_content = """# Main Heading

## Subheading

- Bullet 1
- Bullet 2

**Bold text** and *italic text*"""

        summary = SummaryFile(content=summary_content)
        cost = CostBreakdown(main_cost=0.5, summary_cost=0.25)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "12345")

        # Assert
        assert "# Main Heading" in result
        assert "## Subheading" in result
        assert "- Bullet 1" in result
        assert "**Bold text**" in result
        assert "*italic text*" in result

    def test_format_returns_string(self):
        """Should always return a string"""
        # Arrange
        summary = SummaryFile(content="Content")
        cost = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "12345")

        # Assert
        assert isinstance(result, str)
        assert len(result) > 0

    def test_format_with_whitespace_only_summary(self):
        """Should treat whitespace-only summary as no content"""
        # Arrange
        summary = SummaryFile(content="   \n\t  ")  # Whitespace only
        cost = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = summary.format_with_cost(cost, "owner/repo", "12345")

        # Assert
        # Should start with cost breakdown since has_content is False
        assert result.startswith("## 💰 Cost Breakdown")
        # Should not have summary separator before cost breakdown
        assert not result.startswith("   \n\t  \n---\n")
