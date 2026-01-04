"""Core service for assignee and capacity management.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for checking project capacity and providing assignee information.
"""

from typing import List, Optional

from claudechain.services.core.pr_service import PRService
from claudechain.domain.models import CapacityResult
from claudechain.domain.project_configuration import ProjectConfiguration


class AssigneeService:
    """Core service for capacity checking and assignee management.

    ClaudeChain enforces a single open PR per project. This service checks
    whether a project has capacity for a new PR and provides the configured
    assignee (if any).
    """

    def __init__(self, repo: str, pr_service: PRService):
        self.repo = repo
        self.pr_service = pr_service

    def check_capacity(
        self, config: ProjectConfiguration, label: str, project: str
    ) -> CapacityResult:
        """Check if project has capacity for a new PR.

        ClaudeChain allows only 1 open PR per project at a time.

        Args:
            config: ProjectConfiguration domain model with optional assignee
            label: GitHub label to filter PRs
            project: Project name to match (used for filtering by branch name pattern)

        Returns:
            CapacityResult with capacity status, assignee, and open PRs list
        """
        # Get all open PRs for this project (regardless of assignee)
        open_prs = self.pr_service.get_open_prs_for_project(project, label=label)
        open_count = len(open_prs)

        # Build PR info list for display
        pr_info_list = []
        for pr in open_prs:
            pr_info = {
                "pr_number": pr.number,
                "task_hash": pr.task_hash,
                "task_description": pr.task_description
            }
            pr_info_list.append(pr_info)
            print(f"PR #{pr.number}: project={project}")

        # Only 1 open PR allowed per project
        has_capacity = open_count < 1

        print(f"Project {project}: {open_count} open PR(s) (max: 1)")

        if has_capacity:
            if config.assignee:
                print(f"Capacity available - assignee: {config.assignee}")
            else:
                print("Capacity available (no assignee configured)")
        else:
            print("Project at capacity - skipping PR creation")

        return CapacityResult(
            has_capacity=has_capacity,
            assignee=config.assignee,
            open_prs=pr_info_list,
            project_name=project
        )
