"""GitHub domain models for ClaudeChain

These models represent GitHub API objects with type-safe properties and methods.
They encapsulate JSON parsing to ensure the service layer works with well-formed
domain objects rather than raw dictionaries.

Following the principle: "Parse once into well-formed models"
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class PRState(Enum):
    """State of a GitHub pull request.

    Represents the three possible states of a PR as returned by GitHub API.
    """

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"

    @classmethod
    def from_string(cls, state: str) -> PRState:
        """Parse PR state from string (case-insensitive).

        Args:
            state: State string from GitHub API (e.g., "OPEN", "open", "merged")

        Returns:
            PRState enum value

        Raises:
            ValueError: If state string is not a valid PR state
        """
        normalized = state.lower()
        for member in cls:
            if member.value == normalized:
                return member
        raise ValueError(f"Invalid PR state: {state}")


@dataclass
class GitHubUser:
    """Domain model for GitHub user

    Represents a GitHub user from API responses with type-safe properties.
    """

    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> 'GitHubUser':
        """Parse from GitHub API response

        Args:
            data: Dictionary from GitHub API (e.g., assignee object)

        Returns:
            GitHubUser instance with parsed data

        Example:
            >>> user_data = {"login": "octocat", "name": "The Octocat"}
            >>> user = GitHubUser.from_dict(user_data)
        """
        return cls(
            login=data["login"],
            name=data.get("name"),
            avatar_url=data.get("avatar_url")
        )


@dataclass
class GitHubPullRequest:
    """Domain model for GitHub pull request

    Represents a PR from GitHub API with type-safe properties and helper methods.
    All date parsing and JSON navigation happens in from_dict() constructor.
    """

    number: int
    title: str
    state: str  # "open", "closed", "merged"
    created_at: datetime
    merged_at: Optional[datetime]
    assignees: List[GitHubUser]
    labels: List[str] = field(default_factory=list)
    head_ref_name: Optional[str] = None  # Branch name (source branch)
    base_ref_name: Optional[str] = None  # Target branch (branch PR was merged into)
    url: Optional[str] = None  # PR URL (e.g., https://github.com/owner/repo/pull/123)

    @classmethod
    def from_dict(cls, data: dict) -> 'GitHubPullRequest':
        """Parse from GitHub API response

        Handles all JSON parsing, date conversion, and nested object construction.
        Service layer receives clean, type-safe objects.

        Args:
            data: Dictionary from GitHub API (gh pr list --json output)

        Returns:
            GitHubPullRequest instance with all fields parsed

        Example:
            >>> pr_data = {
            ...     "number": 123,
            ...     "title": "Add feature",
            ...     "state": "OPEN",
            ...     "createdAt": "2024-01-01T12:00:00Z",
            ...     "mergedAt": None,
            ...     "assignees": [{"login": "reviewer"}],
            ...     "labels": [{"name": "claudechain"}]
            ... }
            >>> pr = GitHubPullRequest.from_dict(pr_data)
        """
        # Parse created_at (always present)
        created_at = data["createdAt"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Parse merged_at (optional)
        merged_at = data.get("mergedAt")
        if merged_at and isinstance(merged_at, str):
            merged_at = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))

        # Parse assignees (list of user objects)
        assignees = []
        for assignee_data in data.get("assignees", []):
            assignees.append(GitHubUser.from_dict(assignee_data))

        # Parse labels (list of label objects with "name" field)
        labels = []
        for label_data in data.get("labels", []):
            if isinstance(label_data, dict):
                labels.append(label_data["name"])
            else:
                # Handle case where labels are just strings
                labels.append(str(label_data))

        # Normalize state to lowercase for consistency
        state = data["state"].lower()

        # Get branch names if available
        head_ref_name = data.get("headRefName")
        base_ref_name = data.get("baseRefName")

        # Get PR URL if available
        url = data.get("url")

        return cls(
            number=data["number"],
            title=data["title"],
            state=state,
            created_at=created_at,
            merged_at=merged_at,
            assignees=assignees,
            labels=labels,
            head_ref_name=head_ref_name,
            base_ref_name=base_ref_name,
            url=url
        )

    def is_merged(self) -> bool:
        """Check if PR was merged

        Returns:
            True if PR is in merged state or has merged_at timestamp
        """
        return self.state == "merged" or self.merged_at is not None

    def is_open(self) -> bool:
        """Check if PR is open

        Returns:
            True if PR is in open state
        """
        return self.state == "open"

    def is_closed(self) -> bool:
        """Check if PR is closed (but not merged)

        Returns:
            True if PR is closed but not merged
        """
        return self.state == "closed" and not self.is_merged()

    def has_label(self, label: str) -> bool:
        """Check if PR has a specific label

        Args:
            label: Label name to check

        Returns:
            True if PR has the label
        """
        return label in self.labels

    def get_assignee_logins(self) -> List[str]:
        """Get list of assignee usernames

        Returns:
            List of login names for all assignees
        """
        return [assignee.login for assignee in self.assignees]

    @property
    def project_name(self) -> Optional[str]:
        """Extract project name from branch name.

        Parses the branch name using ClaudeChain branch naming convention
        (claude-chain-{project_name}-{index}) and returns the project name.

        Returns:
            Project name if branch follows ClaudeChain pattern, None otherwise

        Examples:
            >>> pr = GitHubPullRequest(head_ref_name="claude-chain-my-refactor-1", ...)
            >>> pr.project_name
            'my-refactor'
            >>> pr = GitHubPullRequest(head_ref_name="main", ...)
            >>> pr.project_name
            None
        """
        if not self.head_ref_name:
            return None

        # Import here to avoid circular dependency
        from claudechain.services.core.pr_service import PRService

        parsed = PRService.parse_branch_name(self.head_ref_name)
        if parsed:
            return parsed.project_name
        return None

    @property
    def task_hash(self) -> Optional[str]:
        """Extract task hash from branch name.

        Parses the branch name using ClaudeChain branch naming convention
        and returns the task hash.

        Returns:
            Task hash (8-char hex string) if branch follows pattern, None otherwise

        Examples:
            >>> pr = GitHubPullRequest(head_ref_name="claude-chain-my-refactor-a3f2b891", ...)
            >>> pr.task_hash
            'a3f2b891'
            >>> pr = GitHubPullRequest(head_ref_name="main", ...)
            >>> pr.task_hash
            None
        """
        if not self.head_ref_name:
            return None

        # Import here to avoid circular dependency
        from claudechain.services.core.pr_service import PRService

        parsed = PRService.parse_branch_name(self.head_ref_name)
        if parsed:
            return parsed.task_hash
        return None

    @property
    def task_description(self) -> str:
        """Get task description with 'ClaudeChain: ' prefix stripped.

        Returns the PR title with the ClaudeChain prefix removed if present.
        This is the user-facing task description without automation metadata.

        Returns:
            Task description (title with prefix stripped)

        Examples:
            >>> pr = GitHubPullRequest(title="ClaudeChain: Add user authentication", ...)
            >>> pr.task_description
            'Add user authentication'
            >>> pr = GitHubPullRequest(title="Fix bug in login", ...)
            >>> pr.task_description
            'Fix bug in login'
        """
        if self.title.startswith("ClaudeChain: "):
            return self.title[len("ClaudeChain: "):]
        return self.title

    @property
    def is_claudechain_pr(self) -> bool:
        """Check if PR follows ClaudeChain branch naming convention.

        Returns:
            True if branch name matches claude-chain-{project}-{index} pattern

        Examples:
            >>> pr = GitHubPullRequest(head_ref_name="claude-chain-my-refactor-1", ...)
            >>> pr.is_claudechain_pr
            True
            >>> pr = GitHubPullRequest(head_ref_name="feature/new-feature", ...)
            >>> pr.is_claudechain_pr
            False
        """
        if not self.head_ref_name:
            return False

        # Import here to avoid circular dependency
        from claudechain.services.core.pr_service import PRService

        return PRService.parse_branch_name(self.head_ref_name) is not None

    @property
    def days_open(self) -> int:
        """Calculate days the PR was/is open.

        For open PRs: created_at through now
        For closed/merged PRs: created_at through merged_at

        Returns:
            Number of days the PR has been/was open

        Examples:
            >>> # Open PR created 5 days ago
            >>> pr = GitHubPullRequest(state="open", created_at=five_days_ago, ...)
            >>> pr.days_open
            5
            >>> # Merged PR that was open for 3 days
            >>> pr = GitHubPullRequest(state="merged", created_at=created, merged_at=merged, ...)
            >>> pr.days_open
            3
        """
        from datetime import datetime, timezone

        if self.state == "open":
            end_time = datetime.now(timezone.utc)
        else:
            end_time = self.merged_at if self.merged_at else datetime.now(timezone.utc)
        return (end_time - self.created_at).days

    def is_stale(self, stale_pr_days: int) -> bool:
        """Check if PR is stale based on threshold.

        A PR is considered stale if it has been open for at least
        stale_pr_days days.

        Args:
            stale_pr_days: Number of days before a PR is considered stale

        Returns:
            True if PR has been open >= stale_pr_days

        Examples:
            >>> pr = GitHubPullRequest(...)  # open for 10 days
            >>> pr.is_stale(7)
            True
            >>> pr.is_stale(14)
            False
        """
        return self.days_open >= stale_pr_days

    @property
    def first_assignee(self) -> Optional[str]:
        """Get the login of the first assignee, if any.

        Returns:
            First assignee's login, or None if no assignees

        Examples:
            >>> pr = GitHubPullRequest(assignees=[GitHubUser(login="alice")], ...)
            >>> pr.first_assignee
            'alice'
            >>> pr = GitHubPullRequest(assignees=[], ...)
            >>> pr.first_assignee
            None
        """
        return self.assignees[0].login if self.assignees else None


@dataclass
class GitHubPullRequestList:
    """Collection of GitHub pull requests with filtering/grouping methods

    Provides type-safe operations on PR lists without requiring service
    layer to work with raw JSON arrays.
    """

    pull_requests: List[GitHubPullRequest] = field(default_factory=list)

    @classmethod
    def from_json_array(cls, data: List[dict]) -> 'GitHubPullRequestList':
        """Parse from GitHub API JSON array

        Args:
            data: List of PR dictionaries from GitHub API

        Returns:
            GitHubPullRequestList with all PRs parsed

        Example:
            >>> prs_data = [
            ...     {"number": 1, "title": "PR 1", "state": "OPEN", ...},
            ...     {"number": 2, "title": "PR 2", "state": "MERGED", ...}
            ... ]
            >>> pr_list = GitHubPullRequestList.from_json_array(prs_data)
        """
        prs = [GitHubPullRequest.from_dict(pr_data) for pr_data in data]
        return cls(pull_requests=prs)

    def filter_by_state(self, state: str) -> 'GitHubPullRequestList':
        """Filter PRs by state

        Args:
            state: State to filter by ("open", "closed", "merged")

        Returns:
            New GitHubPullRequestList with filtered PRs
        """
        filtered = [pr for pr in self.pull_requests if pr.state == state.lower()]
        return GitHubPullRequestList(pull_requests=filtered)

    def filter_by_label(self, label: str) -> 'GitHubPullRequestList':
        """Filter PRs by label

        Args:
            label: Label name to filter by

        Returns:
            New GitHubPullRequestList with PRs that have the label
        """
        filtered = [pr for pr in self.pull_requests if pr.has_label(label)]
        return GitHubPullRequestList(pull_requests=filtered)

    def filter_merged(self) -> 'GitHubPullRequestList':
        """Get only merged PRs

        Returns:
            New GitHubPullRequestList with only merged PRs
        """
        filtered = [pr for pr in self.pull_requests if pr.is_merged()]
        return GitHubPullRequestList(pull_requests=filtered)

    def filter_open(self) -> 'GitHubPullRequestList':
        """Get only open PRs

        Returns:
            New GitHubPullRequestList with only open PRs
        """
        filtered = [pr for pr in self.pull_requests if pr.is_open()]
        return GitHubPullRequestList(pull_requests=filtered)

    def filter_by_date(self, since: datetime, date_field: str = "created_at") -> 'GitHubPullRequestList':
        """Filter PRs by date

        Args:
            since: Minimum date (PRs on or after this date)
            date_field: Which date field to check ("created_at" or "merged_at")

        Returns:
            New GitHubPullRequestList with PRs matching date criteria
        """
        filtered = []
        for pr in self.pull_requests:
            if date_field == "created_at":
                if pr.created_at >= since:
                    filtered.append(pr)
            elif date_field == "merged_at":
                if pr.merged_at and pr.merged_at >= since:
                    filtered.append(pr)
        return GitHubPullRequestList(pull_requests=filtered)

    def group_by_assignee(self) -> Dict[str, List[GitHubPullRequest]]:
        """Group PRs by assignee

        PRs with multiple assignees appear in multiple groups.

        Returns:
            Dictionary mapping assignee login to list of PRs
        """
        grouped: Dict[str, List[GitHubPullRequest]] = {}
        for pr in self.pull_requests:
            for assignee in pr.assignees:
                if assignee.login not in grouped:
                    grouped[assignee.login] = []
                grouped[assignee.login].append(pr)
        return grouped

    def count(self) -> int:
        """Get count of PRs in list

        Returns:
            Number of PRs
        """
        return len(self.pull_requests)

    def __len__(self) -> int:
        """Allow len() to be called on GitHubPullRequestList"""
        return self.count()

    def __iter__(self):
        """Allow iteration over PRs"""
        return iter(self.pull_requests)


@dataclass
class WorkflowRun:
    """Domain model for GitHub Actions workflow run

    Represents a workflow run from GitHub API with type-safe properties.
    Used for tracking workflow execution status in E2E tests and monitoring.
    """

    database_id: int
    status: str  # "queued", "in_progress", "completed"
    conclusion: Optional[str]  # "success", "failure", "cancelled", etc.
    created_at: datetime
    head_branch: str
    url: str

    @classmethod
    def from_dict(cls, data: dict) -> 'WorkflowRun':
        """Parse from GitHub API response

        Args:
            data: Dictionary from GitHub API (workflow run object)

        Returns:
            WorkflowRun instance with parsed data

        Example:
            >>> run_data = {
            ...     "databaseId": 12345,
            ...     "status": "completed",
            ...     "conclusion": "success",
            ...     "createdAt": "2024-01-01T12:00:00Z",
            ...     "headBranch": "main",
            ...     "url": "https://github.com/owner/repo/actions/runs/12345"
            ... }
            >>> run = WorkflowRun.from_dict(run_data)
        """
        # Parse created_at
        created_at = data["createdAt"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return cls(
            database_id=data["databaseId"],
            status=data["status"],
            conclusion=data.get("conclusion"),
            created_at=created_at,
            head_branch=data["headBranch"],
            url=data["url"]
        )

    def is_completed(self) -> bool:
        """Check if workflow run has completed

        Returns:
            True if workflow run is completed
        """
        return self.status == "completed"

    def is_success(self) -> bool:
        """Check if workflow run succeeded

        Returns:
            True if workflow run completed successfully
        """
        return self.is_completed() and self.conclusion == "success"

    def is_failure(self) -> bool:
        """Check if workflow run failed

        Returns:
            True if workflow run completed with failure
        """
        return self.is_completed() and self.conclusion == "failure"


@dataclass
class PRComment:
    """Domain model for GitHub pull request comment

    Represents a comment on a pull request from GitHub API.
    Used for testing and verification of automated PR interactions.
    """

    body: str
    author: str
    created_at: datetime

    @classmethod
    def from_dict(cls, data: dict) -> 'PRComment':
        """Parse from GitHub API response

        Args:
            data: Dictionary from GitHub API (comment object)

        Returns:
            PRComment instance with parsed data

        Example:
            >>> comment_data = {
            ...     "body": "LGTM!",
            ...     "author": {"login": "reviewer"},
            ...     "createdAt": "2024-01-01T12:00:00Z"
            ... }
            >>> comment = PRComment.from_dict(comment_data)
        """
        # Parse created_at
        created_at = data["createdAt"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        # Extract author login
        author = data["author"]
        if isinstance(author, dict):
            author = author["login"]

        return cls(
            body=data["body"],
            author=author,
            created_at=created_at
        )
