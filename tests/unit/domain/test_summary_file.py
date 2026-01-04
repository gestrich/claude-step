"""Unit tests for SummaryFile domain model"""

import os
import tempfile

import pytest

from claudechain.domain.summary_file import SummaryFile


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
