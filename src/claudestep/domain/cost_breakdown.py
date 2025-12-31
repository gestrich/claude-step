"""Domain model for Claude Code execution cost breakdown."""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class CostBreakdown:
    """Domain model for Claude Code execution cost breakdown."""

    main_cost: float
    summary_cost: float

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
        """Parse cost information from execution files.

        This encapsulates all the file reading and JSON parsing logic
        that currently lives in prepare_summary.py.

        Args:
            main_execution_file: Path to main execution file
            summary_execution_file: Path to summary execution file

        Returns:
            CostBreakdown with costs extracted from files
        """
        main_cost = cls._extract_from_file(main_execution_file)
        summary_cost = cls._extract_from_file(summary_execution_file)
        return cls(main_cost=main_cost, summary_cost=summary_cost)

    @staticmethod
    def _extract_from_file(execution_file: str) -> float:
        """Extract cost from a single execution file.

        Args:
            execution_file: Path to execution file

        Returns:
            Cost in USD as float, or 0.0 if not found/error
        """
        if not execution_file or not execution_file.strip():
            return 0.0

        if not os.path.exists(execution_file):
            return 0.0

        try:
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
                    # Use the last item with cost
                    data = items_with_cost[-1]
                elif data:
                    # Fallback to last item
                    data = data[-1]
                else:
                    return 0.0

            # Extract cost from the data
            cost = CostBreakdown._extract_cost_from_dict(data)
            if cost is None:
                return 0.0

            return cost

        except json.JSONDecodeError:
            return 0.0
        except Exception:
            return 0.0

    @staticmethod
    def _extract_cost_from_dict(data: dict) -> Optional[float]:
        """Extract total_cost_usd from Claude Code execution data.

        Args:
            data: Parsed JSON data from the execution file

        Returns:
            Cost in USD as float, or None if not found
        """
        # Try to get total_cost_usd from the top level
        if 'total_cost_usd' in data:
            try:
                return float(data['total_cost_usd'])
            except (ValueError, TypeError):
                pass

        # Try to get it from a nested structure if needed
        if 'usage' in data and 'total_cost_usd' in data['usage']:
            try:
                return float(data['usage']['total_cost_usd'])
            except (ValueError, TypeError):
                pass

        return None

    def format_for_github(self, repo: str, run_id: str) -> str:
        """Format cost breakdown as markdown table for GitHub PR comment.

        Args:
            repo: Repository name (owner/repo)
            run_id: Workflow run ID

        Returns:
            Formatted markdown string
        """
        workflow_url = f"https://github.com/{repo}/actions/runs/{run_id}"

        cost_section = f"""## 💰 Cost Breakdown

This PR was generated using Claude Code with the following costs:

| Component | Cost (USD) |
|-----------|------------|
| Main refactoring task | ${self.main_cost:.6f} |
| PR summary generation | ${self.summary_cost:.6f} |
| **Total** | **${self.total_cost:.6f}** |

---
*Cost tracking by ClaudeStep • [View workflow run]({workflow_url})*
"""
        return cost_section
