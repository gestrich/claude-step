"""Domain model for Claude Code execution cost breakdown."""

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Self


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaudeModel:
    """Pricing information for a Claude model.

    All rates are in USD per million tokens (MTok).
    Based on official Anthropic pricing: https://docs.anthropic.com/en/docs/about-claude/pricing
    """

    pattern: str  # Pattern to match in model name (e.g., "claude-3-haiku")
    input_rate: float  # $ per MTok for input tokens
    output_rate: float  # $ per MTok for output tokens
    cache_write_rate: float  # $ per MTok for cache write tokens
    cache_read_rate: float  # $ per MTok for cache read tokens

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_write_tokens: int,
        cache_read_tokens: int,
    ) -> float:
        """Calculate cost for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_write_tokens: Number of cache write tokens
            cache_read_tokens: Number of cache read tokens

        Returns:
            Total cost in USD
        """
        return (
            input_tokens * self.input_rate
            + output_tokens * self.output_rate
            + cache_write_tokens * self.cache_write_rate
            + cache_read_tokens * self.cache_read_rate
        ) / 1_000_000


# Claude model pricing registry
# Source: https://docs.anthropic.com/en/docs/about-claude/pricing
CLAUDE_MODELS: list[ClaudeModel] = [
    # Haiku 3 - unique cache multipliers (1.2x write, 0.12x read)
    ClaudeModel(
        pattern="claude-3-haiku",
        input_rate=0.25,
        output_rate=1.25,
        cache_write_rate=0.30,
        cache_read_rate=0.03,
    ),
    # Haiku 4/4.5 - standard multipliers (1.25x write, 0.1x read)
    ClaudeModel(
        pattern="claude-haiku-4",
        input_rate=1.00,
        output_rate=5.00,
        cache_write_rate=1.25,
        cache_read_rate=0.10,
    ),
    # Sonnet 3.5 - standard multipliers
    ClaudeModel(
        pattern="claude-3-5-sonnet",
        input_rate=3.00,
        output_rate=15.00,
        cache_write_rate=3.75,
        cache_read_rate=0.30,
    ),
    # Sonnet 4/4.5 - standard multipliers
    ClaudeModel(
        pattern="claude-sonnet-4",
        input_rate=3.00,
        output_rate=15.00,
        cache_write_rate=3.75,
        cache_read_rate=0.30,
    ),
    # Opus 4/4.5 - standard multipliers
    ClaudeModel(
        pattern="claude-opus-4",
        input_rate=15.00,
        output_rate=75.00,
        cache_write_rate=18.75,
        cache_read_rate=1.50,
    ),
]


class UnknownModelError(ValueError):
    """Raised when a model name is not recognized for pricing."""

    pass


def get_model(model_name: str) -> ClaudeModel:
    """Get the ClaudeModel for a model name.

    Args:
        model_name: Model name from execution file (e.g., "claude-3-haiku-20240307")

    Returns:
        ClaudeModel with pricing information

    Raises:
        UnknownModelError: If model name doesn't match any known patterns
    """
    model_lower = model_name.lower()

    for claude_model in CLAUDE_MODELS:
        if claude_model.pattern in model_lower:
            return claude_model

    raise UnknownModelError(
        f"Unknown model '{model_name}'. Add pricing to CLAUDE_MODELS in cost_breakdown.py"
    )


def get_rate_for_model(model_name: str) -> float:
    """Get the input token rate (per MTok) for a model.

    Args:
        model_name: Model name from execution file (e.g., "claude-3-haiku-20240307")

    Returns:
        Rate per million input tokens

    Raises:
        UnknownModelError: If model name doesn't match any known patterns
    """
    return get_model(model_name).input_rate


@dataclass
class ModelUsage:
    """Usage data for a single model within a Claude Code execution."""

    model: str
    cost: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens for this model."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )

    def calculate_cost(self) -> float:
        """Calculate cost using correct per-model pricing.

        Returns:
            Calculated cost in USD
        """
        claude_model = get_model(self.model)
        return claude_model.calculate_cost(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            cache_write_tokens=self.cache_write_tokens,
            cache_read_tokens=self.cache_read_tokens,
        )

    @classmethod
    def from_dict(cls, model: str, data: dict) -> Self:
        """Parse model usage from execution file modelUsage entry.

        Args:
            model: Model name/identifier
            data: Dict with inputTokens, outputTokens, etc.

        Returns:
            ModelUsage instance

        Raises:
            TypeError: If data is not a dict
        """
        if not isinstance(data, dict):
            raise TypeError(f"Model usage data must be a dict, got {type(data).__name__}")

        return cls(
            model=model,
            cost=float(data.get('costUSD', 0) or 0),
            input_tokens=int(data.get('inputTokens', 0) or 0),
            output_tokens=int(data.get('outputTokens', 0) or 0),
            cache_read_tokens=int(data.get('cacheReadInputTokens', 0) or 0),
            cache_write_tokens=int(data.get('cacheCreationInputTokens', 0) or 0),
        )


