"""Task finding, marking, and tracking operations"""

import os
import re
from typing import Optional

from claudestep.application.services.artifact_operations import find_in_progress_tasks
from claudestep.domain.exceptions import FileNotFoundError


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


def find_next_available_task(plan_file: str, skip_indices: Optional[set] = None) -> Optional[tuple]:
    """Find first unchecked task not in skip_indices

    Args:
        plan_file: Path to spec.md file
        skip_indices: Set of task indices to skip (in-progress tasks)

    Returns:
        Tuple of (task_index, task_text) or None if no available task found
        task_index is 1-based position in spec.md

    Raises:
        FileNotFoundError: If spec file doesn't exist
    """
    if skip_indices is None:
        skip_indices = set()

    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Spec file not found: {plan_file}")

    with open(plan_file, "r") as f:
        task_index = 1
        for line in f:
            # Check for unchecked task
            match = re.match(r'^\s*- \[ \] (.+)$', line)
            if match:
                if task_index not in skip_indices:
                    return (task_index, match.group(1).strip())
                else:
                    print(f"Skipping task {task_index} (already in progress)")
                task_index += 1
            # Also count completed tasks to maintain correct indices
            elif re.match(r'^\s*- \[[xX]\] ', line):
                task_index += 1

    return None


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


def get_in_progress_task_indices(repo: str, label: str, project: str) -> set:
    """Get set of task indices currently being worked on

    Args:
        repo: GitHub repository (owner/name)
        label: GitHub label to filter PRs
        project: Project name to match artifacts

    Returns:
        Set of task indices that are in progress
    """
    return find_in_progress_tasks(repo, project, label)
