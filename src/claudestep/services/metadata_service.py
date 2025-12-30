"""Service Layer class for metadata operations.

Follows Service Layer pattern (Fowler, PoEAA) - provides high-level business
operations for working with project metadata. Serves as the business logic layer
between CLI commands and the infrastructure storage layer, implementing use cases
required by ClaudeStep commands.

The service works with the Hybrid model (HybridProjectMetadata, schema version 2.0)
and provides operations needed by:
- finalize command: Save PR metadata after creation
- statistics command: Get project statistics and team leaderboard
- prepare command: Check reviewer capacity and select next task
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from claudestep.domain.models import (
    HybridProjectMetadata,
    PullRequest,
    Task,
    TaskStatus,
)
from claudestep.infrastructure.metadata.operations import MetadataStore


class MetadataService:
    """Service Layer class for high-level metadata operations.

    Coordinates metadata operations by orchestrating domain models and
    infrastructure storage. Abstracts storage implementation details from
    CLI commands and implements business logic for metadata workflows.

    Attributes:
        store: MetadataStore implementation (e.g., GitHubMetadataStore)
    """

    def __init__(self, store: MetadataStore):
        """Initialize metadata service

        Args:
            store: MetadataStore implementation to use for storage operations
        """
        self.store = store

    # ========================================================================
    # Core CRUD Operations
    # ========================================================================

    def get_project(self, project_name: str) -> Optional[HybridProjectMetadata]:
        """Get project metadata

        Args:
            project_name: Name of the project

        Returns:
            HybridProjectMetadata instance or None if not found
        """
        return self.store.get_project(project_name)

    def save_project(self, project: HybridProjectMetadata) -> None:
        """Save or update project metadata

        Automatically updates last_updated timestamp and syncs task statuses
        before saving.

        Args:
            project: HybridProjectMetadata instance to save
        """
        project.last_updated = datetime.now(timezone.utc)
        project.sync_task_statuses()
        self.store.save_project(project)

    def list_all_projects(self) -> List[HybridProjectMetadata]:
        """Get metadata for all projects

        Returns:
            List of HybridProjectMetadata instances (may be empty)
        """
        return self.store.get_all_projects()

    def get_or_create_project(
        self, project_name: str, tasks: Optional[List[Task]] = None
    ) -> HybridProjectMetadata:
        """Get existing project or create new one

        Args:
            project_name: Name of the project
            tasks: Optional list of tasks to initialize project with

        Returns:
            HybridProjectMetadata instance (existing or newly created)
        """
        project = self.store.get_project(project_name)
        if project is None:
            project = HybridProjectMetadata.create_empty(project_name)
            if tasks:
                project.tasks = tasks
            self.save_project(project)
        return project

    # ========================================================================
    # Query Operations (for backward compatibility with artifact_operations.py)
    # ========================================================================

    def find_in_progress_tasks(self, project_name: str) -> Set[int]:
        """Get task indices that have open PRs

        This replaces the artifact-based find_in_progress_tasks() function.
        Used by the prepare command to check reviewer capacity.

        Args:
            project_name: Name of the project

        Returns:
            Set of task indices (1-based) that have open PRs
        """
        project = self.store.get_project(project_name)
        if not project:
            return set()

        in_progress_indices = set()
        for task in project.get_in_progress_tasks():
            in_progress_indices.add(task.index)
        return in_progress_indices

    def get_reviewer_assignments(self, project_name: str) -> Dict[int, str]:
        """Get mapping of task indices to assigned reviewers

        This replaces the artifact-based get_reviewer_assignments() function.
        Used by the prepare command to check reviewer capacity.

        Args:
            project_name: Name of the project

        Returns:
            Dictionary mapping task_index -> reviewer username
            Only includes tasks with open PRs.
        """
        project = self.store.get_project(project_name)
        if not project:
            return {}

        assignments = {}
        for pr in project.pull_requests:
            if pr.pr_state == "open":
                # If multiple PRs for same task, latest assignment wins
                assignments[pr.task_index] = pr.reviewer
        return assignments

    def get_open_prs_by_reviewer(
        self, project_name: Optional[str] = None
    ) -> Dict[str, List[int]]:
        """Get open PRs grouped by reviewer

        Args:
            project_name: Optional project name to filter by.
                         If None, returns results across all projects.

        Returns:
            Dictionary mapping reviewer username -> list of PR numbers
        """
        if project_name:
            projects = [self.store.get_project(project_name)]
            projects = [p for p in projects if p is not None]
        else:
            projects = self.store.get_all_projects()

        reviewer_prs: Dict[str, List[int]] = {}
        for project in projects:
            for pr in project.pull_requests:
                if pr.pr_state == "open":
                    if pr.reviewer not in reviewer_prs:
                        reviewer_prs[pr.reviewer] = []
                    reviewer_prs[pr.reviewer].append(pr.pr_number)

        return reviewer_prs

    # ========================================================================
    # PR Workflow Operations
    # ========================================================================

    def add_pr_to_project(
        self,
        project_name: str,
        task_index: int,
        pr: PullRequest,
    ) -> None:
        """Add a PR to a project

        If the project doesn't exist, it will be created.
        Task statuses are automatically synchronized after adding the PR.

        Args:
            project_name: Name of the project
            task_index: Task index (1-based) this PR implements
            pr: PullRequest instance to add
        """
        project = self.store.get_project(project_name)
        if project is None:
            project = HybridProjectMetadata.create_empty(project_name)

        # Ensure task exists
        task = project.get_task_by_index(task_index)
        if task is None:
            # Auto-create task if it doesn't exist
            task = Task(
                index=task_index,
                description=f"Task {task_index}",  # Placeholder
                status=TaskStatus.PENDING,
            )
            project.tasks.append(task)

        # Add PR
        project.pull_requests.append(pr)

        # Save with automatic status sync
        self.save_project(project)

    def update_pr_state(
        self, project_name: str, pr_number: int, new_state: str
    ) -> None:
        """Update the state of a PR

        Automatically synchronizes task statuses after updating.

        Args:
            project_name: Name of the project
            pr_number: GitHub PR number
            new_state: New PR state ("open", "merged", or "closed")

        Raises:
            ValueError: If PR not found or state is invalid
        """
        if new_state not in ["open", "merged", "closed"]:
            raise ValueError(f"Invalid PR state: {new_state}")

        project = self.store.get_project(project_name)
        if not project:
            raise ValueError(f"Project not found: {project_name}")

        # Find and update PR
        pr_found = False
        for pr in project.pull_requests:
            if pr.pr_number == pr_number:
                pr.pr_state = new_state
                pr_found = True
                break

        if not pr_found:
            raise ValueError(
                f"PR #{pr_number} not found in project {project_name}"
            )

        # Save with automatic status sync
        self.save_project(project)

    def update_task_status(self, project_name: str, task_index: int) -> None:
        """Update a single task's status based on its PRs

        This is useful after updating PR states externally.

        Args:
            project_name: Name of the project
            task_index: Task index (1-based)

        Raises:
            ValueError: If project or task not found
        """
        project = self.store.get_project(project_name)
        if not project:
            raise ValueError(f"Project not found: {project_name}")

        task = project.get_task_by_index(task_index)
        if not task:
            raise ValueError(
                f"Task {task_index} not found in project {project_name}"
            )

        # Update status and save
        new_status = project.calculate_task_status(task_index)
        task.status = new_status
        self.save_project(project)

    # ========================================================================
    # Statistics and Reporting Operations
    # ========================================================================

    def get_projects_modified_since(
        self, date: datetime
    ) -> List[HybridProjectMetadata]:
        """Get projects modified after a specific date

        Used by the statistics command to filter projects by time period.

        Args:
            date: Datetime threshold

        Returns:
            List of HybridProjectMetadata instances
        """
        return self.store.get_projects_modified_since(date)

    def get_project_stats(
        self, project_name: str
    ) -> Optional[Dict[str, any]]:
        """Get statistics for a single project

        Args:
            project_name: Name of the project

        Returns:
            Dictionary with project statistics or None if project not found
        """
        project = self.store.get_project(project_name)
        if not project:
            return None

        stats = project.get_progress_stats()
        return {
            "project": project.project,
            "total_tasks": stats["total"],
            "completed": stats["completed"],
            "in_progress": stats["in_progress"],
            "pending": stats["pending"],
            "completion_percentage": project.get_completion_percentage(),
            "total_cost": project.get_total_cost(),
            "cost_by_model": project.get_cost_by_model(),
            "last_updated": project.last_updated,
        }

    def get_reviewer_capacity(
        self, max_open_prs: int = 3
    ) -> Dict[str, Dict[str, any]]:
        """Get open PR count and capacity for each reviewer across all projects

        Args:
            max_open_prs: Maximum open PRs per reviewer

        Returns:
            Dict mapping reviewer username to capacity info:
            {
                "reviewer1": {
                    "open_prs": 2,
                    "pr_numbers": [42, 43],
                    "projects": ["project1", "project2"],
                    "has_capacity": True,
                    "available_slots": 1
                }
            }
        """
        reviewer_stats: Dict[str, Dict[str, any]] = {}

        for project in self.store.get_all_projects():
            for pr in project.pull_requests:
                if pr.pr_state == "open":
                    if pr.reviewer not in reviewer_stats:
                        reviewer_stats[pr.reviewer] = {
                            "open_prs": 0,
                            "pr_numbers": [],
                            "projects": set(),
                        }
                    reviewer_stats[pr.reviewer]["open_prs"] += 1
                    reviewer_stats[pr.reviewer]["pr_numbers"].append(pr.pr_number)
                    reviewer_stats[pr.reviewer]["projects"].add(project.project)

        # Add capacity info
        for reviewer, stats in reviewer_stats.items():
            stats["has_capacity"] = stats["open_prs"] < max_open_prs
            stats["available_slots"] = max(0, max_open_prs - stats["open_prs"])
            stats["projects"] = list(stats["projects"])  # Convert set to list

        return reviewer_stats

    # ========================================================================
    # Utility Operations
    # ========================================================================

    def project_exists(self, project_name: str) -> bool:
        """Check if a project exists

        Args:
            project_name: Name of the project

        Returns:
            True if project exists, False otherwise
        """
        return self.store.project_exists(project_name)

    def list_project_names(self) -> List[str]:
        """List names of all projects

        Returns:
            List of project names (may be empty)
        """
        return self.store.list_project_names()
