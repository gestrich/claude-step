"""Tests for parse_claude_result command"""

import json
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from claudechain.cli.commands.parse_claude_result import (
    cmd_parse_claude_result,
    _extract_structured_output,
)


class TestExtractStructuredOutput:
    """Tests for _extract_structured_output helper function"""

    def test_extracts_from_list_with_result(self):
        """Extracts structured output from list format (verbose mode)"""
        data = [
            {"type": "message"},
            {"result": {"structured_output": {"success": True, "summary": "Done"}}}
        ]

        result = _extract_structured_output(data)

        assert result == {"success": True, "summary": "Done"}

    def test_extracts_from_list_with_direct_structured_output(self):
        """Extracts structured output when directly in list item"""
        data = [
            {"type": "message"},
            {"structured_output": {"success": True, "summary": "Done"}}
        ]

        result = _extract_structured_output(data)

        assert result == {"success": True, "summary": "Done"}

    def test_extracts_from_dict_with_result(self):
        """Extracts structured output from dict format"""
        data = {"result": {"structured_output": {"success": True, "summary": "Done"}}}

        result = _extract_structured_output(data)

        assert result == {"success": True, "summary": "Done"}

    def test_extracts_from_dict_with_direct_structured_output(self):
        """Extracts structured output when directly in dict"""
        data = {"structured_output": {"success": True, "summary": "Done"}}

        result = _extract_structured_output(data)

        assert result == {"success": True, "summary": "Done"}

    def test_returns_none_when_not_found(self):
        """Returns None when no structured output present"""
        data = {"type": "message", "content": "Hello"}

        result = _extract_structured_output(data)

        assert result is None

    def test_returns_none_for_empty_list(self):
        """Returns None for empty list"""
        result = _extract_structured_output([])

        assert result is None

    def test_returns_none_for_empty_dict(self):
        """Returns None for empty dict"""
        result = _extract_structured_output({})

        assert result is None

    def test_searches_list_from_end(self):
        """Finds structured output in last item with it"""
        data = [
            {"structured_output": {"success": False}},
            {"type": "message"},
            {"result": {"structured_output": {"success": True, "summary": "Final"}}}
        ]

        result = _extract_structured_output(data)

        assert result == {"success": True, "summary": "Final"}


class TestCmdParseClaudeResult:
    """Tests for cmd_parse_claude_result command"""

    @pytest.fixture
    def mock_gh(self):
        """Create a mock GitHubActionsHelper"""
        gh = MagicMock()
        gh.outputs = {}

        def write_output(key, value):
            gh.outputs[key] = value

        gh.write_output = write_output
        return gh

    def test_handles_missing_execution_file(self, mock_gh):
        """Returns outputs when execution file is empty"""
        result = cmd_parse_claude_result(mock_gh, "", "main")

        assert result == 0
        assert mock_gh.outputs["success"] == "false"
        assert "No execution file provided" in mock_gh.outputs["error_message"]

    def test_handles_nonexistent_execution_file(self, mock_gh):
        """Returns outputs when execution file doesn't exist"""
        result = cmd_parse_claude_result(mock_gh, "/nonexistent/file.json", "main")

        assert result == 0
        assert mock_gh.outputs["success"] == "false"
        assert "not found" in mock_gh.outputs["error_message"]

    def test_handles_invalid_json(self, mock_gh):
        """Returns outputs when execution file has invalid JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json")
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "main")

            assert result == 0
            assert mock_gh.outputs["success"] == "false"
            assert "Invalid JSON" in mock_gh.outputs["error_message"]
        finally:
            os.unlink(temp_path)

    def test_defaults_to_success_when_no_structured_output(self, mock_gh):
        """Defaults to success when no structured output found"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"type": "message", "content": "Hello"}, f)
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "main")

            assert result == 0
            assert mock_gh.outputs["success"] == "true"
            assert mock_gh.outputs["error_message"] == ""
        finally:
            os.unlink(temp_path)

    def test_extracts_success_true(self, mock_gh):
        """Extracts success=true from structured output"""
        data = {
            "result": {
                "structured_output": {
                    "success": True,
                    "summary": "Task completed successfully"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "main")

            assert result == 0
            assert mock_gh.outputs["success"] == "true"
            assert mock_gh.outputs["summary"] == "Task completed successfully"
            assert mock_gh.outputs["error_message"] == ""
        finally:
            os.unlink(temp_path)

    def test_extracts_success_false_with_error(self, mock_gh):
        """Extracts success=false and error_message from structured output"""
        data = {
            "result": {
                "structured_output": {
                    "success": False,
                    "error_message": "Something went wrong",
                    "summary": "Failed to complete task"
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "main")

            assert result == 1  # Should return non-zero exit code on failure
            assert mock_gh.outputs["success"] == "false"
            assert mock_gh.outputs["error_message"] == "Something went wrong"
            assert mock_gh.outputs["summary"] == "Failed to complete task"
        finally:
            os.unlink(temp_path)

    def test_extracts_summary_content_for_summary_type(self, mock_gh):
        """Extracts summary_content field for summary result type"""
        data = {
            "structured_output": {
                "success": True,
                "summary_content": "This PR adds feature X"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "summary")

            assert result == 0
            assert mock_gh.outputs["success"] == "true"
            assert mock_gh.outputs["summary"] == "This PR adds feature X"
        finally:
            os.unlink(temp_path)

    def test_handles_verbose_mode_list_format(self, mock_gh):
        """Handles verbose mode with list of events"""
        data = [
            {"type": "start", "timestamp": "2024-01-01T00:00:00Z"},
            {"type": "message", "content": "Working on task..."},
            {
                "type": "finish",
                "result": {
                    "structured_output": {
                        "success": True,
                        "summary": "Completed"
                    }
                }
            }
        ]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            result = cmd_parse_claude_result(mock_gh, temp_path, "main")

            assert result == 0
            assert mock_gh.outputs["success"] == "true"
            assert mock_gh.outputs["summary"] == "Completed"
        finally:
            os.unlink(temp_path)
