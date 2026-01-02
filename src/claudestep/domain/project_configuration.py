"""Domain models for project configuration"""

from dataclasses import dataclass
from typing import List, Optional

from claudestep.domain.project import Project


@dataclass
class Reviewer:
    """Domain model for a reviewer in project configuration"""

    username: str
    max_open_prs: int = 2  # Default from existing code

    @classmethod
    def from_dict(cls, data: dict) -> 'Reviewer':
        """Parse reviewer from configuration dictionary

        Args:
            data: Dictionary with 'username' and optional 'maxOpenPRs'

        Returns:
            Reviewer instance
        """
        return cls(
            username=data.get("username"),
            max_open_prs=data.get("maxOpenPRs", 2)
        )

    def to_dict(self) -> dict:
        """Convert to dictionary representation

        Returns:
            Dictionary with username and maxOpenPRs
        """
        return {
            "username": self.username,
            "maxOpenPRs": self.max_open_prs
        }


# Default global PR limit when no reviewers are configured
DEFAULT_PROJECT_PR_LIMIT = 1


@dataclass
class ProjectConfiguration:
    """Domain model for parsed project configuration"""

    project: Project
    reviewers: List[Reviewer]
    base_branch: Optional[str] = None  # Optional override for target base branch

    @classmethod
    def default(cls, project: Project) -> 'ProjectConfiguration':
        """Factory: Create default configuration when no config file exists.

        Default configuration:
        - No reviewers (PRs created without assignee)
        - No base branch override (uses workflow default)

        Args:
            project: Project domain model

        Returns:
            ProjectConfiguration with sensible defaults
        """
        return cls(
            project=project,
            reviewers=[],
            base_branch=None
        )

    @classmethod
    def from_yaml_string(cls, project: Project, yaml_content: str) -> 'ProjectConfiguration':
        """Factory: Parse configuration from YAML string

        Args:
            project: Project domain model
            yaml_content: YAML content as string

        Returns:
            ProjectConfiguration instance
        """
        from claudestep.domain.config import load_config_from_string

        config = load_config_from_string(yaml_content, project.config_path)
        reviewers_config = config.get("reviewers", [])
        reviewers = [Reviewer.from_dict(r) for r in reviewers_config if "username" in r]
        base_branch = config.get("baseBranch")

        return cls(
            project=project,
            reviewers=reviewers,
            base_branch=base_branch
        )

    def get_reviewer_usernames(self) -> List[str]:
        """Get list of reviewer usernames

        Returns:
            List of usernames as strings
        """
        return [r.username for r in self.reviewers]

    def get_reviewer(self, username: str) -> Optional[Reviewer]:
        """Find reviewer by username

        Args:
            username: Username to find

        Returns:
            Reviewer instance or None if not found
        """
        return next((r for r in self.reviewers if r.username == username), None)

    def get_base_branch(self, default_base_branch: str) -> str:
        """Resolve base branch from project config or fall back to default.

        Args:
            default_base_branch: Default from workflow/CLI (required, no default here)

        Returns:
            Project's baseBranch if set, otherwise the default
        """
        if self.base_branch:
            return self.base_branch
        return default_base_branch

    def to_dict(self) -> dict:
        """Convert to dictionary representation

        Returns:
            Dictionary with project and reviewer configuration
        """
        result = {
            "project": self.project.name,
            "reviewers": [r.to_dict() for r in self.reviewers]
        }
        if self.base_branch:
            result["baseBranch"] = self.base_branch
        return result
