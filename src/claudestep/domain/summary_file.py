"""Domain model for PR summary file content."""

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from claudestep.domain.cost_breakdown import CostBreakdown


@dataclass
class SummaryFile:
    """Domain model for PR summary file content."""

    content: str | None

    @classmethod
    def from_file(cls, file_path: str) -> 'SummaryFile':
        """Read and parse summary file.

        Args:
            file_path: Path to summary file

        Returns:
            SummaryFile with content, or None content if file missing/empty
        """
        if not file_path or not os.path.exists(file_path):
            return cls(content=None)

        try:
            with open(file_path, 'r') as f:
                content = f.read().strip()
                if not content:
                    return cls(content=None)
                return cls(content=content)
        except Exception:
            return cls(content=None)

    @property
    def has_content(self) -> bool:
        """Check if summary has content."""
        return self.content is not None and bool(self.content.strip())

    def format_with_cost(
        self,
        cost_breakdown: 'CostBreakdown',
        repo: str,
        run_id: str
    ) -> str:
        """Combine summary and cost into unified PR comment.

        Args:
            cost_breakdown: Cost breakdown information
            repo: Repository name (owner/repo)
            run_id: Workflow run ID

        Returns:
            Formatted markdown comment
        """
        # Start with summary if available
        parts = []
        if self.has_content:
            parts.append(self.content)
            parts.append("\n---\n")

        # Add cost breakdown
        cost_section = cost_breakdown.format_for_github(repo, run_id)
        parts.append(cost_section)

        return "".join(parts)
