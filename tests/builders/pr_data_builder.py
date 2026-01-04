"""Builder for creating test PR data"""

from typing import Dict, Any, List, Optional


class PRDataBuilder:
    """Fluent interface for creating test PR data dictionaries

    Provides a clean way to create GitHub PR response data for tests
    with sensible defaults matching real GitHub API responses.

    Example:
        pr = PRDataBuilder()
            .with_number(123)
            .with_title("Task 3 - Add feature")
            .with_state("open")
            .with_branch("claude-chain-my-project-3")
            .build()
    """

    def __init__(self):
        """Initialize builder with default values"""
        self._number: int = 123
        self._title: str = "Task 1 - Default task"
        self._state: str = "open"
        self._merged: bool = False
        self._html_url: str = "https://github.com/owner/repo/pull/123"
        self._user_login: str = "alice"
        self._created_at: str = "2025-01-15T10:00:00Z"
        self._updated_at: str = "2025-01-15T10:00:00Z"
        self._head_ref: str = "claude-chain-sample-project-1"
        self._base_ref: str = "main"
        self._labels: List[Dict[str, str]] = [{"name": "claude-chain"}]
        self._custom_fields: Dict[str, Any] = {}

    def with_number(self, number: int) -> "PRDataBuilder":
        """Set the PR number

        Args:
            number: PR number

        Returns:
            Self for method chaining
        """
        self._number = number
        # Auto-update URL to match
        self._html_url = f"https://github.com/owner/repo/pull/{number}"
        return self

    def with_title(self, title: str) -> "PRDataBuilder":
        """Set the PR title

        Args:
            title: PR title

        Returns:
            Self for method chaining
        """
        self._title = title
        return self

    def with_task(self, task_index: int, description: str, project: str = "sample-project") -> "PRDataBuilder":
        """Set PR data based on task information

        Automatically sets title and branch name based on task.

        Args:
            task_index: Task index (1-based)
            description: Task description
            project: Project name (default: "sample-project")

        Returns:
            Self for method chaining
        """
        self._title = f"Task {task_index} - {description}"
        self._head_ref = f"claude-chain-{project}-{task_index}"
        return self

    def with_state(self, state: str, merged: bool = False) -> "PRDataBuilder":
        """Set the PR state

        Args:
            state: PR state ("open", "closed")
            merged: Whether the PR was merged (only relevant for "closed" state)

        Returns:
            Self for method chaining
        """
        self._state = state
        self._merged = merged if state == "closed" else False
        return self

    def as_merged(self) -> "PRDataBuilder":
        """Mark PR as closed and merged

        Returns:
            Self for method chaining
        """
        self._state = "closed"
        self._merged = True
        return self

    def as_closed(self) -> "PRDataBuilder":
        """Mark PR as closed (but not merged)

        Returns:
            Self for method chaining
        """
        self._state = "closed"
        self._merged = False
        return self

    def with_user(self, username: str) -> "PRDataBuilder":
        """Set the PR author

        Args:
            username: GitHub username

        Returns:
            Self for method chaining
        """
        self._user_login = username
        return self

    def with_branch(self, branch_name: str) -> "PRDataBuilder":
        """Set the head branch name

        Args:
            branch_name: Branch name

        Returns:
            Self for method chaining
        """
        self._head_ref = branch_name
        return self

    def with_base_branch(self, branch_name: str) -> "PRDataBuilder":
        """Set the base branch name

        Args:
            branch_name: Base branch name (default: "main")

        Returns:
            Self for method chaining
        """
        self._base_ref = branch_name
        return self

    def with_label(self, label: str) -> "PRDataBuilder":
        """Add a label to the PR

        Args:
            label: Label name

        Returns:
            Self for method chaining
        """
        if not any(l["name"] == label for l in self._labels):
            self._labels.append({"name": label})
        return self

    def with_labels(self, *labels: str) -> "PRDataBuilder":
        """Set PR labels (replaces existing)

        Args:
            *labels: Label names

        Returns:
            Self for method chaining
        """
        self._labels = [{"name": label} for label in labels]
        return self

    def with_created_at(self, timestamp: str) -> "PRDataBuilder":
        """Set creation timestamp

        Args:
            timestamp: ISO 8601 timestamp

        Returns:
            Self for method chaining
        """
        self._created_at = timestamp
        return self

    def with_field(self, key: str, value: Any) -> "PRDataBuilder":
        """Add a custom field to the PR data

        Args:
            key: Field name
            value: Field value

        Returns:
            Self for method chaining
        """
        self._custom_fields[key] = value
        return self

    def build(self) -> Dict[str, Any]:
        """Build and return the PR data dictionary

        Returns:
            Complete PR data dictionary matching GitHub API response format
        """
        pr_data = {
            "number": self._number,
            "title": self._title,
            "state": self._state,
            "html_url": self._html_url,
            "user": {"login": self._user_login},
            "created_at": self._created_at,
            "updated_at": self._updated_at,
            "head": {"ref": self._head_ref},
            "base": {"ref": self._base_ref},
            "labels": self._labels
        }

        # Add merged field if closed
        if self._state == "closed":
            pr_data["merged"] = self._merged

        # Merge any custom fields
        pr_data.update(self._custom_fields)

        return pr_data

    @staticmethod
    def open_pr(number: int = 123, task_index: int = 1) -> Dict[str, Any]:
        """Quick helper for creating an open PR

        Args:
            number: PR number (default: 123)
            task_index: Task index for branch name (default: 1)

        Returns:
            Open PR data dictionary
        """
        return (PRDataBuilder()
                .with_number(number)
                .with_task(task_index, f"Task {task_index}")
                .build())

    @staticmethod
    def merged_pr(number: int = 123, task_index: int = 1) -> Dict[str, Any]:
        """Quick helper for creating a merged PR

        Args:
            number: PR number (default: 123)
            task_index: Task index for branch name (default: 1)

        Returns:
            Merged PR data dictionary
        """
        return (PRDataBuilder()
                .with_number(number)
                .with_task(task_index, f"Task {task_index}")
                .as_merged()
                .build())
