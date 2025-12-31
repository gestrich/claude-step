"""Unit tests for ProjectConfiguration and Reviewer domain models"""

import pytest

from claudestep.domain.project import Project
from claudestep.domain.project_configuration import Reviewer, ProjectConfiguration


class TestReviewerInitialization:
    """Test suite for Reviewer dataclass initialization"""

    def test_create_reviewer_with_default_max_prs(self):
        """Should create reviewer with default max_open_prs value"""
        # Arrange & Act
        reviewer = Reviewer(username="alice")

        # Assert
        assert reviewer.username == "alice"
        assert reviewer.max_open_prs == 2  # Default value

    def test_create_reviewer_with_custom_max_prs(self):
        """Should create reviewer with custom max_open_prs value"""
        # Arrange & Act
        reviewer = Reviewer(username="bob", max_open_prs=5)

        # Assert
        assert reviewer.username == "bob"
        assert reviewer.max_open_prs == 5


class TestReviewerFromDict:
    """Test suite for Reviewer.from_dict factory method"""

    def test_from_dict_with_all_fields(self):
        """Should parse reviewer from complete dictionary"""
        # Arrange
        data = {
            "username": "alice",
            "maxOpenPRs": 3
        }

        # Act
        reviewer = Reviewer.from_dict(data)

        # Assert
        assert reviewer.username == "alice"
        assert reviewer.max_open_prs == 3

    def test_from_dict_with_missing_max_open_prs(self):
        """Should use default max_open_prs when not provided"""
        # Arrange
        data = {
            "username": "bob"
        }

        # Act
        reviewer = Reviewer.from_dict(data)

        # Assert
        assert reviewer.username == "bob"
        assert reviewer.max_open_prs == 2  # Default

    def test_from_dict_with_none_username(self):
        """Should handle None username from dictionary"""
        # Arrange
        data = {
            "maxOpenPRs": 3
        }

        # Act
        reviewer = Reviewer.from_dict(data)

        # Assert
        assert reviewer.username is None
        assert reviewer.max_open_prs == 3

    def test_from_dict_preserves_case_sensitivity(self):
        """Should preserve username case sensitivity"""
        # Arrange
        data = {
            "username": "Alice-Smith",
            "maxOpenPRs": 2
        }

        # Act
        reviewer = Reviewer.from_dict(data)

        # Assert
        assert reviewer.username == "Alice-Smith"


class TestReviewerToDict:
    """Test suite for Reviewer.to_dict method"""

    def test_to_dict_returns_correct_format(self):
        """Should convert reviewer to dictionary format"""
        # Arrange
        reviewer = Reviewer(username="alice", max_open_prs=3)

        # Act
        result = reviewer.to_dict()

        # Assert
        assert result == {
            "username": "alice",
            "maxOpenPRs": 3
        }

    def test_to_dict_with_default_max_prs(self):
        """Should include default max_open_prs in dictionary"""
        # Arrange
        reviewer = Reviewer(username="bob")

        # Act
        result = reviewer.to_dict()

        # Assert
        assert result == {
            "username": "bob",
            "maxOpenPRs": 2
        }

    def test_to_dict_roundtrip(self):
        """Should be able to roundtrip through dict conversion"""
        # Arrange
        original = Reviewer(username="charlie", max_open_prs=4)

        # Act
        dict_form = original.to_dict()
        restored = Reviewer.from_dict(dict_form)

        # Assert
        assert restored.username == original.username
        assert restored.max_open_prs == original.max_open_prs


class TestProjectConfigurationFromYamlString:
    """Test suite for ProjectConfiguration.from_yaml_string factory method"""

    def test_from_yaml_string_with_valid_config(self):
        """Should parse valid YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.project == project
        assert len(config.reviewers) == 2
        assert config.reviewers[0].username == "alice"
        assert config.reviewers[0].max_open_prs == 2
        assert config.reviewers[1].username == "bob"
        assert config.reviewers[1].max_open_prs == 3

    def test_from_yaml_string_with_default_max_prs(self):
        """Should use default max_open_prs when not specified"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
  - username: bob
    maxOpenPRs: 4
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert len(config.reviewers) == 2
        assert config.reviewers[0].username == "alice"
        assert config.reviewers[0].max_open_prs == 2  # Default
        assert config.reviewers[1].username == "bob"
        assert config.reviewers[1].max_open_prs == 4

    def test_from_yaml_string_with_empty_reviewers(self):
        """Should handle empty reviewers list"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers: []
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.project == project
        assert config.reviewers == []

    def test_from_yaml_string_with_no_reviewers_key(self):
        """Should handle YAML without reviewers key"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
