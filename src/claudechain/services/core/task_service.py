"""Core service for task management operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for task finding, marking, and tracking operations.
"""

import os
import re
from typing import Optional

from claudechain.domain.exceptions import FileNotFoundError
from claudechain.domain.spec_content import SpecContent, generate_task_hash
from claudechain.services.core.pr_service import PRService


class TaskService:
    """Core service for task management operations.

    Coordinates task finding, marking, and tracking by orchestrating
    domain models and infrastructure operations. Implements business
    logic for ClaudeChain's task workflow.
    """

    def __init__(self, repo: str, pr_service: PRService):
        """Initialize TaskService

        Args:
            repo: GitHub repository (owner/name)
            pr_service: Service for PR operations
        """
        self.repo = repo
        self.pr_service = pr_service

    # Public API methods

    def find_next_available_task(self, spec: SpecContent, skip_hashes: Optional[set] = None) -> Optional[tuple]:
        """Find first unchecked task not in skip_hashes

        Args:
            spec: SpecContent domain model
            skip_hashes: Set of task hashes to skip (in-progress tasks)

        Returns:
            Tuple of (task_index, task_text, task_hash) or None if no available task found
            task_index is 1-based position in spec.md
            task_hash is 8-character hash of task description
        """
        if skip_hashes is None:
            skip_hashes = set()

        task = spec.get_next_available_task(skip_hashes)
        if task:
            # Print skip messages for any tasks we're skipping
            for skipped_task in spec.tasks:
                if not skipped_task.is_completed and skipped_task.index < task.index:
                    if skipped_task.task_hash in skip_hashes:
                        print(f"Skipping task {skipped_task.index} (already in progress - hash {skipped_task.task_hash[:6]}...)")

            return (task.index, task.description, task.task_hash)

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

    def get_in_progress_tasks(self, label: str, project: str) -> set:
        """Get task hashes currently being worked on

        Args:
            label: GitHub label to filter PRs
            project: Project name to match

        Returns:
            Set of task hashes from hash-based PRs
        """
        try:
            # Query open PRs for this project using service abstraction
            open_prs = self.pr_service.get_open_prs_for_project(project, label=label)

            # Extract task hashes using domain model properties
            task_hashes = set()

            for pr in open_prs:
                if pr.task_hash is not None:
                    task_hashes.add(pr.task_hash)

            return task_hashes
        except Exception as e:
            print(f"Error: Failed to query GitHub PRs: {e}")
            return set()

    def detect_orphaned_prs(self, label: str, project: str, spec: 'SpecContent') -> list:
        """Detect PRs that reference tasks no longer in spec (orphaned PRs)

        An orphaned PR is one where the task hash doesn't match any current
        task hash in spec.md.

        Args:
            label: GitHub label to filter PRs
            project: Project name to match
            spec: SpecContent domain model with current tasks

        Returns:
            List of orphaned GitHubPullRequest objects
        """
        try:
            # Query all open PRs for this project
            open_prs = self.pr_service.get_open_prs_for_project(project, label=label)

            # Build set of valid task hashes from current spec
            valid_hashes = {task.task_hash for task in spec.tasks}

            orphaned_prs = []

            for pr in open_prs:
                if pr.task_hash is not None:
                    if pr.task_hash not in valid_hashes:
                        orphaned_prs.append(pr)

            return orphaned_prs
        except Exception as e:
            print(f"Warning: Failed to detect orphaned PRs: {e}")
            return []

    # Static utility methods

    @staticmethod
    def generate_task_hash(description: str) -> str:
        """Generate stable hash identifier for a task description.

        Uses SHA-256 hash truncated to 8 characters for readability.
        This provides a stable identifier that doesn't change when tasks
        are reordered in spec.md, only when the description itself changes.

        Args:
            description: Task description text

        Returns:
            8-character hash string (lowercase hexadecimal)

        Examples:
            >>> TaskService.generate_task_hash("Add user authentication")
            'a3f2b891'
            >>> TaskService.generate_task_hash("  Add user authentication  ")
            'a3f2b891'  # Same hash after whitespace normalization
            >>> TaskService.generate_task_hash("")
            'e3b0c442'  # Hash of empty string
        """
        # Delegate to domain model function
        return generate_task_hash(description)

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
