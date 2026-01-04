"""Unit tests for GitHub domain models

Tests GitHubUser, GitHubPullRequest, and GitHubPullRequestList models
from src/claudechain/domain/github_models.py
"""

import pytest
from datetime import datetime, timezone, timedelta
from claudechain.domain.github_models import (
    GitHubUser,
    GitHubPullRequest,
    GitHubPullRequestList,
)


class TestGitHubUser:
    """Tests for GitHubUser model"""

    def test_user_creation_with_all_fields(self):
        """Should create user with all fields"""
        # Arrange & Act
        user = GitHubUser(
            login="octocat",
            name="The Octocat",
            avatar_url="https://github.com/images/octocat.png"
        )

        # Assert
        assert user.login == "octocat"
        assert user.name == "The Octocat"
        assert user.avatar_url == "https://github.com/images/octocat.png"

    def test_user_creation_with_minimal_fields(self):
        """Should create user with only login (required field)"""
        # Arrange & Act
        user = GitHubUser(login="testuser")

        # Assert
        assert user.login == "testuser"
        assert user.name is None
        assert user.avatar_url is None

    def test_user_from_dict_with_all_fields(self):
        """Should parse user from GitHub API response with all fields"""
        # Arrange
        data = {
            "login": "reviewer1",
            "name": "Reviewer One",
            "avatar_url": "https://avatars.githubusercontent.com/u/123"
        }

        # Act
        user = GitHubUser.from_dict(data)

        # Assert
        assert user.login == "reviewer1"
        assert user.name == "Reviewer One"
        assert user.avatar_url == "https://avatars.githubusercontent.com/u/123"

    def test_user_from_dict_with_minimal_fields(self):
        """Should parse user from GitHub API response with only login"""
        # Arrange
        data = {"login": "minimaluser"}

        # Act
        user = GitHubUser.from_dict(data)

        # Assert
        assert user.login == "minimaluser"
        assert user.name is None
        assert user.avatar_url is None


