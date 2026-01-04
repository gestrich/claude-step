"""Domain model for PR summary file content."""

import os
from dataclasses import dataclass


@dataclass
class SummaryFile:
    """Domain model for PR summary file content.

    This class handles parsing of AI-generated summary files.
    Formatting is handled by PullRequestCreatedReport.
    """

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
