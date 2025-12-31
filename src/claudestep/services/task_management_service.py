"""Service Layer class for task management operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for task finding, marking, and tracking operations.
"""

import os
import re
from typing import Optional

from claudestep.domain.exceptions import FileNotFoundError
from claudestep.domain.spec_content import SpecContent
from claudestep.services.pr_operations_service import PROperationsService


class TaskManagementService:
    """Service Layer class for task management operations.

    Coordinates task finding, marking, and tracking by orchestrating
    domain models and infrastructure operations. Implements business
    logic for ClaudeStep's task workflow.
    """

    def __init__(self, repo: str, pr_operations_service: PROperationsService):
        """Initialize TaskManagementService

        Args:
            repo: GitHub repository (owner/name)
            pr_operations_service: Service for PR operations
        """
        self.repo = repo
        self.pr_operations_service = pr_operations_service

    # Public API methods

    def find_next_available_task(self, spec: SpecContent, skip_indices: Optional[set] = None) -> Optional[tuple]:
        """Find first unchecked task not in skip_indices

        Args:
            spec: SpecContent domain model
            skip_indices: Set of task indices to skip (in-progress tasks)

        Returns:
            Tuple of (task_index, task_text) or None if no available task found
            task_index is 1-based position in spec.md
        """
        if skip_indices is None:
            skip_indices = set()

        task = spec.get_next_available_task(skip_indices)
        if task:
            # Print skip messages for any tasks we're skipping
            for skipped_task in spec.tasks:
                if not skipped_task.is_completed and skipped_task.index in skip_indices and skipped_task.index < task.index:
                    print(f"Skipping task {skipped_task.index} (already in progress)")

            return (task.index, task.description)

        return None

    @staticmethod
    def mark_task_complete(plan_file: str, task: str) -> None:
        """Mark a task as complete in the spec file

        Args:
            plan_file: Path to spec.md file
            task: Task description to mark complete

        Raises:
            FileNotFoundError: If spec file doesn't exist
        """
        if not os.path.exists(plan_file):
            raise FileNotFoundError(f"Spec file not found: {plan_file}")

        with open(plan_file, "r") as f:
            content = f.read()

        # Replace the unchecked task with checked version
        # Match the task with surrounding whitespace preserved
        pattern = r'(\s*)- \[ \] ' + re.escape(task)
        replacement = r'\1- [x] ' + task
        updated_content = re.sub(pattern, replacement, content, count=1)

        with open(plan_file, "w") as f:
            f.write(updated_content)

    def get_in_progress_task_indices(self, label: str, project: str) -> set:
        """Get set of task indices currently being worked on

        Args:
            label: GitHub label to filter PRs
            project: Project name to match

        Returns:
            Set of task indices that are in progress
        """
        try:
            # Query open PRs for this project using service abstraction
            open_prs = self.pr_operations_service.get_open_prs_for_project(project, label=label)

            # Extract task indices using domain model properties
            task_indices = set()
            for pr in open_prs:
                if pr.task_index is not None:
                    task_indices.add(pr.task_index)

            return task_indices
        except Exception as e:
            print(f"Error: Failed to query GitHub PRs: {e}")
            return set()

    # Static utility methods

    @staticmethod
    def generate_task_id(task: str, max_length: int = 30) -> str:
        """Generate sanitized task ID from task description

        Args:
            task: Task description text
            max_length: Maximum length for the ID

        Returns:
            Sanitized task ID (lowercase, alphanumeric + dashes, truncated)
        """
        # Convert to lowercase and replace non-alphanumeric with dashes
        sanitized = re.sub(r"[^a-z0-9]+", "-", task.lower())
        # Remove leading/trailing dashes
        sanitized = sanitized.strip("-")
        # Truncate to max length and remove trailing dash if present
        sanitized = sanitized[:max_length].rstrip("-")
        return sanitized
