"""Unit tests for CostBreakdown domain model"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from claudestep.domain.cost_breakdown import (
    CLAUDE_MODELS,
    ClaudeModel,
    CostBreakdown,
    ExecutionUsage,
    ModelUsage,
    UnknownModelError,
    get_model,
    get_rate_for_model,
)


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
        """Should parse and calculate costs from valid execution files"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            # Files with modelUsage so calculated_cost works
            # 1M input tokens at Haiku rate $0.25/MTok = $0.25
            main_file.write_text(json.dumps({
                "total_cost_usd": 1.5,  # File cost (ignored)
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": 1_000_000,
                    }
                }
            }))
            # 500k input tokens at Haiku rate = $0.125
            summary_file.write_text(json.dumps({
                "total_cost_usd": 0.5,  # File cost (ignored)
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": 500_000,
                    }
                }
            }))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert - uses calculated_cost, not file's total_cost_usd
            assert breakdown.main_cost == pytest.approx(0.25)
            assert breakdown.summary_cost == pytest.approx(0.125)
            assert breakdown.total_cost == pytest.approx(0.375)

    def test_from_execution_files_raises_on_missing_files(self):
        """Should raise FileNotFoundError when files don't exist"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            CostBreakdown.from_execution_files(
                "/nonexistent/main.json",
                "/nonexistent/summary.json"
            )

    def test_from_execution_files_raises_on_empty_paths(self):
        """Should raise ValueError for empty file paths"""
        # Act & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            CostBreakdown.from_execution_files("", "")

    def test_from_execution_files_with_list_format(self):
        """Should handle execution files with list format (multiple executions)"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            # List with multiple entries - should use the last one with cost
            main_file.write_text(json.dumps([
                {
                    "total_cost_usd": 0.5,
                    "modelUsage": {
                        "claude-3-haiku-20240307": {"inputTokens": 100_000}
                    }
                },
                {
                    "total_cost_usd": 1.5,  # Last one with cost is used
                    "modelUsage": {
                        "claude-3-haiku-20240307": {"inputTokens": 1_000_000}  # $0.25
                    }
                },
            ]))
            summary_file.write_text(json.dumps([
                {
                    "total_cost_usd": 0.3,
                    "modelUsage": {
                        "claude-3-haiku-20240307": {"inputTokens": 100_000}
                    }
                },
                {
                    "total_cost_usd": 0.7,  # Last one with cost is used
                    "modelUsage": {
                        "claude-3-haiku-20240307": {"inputTokens": 400_000}  # $0.10
                    }
                },
            ]))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert - uses calculated_cost from modelUsage
            assert breakdown.main_cost == pytest.approx(0.25)
            assert breakdown.summary_cost == pytest.approx(0.10)


class TestModelUsage:
    """Test suite for ModelUsage dataclass"""

    def test_create_model_usage(self):
        """Should be able to create ModelUsage instance"""
        # Act
        usage = ModelUsage(
            model="claude-haiku",
            cost=0.5,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
        )

        # Assert
        assert usage.model == "claude-haiku"
        assert usage.cost == 0.5
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cache_read_tokens == 200
        assert usage.cache_write_tokens == 30

    def test_model_usage_total_tokens(self):
        """Should calculate total tokens correctly"""
        # Arrange
        usage = ModelUsage(
            model="claude-haiku",
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
        )

        # Act
        total = usage.total_tokens

        # Assert
        assert total == 380

    def test_model_usage_from_dict(self):
        """Should parse model usage from dict"""
        # Arrange
        data = {
            "inputTokens": 4271,
            "outputTokens": 389,
            "cacheReadInputTokens": 90755,
            "cacheCreationInputTokens": 12299,
            "costUSD": 0.02158975,
        }

        # Act
        usage = ModelUsage.from_dict("claude-haiku-4-5", data)

        # Assert
        assert usage.model == "claude-haiku-4-5"
        assert usage.cost == 0.02158975
        assert usage.input_tokens == 4271
        assert usage.output_tokens == 389
        assert usage.cache_read_tokens == 90755
        assert usage.cache_write_tokens == 12299

    def test_model_usage_from_dict_handles_missing_fields(self):
        """Should handle missing fields in dict"""
        # Arrange
        data = {"inputTokens": 100}

        # Act
        usage = ModelUsage.from_dict("claude-haiku", data)

        # Assert
        assert usage.input_tokens == 100
        assert usage.output_tokens == 0
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0
        assert usage.cost == 0.0

    def test_model_usage_from_dict_handles_null_values(self):
        """Should handle null/None values in dict"""
        # Arrange
        data = {
            "inputTokens": None,
            "outputTokens": 50,
            "costUSD": None,
        }

        # Act
        usage = ModelUsage.from_dict("claude-haiku", data)

        # Assert
        assert usage.input_tokens == 0
        assert usage.output_tokens == 50
        assert usage.cost == 0.0

    def test_model_usage_from_dict_raises_on_non_dict(self):
        """Should raise TypeError for non-dict data"""
        # Act & Assert
        with pytest.raises(TypeError, match="must be a dict"):
            ModelUsage.from_dict("claude-haiku", "not a dict")


