"""
Tests for extract_cost.py command
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from claudestep.cli.commands.extract_cost import cmd_extract_cost, extract_cost_from_execution


class TestExtractCostFromExecution:
    """Test suite for extract_cost_from_execution function"""

    def test_extracts_cost_from_top_level(self):
        """Should extract cost from top-level total_cost_usd field"""
        # Arrange
        data = {"total_cost_usd": 1.234567}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 1.234567

    def test_extracts_cost_from_nested_usage(self):
        """Should extract cost from nested usage.total_cost_usd field"""
        # Arrange
        data = {"usage": {"total_cost_usd": 2.345678}}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 2.345678

    def test_prefers_top_level_over_nested(self):
        """Should prefer top-level total_cost_usd when both exist"""
        # Arrange
        data = {
            "total_cost_usd": 1.5,
            "usage": {"total_cost_usd": 2.5}
        }

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 1.5

    def test_returns_none_when_cost_not_found(self):
        """Should return None when no cost field is present"""
        # Arrange
        data = {"some_field": "value", "other": 123}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result is None

    def test_handles_string_cost_value(self):
        """Should convert string cost values to float"""
        # Arrange
        data = {"total_cost_usd": "3.456"}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 3.456

    def test_handles_invalid_cost_value(self):
        """Should return None for invalid cost values"""
        # Arrange
        data = {"total_cost_usd": "invalid"}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result is None

    def test_handles_null_cost_value(self):
        """Should return None for null cost values"""
        # Arrange
        data = {"total_cost_usd": None}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result is None

    def test_handles_zero_cost(self):
        """Should correctly handle zero cost"""
        # Arrange
        data = {"total_cost_usd": 0.0}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 0.0

    def test_handles_high_precision_cost(self):
        """Should preserve high precision cost values"""
        # Arrange
        data = {"total_cost_usd": 0.123456789}

        # Act
        result = extract_cost_from_execution(data)

        # Assert
        assert result == 0.123456789


class TestCmdExtractCost:
    """Test suite for cmd_extract_cost command"""

    @pytest.fixture
    def mock_github_actions_helper(self):
        """Fixture providing mocked GitHubActionsHelper"""
        return Mock()

    def test_extracts_cost_from_execution_file_successfully(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should extract cost from execution file and write output"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = {"total_cost_usd": 1.234567}
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "1.234567"
        )

    def test_extracts_cost_from_list_last_item_by_default(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should extract cost from last item in list when EXECUTION_INDEX not set"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"total_cost_usd": 1.0},
            {"total_cost_usd": 2.0},
            {"total_cost_usd": 3.5}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "3.500000"
        )

    def test_extracts_cost_from_list_at_specific_index(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should extract cost from specific index when EXECUTION_INDEX is set"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"total_cost_usd": 1.0},
            {"total_cost_usd": 2.5},
            {"total_cost_usd": 3.0}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {
            "EXECUTION_FILE": str(execution_file),
            "EXECUTION_INDEX": "1"
        }

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "2.500000"
        )

    def test_handles_index_out_of_range_in_list(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should use last item when EXECUTION_INDEX is out of range"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"total_cost_usd": 1.0},
            {"total_cost_usd": 2.0}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {
            "EXECUTION_FILE": str(execution_file),
            "EXECUTION_INDEX": "10"  # Out of range
        }

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "2.000000"
        )

    def test_filters_to_items_with_cost_in_list(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should filter to only items with total_cost_usd when processing list"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"some_field": "value"},
            {"total_cost_usd": 1.5},
            {"other_field": 123},
            {"total_cost_usd": 2.5}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        # Should get last item with cost (2.5)
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "2.500000"
        )

    def test_returns_error_when_execution_file_not_provided(
        self, mock_github_actions_helper
    ):
        """Should return error when EXECUTION_FILE environment variable is missing"""
        # Arrange
        args = Mock()

        # Act
        with patch.dict(os.environ, {}, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 1
        mock_github_actions_helper.set_error.assert_called_once_with(
            "EXECUTION_FILE environment variable is required"
        )

    def test_defaults_to_zero_when_file_not_found(
        self, mock_github_actions_helper
    ):
        """Should write zero cost when execution file does not exist"""
        # Arrange
        env_vars = {"EXECUTION_FILE": "/nonexistent/file.json"}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_defaults_to_zero_when_cost_not_found_in_data(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should write zero cost when cost field is missing from data"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = {"some_field": "value", "other": 123}
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_handles_invalid_json_gracefully(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should handle invalid JSON and default to zero cost"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_file.write_text("not valid json")

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.set_error.assert_called_once()
        assert "Failed to parse execution file as JSON" in str(
            mock_github_actions_helper.set_error.call_args[0][0]
        )
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_handles_unexpected_exception(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should handle unexpected exceptions and default to zero cost"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_file.write_text('{"total_cost_usd": 1.5}')

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            with patch("builtins.open", side_effect=Exception("Unexpected error")):
                result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.set_error.assert_called_once()
        assert "Error extracting cost" in str(
            mock_github_actions_helper.set_error.call_args[0][0]
        )
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_outputs_cost_with_six_decimal_places(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should format cost output with exactly 6 decimal places"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = {"total_cost_usd": 1.23}
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "1.230000"
        )

    def test_handles_empty_list(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should handle empty list and default to zero cost"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = []
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_handles_list_without_cost_items(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should fallback to last item when list has no items with cost"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"field": "value1"},
            {"field": "value2"}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        # Should default to 0 since last item has no cost
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "0"
        )

    def test_extracts_from_nested_usage_field(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should extract cost from nested usage.total_cost_usd field"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = {
            "usage": {
                "total_cost_usd": 4.567890
            }
        }
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {"EXECUTION_FILE": str(execution_file)}
        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "4.567890"
        )

    def test_handles_negative_execution_index(
        self, mock_github_actions_helper, tmp_path
    ):
        """Should handle negative EXECUTION_INDEX correctly (Python list indexing)"""
        # Arrange
        execution_file = tmp_path / "execution.json"
        execution_data = [
            {"total_cost_usd": 1.0},
            {"total_cost_usd": 2.0},
            {"total_cost_usd": 3.0}
        ]
        execution_file.write_text(json.dumps(execution_data))

        env_vars = {
            "EXECUTION_FILE": str(execution_file),
            "EXECUTION_INDEX": "-2"  # Second to last
        }

        args = Mock()

        # Act
        with patch.dict(os.environ, env_vars, clear=True):
            result = cmd_extract_cost(args, mock_github_actions_helper)

        # Assert
        assert result == 0
        mock_github_actions_helper.write_output.assert_called_once_with(
            "cost_usd", "2.000000"
        )
