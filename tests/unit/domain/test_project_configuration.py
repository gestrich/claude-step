"""Unit tests for ProjectConfiguration and Reviewer domain models"""

import pytest

from claudestep.domain.project import Project
from claudestep.domain.project_configuration import (
    Reviewer,
    ProjectConfiguration,
    DEFAULT_PROJECT_PR_LIMIT,
)


class TestDefaultProjectPRLimit:
    """Test suite for DEFAULT_PROJECT_PR_LIMIT constant"""

    def test_default_project_pr_limit_is_one(self):
        """Should have default PR limit of 1 for projects without reviewers"""
        assert DEFAULT_PROJECT_PR_LIMIT == 1


class TestProjectConfigurationDefault:
    """Test suite for ProjectConfiguration.default factory method"""

    def test_default_creates_config_with_empty_reviewers(self):
        """Should create config with empty reviewers list"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.reviewers == []

    def test_default_creates_config_with_no_base_branch(self):
        """Should create config with no base branch override"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.base_branch is None

    def test_default_preserves_project_reference(self):
        """Should preserve the project reference"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.project == project
        assert config.project.name == "my-project"

    def test_default_get_base_branch_returns_workflow_default(self):
        """Default config should fall back to workflow's default base branch"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration.default(project)

        # Act
        base_branch = config.get_base_branch("main")

        # Assert
        assert base_branch == "main"

    def test_default_get_reviewer_usernames_returns_empty_list(self):
        """Default config should return empty reviewer list"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration.default(project)

        # Act
        usernames = config.get_reviewer_usernames()

        # Assert
        assert usernames == []

    def test_default_to_dict_format(self):
        """Default config should serialize correctly"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration.default(project)

        # Act
        result = config.to_dict()

        # Assert
        assert result == {
            "project": "my-project",
            "reviewers": []
        }
        assert "baseBranch" not in result


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


class TestProjectConfigurationBaseBranch:
    """Test suite for ProjectConfiguration base_branch functionality"""

    def test_from_yaml_string_parses_base_branch(self):
        """Should parse baseBranch from YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
baseBranch: develop
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.base_branch == "develop"

    def test_from_yaml_string_base_branch_is_none_when_not_specified(self):
        """Should have None base_branch when not specified in YAML"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
    maxOpenPRs: 2
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.base_branch is None

    def test_get_base_branch_returns_config_value_when_set(self):
        """Should return config's base_branch when it is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            reviewers=[],
            base_branch="develop"
        )

        # Act
        result = config.get_base_branch("main")

        # Assert
        assert result == "develop"

    def test_get_base_branch_returns_default_when_not_set(self):
        """Should return default_base_branch when config's base_branch is not set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            reviewers=[],
            base_branch=None
        )

        # Act
        result = config.get_base_branch("main")

        # Assert
        assert result == "main"

    def test_to_dict_includes_base_branch_when_set(self):
        """Should include baseBranch in dict when base_branch is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            reviewers=[],
            base_branch="develop"
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "baseBranch" in result
        assert result["baseBranch"] == "develop"

    def test_to_dict_excludes_base_branch_when_not_set(self):
        """Should not include baseBranch in dict when base_branch is None"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            reviewers=[],
            base_branch=None
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "baseBranch" not in result

    def test_base_branch_with_special_characters(self):
        """Should handle base_branch with special characters like slashes"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
reviewers:
  - username: alice
baseBranch: feature/my-branch
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.base_branch == "feature/my-branch"
        assert config.get_base_branch("main") == "feature/my-branch"

        # Verify to_dict also handles it correctly
        result = config.to_dict()
        assert result["baseBranch"] == "feature/my-branch"


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
