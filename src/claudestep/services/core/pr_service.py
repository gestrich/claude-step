"""Core service for PR operations and branch naming utilities.

Follows Service Layer pattern (Fowler, PoEAA) - provides a unified interface
for branch naming and PR fetching, eliminating duplication across the codebase.
Encapsulates business logic for PR-related operations.
"""

import re
from typing import List, Literal, Optional, Set, Tuple, Union

from claudestep.domain.constants import DEFAULT_STATS_DAYS_BACK
from claudestep.domain.exceptions import GitHubAPIError
from claudestep.domain.github_models import GitHubPullRequest
from claudestep.domain.models import BranchInfo
from claudestep.infrastructure.github.operations import (
    list_pull_requests,
    list_open_pull_requests,
)
from claudestep.domain.project import Project

# Re-export for external use and test mocking compatibility
__all__ = ["PRService", "list_pull_requests", "list_open_pull_requests"]


class PRService:
    """Core service for PR operations and branch naming utilities.

    Coordinates PR fetching and branch naming operations by orchestrating
    GitHub API interactions. Implements business logic for ClaudeStep's
    PR management workflows.
    """

    def __init__(self, repo: str):
        """Initialize PR service

        Args:
            repo: GitHub repository (owner/name)
        """
        self.repo = repo

    # Public API methods

    def get_project_prs(
        self, project_name: str, state: str = "all", label: str = "claudestep"
    ) -> List[GitHubPullRequest]:
        """Fetch all PRs for a project by branch prefix.

        This is the primary API for getting PRs associated with a ClaudeStep project.
        It filters PRs by matching the branch name pattern.

        Args:
            project_name: Project name (e.g., "my-refactor")
            state: PR state filter - "open", "closed", "merged", or "all"
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            List of GitHubPullRequest domain models filtered by project

        Raises:
            GitHubAPIError: If the GitHub API call fails

        Examples:
            >>> service = PRService("owner/repo")
            >>> prs = service.get_project_prs("my-refactor", state="open")
            >>> len(prs)
            3
            >>> prs[0].head_ref_name
            'claude-step-my-refactor-1'
        """
        print(
            f"Fetching PRs for project '{project_name}' with state='{state}' and label='{label}'"
        )

        # Fetch PRs with the label using infrastructure layer
        try:
            all_prs = list_pull_requests(
                repo=self.repo,
                state=state,
                label=label,
                limit=100
            )
        except GitHubAPIError as e:
            print(f"Warning: Failed to list PRs: {e}")
            return []

        # Filter to only PRs whose branch names match the project pattern
        project_prefix = f"claude-step-{project_name}-"
        project_prs = [
            pr for pr in all_prs
            if pr.head_ref_name and pr.head_ref_name.startswith(project_prefix)
        ]

        print(
            f"Found {len(project_prs)} PR(s) for project '{project_name}' (out of {len(all_prs)} total)"
        )
        return project_prs

    def get_open_prs_for_project(
        self, project: str, label: str = "claudestep"
    ) -> List[GitHubPullRequest]:
        """Fetch open PRs for a project.

        Convenience wrapper for get_project_prs() with state="open".

        Args:
            project: Project name (e.g., "my-refactor")
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            List of open GitHubPullRequest domain models for the project

        Examples:
            >>> service = PRService("owner/repo")
            >>> open_prs = service.get_open_prs_for_project("my-refactor")
            >>> all(pr.is_open() for pr in open_prs)
            True
        """
        return self.get_project_prs(project, state="open", label=label)

    def get_merged_prs_for_project(
        self, project: str, label: str = "claudestep", days_back: int = DEFAULT_STATS_DAYS_BACK
    ) -> List[GitHubPullRequest]:
        """Fetch merged PRs for a project within a time window.

        Convenience wrapper for get_project_prs() with state="merged",
        filtered to only include PRs merged within the specified days.

        Args:
            project: Project name (e.g., "my-refactor")
            label: GitHub label to filter PRs (default: "claudestep")
            days_back: Only include PRs merged within this many days (default: 30)

        Returns:
            List of merged GitHubPullRequest domain models for the project

        Examples:
            >>> service = PRService("owner/repo")
            >>> merged_prs = service.get_merged_prs_for_project("my-refactor", days_back=7)
            >>> all(pr.is_merged() for pr in merged_prs)
            True
        """
        from datetime import datetime, timedelta, timezone

        all_merged = self.get_project_prs(project, state="merged", label=label)

        # Filter by merge date
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        recent_merged = [
            pr for pr in all_merged
            if pr.merged_at and pr.merged_at >= cutoff
        ]

        return recent_merged

    def get_all_prs(
        self, label: str = "claudestep", state: str = "all", limit: int = 500
    ) -> List[GitHubPullRequest]:
        """Fetch all PRs with the specified label.

        Used for statistics and project discovery across all ClaudeStep PRs.

        Args:
            label: GitHub label to filter PRs (default: "claudestep")
            state: PR state filter - "open", "closed", "merged", or "all"
            limit: Max results (default: 500)

        Returns:
            List of GitHubPullRequest domain models with the label

        Examples:
            >>> service = PRService("owner/repo")
            >>> all_prs = service.get_all_prs()
            >>> len(all_prs)
            150
        """
        return list_pull_requests(
            repo=self.repo,
            state=state,
            label=label,
            limit=limit
        )

    def get_unique_projects(self, label: str = "claudestep") -> Set[str]:
        """Extract unique project names from all PRs with the label.

        Used by statistics service for multi-project discovery.

        Args:
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            Set of unique project names extracted from branch names

        Examples:
            >>> service = PRService("owner/repo")
            >>> projects = service.get_unique_projects()
            >>> projects
            {'my-refactor', 'swift-migration', 'api-cleanup'}
        """
        all_prs = self.get_all_prs(label=label)
        projects = set()

        for pr in all_prs:
            if pr.head_ref_name:
                parsed = self.parse_branch_name(pr.head_ref_name)
                if parsed:
                    projects.add(parsed.project_name)

        return projects

    # Static utility methods

    @staticmethod
    def format_branch_name(project_name: str, task_hash: str) -> str:
        """Format branch name using the standard ClaudeStep format (hash-based).

        This method now uses hash-based identification for stable task tracking.
        The signature has been updated from index-based to hash-based.

        Args:
            project_name: Project name (e.g., "my-refactor")
            task_hash: 8-character task hash from generate_task_hash()

        Returns:
            Formatted branch name (e.g., "claude-step-my-refactor-a3f2b891")

        Examples:
            >>> PRService.format_branch_name("my-refactor", "a3f2b891")
            'claude-step-my-refactor-a3f2b891'
            >>> PRService.format_branch_name("swift-migration", "f7c4d3e2")
            'claude-step-swift-migration-f7c4d3e2'
        """
        return PRService.format_branch_name_with_hash(project_name, task_hash)

    @staticmethod
    def format_branch_name_with_hash(project_name: str, task_hash: str) -> str:
        """Format branch name using hash-based ClaudeStep format.

        This is the new format that provides stable task identification
        regardless of task position in spec.md.

        Args:
            project_name: Project name (e.g., "my-refactor")
            task_hash: 8-character task hash from generate_task_hash()

        Returns:
            Formatted branch name (e.g., "claude-step-my-refactor-a3f2b891")

        Examples:
            >>> PRService.format_branch_name_with_hash("my-refactor", "a3f2b891")
            'claude-step-my-refactor-a3f2b891'
            >>> PRService.format_branch_name_with_hash("auth-refactor", "f7c4d3e2")
            'claude-step-auth-refactor-f7c4d3e2'
        """
        return f"claude-step-{project_name}-{task_hash}"

    @staticmethod
    def parse_branch_name(branch: str) -> Optional[BranchInfo]:
        """Parse branch name for hash-based format.

        Expected format: claude-step-{project_name}-{hash}

        Args:
            branch: Branch name to parse

        Returns:
            BranchInfo instance if branch matches pattern, None otherwise

        Examples:
            >>> info = PRService.parse_branch_name("claude-step-my-refactor-a3f2b891")
            >>> info.project_name
            'my-refactor'
            >>> info.task_hash
            'a3f2b891'
            >>> PRService.parse_branch_name("invalid-branch")
            None
        """
        return BranchInfo.from_branch_name(branch)