class TestExecutionUsage:
    """Test suite for ExecutionUsage dataclass"""

    def test_create_execution_usage(self):
        """Should be able to create ExecutionUsage with models"""
        # Arrange
        models = [
            ModelUsage(model="haiku", input_tokens=100, output_tokens=50),
            ModelUsage(model="sonnet", input_tokens=200, output_tokens=100),
        ]

        # Act
        usage = ExecutionUsage(models=models, total_cost_usd=1.5)

        # Assert
        assert len(usage.models) == 2
        assert usage.total_cost_usd == 1.5
        assert usage.cost == 1.5

    def test_execution_usage_default_values(self):
        """Should default to empty models and zero cost"""
        # Act
        usage = ExecutionUsage()

        # Assert
        assert usage.models == []
        assert usage.total_cost_usd == 0.0
        assert usage.cost == 0.0
        assert usage.total_tokens == 0

    def test_execution_usage_aggregates_tokens(self):
        """Should sum tokens across all models"""
        # Arrange
        models = [
            ModelUsage(
                model="haiku",
                input_tokens=100,
                output_tokens=50,
                cache_read_tokens=200,
                cache_write_tokens=30,
            ),
            ModelUsage(
                model="sonnet",
                input_tokens=150,
                output_tokens=75,
                cache_read_tokens=100,
                cache_write_tokens=20,
            ),
        ]
        usage = ExecutionUsage(models=models)

        # Assert
        assert usage.input_tokens == 250
        assert usage.output_tokens == 125
        assert usage.cache_read_tokens == 300
        assert usage.cache_write_tokens == 50
        assert usage.total_tokens == 725

    def test_add_execution_usage(self):
        """Should combine two ExecutionUsage instances"""
        # Arrange
        usage1 = ExecutionUsage(
            models=[ModelUsage(model="haiku", input_tokens=100)],
            total_cost_usd=1.0,
        )
        usage2 = ExecutionUsage(
            models=[ModelUsage(model="sonnet", input_tokens=200)],
            total_cost_usd=0.5,
        )

        # Act
        result = usage1 + usage2

        # Assert
        assert result.total_cost_usd == 1.5
        assert len(result.models) == 2
        assert result.input_tokens == 300


