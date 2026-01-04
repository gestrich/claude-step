"""Tests for GitHub Actions environment helpers"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from claudechain.infrastructure.github.actions import GitHubActionsHelper


class TestGitHubActionsHelper:
    """Test suite for GitHubActionsHelper class"""

    def test_init_with_environment_variables(self):
        """Should initialize with environment variables when present"""
        # Arrange & Act
        with patch.dict(os.environ, {
            "GITHUB_OUTPUT": "/tmp/output",
            "GITHUB_STEP_SUMMARY": "/tmp/summary"
        }):
            helper = GitHubActionsHelper()

        # Assert
        assert helper.github_output_file == "/tmp/output"
        assert helper.github_step_summary_file == "/tmp/summary"

    def test_init_without_environment_variables(self):
        """Should initialize with None when environment variables not set"""
        # Arrange & Act
        with patch.dict(os.environ, {}, clear=True):
            helper = GitHubActionsHelper()

        # Assert
        assert helper.github_output_file is None
        assert helper.github_step_summary_file is None


class TestWriteOutput:
    """Test suite for write_output method"""

    def test_write_output_single_line_value(self, tmp_path):
        """Should write single-line value in simple format"""
        # Arrange
        output_file = tmp_path / "output.txt"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_output("my_var", "simple value")

        # Assert
        content = output_file.read_text()
        assert content == "my_var=simple value\n"

    def test_write_output_multiline_value(self, tmp_path):
        """Should write multi-line value using heredoc format"""
        # Arrange
        output_file = tmp_path / "output.txt"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            helper = GitHubActionsHelper()

        # Act
        multiline_value = "line1\nline2\nline3"
        helper.write_output("my_var", multiline_value)

        # Assert
        content = output_file.read_text()
        assert content.startswith("my_var<<EOF_")
        assert "line1\nline2\nline3\n" in content
        assert content.count("EOF_") == 2  # Opening and closing delimiter

    def test_write_output_appends_to_file(self, tmp_path):
        """Should append to output file not overwrite"""
        # Arrange
        output_file = tmp_path / "output.txt"
        output_file.write_text("existing=value\n")
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_output("new_var", "new value")

        # Assert
        content = output_file.read_text()
        assert "existing=value\n" in content
        assert "new_var=new value\n" in content

    def test_write_output_without_github_output_env(self, capsys):
        """Should print to stdout when GITHUB_OUTPUT not set"""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            helper = GitHubActionsHelper()

        # Act
        helper.write_output("test_var", "test value")

        # Assert
        captured = capsys.readouterr()
        assert "test_var=test value" in captured.out

    def test_write_output_handles_empty_value(self, tmp_path):
        """Should handle empty string value"""
        # Arrange
        output_file = tmp_path / "output.txt"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_output("empty_var", "")

        # Assert
        content = output_file.read_text()
        assert "empty_var=\n" in content

    def test_write_output_multiline_uses_unique_delimiter(self, tmp_path):
        """Should use unique delimiter for each multiline value"""
        # Arrange
        output_file = tmp_path / "output.txt"
        with patch.dict(os.environ, {"GITHUB_OUTPUT": str(output_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_output("var1", "line1\nline2")
        helper.write_output("var2", "line3\nline4")

        # Assert
        content = output_file.read_text()
        # Each should have its own delimiter
        assert content.count("<<EOF_") == 2
        # Delimiters should be different (have different hex suffixes)
        lines = content.split('\n')
        delimiters = [line.split('<<')[1] for line in lines if '<<EOF_' in line]
        assert len(delimiters) == 2
        assert delimiters[0] != delimiters[1]


class TestWriteStepSummary:
    """Test suite for write_step_summary method"""

    def test_write_step_summary_success(self, tmp_path):
        """Should write text to step summary file"""
        # Arrange
        summary_file = tmp_path / "summary.txt"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_step_summary("## Test Summary")

        # Assert
        content = summary_file.read_text()
        assert content == "## Test Summary\n"

    def test_write_step_summary_appends_to_file(self, tmp_path):
        """Should append to summary file not overwrite"""
        # Arrange
        summary_file = tmp_path / "summary.txt"
        summary_file.write_text("# Existing Header\n")
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            helper = GitHubActionsHelper()

        # Act
        helper.write_step_summary("- New item")

        # Assert
        content = summary_file.read_text()
        assert "# Existing Header\n" in content
        assert "- New item\n" in content

    def test_write_step_summary_without_env_var(self, capsys):
        """Should print to stdout when GITHUB_STEP_SUMMARY not set"""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            helper = GitHubActionsHelper()

        # Act
        helper.write_step_summary("Test summary text")

        # Assert
        captured = capsys.readouterr()
        assert "SUMMARY: Test summary text" in captured.out

    def test_write_step_summary_handles_markdown(self, tmp_path):
        """Should write markdown content correctly"""
        # Arrange
        summary_file = tmp_path / "summary.txt"
        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            helper = GitHubActionsHelper()

        # Act
        markdown = "## Section\n- Item 1\n- Item 2\n**Bold text**"
        helper.write_step_summary(markdown)

        # Assert
        content = summary_file.read_text()
        assert "## Section\n- Item 1\n- Item 2\n**Bold text**\n" in content


class TestAnnotations:
    """Test suite for annotation methods (error, notice, warning)"""

    def test_set_error_outputs_workflow_command(self, capsys):
        """Should output GitHub Actions error command"""
        # Arrange
        helper = GitHubActionsHelper()

        # Act
        helper.set_error("Something went wrong")

        # Assert
        captured = capsys.readouterr()
        assert "::error::Something went wrong" in captured.out

    def test_set_notice_outputs_workflow_command(self, capsys):
        """Should output GitHub Actions notice command"""
        # Arrange
        helper = GitHubActionsHelper()

        # Act
        helper.set_notice("Informational message")

        # Assert
        captured = capsys.readouterr()
        assert "::notice::Informational message" in captured.out

    def test_set_warning_outputs_workflow_command(self, capsys):
        """Should output GitHub Actions warning command"""
        # Arrange
        helper = GitHubActionsHelper()

        # Act
        helper.set_warning("Warning message")

        # Assert
        captured = capsys.readouterr()
        assert "::warning::Warning message" in captured.out

    def test_set_error_with_special_characters(self, capsys):
        """Should handle special characters in error message"""
        # Arrange
        helper = GitHubActionsHelper()

        # Act
        helper.set_error("Error: file 'test.py' has issues")

        # Assert
        captured = capsys.readouterr()
        assert "::error::Error: file 'test.py' has issues" in captured.out

    def test_annotation_methods_work_without_env_vars(self, capsys):
        """Should work correctly even without GitHub environment variables"""
        # Arrange
        with patch.dict(os.environ, {}, clear=True):
            helper = GitHubActionsHelper()

        # Act
        helper.set_error("error")
        helper.set_notice("notice")
        helper.set_warning("warning")

        # Assert
        captured = capsys.readouterr()
        assert "::error::error" in captured.out
        assert "::notice::notice" in captured.out
        assert "::warning::warning" in captured.out