@dataclass
class ExecutionUsage:
    """Usage data from a single Claude Code execution."""

    models: list[ModelUsage] = field(default_factory=list)
    # Top-level cost from execution file (may differ from sum of model costs)
    total_cost_usd: float = 0.0

    @property
    def cost(self) -> float:
        """Total cost (uses top-level total_cost_usd from file)."""
        return self.total_cost_usd

    @property
    def calculated_cost(self) -> float:
        """Calculate total cost using correct per-model pricing.

        Sums calculate_cost() across all models, using hardcoded rates.
        """
        return sum(m.calculate_cost() for m in self.models)

    @property
    def input_tokens(self) -> int:
        """Sum of input tokens across all models."""
        return sum(m.input_tokens for m in self.models)

    @property
    def output_tokens(self) -> int:
        """Sum of output tokens across all models."""
        return sum(m.output_tokens for m in self.models)

    @property
    def cache_read_tokens(self) -> int:
        """Sum of cache read tokens across all models."""
        return sum(m.cache_read_tokens for m in self.models)

    @property
    def cache_write_tokens(self) -> int:
        """Sum of cache write tokens across all models."""
        return sum(m.cache_write_tokens for m in self.models)

    @property
    def total_tokens(self) -> int:
        """Sum of all tokens across all models."""
        return sum(m.total_tokens for m in self.models)

    def __add__(self, other: Self) -> Self:
        """Combine two ExecutionUsage instances."""
        return ExecutionUsage(
            models=self.models + other.models,
            total_cost_usd=self.total_cost_usd + other.total_cost_usd,
        )

    @classmethod
    def from_execution_file(cls, execution_file: str) -> Self:
        """Extract usage data from a Claude Code execution file.

        Args:
            execution_file: Path to execution file

        Returns:
            ExecutionUsage with cost and per-model usage

        Raises:
            ValueError: If execution_file is empty/whitespace
            FileNotFoundError: If file does not exist
            json.JSONDecodeError: If file contains invalid JSON
        """
        if not execution_file or not execution_file.strip():
            raise ValueError("execution_file cannot be empty")

        if not os.path.exists(execution_file):
            raise FileNotFoundError(f"Execution file not found: {execution_file}")

        with open(execution_file, 'r') as f:
            data = json.load(f)

        # Handle list format (may have multiple executions)
        if isinstance(data, list):
            # Filter to only items that have cost information
            items_with_cost = [
                item for item in data
                if isinstance(item, dict) and 'total_cost_usd' in item
            ]

            if items_with_cost:
                data = items_with_cost[-1]
            elif data:
                data = data[-1]
            else:
                raise ValueError(f"Execution file contains empty list: {execution_file}")

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> Self:
        """Extract usage data from parsed JSON dict.

        Args:
            data: Parsed JSON data from the execution file

        Returns:
            ExecutionUsage with cost and per-model usage

        Raises:
            TypeError: If data is not a dict or modelUsage is not a dict
            ValueError: If total_cost_usd cannot be parsed as float
        """
        if not isinstance(data, dict):
            raise TypeError(f"Execution data must be a dict, got {type(data).__name__}")

        # Extract top-level cost
        total_cost = 0.0
        if 'total_cost_usd' in data:
            try:
                total_cost = float(data['total_cost_usd'])
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid total_cost_usd value: {data['total_cost_usd']}") from e
        elif 'usage' in data and isinstance(data['usage'], dict) and 'total_cost_usd' in data['usage']:
            try:
                total_cost = float(data['usage']['total_cost_usd'])
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid usage.total_cost_usd value: {data['usage']['total_cost_usd']}") from e

        # Extract per-model usage
        models = []
        model_usage = data.get('modelUsage', {})
        if model_usage:
            if not isinstance(model_usage, dict):
                raise TypeError(f"modelUsage must be a dict, got {type(model_usage).__name__}")
            for model_name, model_data in model_usage.items():
                models.append(ModelUsage.from_dict(model_name, model_data))

        return cls(models=models, total_cost_usd=total_cost)