class TestExecutionUsageFromFile:
    """Test suite for ExecutionUsage.from_execution_file() class method"""

    def test_from_valid_json(self):
        """Should extract usage from valid JSON file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"total_cost_usd": 2.345678}, f)
            filepath = f.name

        try:
            # Act
            usage = ExecutionUsage.from_execution_file(filepath)

            # Assert
            assert usage.cost == 2.345678
            assert usage.models == []
        finally:
            os.unlink(filepath)

    def test_from_nested_usage_field(self):
        """Should extract cost from nested usage.total_cost_usd field"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"usage": {"total_cost_usd": 3.456789}}, f)
            filepath = f.name

        try:
            # Act
            usage = ExecutionUsage.from_execution_file(filepath)

            # Assert
            assert usage.cost == 3.456789
        finally:
            os.unlink(filepath)

    def test_from_empty_file_raises(self):
        """Should raise JSONDecodeError for empty file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name

        try:
            # Act & Assert
            with pytest.raises(json.JSONDecodeError):
                ExecutionUsage.from_execution_file(filepath)
        finally:
            os.unlink(filepath)

    def test_from_invalid_json_raises(self):
        """Should raise JSONDecodeError for invalid JSON"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("not valid json {]}")
            filepath = f.name

        try:
            # Act & Assert
            with pytest.raises(json.JSONDecodeError):
                ExecutionUsage.from_execution_file(filepath)
        finally:
            os.unlink(filepath)

    def test_from_nonexistent_file_raises(self):
        """Should raise FileNotFoundError for nonexistent file"""
        # Act & Assert
        with pytest.raises(FileNotFoundError):
            ExecutionUsage.from_execution_file("/nonexistent/file.json")

    def test_from_whitespace_path_raises(self):
        """Should raise ValueError for whitespace-only path"""
        # Act & Assert
        with pytest.raises(ValueError, match="cannot be empty"):
            ExecutionUsage.from_execution_file("   ")

    def test_from_list_with_items_with_cost(self):
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
            usage = ExecutionUsage.from_execution_file(filepath)

            # Assert
            assert usage.cost == 2.5
        finally:
            os.unlink(filepath)

    def test_from_list_without_cost_fields(self):
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
            usage = ExecutionUsage.from_execution_file(filepath)

            # Assert
            assert usage.cost == 0.0  # No cost field found
        finally:
            os.unlink(filepath)

    def test_from_empty_list_raises(self):
        """Should raise ValueError for empty list"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([], f)
            filepath = f.name

        try:
            # Act & Assert
            with pytest.raises(ValueError, match="empty list"):
                ExecutionUsage.from_execution_file(filepath)
        finally:
            os.unlink(filepath)

    def test_from_file_with_model_usage(self):
        """Should extract both cost and per-model usage from file"""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({
                "total_cost_usd": 1.5,
                "modelUsage": {
                    "claude-haiku": {
                        "inputTokens": 1000,
                        "outputTokens": 500,
                        "cacheReadInputTokens": 2000,
                        "cacheCreationInputTokens": 300,
                        "costUSD": 0.5,
                    },
                    "claude-sonnet": {
                        "inputTokens": 200,
                        "outputTokens": 100,
                        "costUSD": 1.0,
                    },
                },
            }, f)
            filepath = f.name

        try:
            # Act
            usage = ExecutionUsage.from_execution_file(filepath)

            # Assert
            assert usage.cost == 1.5
            assert len(usage.models) == 2
            assert usage.input_tokens == 1200
            assert usage.output_tokens == 600
            assert usage.cache_read_tokens == 2000
            assert usage.cache_write_tokens == 300
        finally:
            os.unlink(filepath)


class TestExecutionUsageFromDict:
    """Test suite for ExecutionUsage._from_dict() class method"""

    def test_from_dict_with_model_usage(self):
        """Should extract per-model usage from modelUsage section"""
        # Arrange
        data = {
            "total_cost_usd": 0.5,
            "modelUsage": {
                "claude-haiku-4-5-20251001": {
                    "inputTokens": 4271,
                    "outputTokens": 389,
                    "cacheReadInputTokens": 0,
                    "cacheCreationInputTokens": 12299,
                    "costUSD": 0.02,
                },
                "claude-3-haiku-20240307": {
                    "inputTokens": 15,
                    "outputTokens": 426,
                    "cacheReadInputTokens": 90755,
                    "cacheCreationInputTokens": 30605,
                    "costUSD": 0.15,
                },
            },
        }

        # Act
        usage = ExecutionUsage._from_dict(data)

        # Assert
        assert usage.cost == 0.5
        assert len(usage.models) == 2
        assert usage.input_tokens == 4271 + 15
        assert usage.output_tokens == 389 + 426
        assert usage.cache_read_tokens == 0 + 90755
        assert usage.cache_write_tokens == 12299 + 30605

    def test_from_dict_without_model_usage(self):
        """Should return empty models when modelUsage is missing"""
        # Arrange
        data = {"total_cost_usd": 0.5}

        # Act
        usage = ExecutionUsage._from_dict(data)

        # Assert
        assert usage.cost == 0.5
        assert usage.models == []
        assert usage.total_tokens == 0

    def test_from_dict_with_empty_model_usage(self):
        """Should return empty models when modelUsage is empty"""
        # Arrange
        data = {"total_cost_usd": 0.5, "modelUsage": {}}

        # Act
        usage = ExecutionUsage._from_dict(data)

        # Assert
        assert usage.cost == 0.5
        assert usage.models == []

    def test_from_dict_raises_on_invalid_model_usage_type(self):
        """Should raise TypeError when modelUsage is not a dict"""
        # Arrange
        data = {"total_cost_usd": 1.0, "modelUsage": "not a dict"}

        # Act & Assert
        with pytest.raises(TypeError, match="modelUsage must be a dict"):
            ExecutionUsage._from_dict(data)

    def test_from_dict_with_nested_usage_cost(self):
        """Should extract cost from nested usage.total_cost_usd"""
        # Arrange
        data = {"usage": {"total_cost_usd": 2.5}}

        # Act
        usage = ExecutionUsage._from_dict(data)

        # Assert
        assert usage.cost == 2.5

    def test_from_dict_prefers_top_level_cost(self):
        """Should prefer top-level total_cost_usd over nested"""
        # Arrange
        data = {
            "total_cost_usd": 3.0,
            "usage": {"total_cost_usd": 1.0}
        }

        # Act
        usage = ExecutionUsage._from_dict(data)

        # Assert
        assert usage.cost == 3.0

    def test_from_dict_raises_on_invalid_cost_value(self):
        """Should raise ValueError for non-numeric cost values"""
        # Arrange
        data = {"total_cost_usd": "not a number"}

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid total_cost_usd"):
            ExecutionUsage._from_dict(data)

    def test_from_dict_raises_on_none_cost_value(self):
        """Should raise ValueError when cost value is None"""
        # Arrange
        data = {"total_cost_usd": None}

        # Act & Assert
        with pytest.raises(ValueError, match="Invalid total_cost_usd"):
            ExecutionUsage._from_dict(data)


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

    def test_format_includes_model_section_when_models_present(self):
        """Should include per-model breakdown section when models are available"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=1.0,
            summary_cost=0.5,
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=2000,
            cache_write_tokens=300,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=1000,
                    output_tokens=500,
                    cache_read_tokens=2000,
                    cache_write_tokens=300,
                )
            ],
        )

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "### Per-Model Breakdown" in result
        assert "| Model | Input | Output | Cache R | Cache W | Cost |" in result
        assert "claude-3-haiku-20240307" in result
        assert "1,000" in result
        assert "500" in result
        assert "| **Total** |" in result

    def test_format_excludes_model_section_when_no_models(self):
        """Should not include per-model breakdown section when no models"""
        # Arrange
        breakdown = CostBreakdown(main_cost=1.0, summary_cost=0.5)

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "### Per-Model Breakdown" not in result

    def test_format_with_large_token_counts_in_model_breakdown(self):
        """Should format large token counts with thousands separators in model breakdown"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=1.0,
            summary_cost=0.5,
            input_tokens=1234567,
            output_tokens=987654,
            cache_read_tokens=0,
            cache_write_tokens=0,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=1234567,
                    output_tokens=987654,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                )
            ],
        )

        # Act
        result = breakdown.format_for_github("owner/repo", "12345")

        # Assert
        assert "1,234,567" in result
        assert "987,654" in result


class TestCostBreakdownWithTokens:
    """Test suite for CostBreakdown with token data from execution files"""

    def test_from_execution_files_extracts_tokens(self):
        """Should extract token data from execution files with modelUsage"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            main_file.write_text(json.dumps({
                "total_cost_usd": 1.5,  # File cost (ignored)
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": 1000,
                        "outputTokens": 500,
                        "cacheReadInputTokens": 2000,
                        "cacheCreationInputTokens": 300,
                    },
                },
            }))
            summary_file.write_text(json.dumps({
                "total_cost_usd": 0.5,  # File cost (ignored)
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": 200,
                        "outputTokens": 100,
                        "cacheReadInputTokens": 400,
                        "cacheCreationInputTokens": 50,
                    },
                },
            }))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert - costs are calculated using Haiku 3 rates:
            # input $0.25, output $1.25, cache_write $0.30, cache_read $0.03
            # Main: (1000*0.25 + 500*1.25 + 300*0.30 + 2000*0.03) / 1M
            #     = (250 + 625 + 90 + 60) / 1M = 0.001025
            # Summary: (200*0.25 + 100*1.25 + 50*0.30 + 400*0.03) / 1M
            #        = (50 + 125 + 15 + 12) / 1M = 0.000202
            assert breakdown.main_cost == pytest.approx(0.001025)
            assert breakdown.summary_cost == pytest.approx(0.000202)
            # Tokens should be summed from both files
            assert breakdown.input_tokens == 1000 + 200
            assert breakdown.output_tokens == 500 + 100
            assert breakdown.cache_read_tokens == 2000 + 400
            assert breakdown.cache_write_tokens == 300 + 50

    def test_from_execution_files_without_model_usage_returns_zero_cost(self):
        """Should return zero cost when modelUsage is missing"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            # Files without modelUsage - no tokens means no calculated cost
            main_file.write_text(json.dumps({"total_cost_usd": 1.5}))
            summary_file.write_text(json.dumps({"total_cost_usd": 0.5}))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert - calculated_cost is 0 when no modelUsage
            assert breakdown.main_cost == 0.0
            assert breakdown.summary_cost == 0.0
            # Tokens should be zero
            assert breakdown.input_tokens == 0
            assert breakdown.output_tokens == 0
            assert breakdown.cache_read_tokens == 0
            assert breakdown.cache_write_tokens == 0

    def test_total_tokens_property(self):
        """Should calculate total tokens correctly"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=1.0,
            summary_cost=0.5,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
        )

        # Act
        total = breakdown.total_tokens

        # Assert
        assert total == 100 + 50 + 200 + 30