class TestGitHubPullRequest:
    """Tests for GitHubPullRequest model"""

    def test_pr_creation_with_all_fields(self):
        """Should create PR with all fields"""
        # Arrange
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        merged_at = datetime(2024, 1, 2, 15, 30, 0, tzinfo=timezone.utc)
        assignee = GitHubUser(login="reviewer1")

        # Act
        pr = GitHubPullRequest(
            number=123,
            title="Add new feature",
            state="merged",
            created_at=created_at,
            merged_at=merged_at,
            assignees=[assignee],
            labels=["claudechain", "enhancement"]
        )

        # Assert
        assert pr.number == 123
        assert pr.title == "Add new feature"
        assert pr.state == "merged"
        assert pr.created_at == created_at
        assert pr.merged_at == merged_at
        assert len(pr.assignees) == 1
        assert pr.assignees[0].login == "reviewer1"
        assert pr.labels == ["claudechain", "enhancement"]

    def test_pr_from_dict_with_open_state(self):
        """Should parse open PR from GitHub API response"""
        # Arrange
        data = {
            "number": 456,
            "title": "Fix bug",
            "state": "OPEN",
            "createdAt": "2024-01-15T10:00:00Z",
            "mergedAt": None,
            "assignees": [
                {"login": "reviewer2", "name": "Reviewer Two"}
            ],
            "labels": [
                {"name": "claudechain"},
                {"name": "bug"}
            ]
        }

        # Act
        pr = GitHubPullRequest.from_dict(data)

        # Assert
        assert pr.number == 456
        assert pr.title == "Fix bug"
        assert pr.state == "open"  # Should be normalized to lowercase
        assert pr.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        assert pr.merged_at is None
        assert len(pr.assignees) == 1
        assert pr.assignees[0].login == "reviewer2"
        assert pr.labels == ["claudechain", "bug"]

    def test_pr_from_dict_with_merged_state(self):
        """Should parse merged PR from GitHub API response"""
        # Arrange
        data = {
            "number": 789,
            "title": "Implement feature",
            "state": "MERGED",
            "createdAt": "2024-02-01T08:00:00Z",
            "mergedAt": "2024-02-02T16:30:00Z",
            "assignees": [],
            "labels": []
        }

        # Act
        pr = GitHubPullRequest.from_dict(data)

        # Assert
        assert pr.number == 789
        assert pr.state == "merged"
        assert pr.merged_at == datetime(2024, 2, 2, 16, 30, 0, tzinfo=timezone.utc)

    def test_pr_from_dict_with_multiple_assignees(self):
        """Should parse PR with multiple assignees"""
        # Arrange
        data = {
            "number": 101,
            "title": "Multi-reviewer PR",
            "state": "OPEN",
            "createdAt": "2024-03-01T12:00:00Z",
            "mergedAt": None,
            "assignees": [
                {"login": "reviewer1"},
                {"login": "reviewer2"},
                {"login": "reviewer3"}
            ],
            "labels": []
        }

        # Act
        pr = GitHubPullRequest.from_dict(data)

        # Assert
        assert len(pr.assignees) == 3
        assert pr.assignees[0].login == "reviewer1"
        assert pr.assignees[1].login == "reviewer2"
        assert pr.assignees[2].login == "reviewer3"

    def test_pr_from_dict_with_string_labels(self):
        """Should handle labels as strings (edge case)"""
        # Arrange
        data = {
            "number": 102,
            "title": "Test PR",
            "state": "OPEN",
            "createdAt": "2024-03-01T12:00:00Z",
            "mergedAt": None,
            "assignees": [],
            "labels": ["label1", "label2"]  # Sometimes labels come as strings
        }

        # Act
        pr = GitHubPullRequest.from_dict(data)

        # Assert
        assert pr.labels == ["label1", "label2"]

    def test_is_merged_with_merged_state(self):
        """Should return True when PR state is merged"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="merged",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            assignees=[]
        )

        # Act & Assert
        assert pr.is_merged() is True

    def test_is_merged_with_merged_at_timestamp(self):
        """Should return True when merged_at is set"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="closed",  # State might be closed but merged_at is set
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            assignees=[]
        )

        # Act & Assert
        assert pr.is_merged() is True

    def test_is_merged_with_open_pr(self):
        """Should return False for open PR"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.is_merged() is False

    def test_is_open_with_open_state(self):
        """Should return True for open PR"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.is_open() is True

    def test_is_open_with_merged_state(self):
        """Should return False for merged PR"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="merged",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),
            assignees=[]
        )

        # Act & Assert
        assert pr.is_open() is False

    def test_is_closed_with_closed_state(self):
        """Should return True for closed (not merged) PR"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="closed",
            created_at=datetime.now(timezone.utc),
            merged_at=None,  # Not merged
            assignees=[]
        )

        # Act & Assert
        assert pr.is_closed() is True

    def test_is_closed_with_merged_pr(self):
        """Should return False for merged PR"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="closed",
            created_at=datetime.now(timezone.utc),
            merged_at=datetime.now(timezone.utc),  # Merged
            assignees=[]
        )

        # Act & Assert
        assert pr.is_closed() is False

    def test_has_label_with_matching_label(self):
        """Should return True when PR has the label"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            labels=["claudechain", "bug", "enhancement"]
        )

        # Act & Assert
        assert pr.has_label("claudechain") is True
        assert pr.has_label("bug") is True

    def test_has_label_without_matching_label(self):
        """Should return False when PR doesn't have the label"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            labels=["claudechain"]
        )

        # Act & Assert
        assert pr.has_label("nonexistent") is False

    def test_get_assignee_logins_with_multiple_assignees(self):
        """Should return list of assignee login names"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[
                GitHubUser(login="alice"),
                GitHubUser(login="bob"),
                GitHubUser(login="charlie")
            ]
        )

        # Act
        logins = pr.get_assignee_logins()

        # Assert
        assert logins == ["alice", "bob", "charlie"]

    def test_get_assignee_logins_with_no_assignees(self):
        """Should return empty list when no assignees"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act
        logins = pr.get_assignee_logins()

        # Assert
        assert logins == []


class TestGitHubPullRequestList:
    """Tests for GitHubPullRequestList collection"""

    def test_creation_with_empty_list(self):
        """Should create empty PR list"""
        # Arrange & Act
        pr_list = GitHubPullRequestList()

        # Assert
        assert pr_list.count() == 0
        assert len(pr_list) == 0

    def test_from_json_array_with_multiple_prs(self):
        """Should parse multiple PRs from GitHub API JSON array"""
        # Arrange
        data = [
            {
                "number": 1,
                "title": "First PR",
                "state": "OPEN",
                "createdAt": "2024-01-01T12:00:00Z",
                "mergedAt": None,
                "assignees": [],
                "labels": []
            },
            {
                "number": 2,
                "title": "Second PR",
                "state": "MERGED",
                "createdAt": "2024-01-02T12:00:00Z",
                "mergedAt": "2024-01-03T15:00:00Z",
                "assignees": [],
                "labels": []
            }
        ]

        # Act
        pr_list = GitHubPullRequestList.from_json_array(data)

        # Assert
        assert pr_list.count() == 2
        assert pr_list.pull_requests[0].number == 1
        assert pr_list.pull_requests[1].number == 2

    def test_filter_by_state_open(self):
        """Should filter PRs by open state"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
            GitHubPullRequest(3, "PR 3", "open", datetime.now(timezone.utc), None, []),
        ])

        # Act
        filtered = pr_list.filter_by_state("open")

        # Assert
        assert filtered.count() == 2
        assert all(pr.state == "open" for pr in filtered.pull_requests)

    def test_filter_by_state_merged(self):
        """Should filter PRs by merged state"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
            GitHubPullRequest(3, "PR 3", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
        ])

        # Act
        filtered = pr_list.filter_by_state("merged")

        # Assert
        assert filtered.count() == 2
        assert all(pr.state == "merged" for pr in filtered.pull_requests)

    def test_filter_by_label(self):
        """Should filter PRs by label"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, [], ["claudechain"]),
            GitHubPullRequest(2, "PR 2", "open", datetime.now(timezone.utc), None, [], ["other"]),
            GitHubPullRequest(3, "PR 3", "open", datetime.now(timezone.utc), None, [], ["claudechain", "bug"]),
        ])

        # Act
        filtered = pr_list.filter_by_label("claudechain")

        # Assert
        assert filtered.count() == 2
        assert all(pr.has_label("claudechain") for pr in filtered.pull_requests)

    def test_filter_merged(self):
        """Should filter only merged PRs"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
            GitHubPullRequest(3, "PR 3", "closed", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(4, "PR 4", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
        ])

        # Act
        filtered = pr_list.filter_merged()

        # Assert
        assert filtered.count() == 2
        assert all(pr.is_merged() for pr in filtered.pull_requests)

    def test_filter_open(self):
        """Should filter only open PRs"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "merged", datetime.now(timezone.utc), datetime.now(timezone.utc), []),
            GitHubPullRequest(3, "PR 3", "open", datetime.now(timezone.utc), None, []),
        ])

        # Act
        filtered = pr_list.filter_open()

        # Assert
        assert filtered.count() == 2
        assert all(pr.is_open() for pr in filtered.pull_requests)

    def test_filter_by_date_created_at(self):
        """Should filter PRs by created_at date"""
        # Arrange
        now = datetime.now(timezone.utc)
        old_date = now - timedelta(days=10)
        recent_date = now - timedelta(days=2)

        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "Old PR", "open", old_date, None, []),
            GitHubPullRequest(2, "Recent PR", "open", recent_date, None, []),
            GitHubPullRequest(3, "Today PR", "open", now, None, []),
        ])

        cutoff = now - timedelta(days=5)

        # Act
        filtered = pr_list.filter_by_date(cutoff, "created_at")

        # Assert
        assert filtered.count() == 2
        assert all(pr.created_at >= cutoff for pr in filtered.pull_requests)

    def test_filter_by_date_merged_at(self):
        """Should filter PRs by merged_at date"""
        # Arrange
        now = datetime.now(timezone.utc)
        old_merge = now - timedelta(days=10)
        recent_merge = now - timedelta(days=2)

        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "Old merged", "merged", old_merge, old_merge, []),
            GitHubPullRequest(2, "Recent merged", "merged", recent_merge, recent_merge, []),
            GitHubPullRequest(3, "Open PR", "open", now, None, []),
        ])

        cutoff = now - timedelta(days=5)

        # Act
        filtered = pr_list.filter_by_date(cutoff, "merged_at")

        # Assert
        assert filtered.count() == 1
        assert filtered.pull_requests[0].number == 2

    def test_group_by_assignee_single_assignee_per_pr(self):
        """Should group PRs by assignee"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None,
                            [GitHubUser("alice")]),
            GitHubPullRequest(2, "PR 2", "open", datetime.now(timezone.utc), None,
                            [GitHubUser("bob")]),
            GitHubPullRequest(3, "PR 3", "open", datetime.now(timezone.utc), None,
                            [GitHubUser("alice")]),
        ])

        # Act
        grouped = pr_list.group_by_assignee()

        # Assert
        assert len(grouped) == 2
        assert len(grouped["alice"]) == 2
        assert len(grouped["bob"]) == 1
        assert grouped["alice"][0].number == 1
        assert grouped["alice"][1].number == 3

    def test_group_by_assignee_multiple_assignees_per_pr(self):
        """Should include PR in multiple groups when it has multiple assignees"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None,
                            [GitHubUser("alice"), GitHubUser("bob")]),
        ])

        # Act
        grouped = pr_list.group_by_assignee()

        # Assert
        assert len(grouped) == 2
        assert len(grouped["alice"]) == 1
        assert len(grouped["bob"]) == 1
        assert grouped["alice"][0].number == 1
        assert grouped["bob"][0].number == 1

    def test_iteration_over_pr_list(self):
        """Should allow iteration over PRs"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "open", datetime.now(timezone.utc), None, []),
        ])

        # Act
        numbers = [pr.number for pr in pr_list]

        # Assert
        assert numbers == [1, 2]

    def test_len_operator(self):
        """Should support len() operator"""
        # Arrange
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(2, "PR 2", "open", datetime.now(timezone.utc), None, []),
            GitHubPullRequest(3, "PR 3", "open", datetime.now(timezone.utc), None, []),
        ])

        # Act & Assert
        assert len(pr_list) == 3

    def test_chaining_filters(self):
        """Should allow chaining multiple filters"""
        # Arrange
        now = datetime.now(timezone.utc)
        pr_list = GitHubPullRequestList(pull_requests=[
            GitHubPullRequest(1, "PR 1", "open", now, None, [], ["claudechain"]),
            GitHubPullRequest(2, "PR 2", "merged", now, now, [], ["claudechain"]),
            GitHubPullRequest(3, "PR 3", "merged", now, now, [], ["other"]),
            GitHubPullRequest(4, "PR 4", "merged", now, now, [], ["claudechain"]),
        ])

        # Act - Chain filters: merged + has label "claudechain"
        filtered = pr_list.filter_merged().filter_by_label("claudechain")

        # Assert
        assert filtered.count() == 2
        assert filtered.pull_requests[0].number == 2
        assert filtered.pull_requests[1].number == 4


class TestGitHubPullRequestPropertyEnhancements:
    """Tests for new properties added to GitHubPullRequest in Phase 2

    Tests the domain model enhancements for parsing ClaudeChain-specific
    information from branch names and PR titles.
    """

    def test_project_name_with_valid_claudechain_branch(self):
        """Should extract project name from valid ClaudeChain branch"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="ClaudeChain: Test task",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="claude-chain-my-refactor-a3f2b891"
        )

        # Act & Assert
        assert pr.project_name == "my-refactor"

    def test_project_name_with_multipart_project_name(self):
        """Should handle project names with hyphens"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="claude-chain-my-complex-refactor-project-f7c4d3e2"
        )

        # Act & Assert
        assert pr.project_name == "my-complex-refactor-project"

    def test_project_name_with_invalid_branch_name(self):
        """Should return None for non-ClaudeChain branch names"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="feature/new-feature"
        )

        # Act & Assert
        assert pr.project_name is None

    def test_project_name_with_main_branch(self):
        """Should return None for main branch"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="main"
        )

        # Act & Assert
        assert pr.project_name is None

    def test_project_name_with_no_branch_name(self):
        """Should return None when head_ref_name is None"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name=None
        )

        # Act & Assert
        assert pr.project_name is None

    def test_task_description_strips_claudechain_prefix(self):
        """Should strip 'ClaudeChain: ' prefix from title"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="ClaudeChain: Add user authentication",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.task_description == "Add user authentication"

    def test_task_description_handles_title_without_prefix(self):
        """Should return title as-is when no ClaudeChain prefix"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Fix bug in login",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.task_description == "Fix bug in login"

    def test_task_description_handles_empty_title(self):
        """Should handle empty title gracefully"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.task_description == ""

    def test_task_description_handles_prefix_only(self):
        """Should handle title that is just the prefix"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="ClaudeChain: ",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.task_description == ""

    def test_task_description_case_sensitive(self):
        """Should only strip exact prefix (case-sensitive)"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="claudechain: Add feature",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[]
        )

        # Act & Assert
        assert pr.task_description == "claudechain: Add feature"

    def test_is_claudechain_pr_with_valid_branch(self):
        """Should return True for valid ClaudeChain branch names"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="claude-chain-my-refactor-a3f2b891"
        )

        # Act & Assert
        assert pr.is_claudechain_pr is True

    def test_is_claudechain_pr_with_feature_branch(self):
        """Should return False for feature branch"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="feature/new-feature"
        )

        # Act & Assert
        assert pr.is_claudechain_pr is False

    def test_is_claudechain_pr_with_main_branch(self):
        """Should return False for main branch"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="main"
        )

        # Act & Assert
        assert pr.is_claudechain_pr is False

    def test_is_claudechain_pr_with_no_branch_name(self):
        """Should return False when head_ref_name is None"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name=None
        )

        # Act & Assert
        assert pr.is_claudechain_pr is False

    def test_is_claudechain_pr_with_similar_branch_name(self):
        """Should return False for branch names similar to but not matching pattern"""
        # Arrange
        pr = GitHubPullRequest(
            number=1,
            title="Test",
            state="open",
            created_at=datetime.now(timezone.utc),
            merged_at=None,
            assignees=[],
            head_ref_name="claude-chain-invalid"  # Missing task index
        )

        # Act & Assert
        assert pr.is_claudechain_pr is False
