"""Unit tests for GitHub event context module.

Tests GitHubEventContext from src/claudechain/domain/github_event.py.
Tests cover parsing of different event types, skip logic, and project extraction.
"""

import json
import pytest
from claudechain.domain.github_event import GitHubEventContext


class TestGitHubEventContextParsing:
    """Tests for GitHubEventContext.from_json parsing."""

    def test_parse_workflow_dispatch_event(self):
        """Should parse workflow_dispatch event with inputs."""
        # Arrange
        event_json = json.dumps({
            "inputs": {
                "project_name": "my-refactor"
            },
            "ref": "refs/heads/main"
        })

        # Act
        context = GitHubEventContext.from_json("workflow_dispatch", event_json)

        # Assert
        assert context.event_name == "workflow_dispatch"
        assert context.inputs == {"project_name": "my-refactor"}
        assert context.ref_name == "main"

    def test_parse_workflow_dispatch_with_empty_inputs(self):
        """Should handle workflow_dispatch with no inputs."""
        # Arrange
        event_json = json.dumps({
            "inputs": None,
            "ref": "refs/heads/develop"
        })

        # Act
        context = GitHubEventContext.from_json("workflow_dispatch", event_json)

        # Assert
        assert context.event_name == "workflow_dispatch"
        assert context.inputs == {}
        assert context.ref_name == "develop"

    def test_parse_pull_request_closed_merged(self):
        """Should parse pull_request:closed event when merged."""
        # Arrange
        event_json = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 42,
                "merged": True,
                "base": {"ref": "main"},
                "head": {"ref": "claude-chain-my-project-a3f2b891"},
                "labels": [
                    {"name": "claudechain"},
                    {"name": "enhancement"}
                ]
            }
        })

        # Act
        context = GitHubEventContext.from_json("pull_request", event_json)

        # Assert
        assert context.event_name == "pull_request"
        assert context.pr_number == 42
        assert context.pr_merged is True
        assert context.base_ref == "main"
        assert context.head_ref == "claude-chain-my-project-a3f2b891"
        assert "claudechain" in context.pr_labels
        assert "enhancement" in context.pr_labels

    def test_parse_pull_request_closed_not_merged(self):
        """Should parse pull_request:closed event when not merged."""
        # Arrange
        event_json = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 43,
                "merged": False,
                "base": {"ref": "main"},
                "head": {"ref": "feature/some-feature"},
                "labels": []
            }
        })

        # Act
        context = GitHubEventContext.from_json("pull_request", event_json)

        # Assert
        assert context.pr_number == 43
        assert context.pr_merged is False
        assert context.pr_labels == []

    def test_parse_push_event(self):
        """Should parse push event with ref and shas."""
        # Arrange
        event_json = json.dumps({
            "ref": "refs/heads/main",
            "before": "abc123def456",
            "after": "789xyz000111"
        })

        # Act
        context = GitHubEventContext.from_json("push", event_json)

        # Assert
        assert context.event_name == "push"
        assert context.ref_name == "main"
        assert context.before_sha == "abc123def456"
        assert context.after_sha == "789xyz000111"

    def test_parse_push_event_to_feature_branch(self):
        """Should parse push event to non-main branch."""
        # Arrange
        event_json = json.dumps({
            "ref": "refs/heads/feature/new-feature",
            "before": "000000",
            "after": "111111"
        })

        # Act
        context = GitHubEventContext.from_json("push", event_json)

        # Assert
        assert context.ref_name == "feature/new-feature"

    def test_parse_empty_event_json(self):
        """Should handle empty event JSON gracefully."""
        # Act
        context = GitHubEventContext.from_json("workflow_dispatch", "{}")

        # Assert
        assert context.event_name == "workflow_dispatch"
        assert context.inputs == {}
        assert context.ref_name == ""

    def test_parse_labels_as_strings(self):
        """Should handle labels as plain strings (edge case)."""
        # Arrange
        event_json = json.dumps({
            "pull_request": {
                "number": 1,
                "merged": True,
                "base": {"ref": "main"},
                "head": {"ref": "test"},
                "labels": ["label1", "label2"]
            }
        })

        # Act
        context = GitHubEventContext.from_json("pull_request", event_json)

        # Assert
        assert "label1" in context.pr_labels
        assert "label2" in context.pr_labels