class TestGetRateForModel:
    """Test suite for get_rate_for_model() function"""

    def test_haiku_3_rate(self):
        """Should return Haiku 3 rate for claude-3-haiku models"""
        assert get_rate_for_model("claude-3-haiku-20240307") == 0.25
        assert get_rate_for_model("Claude-3-Haiku-20240307") == 0.25

    def test_haiku_4_rate(self):
        """Should return Haiku 4 rate for claude-haiku-4 models"""
        assert get_rate_for_model("claude-haiku-4-5-20251001") == 1.00
        assert get_rate_for_model("claude-haiku-4-20250101") == 1.00

    def test_sonnet_35_rate(self):
        """Should return Sonnet 3.5 rate for claude-3-5-sonnet models"""
        assert get_rate_for_model("claude-3-5-sonnet-20241022") == 3.00

    def test_sonnet_4_rate(self):
        """Should return Sonnet 4 rate for claude-sonnet-4 models"""
        assert get_rate_for_model("claude-sonnet-4-20250514") == 3.00

    def test_opus_4_rate(self):
        """Should return Opus 4 rate for claude-opus-4 models"""
        assert get_rate_for_model("claude-opus-4-20250514") == 15.00

    def test_unknown_model_raises_error(self):
        """Should raise UnknownModelError for unknown models"""
        with pytest.raises(UnknownModelError, match="Unknown model 'unknown-model'"):
            get_rate_for_model("unknown-model")

        with pytest.raises(UnknownModelError, match="Unknown model 'gpt-4'"):
            get_rate_for_model("gpt-4")

    def test_case_insensitive(self):
        """Should match model names case-insensitively"""
        assert get_rate_for_model("CLAUDE-3-HAIKU-20240307") == 0.25
        assert get_rate_for_model("Claude-Haiku-4-5-20251001") == 1.00


