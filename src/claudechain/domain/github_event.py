"""GitHub event context for simplified workflow handling.

This module provides parsing and interpretation of GitHub event payloads,
enabling ClaudeChain to handle all event-related logic internally rather
than requiring users to maintain complex bash scripts in their workflows.

Following the principle: "Parse once into well-formed models"
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class GitHubEventContext:
    """Parsed GitHub event with extracted fields for ClaudeChain.

    This class encapsulates the logic for interpreting GitHub webhook events
    and determining how ClaudeChain should respond. It extracts relevant
    information from the event payload and provides methods for:
    - Determining if execution should be skipped
    - Finding the appropriate git ref to checkout
    - Getting context for changed files detection (for push events)
    - Getting the default base branch from event context

    Attributes:
        event_name: The GitHub event type (workflow_dispatch, pull_request, push)
        pr_number: Pull request number (for pull_request events)
        pr_merged: Whether the PR was merged (for pull_request events)
        pr_labels: List of label names on the PR
        base_ref: The branch the PR targets (for pull_request events)
        head_ref: The branch the PR comes from (for pull_request events)
        ref_name: The branch pushed to (for push events)
        before_sha: SHA before push (for push events)
        after_sha: SHA after push (for push events)
        inputs: Workflow dispatch inputs (for workflow_dispatch events)

    Examples:
        >>> context = GitHubEventContext.from_json("pull_request", '{"action": "closed", ...}')
        >>> should_skip, reason = context.should_skip()
        >>> checkout_ref = context.get_checkout_ref()
    """

    event_name: str  # workflow_dispatch, pull_request, push

    # For pull_request events
    pr_number: Optional[int] = None
    pr_merged: bool = False
    pr_labels: List[str] = field(default_factory=list)
    base_ref: Optional[str] = None  # Branch PR targets
    head_ref: Optional[str] = None  # Branch PR comes from

    # For push events
    ref_name: Optional[str] = None  # Branch pushed to (extracted from ref)
    before_sha: Optional[str] = None
    after_sha: Optional[str] = None

    # For workflow_dispatch
    inputs: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, event_name: str, event_json: str) -> 'GitHubEventContext':
        """Parse GitHub event JSON into structured context.

        Args:
            event_name: The GitHub event name (e.g., "pull_request", "push")
            event_json: The JSON payload from ${{ toJson(github.event) }}

        Returns:
            GitHubEventContext with all relevant fields extracted

        Raises:
            json.JSONDecodeError: If event_json is not valid JSON

        Examples:
            >>> context = GitHubEventContext.from_json(
            ...     "pull_request",
            ...     '{"action": "closed", "pull_request": {"merged": true, "number": 42}}'
            ... )
            >>> context.pr_number
            42
            >>> context.pr_merged
            True
        """
        event = json.loads(event_json) if event_json else {}

        context = cls(event_name=event_name)

        if event_name == "pull_request":
            context._parse_pull_request_event(event)
        elif event_name == "push":
            context._parse_push_event(event)
        elif event_name == "workflow_dispatch":
            context._parse_workflow_dispatch_event(event)

        return context

    def _parse_pull_request_event(self, event: dict) -> None:
        """Extract fields from pull_request event payload.

        Args:
            event: The parsed event JSON
        """
        pr = event.get("pull_request", {})
        self.pr_number = pr.get("number")
        self.pr_merged = pr.get("merged", False)
        self.base_ref = pr.get("base", {}).get("ref")
        self.head_ref = pr.get("head", {}).get("ref")

        # Extract labels (can be list of dicts with "name" key or strings)
        labels_data = pr.get("labels", [])
        for label in labels_data:
            if isinstance(label, dict):
                self.pr_labels.append(label.get("name", ""))
            else:
                self.pr_labels.append(str(label))

    def _parse_push_event(self, event: dict) -> None:
        """Extract fields from push event payload.

        Args:
            event: The parsed event JSON
        """
        # ref is like "refs/heads/main" - extract just the branch name
        ref = event.get("ref", "")
        if ref.startswith("refs/heads/"):
            self.ref_name = ref[len("refs/heads/"):]
        else:
            self.ref_name = ref

        self.before_sha = event.get("before")
        self.after_sha = event.get("after")

    def _parse_workflow_dispatch_event(self, event: dict) -> None:
        """Extract fields from workflow_dispatch event payload.

        Args:
            event: The parsed event JSON
        """
        self.inputs = event.get("inputs", {}) or {}
        # Also capture the ref for workflow_dispatch (branch that triggered it)
        ref = event.get("ref", "")
        if ref.startswith("refs/heads/"):
            self.ref_name = ref[len("refs/heads/"):]
        else:
            self.ref_name = ref

    def should_skip(self, required_label: str = "claudechain") -> Tuple[bool, str]:
        """Determine if ClaudeChain should skip this event.

        Checks various conditions to determine if ClaudeChain should not
        process this event. Different event types have different skip criteria.

        Args:
            required_label: Label required on PR for processing (default: "claudechain")

        Returns:
            Tuple of (should_skip: bool, reason: str)
            - If should_skip is False, reason will be empty string
            - If should_skip is True, reason explains why

        Examples:
            >>> context = GitHubEventContext(event_name="pull_request", pr_merged=False)
            >>> context.should_skip()
            (True, 'PR was closed but not merged')

            >>> context = GitHubEventContext(event_name="pull_request", pr_merged=True, pr_labels=["claudechain"])
            >>> context.should_skip()
            (False, '')
        """
        if self.event_name == "pull_request":
            # Skip if PR was not merged
            if not self.pr_merged:
                return (True, "PR was closed but not merged")

            # Skip if missing required label
            if required_label and required_label not in self.pr_labels:
                return (True, f"PR does not have required label '{required_label}'")

        # workflow_dispatch and push events don't have skip conditions
        # (they're always intentional triggers)

        return (False, "")

    def get_checkout_ref(self) -> str:
        """Determine which git ref to checkout.

        Returns the appropriate git reference to checkout based on the event type:
        - For push events: the branch that was pushed to
        - For pull_request events: the base branch (target of the PR)
        - For workflow_dispatch: the branch that triggered the workflow

        Returns:
            Git reference (branch name) to checkout

        Raises:
            ValueError: If no suitable ref can be determined

        Examples:
            >>> context = GitHubEventContext(event_name="push", ref_name="main")
            >>> context.get_checkout_ref()
            'main'

            >>> context = GitHubEventContext(event_name="pull_request", base_ref="main")
            >>> context.get_checkout_ref()
            'main'
        """
        if self.event_name == "push":
            if self.ref_name:
                return self.ref_name
            raise ValueError("Push event missing ref_name")

        if self.event_name == "pull_request":
            if self.base_ref:
                return self.base_ref
            raise ValueError("Pull request event missing base_ref")

        if self.event_name == "workflow_dispatch":
            if self.ref_name:
                return self.ref_name
            raise ValueError("Workflow dispatch event missing ref")

        raise ValueError(f"Unknown event type: {self.event_name}")

    def get_default_base_branch(self) -> str:
        """Get default base branch from event context.

        Determines the appropriate base branch for PR creation based on
        the event context. This is where ClaudeChain PRs should target.

        Returns:
            Branch name to use as base branch for new PRs

        Raises:
            ValueError: If no base branch can be determined

        Examples:
            >>> context = GitHubEventContext(event_name="pull_request", base_ref="develop")
            >>> context.get_default_base_branch()
            'develop'
        """
        # For all event types, we want to target the same branch
        # that was pushed to or that the workflow was triggered from
        return self.get_checkout_ref()

    def get_changed_files_context(self) -> Optional[Tuple[str, str]]:
        """Get refs for detecting changed files via GitHub Compare API.

        For push events, returns the before and after SHAs.
        For pull_request events, returns the base and head branch names.
        This enables project detection by looking for modified spec.md files.

        Returns:
            Tuple of (base_ref, head_ref) for push/pull_request events, None otherwise.
            The caller can use these refs with the GitHub Compare API.

        Examples:
            >>> context = GitHubEventContext(
            ...     event_name="push",
            ...     before_sha="abc123",
            ...     after_sha="def456"
            ... )
            >>> context.get_changed_files_context()
            ('abc123', 'def456')

            >>> context = GitHubEventContext(
            ...     event_name="pull_request",
            ...     base_ref="main",
            ...     head_ref="feature-branch"
            ... )
            >>> context.get_changed_files_context()
            ('main', 'feature-branch')

            >>> context = GitHubEventContext(event_name="workflow_dispatch")
            >>> context.get_changed_files_context()
            None
        """
        if self.event_name == "push" and self.before_sha and self.after_sha:
            return (self.before_sha, self.after_sha)
        if self.event_name == "pull_request" and self.base_ref and self.head_ref:
            return (self.base_ref, self.head_ref)
        return None

    def has_label(self, label: str) -> bool:
        """Check if the PR has a specific label.

        Args:
            label: Label name to check for

        Returns:
            True if the PR has the label, False otherwise

        Examples:
            >>> context = GitHubEventContext(pr_labels=["claudechain", "bug"])
            >>> context.has_label("claudechain")
            True
            >>> context.has_label("feature")
            False
        """
        return label in self.pr_labels