class TestGitHubEventContextShouldSkip:
    """Tests for should_skip logic."""

    def test_should_skip_pr_not_merged(self):
        """Should skip when PR was closed but not merged."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=False,
            pr_labels=["claudechain"]
        )

        # Act
        should_skip, reason = context.should_skip()

        # Assert
        assert should_skip is True
        assert "not merged" in reason.lower()

    def test_should_skip_pr_missing_label(self):
        """Should skip when PR is missing required label."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            pr_labels=["bug", "enhancement"]
        )

        # Act
        should_skip, reason = context.should_skip()

        # Assert
        assert should_skip is True
        assert "claudechain" in reason

    def test_should_not_skip_merged_pr_with_label(self):
        """Should not skip when PR is merged and has required label."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            pr_labels=["claudechain", "enhancement"]
        )

        # Act
        should_skip, reason = context.should_skip()

        # Assert
        assert should_skip is False
        assert reason == ""

    def test_should_skip_with_custom_label(self):
        """Should check for custom label when specified."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            pr_labels=["claudechain"]
        )

        # Act
        should_skip, reason = context.should_skip(required_label="custom-label")

        # Assert
        assert should_skip is True
        assert "custom-label" in reason

    def test_should_not_skip_workflow_dispatch(self):
        """Should not skip workflow_dispatch events."""
        # Arrange
        context = GitHubEventContext(
            event_name="workflow_dispatch",
            inputs={"project_name": "test"}
        )

        # Act
        should_skip, reason = context.should_skip()

        # Assert
        assert should_skip is False
        assert reason == ""

    def test_should_not_skip_push_event(self):
        """Should not skip push events."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name="main"
        )

        # Act
        should_skip, reason = context.should_skip()

        # Assert
        assert should_skip is False
        assert reason == ""

    def test_should_skip_with_no_required_label(self):
        """Should not check for label when required_label is empty."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            pr_labels=[]  # No labels
        )

        # Act
        should_skip, reason = context.should_skip(required_label="")

        # Assert
        assert should_skip is False
        assert reason == ""


class TestGitHubEventContextCheckoutRef:
    """Tests for get_checkout_ref method."""

    def test_checkout_ref_for_push_event(self):
        """Should return branch name for push event."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name="main"
        )

        # Act
        ref = context.get_checkout_ref()

        # Assert
        assert ref == "main"

    def test_checkout_ref_for_push_to_feature_branch(self):
        """Should return feature branch name for push."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name="feature/new-feature"
        )

        # Act
        ref = context.get_checkout_ref()

        # Assert
        assert ref == "feature/new-feature"

    def test_checkout_ref_for_pull_request(self):
        """Should return base branch for pull_request event."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            base_ref="develop",
            head_ref="claude-chain-test-12345678"
        )

        # Act
        ref = context.get_checkout_ref()

        # Assert
        assert ref == "develop"

    def test_checkout_ref_for_workflow_dispatch(self):
        """Should return ref for workflow_dispatch event."""
        # Arrange
        context = GitHubEventContext(
            event_name="workflow_dispatch",
            ref_name="main"
        )

        # Act
        ref = context.get_checkout_ref()

        # Assert
        assert ref == "main"

    def test_checkout_ref_raises_for_push_missing_ref(self):
        """Should raise error when push event has no ref."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name=None
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Push event missing ref_name"):
            context.get_checkout_ref()

    def test_checkout_ref_raises_for_pr_missing_base_ref(self):
        """Should raise error when pull_request event has no base_ref."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            base_ref=None
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Pull request event missing base_ref"):
            context.get_checkout_ref()

    def test_checkout_ref_raises_for_workflow_dispatch_missing_ref(self):
        """Should raise error when workflow_dispatch has no ref."""
        # Arrange
        context = GitHubEventContext(
            event_name="workflow_dispatch",
            ref_name=None
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Workflow dispatch event missing ref"):
            context.get_checkout_ref()

    def test_checkout_ref_raises_for_unknown_event(self):
        """Should raise error for unknown event type."""
        # Arrange
        context = GitHubEventContext(event_name="unknown_event")

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown event type"):
            context.get_checkout_ref()


class TestGitHubEventContextChangedFilesContext:
    """Tests for get_changed_files_context method."""

    def test_returns_shas_for_push_event(self):
        """Should return before/after SHAs for push events."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            before_sha="abc123",
            after_sha="def456"
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result == ("abc123", "def456")

    def test_returns_none_for_workflow_dispatch(self):
        """Should return None for workflow_dispatch events."""
        # Arrange
        context = GitHubEventContext(
            event_name="workflow_dispatch",
            ref_name="main",
            inputs={"project_name": "test"}
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None

    def test_returns_refs_for_pull_request(self):
        """Should return base/head refs for pull_request events."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            base_ref="main",
            head_ref="feature-branch"
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result == ("main", "feature-branch")

    def test_returns_none_for_pull_request_missing_base_ref(self):
        """Should return None for pull_request events without base_ref."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            base_ref=None,
            head_ref="feature-branch"
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None

    def test_returns_none_for_pull_request_missing_head_ref(self):
        """Should return None for pull_request events without head_ref."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_merged=True,
            base_ref="main",
            head_ref=None
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None

    def test_returns_none_when_before_sha_missing(self):
        """Should return None if before_sha is missing."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            before_sha=None,
            after_sha="def456"
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None

    def test_returns_none_when_after_sha_missing(self):
        """Should return None if after_sha is missing."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            before_sha="abc123",
            after_sha=None
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None

    def test_returns_none_when_both_shas_missing(self):
        """Should return None if both SHAs are missing."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name="main"
        )

        # Act
        result = context.get_changed_files_context()

        # Assert
        assert result is None