class TestClaudeModel:
    """Test suite for ClaudeModel dataclass"""

    def test_claude_model_creation(self):
        """Should create ClaudeModel with all pricing rates"""
        # Act
        model = ClaudeModel(
            pattern="test-model",
            input_rate=1.00,
            output_rate=5.00,
            cache_write_rate=1.25,
            cache_read_rate=0.10,
        )

        # Assert
        assert model.pattern == "test-model"
        assert model.input_rate == 1.00
        assert model.output_rate == 5.00
        assert model.cache_write_rate == 1.25
        assert model.cache_read_rate == 0.10

    def test_claude_model_calculate_cost(self):
        """Should calculate cost using all token types"""
        # Arrange
        model = ClaudeModel(
            pattern="test-model",
            input_rate=1.00,
            output_rate=5.00,
            cache_write_rate=1.25,
            cache_read_rate=0.10,
        )

        # Act - 1M of each token type
        cost = model.calculate_cost(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_write_tokens=1_000_000,
            cache_read_tokens=1_000_000,
        )

        # Assert: $1.00 + $5.00 + $1.25 + $0.10 = $7.35
        assert cost == pytest.approx(7.35)

    def test_claude_model_is_frozen(self):
        """Should be immutable (frozen dataclass)"""
        # Arrange
        model = ClaudeModel(
            pattern="test-model",
            input_rate=1.00,
            output_rate=5.00,
            cache_write_rate=1.25,
            cache_read_rate=0.10,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            model.input_rate = 2.00

    def test_haiku_3_has_unique_cache_rates(self):
        """Should have correct unique cache rates for Haiku 3 (1.2x write, 0.12x read)"""
        # Act
        model = get_model("claude-3-haiku-20240307")

        # Assert - Haiku 3 uses different multipliers than other models
        assert model.input_rate == 0.25
        assert model.output_rate == 1.25
        assert model.cache_write_rate == 0.30  # 1.2x input (not 1.25x)
        assert model.cache_read_rate == 0.03   # 0.12x input (not 0.1x)

    def test_haiku_4_has_standard_cache_rates(self):
        """Should have standard cache rates for Haiku 4 (1.25x write, 0.1x read)"""
        # Act
        model = get_model("claude-haiku-4-5-20251001")

        # Assert - Haiku 4 uses standard multipliers
        assert model.input_rate == 1.00
        assert model.output_rate == 5.00
        assert model.cache_write_rate == 1.25  # 1.25x input
        assert model.cache_read_rate == 0.10   # 0.1x input


class TestGetModel:
    """Test suite for get_model() function"""

    def test_get_model_returns_claude_model(self):
        """Should return ClaudeModel instance"""
        # Act
        model = get_model("claude-3-haiku-20240307")

        # Assert
        assert isinstance(model, ClaudeModel)

    def test_get_model_haiku_3(self):
        """Should return correct model for Haiku 3"""
        # Act
        model = get_model("claude-3-haiku-20240307")

        # Assert
        assert model.pattern == "claude-3-haiku"
        assert model.input_rate == 0.25

    def test_get_model_haiku_4(self):
        """Should return correct model for Haiku 4"""
        # Act
        model = get_model("claude-haiku-4-5-20251001")

        # Assert
        assert model.pattern == "claude-haiku-4"
        assert model.input_rate == 1.00

    def test_get_model_sonnet_4(self):
        """Should return correct model for Sonnet 4"""
        # Act
        model = get_model("claude-sonnet-4-20250514")

        # Assert
        assert model.pattern == "claude-sonnet-4"
        assert model.input_rate == 3.00

    def test_get_model_opus_4(self):
        """Should return correct model for Opus 4"""
        # Act
        model = get_model("claude-opus-4-20250514")

        # Assert
        assert model.pattern == "claude-opus-4"
        assert model.input_rate == 15.00

    def test_get_model_unknown_raises_error(self):
        """Should raise UnknownModelError for unknown models"""
        # Act & Assert
        with pytest.raises(UnknownModelError, match="Unknown model 'gpt-4'"):
            get_model("gpt-4")

    def test_get_model_case_insensitive(self):
        """Should match model names case-insensitively"""
        # Act
        model = get_model("CLAUDE-3-HAIKU-20240307")

        # Assert
        assert model.pattern == "claude-3-haiku"


class TestModelUsageCalculateCost:
    """Test suite for ModelUsage.calculate_cost() method"""

    def test_calculate_cost_haiku_3(self):
        """Should calculate cost correctly for Haiku 3"""
        # Arrange - 1M input tokens at $0.25/MTok = $0.25
        usage = ModelUsage(
            model="claude-3-haiku-20240307",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(0.25)

    def test_calculate_cost_with_output_tokens(self):
        """Should calculate output tokens at 5x input rate"""
        # Arrange - 1M output tokens at $0.25 * 5 = $1.25
        usage = ModelUsage(
            model="claude-3-haiku-20240307",
            input_tokens=0,
            output_tokens=1_000_000,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(1.25)

    def test_calculate_cost_with_cache_write(self):
        """Should calculate cache write tokens at correct rate for Haiku 3"""
        # Arrange - 1M cache write tokens at $0.30/MTok (Haiku 3 uses 1.2x, not 1.25x)
        usage = ModelUsage(
            model="claude-3-haiku-20240307",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=1_000_000,
        )

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(0.30)

    def test_calculate_cost_with_cache_read(self):
        """Should calculate cache read tokens at correct rate for Haiku 3"""
        # Arrange - 1M cache read tokens at $0.03/MTok (Haiku 3 uses 0.12x, not 0.1x)
        usage = ModelUsage(
            model="claude-3-haiku-20240307",
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,
            cache_write_tokens=0,
        )

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(0.03)

    def test_calculate_cost_combined(self):
        """Should calculate combined cost correctly for Haiku 3"""
        # Arrange - Haiku 3 rates: input $0.25, output $1.25, cache_write $0.30, cache_read $0.03
        usage = ModelUsage(
            model="claude-3-haiku-20240307",
            input_tokens=100_000,      # $0.025
            output_tokens=50_000,      # $0.0625
            cache_read_tokens=200_000,  # $0.006 (200k * $0.03/MTok)
            cache_write_tokens=30_000,  # $0.009 (30k * $0.30/MTok)
        )
        # Total: $0.025 + $0.0625 + $0.006 + $0.009 = $0.1025

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(0.1025)

    def test_calculate_cost_sonnet_4(self):
        """Should calculate cost correctly for Sonnet 4"""
        # Arrange - 1M input tokens at $3.00/MTok = $3.00
        usage = ModelUsage(
            model="claude-sonnet-4-20250514",
            input_tokens=1_000_000,
            output_tokens=0,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )

        # Act
        cost = usage.calculate_cost()

        # Assert
        assert cost == pytest.approx(3.00)


class TestExecutionUsageCalculatedCost:
    """Test suite for ExecutionUsage.calculated_cost property"""

    def test_calculated_cost_single_model(self):
        """Should calculate cost for single model"""
        # Arrange
        models = [
            ModelUsage(
                model="claude-3-haiku-20240307",
                input_tokens=1_000_000,
            )
        ]
        usage = ExecutionUsage(models=models)

        # Act
        cost = usage.calculated_cost

        # Assert
        assert cost == pytest.approx(0.25)

    def test_calculated_cost_multiple_models(self):
        """Should sum costs across multiple models"""
        # Arrange
        models = [
            ModelUsage(
                model="claude-3-haiku-20240307",
                input_tokens=1_000_000,  # $0.25
            ),
            ModelUsage(
                model="claude-sonnet-4-20250514",
                input_tokens=1_000_000,  # $3.00
            ),
        ]
        usage = ExecutionUsage(models=models)

        # Act
        cost = usage.calculated_cost

        # Assert
        assert cost == pytest.approx(3.25)

    def test_calculated_cost_empty_models(self):
        """Should return 0 for empty models list"""
        # Arrange
        usage = ExecutionUsage(models=[])

        # Act
        cost = usage.calculated_cost

        # Assert
        assert cost == 0.0

    def test_calculated_cost_differs_from_file_cost(self):
        """Should calculate differently from inaccurate file cost"""
        # Arrange - file says $0.148 but actual should be ~$0.033
        models = [
            ModelUsage(
                model="claude-3-haiku-20240307",
                input_tokens=15,
                output_tokens=426,
                cache_read_tokens=90755,
                cache_write_tokens=30605,
            )
        ]
        usage = ExecutionUsage(models=models, total_cost_usd=0.14843025)

        # Act
        file_cost = usage.cost  # From file
        calculated = usage.calculated_cost  # Our calculation

        # Assert - calculated cost should be much lower for Haiku
        assert file_cost == pytest.approx(0.14843025)
        # Formula: (15 * 0.25) + (426 * 1.25) + (30605 * 0.3125) + (90755 * 0.025) / 1M
        # = 0.00000375 + 0.000532 + 0.00956 + 0.00227 = 0.01237 ≈ $0.012
        assert calculated < file_cost  # Calculated should be less than inflated file cost
        assert calculated == pytest.approx(0.01237, rel=0.01)


class TestRealWorkflowData:
    """Test suite using real workflow data from gestrich/swift-lambda-sample PR #24"""

    @pytest.fixture
    def pr24_main_file(self):
        """Path to PR #24 main execution fixture"""
        return Path(__file__).parent.parent.parent / "fixtures" / "pr24_main_execution.json"

    @pytest.fixture
    def pr24_summary_file(self):
        """Path to PR #24 summary execution fixture"""
        return Path(__file__).parent.parent.parent / "fixtures" / "pr24_summary_execution.json"

    def test_main_execution_calculated_cost(self, pr24_main_file):
        """Should calculate correct cost for main execution from real workflow data"""
        # Arrange
        usage = ExecutionUsage.from_execution_file(str(pr24_main_file))

        # Act
        calculated = usage.calculated_cost
        file_cost = usage.cost

        # Assert - file cost is inflated due to wrong rates
        assert file_cost == pytest.approx(0.170020, rel=0.01)
        # Our calculated cost should be accurate:
        # claude-haiku-4-5: (4271*1.00 + 389*5.00 + 12299*1.25 + 0*0.10) / 1M = 0.02158975
        # claude-3-haiku: (15*0.25 + 426*1.25 + 30605*0.3125 + 90755*0.025) / 1M = 0.012369188
        # Total: 0.033958938
        assert calculated == pytest.approx(0.033959, rel=0.01)
        # Overcharge factor should be ~5x
        assert file_cost / calculated == pytest.approx(5.0, rel=0.1)

    def test_summary_execution_calculated_cost(self, pr24_summary_file):
        """Should calculate correct cost for summary execution from real workflow data"""
        # Arrange
        usage = ExecutionUsage.from_execution_file(str(pr24_summary_file))

        # Act
        calculated = usage.calculated_cost
        file_cost = usage.cost

        # Assert - file cost is inflated
        assert file_cost == pytest.approx(0.091275, rel=0.01)
        # Our calculated cost:
        # claude-haiku-4-5: (3*1.00 + 208*5.00 + 12247*1.25 + 0*0.10) / 1M = 0.01635175
        # claude-3-haiku: (6*0.25 + 303*1.25 + 15204*0.3125 + 44484*0.025) / 1M = 0.006244850
        # Total: 0.022596600
        assert calculated == pytest.approx(0.022597, rel=0.01)
        # Overcharge factor should be ~4x
        assert file_cost / calculated == pytest.approx(4.0, rel=0.2)

    def test_combined_cost_breakdown(self, pr24_main_file, pr24_summary_file):
        """Should calculate correct total cost from both execution files"""
        # Arrange
        breakdown = CostBreakdown.from_execution_files(
            str(pr24_main_file),
            str(pr24_summary_file)
        )

        # Act & Assert
        # Main: $0.033959, Summary: $0.022597, Total: $0.056556
        assert breakdown.main_cost == pytest.approx(0.033959, rel=0.01)
        assert breakdown.summary_cost == pytest.approx(0.022597, rel=0.01)
        assert breakdown.total_cost == pytest.approx(0.056556, rel=0.01)

        # Token totals
        assert breakdown.input_tokens == 4271 + 15 + 3 + 6  # 4295
        assert breakdown.output_tokens == 389 + 426 + 208 + 303  # 1326
        assert breakdown.cache_read_tokens == 0 + 90755 + 0 + 44484  # 135239
        assert breakdown.cache_write_tokens == 12299 + 30605 + 12247 + 15204  # 70355

    def test_github_format_with_real_data(self, pr24_main_file, pr24_summary_file):
        """Should format real workflow data correctly for GitHub comment"""
        # Arrange
        breakdown = CostBreakdown.from_execution_files(
            str(pr24_main_file),
            str(pr24_summary_file)
        )

        # Act
        result = breakdown.format_for_github("gestrich/swift-lambda-sample", "20658904611")

        # Assert - should show our calculated costs, not inflated file costs
        assert "## 💰 Cost Breakdown" in result
        assert "$0.03" in result  # Main cost ~$0.033959
        assert "$0.02" in result  # Summary cost ~$0.022597
        assert "$0.05" in result  # Total ~$0.056556
        # Should NOT show inflated costs
        assert "$0.17" not in result
        assert "$0.09" not in result
        assert "$0.26" not in result
        # Per-model breakdown section
        assert "### Per-Model Breakdown" in result
        assert "claude-haiku-4-5-20251001" in result
        assert "claude-3-haiku-20240307" in result
        assert "4,295" in result  # Input tokens (total)
        assert "1,326" in result  # Output tokens (total)
        assert "135,239" in result  # Cache read tokens (total)
        assert "70,355" in result  # Cache write tokens (total)


class TestPerModelBreakdown:
    """Test suite for per-model breakdown functionality"""

    def test_all_models_combines_main_and_summary(self):
        """Should combine models from main and summary executions"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.05,
            main_models=[ModelUsage(model="model-a", input_tokens=100)],
            summary_models=[ModelUsage(model="model-b", input_tokens=200)],
        )

        # Act
        all_models = breakdown.all_models

        # Assert
        assert len(all_models) == 2
        assert all_models[0].model == "model-a"
        assert all_models[1].model == "model-b"

    def test_get_aggregated_models_combines_same_model(self):
        """Should aggregate tokens for same model across executions"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.05,
            main_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=100, output_tokens=50)
            ],
            summary_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=200, output_tokens=100)
            ],
        )

        # Act
        aggregated = breakdown.get_aggregated_models()

        # Assert
        assert len(aggregated) == 1
        assert aggregated[0].model == "claude-3-haiku-20240307"
        assert aggregated[0].input_tokens == 300
        assert aggregated[0].output_tokens == 150

    def test_get_aggregated_models_keeps_different_models_separate(self):
        """Should keep different models separate in aggregation"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.05,
            main_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=100),
                ModelUsage(model="claude-sonnet-4-20250514", input_tokens=200),
            ],
            summary_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=50),
            ],
        )

        # Act
        aggregated = breakdown.get_aggregated_models()

        # Assert
        assert len(aggregated) == 2
        haiku = next(m for m in aggregated if "haiku" in m.model)
        sonnet = next(m for m in aggregated if "sonnet" in m.model)
        assert haiku.input_tokens == 150  # 100 + 50
        assert sonnet.input_tokens == 200

    def test_format_model_breakdown_empty_when_no_models(self):
        """Should return empty string when no models"""
        # Arrange
        breakdown = CostBreakdown(main_cost=0.1, summary_cost=0.05)

        # Act
        result = breakdown.format_model_breakdown()

        # Assert
        assert result == ""

    def test_format_model_breakdown_includes_all_columns(self):
        """Should include all token types and cost in table"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.0,
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=200,
            cache_write_tokens=30,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=100,
                    output_tokens=50,
                    cache_read_tokens=200,
                    cache_write_tokens=30,
                )
            ],
        )

        # Act
        result = breakdown.format_model_breakdown()

        # Assert
        assert "### Per-Model Breakdown" in result
        assert "| Model | Input | Output | Cache R | Cache W | Cost |" in result
        assert "claude-3-haiku-20240307" in result
        assert "100" in result
        assert "50" in result
        assert "200" in result
        assert "30" in result
        assert "$" in result  # Cost is formatted with $

    def test_to_model_breakdown_json_returns_list_of_dicts(self):
        """Should return list of dicts with model data"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.0,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=1000,
                    output_tokens=500,
                    cache_read_tokens=2000,
                    cache_write_tokens=300,
                )
            ],
        )

        # Act
        result = breakdown.to_model_breakdown_json()

        # Assert
        assert len(result) == 1
        assert result[0]["model"] == "claude-3-haiku-20240307"
        assert result[0]["input_tokens"] == 1000
        assert result[0]["output_tokens"] == 500
        assert result[0]["cache_read_tokens"] == 2000
        assert result[0]["cache_write_tokens"] == 300
        assert "cost" in result[0]
        assert isinstance(result[0]["cost"], float)

    def test_to_model_breakdown_json_aggregates_models(self):
        """Should aggregate same model in JSON output"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.05,
            main_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=100)
            ],
            summary_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=200)
            ],
        )

        # Act
        result = breakdown.to_model_breakdown_json()

        # Assert
        assert len(result) == 1
        assert result[0]["input_tokens"] == 300

    def test_to_model_breakdown_json_empty_when_no_models(self):
        """Should return empty list when no models"""
        # Arrange
        breakdown = CostBreakdown(main_cost=0.1, summary_cost=0.05)

        # Act
        result = breakdown.to_model_breakdown_json()

        # Assert
        assert result == []

    def test_from_execution_files_preserves_models(self):
        """Should preserve per-model data from execution files"""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            main_file = Path(tmpdir) / "main.json"
            summary_file = Path(tmpdir) / "summary.json"

            main_file.write_text(json.dumps({
                "total_cost_usd": 1.5,
                "modelUsage": {
                    "claude-3-haiku-20240307": {
                        "inputTokens": 1000,
                        "outputTokens": 500,
                    },
                },
            }))
            summary_file.write_text(json.dumps({
                "total_cost_usd": 0.5,
                "modelUsage": {
                    "claude-sonnet-4-20250514": {
                        "inputTokens": 200,
                        "outputTokens": 100,
                    },
                },
            }))

            # Act
            breakdown = CostBreakdown.from_execution_files(
                str(main_file),
                str(summary_file)
            )

            # Assert
            assert len(breakdown.main_models) == 1
            assert len(breakdown.summary_models) == 1
            assert breakdown.main_models[0].model == "claude-3-haiku-20240307"
            assert breakdown.summary_models[0].model == "claude-sonnet-4-20250514"


