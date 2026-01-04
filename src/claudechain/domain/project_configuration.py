"""Domain models for project configuration"""

from dataclasses import dataclass
from typing import Optional

from claudechain.domain.constants import DEFAULT_STALE_PR_DAYS
from claudechain.domain.project import Project


@dataclass
class ProjectConfiguration:
    """Domain model for parsed project configuration

    ClaudeChain enforces a single open PR per project. The optional assignee
    is assigned to PRs when created.
    """

    project: Project
    assignee: Optional[str] = None  # Optional GitHub username to assign PRs to
    base_branch: Optional[str] = None  # Optional override for target base branch
    allowed_tools: Optional[str] = None  # Optional override for Claude's allowed tools
    stale_pr_days: Optional[int] = None  # Days before a PR is considered stale

    @classmethod
    def default(cls, project: Project) -> 'ProjectConfiguration':
        """Factory: Create default configuration when no config file exists.

        Default configuration:
        - No assignee (PRs created without assignee)
        - No base branch override (uses workflow default)
        - No allowed tools override (uses workflow default)

        Args:
            project: Project domain model

        Returns:
            ProjectConfiguration with sensible defaults
        """
        return cls(
            project=project,
            assignee=None,
            base_branch=None,
            allowed_tools=None,
            stale_pr_days=None
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
        from claudechain.domain.config import load_config_from_string

        config = load_config_from_string(yaml_content, project.config_path)
        assignee = config.get("assignee")
        base_branch = config.get("baseBranch")
        allowed_tools = config.get("allowedTools")
        stale_pr_days = config.get("stalePRDays")

        return cls(
            project=project,
            assignee=assignee,
            base_branch=base_branch,
            allowed_tools=allowed_tools,
            stale_pr_days=stale_pr_days
        )

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

    def get_allowed_tools(self, default_allowed_tools: str) -> str:
        """Resolve allowed tools from project config or fall back to default.

        Args:
            default_allowed_tools: Default from workflow/CLI (required, no default here)

        Returns:
            Project's allowedTools if set, otherwise the default
        """
        if self.allowed_tools:
            return self.allowed_tools
        return default_allowed_tools

    def get_stale_pr_days(self, default: int = DEFAULT_STALE_PR_DAYS) -> int:
        """Get the number of days before a PR is considered stale.

        Args:
            default: Default value if not configured (default: DEFAULT_STALE_PR_DAYS)

        Returns:
            stalePRDays from config if set, otherwise the default
        """
        if self.stale_pr_days is not None:
            return self.stale_pr_days
        return default

    def to_dict(self) -> dict:
        """Convert to dictionary representation

        Returns:
            Dictionary with project and configuration
        """
        result = {
            "project": self.project.name,
        }
        if self.assignee:
            result["assignee"] = self.assignee
        if self.base_branch:
            result["baseBranch"] = self.base_branch
        if self.allowed_tools:
            result["allowedTools"] = self.allowed_tools
        if self.stale_pr_days is not None:
            result["stalePRDays"] = self.stale_pr_days
        return result
