"""Centralized PR operations and branch naming utilities

This module provides a unified interface for branch naming and PR fetching,
eliminating duplication across the codebase.
"""

import json
import re
from typing import List, Optional, Tuple

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.infrastructure.github.operations import run_gh_command


class PROperationsService:
    """Service for PR operations and branch naming utilities"""

    def __init__(self, repo: str):
        """Initialize PR operations service

        Args:
            repo: GitHub repository (owner/name)
        """
        self.repo = repo

    # Public API methods

    def get_project_prs(
        self, project_name: str, state: str = "all", label: str = "claudestep"
    ) -> List[dict]:
        """Fetch all PRs for a project by branch prefix.

        This is the primary API for getting PRs associated with a ClaudeStep project.
        It filters PRs by matching the branch name pattern.

        Args:
            project_name: Project name (e.g., "my-refactor")
            state: PR state filter - "open", "closed", "merged", or "all"
            label: GitHub label to filter PRs (default: "claudestep")

        Returns:
            List of PR data dicts with fields:
                - number: PR number
                - state: PR state
                - headRefName: Branch name
                - title: PR title
                - labels: List of label dicts
                - assignees: List of assignee dicts
                - mergedAt: Merge timestamp (if merged)
                - createdAt: Creation timestamp

        Raises:
            GitHubAPIError: If the GitHub API call fails

        Examples:
            >>> service = PROperationsService("owner/repo")
            >>> prs = service.get_project_prs("my-refactor", state="open")
            >>> len(prs)
            3
            >>> prs[0]["headRefName"]
            'claude-step-my-refactor-1'
        """
        print(
            f"Fetching PRs for project '{project_name}' with state='{state}' and label='{label}'"
        )

        # Fetch PRs with the label
        try:
            pr_output = run_gh_command(
                [
                    "pr",
                    "list",
                    "--repo",
                    self.repo,
                    "--label",
                    label,
                    "--state",
                    state,
                    "--json",
                    "number,state,headRefName,title,labels,assignees,mergedAt,createdAt",
                    "--limit",
                    "100",
                ]
            )
            all_prs = json.loads(pr_output) if pr_output else []
        except (GitHubAPIError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to list PRs: {e}")
            return []

        # Filter to only PRs whose branch names match the project pattern
        project_prefix = f"claude-step-{project_name}-"
        project_prs = [
            pr for pr in all_prs if pr.get("headRefName", "").startswith(project_prefix)
        ]

        print(
            f"Found {len(project_prs)} PR(s) for project '{project_name}' (out of {len(all_prs)} total)"
        )
        return project_prs

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
        return f"claude-step-{project_name}-{index}"

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