other_setting: value
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.reviewers == []

    def test_from_yaml_string_filters_reviewers_without_username(self):
        """Should filter out reviewers without username field"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - maxOpenPRs: 3
  - username: bob
    maxOpenPRs: 4
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert len(config.reviewers) == 2
        assert config.reviewers[0].username == "alice"
        assert config.reviewers[1].username == "bob"

    def test_from_yaml_string_with_complex_yaml(self):
        """Should parse YAML with additional fields beyond reviewers"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
settings:
  auto_merge: true
  pr_template: custom
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert len(config.reviewers) == 1


class TestProjectConfigurationGetReviewerUsernames:
    """Test suite for ProjectConfiguration.get_reviewer_usernames method"""

    def test_get_reviewer_usernames_returns_all_usernames(self):
        """Should return list of all reviewer usernames"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
  - username: bob
  - username: charlie
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        usernames = config.get_reviewer_usernames()

        # Assert
        assert usernames == ["alice", "bob", "charlie"]

    def test_get_reviewer_usernames_with_empty_reviewers(self):
        """Should return empty list when no reviewers"""
        # Arrange
        project = Project("my-project")
        yaml_content = "reviewers: []"
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        usernames = config.get_reviewer_usernames()

        # Assert
        assert usernames == []

    def test_get_reviewer_usernames_preserves_order(self):
        """Should preserve order of reviewers"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: zoe
  - username: alice
  - username: mike
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        usernames = config.get_reviewer_usernames()

        # Assert
        assert usernames == ["zoe", "alice", "mike"]


class TestProjectConfigurationGetReviewer:
    """Test suite for ProjectConfiguration.get_reviewer method"""

    def test_get_reviewer_finds_existing_reviewer(self):
        """Should find and return reviewer by username"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        reviewer = config.get_reviewer("bob")

        # Assert
        assert reviewer is not None
        assert reviewer.username == "bob"
        assert reviewer.max_open_prs == 3

    def test_get_reviewer_returns_none_for_non_existent(self):
        """Should return None when reviewer not found"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        reviewer = config.get_reviewer("charlie")

        # Assert
        assert reviewer is None

    def test_get_reviewer_is_case_sensitive(self):
        """Should be case-sensitive when searching for reviewer"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: Alice
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        reviewer_upper = config.get_reviewer("Alice")
        reviewer_lower = config.get_reviewer("alice")

        # Assert
        assert reviewer_upper is not None
        assert reviewer_upper.username == "Alice"
        assert reviewer_lower is None

    def test_get_reviewer_returns_first_match(self):
        """Should return first matching reviewer if duplicates exist"""
        # Arrange
        project = Project("my-project")
        reviewers = [
            Reviewer(username="alice", max_open_prs=2),
            Reviewer(username="alice", max_open_prs=5)
        ]
        config = ProjectConfiguration(
            project=project,
            reviewers=reviewers
        )

        # Act
        reviewer = config.get_reviewer("alice")

        # Assert
        assert reviewer is not None
        assert reviewer.max_open_prs == 2  # First match


class TestProjectConfigurationToDict:
    """Test suite for ProjectConfiguration.to_dict method"""

    def test_to_dict_returns_correct_format(self):
        """Should convert configuration to dictionary format"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
"""
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Act
        result = config.to_dict()

        # Assert
        assert result["project"] == "my-project"
        assert len(result["reviewers"]) == 2
        assert result["reviewers"][0] == {"username": "alice", "maxOpenPRs": 2}
        assert result["reviewers"][1] == {"username": "bob", "maxOpenPRs": 3}

    def test_to_dict_with_empty_reviewers(self):
        """Should handle empty reviewers list"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            reviewers=[]
        )

        # Act
        result = config.to_dict()

        # Assert
        assert result == {
            "project": "my-project",
            "reviewers": []
        }


class TestProjectConfigurationIntegration:
    """Integration tests for ProjectConfiguration with various scenarios"""

    def test_full_workflow_with_multiple_reviewers(self):
        """Should handle complete workflow with multiple reviewers"""
        # Arrange
        project = Project("integration-test")
        yaml_content = """
reviewers:
  - username: dev1
    maxOpenPRs: 1
  - username: dev2
    maxOpenPRs: 2
  - username: dev3
    maxOpenPRs: 3
settings:
  auto_merge: true
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert - Basic properties
        assert config.project.name == "integration-test"
        assert len(config.reviewers) == 3

        # Assert - Usernames extraction
        usernames = config.get_reviewer_usernames()
        assert usernames == ["dev1", "dev2", "dev3"]

        # Assert - Individual reviewer lookup
        dev2 = config.get_reviewer("dev2")
        assert dev2 is not None
        assert dev2.max_open_prs == 2

        # Assert - Conversion to dict
        dict_form = config.to_dict()
        assert dict_form["project"] == "integration-test"
        assert len(dict_form["reviewers"]) == 3