class TestGitHubEventContextDefaultBaseBranch:
    """Tests for get_default_base_branch method."""

    def test_default_base_branch_from_push(self):
        """Should return pushed branch as default base branch."""
        # Arrange
        context = GitHubEventContext(
            event_name="push",
            ref_name="develop"
        )

        # Act
        base = context.get_default_base_branch()

        # Assert
        assert base == "develop"

    def test_default_base_branch_from_pull_request(self):
        """Should return PR base branch as default base branch."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            base_ref="staging"
        )

        # Act
        base = context.get_default_base_branch()

        # Assert
        assert base == "staging"

    def test_default_base_branch_from_workflow_dispatch(self):
        """Should return workflow dispatch ref as default base branch."""
        # Arrange
        context = GitHubEventContext(
            event_name="workflow_dispatch",
            ref_name="main"
        )

        # Act
        base = context.get_default_base_branch()

        # Assert
        assert base == "main"


class TestGitHubEventContextHasLabel:
    """Tests for has_label helper method."""

    def test_has_label_when_present(self):
        """Should return True when label is present."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_labels=["claudechain", "bug", "enhancement"]
        )

        # Act & Assert
        assert context.has_label("claudechain") is True
        assert context.has_label("bug") is True

    def test_has_label_when_absent(self):
        """Should return False when label is absent."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_labels=["claudechain"]
        )

        # Act & Assert
        assert context.has_label("missing") is False

    def test_has_label_with_empty_labels(self):
        """Should return False when labels list is empty."""
        # Arrange
        context = GitHubEventContext(
            event_name="pull_request",
            pr_labels=[]
        )

        # Act & Assert
        assert context.has_label("any") is False


class TestGitHubEventContextIntegration:
    """Integration tests for complete event processing scenarios."""

    def test_full_pr_merged_workflow(self):
        """Should correctly process a merged PR event end-to-end."""
        # Arrange - simulate a real merged PR event
        event_json = json.dumps({
            "action": "closed",
            "pull_request": {
                "number": 123,
                "merged": True,
                "base": {"ref": "main"},
                "head": {"ref": "claude-chain-auth-refactor-f7c4d3e2"},
                "labels": [{"name": "claudechain"}]
            }
        })

        # Act
        context = GitHubEventContext.from_json("pull_request", event_json)

        # Assert - check all derived values
        assert context.should_skip() == (False, "")
        assert context.get_checkout_ref() == "main"
        assert context.get_default_base_branch() == "main"
        # PR events have changed files context (base/head refs for compare API)
        assert context.get_changed_files_context() == ("main", "claude-chain-auth-refactor-f7c4d3e2")

    def test_full_push_workflow(self):
        """Should correctly process a push event end-to-end."""
        # Arrange
        event_json = json.dumps({
            "ref": "refs/heads/main",
            "before": "abc123",
            "after": "def456"
        })

        # Act
        context = GitHubEventContext.from_json("push", event_json)

        # Assert
        assert context.should_skip() == (False, "")
        assert context.get_checkout_ref() == "main"
        assert context.get_default_base_branch() == "main"
        # Push events have changed files context for project detection
        assert context.get_changed_files_context() == ("abc123", "def456")

    def test_full_workflow_dispatch_workflow(self):
        """Should correctly process a workflow_dispatch event end-to-end."""
        # Arrange
        event_json = json.dumps({
            "inputs": {"project_name": "database-migration"},
            "ref": "refs/heads/develop"
        })

        # Act
        context = GitHubEventContext.from_json("workflow_dispatch", event_json)

        # Assert
        assert context.should_skip() == (False, "")
        assert context.get_checkout_ref() == "develop"
        assert context.get_default_base_branch() == "develop"
        assert context.inputs["project_name"] == "database-migration"
        # workflow_dispatch doesn't have changed files context
        assert context.get_changed_files_context() is None
