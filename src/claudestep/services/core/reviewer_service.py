"""Core service for reviewer management operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for reviewer capacity checking and assignment.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from claudestep.services.core.pr_service import PRService
from claudestep.domain.models import ReviewerCapacityResult
from claudestep.domain.project_configuration import (
    ProjectConfiguration,
    DEFAULT_PROJECT_PR_LIMIT,
)


class ReviewerService:
    """Core service for reviewer management operations.

    Coordinates reviewer capacity checking and assignment by querying
    GitHub API for open PRs. Implements business logic for ClaudeStep's
    reviewer assignment workflow.

    Handles two modes:
    1. With reviewers: Assigns PRs to specific reviewers based on capacity
    2. Without reviewers: Uses global project PR limit (default: 1)
    """

    def __init__(self, repo: str, pr_service: PRService):
        self.repo = repo
        self.pr_service = pr_service

    # Public API methods

    def find_available_reviewer(
        self, config: ProjectConfiguration, label: str, project: str
    ) -> tuple[Optional[str], ReviewerCapacityResult]:
        """Find first reviewer with capacity based on GitHub API queries

        For projects without reviewers configured, checks global project PR limit
        instead of per-reviewer capacity. In this mode, returns None as the
        reviewer (PR created without assignee) but still indicates whether
        capacity is available.

        Args:
            config: ProjectConfiguration domain model with reviewers
            label: GitHub label to filter PRs
            project: Project name to match (used for filtering by branch name pattern)

        Returns:
            Tuple of (username or None, ReviewerCapacityResult)
            - If reviewers configured: returns first available reviewer or None if at capacity
            - If no reviewers: returns None (no assignee) but result.all_at_capacity
              indicates whether global project limit allows creating a PR
        """
        result = ReviewerCapacityResult()

        # Handle no-reviewer case: use global project PR limit
        if not config.reviewers:
            return self._check_project_capacity(label, project, result)

        # Initialize reviewer PR lists
        reviewer_prs = defaultdict(list)
        for reviewer in config.reviewers:
            reviewer_prs[reviewer.username] = []

        # Query open PRs for each reviewer from GitHub API using PRService
        for reviewer in config.reviewers:
            username = reviewer.username

            # Get open PRs for this reviewer on this project using service layer
            prs = self.pr_service.get_reviewer_prs_for_project(
                username=username,
                project=project,
                label=label
            )

            # Build PR info list using domain model properties
            for pr in prs:
                pr_info = {
                    "pr_number": pr.number,
                    "task_hash": pr.task_hash,
                    "task_description": pr.task_description
                }
                reviewer_prs[username].append(pr_info)
                print(f"PR #{pr.number}: reviewer={username}")

        # Build result and find first available reviewer
        selected_reviewer = None
        for reviewer in config.reviewers:
            username = reviewer.username
            max_prs = reviewer.max_open_prs
            open_prs = reviewer_prs[username]
            has_capacity = len(open_prs) < max_prs

            # Add to result
            result.add_reviewer(username, max_prs, open_prs, has_capacity)

            print(f"Reviewer {username}: {len(open_prs)} open PRs (max: {max_prs})")

            # Select first available reviewer
            if has_capacity and selected_reviewer is None:
                selected_reviewer = username
                print(f"Selected reviewer: {username}")

        result.selected_reviewer = selected_reviewer
        result.all_at_capacity = (selected_reviewer is None)

        return selected_reviewer, result

    def _check_project_capacity(
        self, label: str, project: str, result: ReviewerCapacityResult
    ) -> tuple[Optional[str], ReviewerCapacityResult]:
        """Check capacity using global project PR limit (no reviewers configured).

        When no reviewers are configured, we use a global limit on open PRs
        per project (default: 1). This prevents runaway automation while still
        allowing projects to work without configuration.

        Args:
            label: GitHub label to filter PRs
            project: Project name to check
            result: ReviewerCapacityResult to populate

        Returns:
            Tuple of (None, ReviewerCapacityResult)
            - Always returns None as reviewer (no assignee)
            - result.all_at_capacity indicates if PR can be created
        """
        # Get all open PRs for this project (regardless of assignee)
        open_prs = self.pr_service.get_open_prs_for_project(project, label=label)
        open_count = len(open_prs)
        max_prs = DEFAULT_PROJECT_PR_LIMIT

        # Build PR info list for display
        pr_info_list = []
        for pr in open_prs:
            pr_info = {
                "pr_number": pr.number,
                "task_hash": pr.task_hash,
                "task_description": pr.task_description
            }
            pr_info_list.append(pr_info)
            print(f"PR #{pr.number}: project={project} (no reviewer)")

        has_capacity = open_count < max_prs

        # Add virtual "project" entry to result for display purposes
        result.add_reviewer(
            f"(project: {project})",
            max_prs,
            pr_info_list,
            has_capacity
        )

        print(f"Project {project}: {open_count} open PRs (max: {max_prs}, no reviewer)")

        # No reviewer selected (will create PR without assignee)
        result.selected_reviewer = None
        result.all_at_capacity = not has_capacity

        if has_capacity:
            print("Capacity available (no reviewer - PR will be created without assignee)")
        else:
            print("Project at capacity - skipping PR creation")

        return None, result