class TestCostBreakdownSerialization:
    """Test suite for CostBreakdown.to_json() and from_json() methods"""

    def test_to_json_returns_valid_json(self):
        """Should return valid JSON string"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=1.234567,
            summary_cost=0.654321,
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=2000,
            cache_write_tokens=300,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=1000,
                    output_tokens=500,
                    cache_read_tokens=2000,
                    cache_write_tokens=300,
                )
            ],
        )

        # Act
        result = breakdown.to_json()

        # Assert
        parsed = json.loads(result)  # Should not raise
        assert parsed["main_cost"] == 1.234567
        assert parsed["summary_cost"] == 0.654321
        assert parsed["input_tokens"] == 1000
        assert parsed["output_tokens"] == 500
        assert parsed["cache_read_tokens"] == 2000
        assert parsed["cache_write_tokens"] == 300
        assert len(parsed["models"]) == 1
        assert parsed["models"][0]["model"] == "claude-3-haiku-20240307"

    def test_from_json_restores_cost_breakdown(self):
        """Should restore CostBreakdown from JSON"""
        # Arrange
        json_str = json.dumps({
            "main_cost": 1.5,
            "summary_cost": 0.5,
            "input_tokens": 1000,
            "output_tokens": 500,
            "cache_read_tokens": 2000,
            "cache_write_tokens": 300,
            "models": [
                {
                    "model": "claude-3-haiku-20240307",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_read_tokens": 2000,
                    "cache_write_tokens": 300,
                }
            ]
        })

        # Act
        result = CostBreakdown.from_json(json_str)

        # Assert
        assert result.main_cost == 1.5
        assert result.summary_cost == 0.5
        assert result.total_cost == 2.0
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.cache_read_tokens == 2000
        assert result.cache_write_tokens == 300
        assert len(result.main_models) == 1
        assert result.main_models[0].model == "claude-3-haiku-20240307"

    def test_roundtrip_preserves_data(self):
        """Should preserve all data through to_json/from_json roundtrip"""
        # Arrange
        original = CostBreakdown(
            main_cost=1.234567,
            summary_cost=0.654321,
            input_tokens=1000,
            output_tokens=500,
            cache_read_tokens=2000,
            cache_write_tokens=300,
            main_models=[
                ModelUsage(
                    model="claude-3-haiku-20240307",
                    input_tokens=600,
                    output_tokens=300,
                    cache_read_tokens=1200,
                    cache_write_tokens=180,
                ),
                ModelUsage(
                    model="claude-sonnet-4-20250514",
                    input_tokens=400,
                    output_tokens=200,
                    cache_read_tokens=800,
                    cache_write_tokens=120,
                ),
            ],
            summary_models=[],  # Will be empty after roundtrip (models aggregated)
        )

        # Act
        json_str = original.to_json()
        restored = CostBreakdown.from_json(json_str)

        # Assert
        assert restored.main_cost == original.main_cost
        assert restored.summary_cost == original.summary_cost
        assert restored.total_cost == original.total_cost
        assert restored.input_tokens == original.input_tokens
        assert restored.output_tokens == original.output_tokens
        assert restored.cache_read_tokens == original.cache_read_tokens
        assert restored.cache_write_tokens == original.cache_write_tokens
        # Models are aggregated on to_json, so count may differ
        assert len(restored.get_aggregated_models()) == len(original.get_aggregated_models())

    def test_from_json_handles_empty_models(self):
        """Should handle empty models list"""
        # Arrange
        json_str = json.dumps({
            "main_cost": 1.0,
            "summary_cost": 0.5,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "models": []
        })

        # Act
        result = CostBreakdown.from_json(json_str)

        # Assert
        assert result.main_cost == 1.0
        assert result.summary_cost == 0.5
        assert result.get_aggregated_models() == []

    def test_from_json_raises_on_invalid_json(self):
        """Should raise JSONDecodeError for invalid JSON"""
        # Act & Assert
        with pytest.raises(json.JSONDecodeError):
            CostBreakdown.from_json("not valid json {]}")

    def test_from_json_raises_on_missing_required_fields(self):
        """Should raise KeyError when required fields are missing"""
        # Act & Assert
        with pytest.raises(KeyError):
            CostBreakdown.from_json('{"main_cost": 1.0}')  # Missing summary_cost and others

    def test_to_json_aggregates_models(self):
        """Should aggregate same model from main and summary in JSON output"""
        # Arrange
        breakdown = CostBreakdown(
            main_cost=0.1,
            summary_cost=0.05,
            input_tokens=300,
            output_tokens=150,
            cache_read_tokens=0,
            cache_write_tokens=0,
            main_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=100, output_tokens=50)
            ],
            summary_models=[
                ModelUsage(model="claude-3-haiku-20240307", input_tokens=200, output_tokens=100)
            ],
        )

        # Act
        json_str = breakdown.to_json()
        parsed = json.loads(json_str)

        # Assert - should have single aggregated model
        assert len(parsed["models"]) == 1
        assert parsed["models"][0]["input_tokens"] == 300
        assert parsed["models"][0]["output_tokens"] == 150
