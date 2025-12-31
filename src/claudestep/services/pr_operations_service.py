"""Service Layer class for PR operations and branch naming utilities.

Follows Service Layer pattern (Fowler, PoEAA) - provides a unified interface
for branch naming and PR fetching, eliminating duplication across the codebase.
Encapsulates business logic for PR-related operations.
"""

import re
from typing import List, Optional, Set, Tuple

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.domain.github_models import GitHubPullRequest
from claudestep.infrastructure.github.operations import (
    list_pull_requests,
    list_open_pull_requests,
)
from claudestep.domain.project import Project


class PROperationsService:
    """Service Layer class for PR operations and branch naming utilities.

    Coordinates PR fetching and branch naming operations by orchestrating
    GitHub API interactions. Implements business logic for ClaudeStep's
    PR management workflows.
    """

    def __init__(self, repo: str):
        """Initialize PR operations service

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
            >>> service = PROperationsService("owner/repo")
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
            >>> service = PROperationsService("owner/repo")
            >>> open_prs = service.get_open_prs_for_project("my-refactor")
            >>> all(pr.is_open() for pr in open_prs)
            True
        """
        return self.get_project_prs(project, state="open", label=label)

    def get_open_prs_for_reviewer(
        self, username: str, label: str = "claudestep"
    ) -> List[GitHubPullRequest]:
        """Fetch open PRs assigned to a specific reviewer.

        Args:
            username: GitHub username of the reviewer
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            List of open GitHubPullRequest domain models assigned to the reviewer

        Examples:
            >>> service = PROperationsService("owner/repo")
            >>> reviewer_prs = service.get_open_prs_for_reviewer("reviewer1")
            >>> len(reviewer_prs)
            5
        """
        return list_open_pull_requests(
            repo=self.repo,
            label=label,
            assignee=username
        )

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
            >>> service = PROperationsService("owner/repo")
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
            >>> service = PROperationsService("owner/repo")
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
                    project_name, _ = parsed
                    projects.add(project_name)

        return projects

    def get_reviewer_prs_for_project(
        self, username: str, project: str, label: str = "claudestep"
    ) -> List[GitHubPullRequest]:
        """Fetch open PRs assigned to a reviewer for a specific project.

        Combines reviewer filtering with project filtering to get PRs
        assigned to a specific reviewer on a specific project. Used by
        ReviewerManagementService for capacity checking.

        Args:
            username: GitHub username of the reviewer
            project: Project name (e.g., "my-refactor")
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            List of GitHubPullRequest domain models assigned to the reviewer
            for the specified project

        Examples:
            >>> service = PROperationsService("owner/repo")
            >>> prs = service.get_reviewer_prs_for_project("reviewer1", "my-refactor")
            >>> len(prs)
            2
            >>> all(pr.project_name == "my-refactor" for pr in prs)
            True
        """
        # Get all open PRs for the reviewer
        reviewer_prs = self.get_open_prs_for_reviewer(username, label=label)

        # Filter to only PRs for the specified project
        # Use domain model property for project name
        project_prs = [
            pr for pr in reviewer_prs
            if pr.project_name == project
        ]

        return project_prs

    def get_reviewer_pr_count(
        self, username: str, project: str, label: str = "claudestep"
    ) -> int:
        """Get count of open PRs assigned to a reviewer for a specific project.

        Convenience method for capacity checking that returns just the count.

        Args:
            username: GitHub username of the reviewer
            project: Project name (e.g., "my-refactor")
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            Number of open PRs assigned to the reviewer for the project

        Examples:
            >>> service = PROperationsService("owner/repo")
            >>> count = service.get_reviewer_pr_count("reviewer1", "my-refactor")
            >>> count
            2
        """
        prs = self.get_reviewer_prs_for_project(username, project, label=label)
        return len(prs)

    # Static utility methods

    @staticmethod
    def format_branch_name(project_name: str, index: int) -> str:
        """Format branch name using the standard ClaudeStep format.

        Args:
            project_name: Project name (e.g., "my-refactor")
            index: Task index (1-based)

        Returns:
            Formatted branch name (e.g., "claude-step-my-refactor-1")

        Examples:
            >>> PROperationsService.format_branch_name("my-refactor", 1)
            'claude-step-my-refactor-1'
            >>> PROperationsService.format_branch_name("swift-migration", 5)
            'claude-step-swift-migration-5'
        """
        project = Project(project_name)
        return project.get_branch_name(index)

    @staticmethod
    def parse_branch_name(branch: str) -> Optional[Tuple[str, int]]:
        """Parse branch name to extract project name and task index.

        Expected format: claude-step-{project_name}-{index}

        Args:
            branch: Branch name to parse

        Returns:
            Tuple of (project_name, index) or None if parsing fails

        Examples:
            >>> PROperationsService.parse_branch_name("claude-step-my-refactor-1")
            ('my-refactor', 1)
            >>> PROperationsService.parse_branch_name("claude-step-swift-migration-5")
            ('swift-migration', 5)
            >>> PROperationsService.parse_branch_name("invalid-branch")
            None
        """
        # Delegate to Project domain model for parsing
        # Pattern: claude-step-{project}-{index}
        # Project name can contain hyphens, so we need to match the last number
        pattern = r"^claude-step-(.+)-(\d+)$"
        match = re.match(pattern, branch)

        if match:
            project_name = match.group(1)
            try:
                index = int(match.group(2))
                return (project_name, index)
            except ValueError:
                return None

        return None
