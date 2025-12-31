"""Unit tests for CostBreakdown domain model"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from claudestep.domain.cost_breakdown import CostBreakdown


class TestCostBreakdownConstruction:
    """Test suite for CostBreakdown construction and basic properties"""

    def test_can_create_cost_breakdown(self):
        """Should be able to create CostBreakdown instance"""
        # Act
        breakdown = CostBreakdown(main_cost=1.5, summary_cost=0.5)

        # Assert
        assert breakdown.main_cost == 1.5
        assert breakdown.summary_cost == 0.5

    def test_total_cost_calculation(self):
        """Should calculate total cost correctly"""
        # Arrange
        breakdown = CostBreakdown(main_cost=1.234567, summary_cost=0.654321)

        # Act
        total = breakdown.total_cost

        # Assert
        assert total == pytest.approx(1.888888)

    def test_zero_costs(self):
        """Should handle zero costs"""
        # Arrange
        breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)

        # Act
        total = breakdown.total_cost

        # Assert
        assert total == 0.0


class TestCostBreakdownFromExecutionFiles:
    """Test suite for CostBreakdown.from_execution_files() class method"""

    def test_from_execution_files_with_valid_files(self):
        """Should parse costs from valid execution files"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            main_file.write_text(json.dumps({"total_cost_usd": 1.5}))
            summary_file.write_text(json.dumps({"total_cost_usd": 0.5}))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert
            assert breakdown.main_cost == 1.5
            assert breakdown.summary_cost == 0.5
            assert breakdown.total_cost == 2.0

    def test_from_execution_files_with_missing_files(self):
        """Should return zero costs when files don't exist"""
        # Act
        breakdown = CostBreakdown.from_execution_files(
            "/nonexistent/main.json",
            "/nonexistent/summary.json"
        )

        # Assert
        assert breakdown.main_cost == 0.0
        assert breakdown.summary_cost == 0.0
        assert breakdown.total_cost == 0.0

    def test_from_execution_files_with_empty_paths(self):
        """Should handle empty file paths"""
        # Act
        breakdown = CostBreakdown.from_execution_files("", "")

        # Assert
        assert breakdown.main_cost == 0.0
        assert breakdown.summary_cost == 0.0

    def test_from_execution_files_with_list_format(self):
        """Should handle execution files with list format (multiple executions)"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            # List with multiple entries - should use the last one with cost
            main_file.write_text(json.dumps([
                {"total_cost_usd": 0.5},
                {"total_cost_usd": 1.5},  # This should be used
            ]))
            summary_file.write_text(json.dumps([
                {"total_cost_usd": 0.3},
                {"total_cost_usd": 0.7},  # This should be used
            ]))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert
            assert breakdown.main_cost == 1.5
            assert breakdown.summary_cost == 0.7


class TestExtractFromFile:
    """Test suite for CostBreakdown._extract_from_file() static method"""

    def test_extract_from_valid_json(self):
        """Should extract cost from valid JSON file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"total_cost_usd": 2.345678}, f)
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 2.345678
        finally:
            os.unlink(filepath)

    def test_extract_from_nested_usage_field(self):
        """Should extract cost from nested usage.total_cost_usd field"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"usage": {"total_cost_usd": 3.456789}}, f)
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 3.456789
        finally:
            os.unlink(filepath)

    def test_extract_from_empty_file(self):
        """Should return 0.0 for empty file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 0.0
        finally:
            os.unlink(filepath)

    def test_extract_from_invalid_json(self):
        """Should return 0.0 for invalid JSON"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {]}")
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 0.0
        finally:
            os.unlink(filepath)

    def test_extract_from_nonexistent_file(self):
        """Should return 0.0 for nonexistent file"""
        # Act
        cost = CostBreakdown._extract_from_file("/nonexistent/file.json")

        # Assert
        assert cost == 0.0

    def test_extract_from_whitespace_path(self):
        """Should return 0.0 for whitespace-only path"""
        # Act
        cost = CostBreakdown._extract_from_file("   ")

        # Assert
        assert cost == 0.0

    def test_extract_from_list_with_items_with_cost(self):
        """Should use last item with cost from list format"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([
                {"other_field": "value"},
                {"total_cost_usd": 1.0},
                {"other_field": "another"},
                {"total_cost_usd": 2.5},  # Last item with cost
            ], f)
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 2.5
        finally:
            os.unlink(filepath)

    def test_extract_from_list_without_cost_fields(self):
        """Should use last item when no items have total_cost_usd"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([
                {"other_field": "value1"},
                {"other_field": "value2"},
            ], f)
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 0.0  # No cost field found
        finally:
            os.unlink(filepath)

    def test_extract_from_empty_list(self):
        """Should return 0.0 for empty list"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            filepath = f.name

        try:
            # Act
            cost = CostBreakdown._extract_from_file(filepath)

            # Assert
            assert cost == 0.0
        finally:
            os.unlink(filepath)


class TestExtractCostFromDict:
    """Test suite for CostBreakdown._extract_cost_from_dict() static method"""

    def test_extract_from_top_level_field(self):
        """Should extract total_cost_usd from top level"""
        # Arrange
        data = {"total_cost_usd": 1.234567}

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost == 1.234567

    def test_extract_from_nested_usage_field(self):
        """Should extract from usage.total_cost_usd"""
        # Arrange
        data = {"usage": {"total_cost_usd": 2.345678}}

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost == 2.345678

    def test_prefer_top_level_over_nested(self):
        """Should prefer top-level total_cost_usd over nested"""
        # Arrange
        data = {
            "total_cost_usd": 3.0,
            "usage": {"total_cost_usd": 1.0}
        }

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost == 3.0

    def test_extract_from_dict_without_cost(self):
        """Should return None when no cost field exists"""
        # Arrange
        data = {"other_field": "value"}

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost is None

    def test_extract_handles_invalid_cost_value(self):
        """Should return None for non-numeric cost values"""
        # Arrange
        data = {"total_cost_usd": "not a number"}

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost is None

    def test_extract_handles_none_cost_value(self):
        """Should return None when cost value is None"""
        # Arrange
        data = {"total_cost_usd": None}

        # Act
        cost = CostBreakdown._extract_cost_from_dict(data)

        # Assert
        assert cost is None


class TestFormatForGitHub:
    """Test suite for CostBreakdown.format_for_github() method"""

    def test_format_creates_markdown_table(self):
        """Should create properly formatted markdown table"""
        # Arrange
        breakdown = CostBreakdown(main_cost=1.234567, summary_cost=0.543210)

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "## 💰 Cost Breakdown" in result
        assert "| Component | Cost (USD) |" in result
        assert "| Main refactoring task | $1.234567 |" in result
        assert "| PR summary generation | $0.543210 |" in result
        assert "| **Total** | **$1.777777** |" in result

    def test_format_includes_workflow_url(self):
        """Should include link to workflow run"""
        # Arrange
        breakdown = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "https://github.com/owner/repo/actions/runs/12345" in result
        assert "[View workflow run]" in result

    def test_format_with_zero_costs(self):
        """Should format zero costs correctly"""
        # Arrange
        breakdown = CostBreakdown(main_cost=0.0, summary_cost=0.0)

        # Act
        result = breakdown.format_for_github("owner/repo", "99999")

        # Assert
        assert "$0.000000" in result
        assert "**$0.000000**" in result  # Total

    def test_format_preserves_six_decimal_places(self):
        """Should format costs with 6 decimal places"""
        # Arrange
        breakdown = CostBreakdown(main_cost=1.23, summary_cost=0.45)

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "$1.230000" in result
        assert "$0.450000" in result
        assert "**$1.680000**" in result