@dataclass
class CostBreakdown:
    """Domain model for Claude Code execution cost breakdown."""

    main_cost: float
    summary_cost: float
    # Token counts (summed across all models in modelUsage)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # Per-model breakdowns for detailed display
    main_models: list[ModelUsage] = field(default_factory=list)
    summary_models: list[ModelUsage] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        return self.main_cost + self.summary_cost

    @classmethod
    def from_execution_files(
        cls,
        main_execution_file: str,
        summary_execution_file: str
    ) -> 'CostBreakdown':
        """Parse cost and token information from execution files.

        Args:
            main_execution_file: Path to main execution file
            summary_execution_file: Path to summary execution file

        Returns:
            CostBreakdown with costs and tokens extracted from files
        """
        main_usage = ExecutionUsage.from_execution_file(main_execution_file)
        summary_usage = ExecutionUsage.from_execution_file(summary_execution_file)
        total_usage = main_usage + summary_usage

        return cls(
            main_cost=main_usage.calculated_cost,
            summary_cost=summary_usage.calculated_cost,
            input_tokens=total_usage.input_tokens,
            output_tokens=total_usage.output_tokens,
            cache_read_tokens=total_usage.cache_read_tokens,
            cache_write_tokens=total_usage.cache_write_tokens,
            main_models=main_usage.models,
            summary_models=summary_usage.models,
        )

    @property
    def total_tokens(self) -> int:
        """Calculate total token count (all token types)."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )

    @property
    def all_models(self) -> list[ModelUsage]:
        """Get all models from both main and summary executions."""
        return self.main_models + self.summary_models

    def get_aggregated_models(self) -> list[ModelUsage]:
        """Aggregate model usage across main and summary executions.

        Models with the same name are combined into a single entry.

        Returns:
            List of ModelUsage with unique model names, tokens/costs summed.
        """
        aggregated: dict[str, ModelUsage] = {}

        for model in self.all_models:
            if model.model in aggregated:
                existing = aggregated[model.model]
                aggregated[model.model] = ModelUsage(
                    model=model.model,
                    cost=existing.cost + model.cost,
                    input_tokens=existing.input_tokens + model.input_tokens,
                    output_tokens=existing.output_tokens + model.output_tokens,
                    cache_read_tokens=existing.cache_read_tokens + model.cache_read_tokens,
                    cache_write_tokens=existing.cache_write_tokens + model.cache_write_tokens,
                )
            else:
                aggregated[model.model] = ModelUsage(
                    model=model.model,
                    cost=model.cost,
                    input_tokens=model.input_tokens,
                    output_tokens=model.output_tokens,
                    cache_read_tokens=model.cache_read_tokens,
                    cache_write_tokens=model.cache_write_tokens,
                )

        return list(aggregated.values())

    def to_model_breakdown_json(self) -> list[dict]:
        """Convert per-model breakdown to JSON-serializable format.

        Returns:
            List of dicts with model breakdown data for downstream steps.
        """
        models = self.get_aggregated_models()
        return [
            {
                "model": m.model,
                "input_tokens": m.input_tokens,
                "output_tokens": m.output_tokens,
                "cache_read_tokens": m.cache_read_tokens,
                "cache_write_tokens": m.cache_write_tokens,
                "cost": m.calculate_cost(),
            }
            for m in models
        ]

    def to_json(self) -> str:
        """Serialize to JSON for passing between workflow steps.

        Returns:
            JSON string containing all cost breakdown data.
        """
        return json.dumps({
            "main_cost": self.main_cost,
            "summary_cost": self.summary_cost,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "models": [
                {
                    "model": m.model,
                    "input_tokens": m.input_tokens,
                    "output_tokens": m.output_tokens,
                    "cache_read_tokens": m.cache_read_tokens,
                    "cache_write_tokens": m.cache_write_tokens,
                }
                for m in self.get_aggregated_models()
            ]
        })

    @classmethod
    def from_json(cls, json_str: str) -> 'CostBreakdown':
        """Deserialize from JSON.

        Args:
            json_str: JSON string from to_json()

        Returns:
            CostBreakdown instance with all data restored.

        Raises:
            json.JSONDecodeError: If JSON is invalid
            KeyError: If required fields are missing
        """
        data = json.loads(json_str)

        # Parse model usage data
        models = [
            ModelUsage(
                model=m["model"],
                input_tokens=m["input_tokens"],
                output_tokens=m["output_tokens"],
                cache_read_tokens=m["cache_read_tokens"],
                cache_write_tokens=m["cache_write_tokens"],
            )
            for m in data.get("models", [])
        ]

        return cls(
            main_cost=data["main_cost"],
            summary_cost=data["summary_cost"],
            input_tokens=data["input_tokens"],
            output_tokens=data["output_tokens"],
            cache_read_tokens=data["cache_read_tokens"],
            cache_write_tokens=data["cache_write_tokens"],
            # Store aggregated models in main_models (they're already aggregated)
            main_models=models,
            summary_models=[],
        )
