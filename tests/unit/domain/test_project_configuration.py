"""Unit tests for ProjectConfiguration domain model"""

import pytest

from claudechain.domain.constants import DEFAULT_STALE_PR_DAYS
from claudechain.domain.project import Project
from claudechain.domain.project_configuration import ProjectConfiguration


class TestProjectConfigurationDefault:
    """Test suite for ProjectConfiguration.default factory method"""

    def test_default_creates_config_with_no_assignee(self):
        """Should create config with no assignee"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.assignee is None

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
        }
        assert "baseBranch" not in result
        assert "assignee" not in result


class TestProjectConfigurationFromYamlString:
    """Test suite for ProjectConfiguration.from_yaml_string factory method"""

    def test_from_yaml_string_with_assignee(self):
        """Should parse assignee from YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.project == project
        assert config.assignee == "alice"

    def test_from_yaml_string_without_assignee(self):
        """Should have None assignee when not specified"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
other_setting: value
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.assignee is None


class TestProjectConfigurationToDict:
    """Test suite for ProjectConfiguration.to_dict method"""

    def test_to_dict_with_assignee(self):
        """Should include assignee in dict when set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            assignee="alice"
        )

        # Act
        result = config.to_dict()

        # Assert
        assert result["project"] == "my-project"
        assert result["assignee"] == "alice"

    def test_to_dict_without_assignee(self):
        """Should not include assignee in dict when not set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            assignee=None
        )

        # Act
        result = config.to_dict()

        # Assert
        assert result == {
            "project": "my-project",
        }
        assert "assignee" not in result


class TestProjectConfigurationBaseBranch:
    """Test suite for ProjectConfiguration base_branch functionality"""

    def test_from_yaml_string_parses_base_branch(self):
        """Should parse baseBranch from YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
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
assignee: alice
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
assignee: alice
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


class TestProjectConfigurationAllowedTools:
    """Test suite for ProjectConfiguration allowed_tools functionality"""

    def test_from_yaml_string_parses_allowed_tools(self):
        """Should parse allowedTools from YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
allowedTools: Write,Read,Edit
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.allowed_tools == "Write,Read,Edit"

    def test_from_yaml_string_allowed_tools_is_none_when_not_specified(self):
        """Should have None allowed_tools when not specified in YAML"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.allowed_tools is None

    def test_get_allowed_tools_returns_config_value_when_set(self):
        """Should return config's allowed_tools when it is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            allowed_tools="Write,Read,Edit"
        )

        # Act
        result = config.get_allowed_tools("Write,Read,Bash,Edit")

        # Assert
        assert result == "Write,Read,Edit"

    def test_get_allowed_tools_returns_default_when_not_set(self):
        """Should return default_allowed_tools when config's allowed_tools is not set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            allowed_tools=None
        )

        # Act
        result = config.get_allowed_tools("Write,Read,Bash,Edit")

        # Assert
        assert result == "Write,Read,Bash,Edit"

    def test_to_dict_includes_allowed_tools_when_set(self):
        """Should include allowedTools in dict when allowed_tools is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            allowed_tools="Write,Read,Edit"
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "allowedTools" in result
        assert result["allowedTools"] == "Write,Read,Edit"

    def test_to_dict_excludes_allowed_tools_when_not_set(self):
        """Should not include allowedTools in dict when allowed_tools is None"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            allowed_tools=None
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "allowedTools" not in result

    def test_allowed_tools_with_granular_bash_permissions(self):
        """Should handle allowed_tools with Bash(command:*) syntax"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
allowedTools: Read,Write,Edit,Bash(git add:*),Bash(git commit:*)
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.allowed_tools == "Read,Write,Edit,Bash(git add:*),Bash(git commit:*)"
        assert config.get_allowed_tools("default") == "Read,Write,Edit,Bash(git add:*),Bash(git commit:*)"

        # Verify to_dict also handles it correctly
        result = config.to_dict()
        assert result["allowedTools"] == "Read,Write,Edit,Bash(git add:*),Bash(git commit:*)"

    def test_default_creates_config_with_no_allowed_tools(self):
        """Should create default config with no allowed_tools override"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.allowed_tools is None

    def test_default_get_allowed_tools_returns_workflow_default(self):
        """Default config should fall back to workflow's default allowed_tools"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration.default(project)

        # Act
        allowed_tools = config.get_allowed_tools("Write,Read,Bash,Edit")

        # Assert
        assert allowed_tools == "Write,Read,Bash,Edit"


class TestProjectConfigurationStalePRDays:
    """Test suite for ProjectConfiguration stale_pr_days functionality"""

    def test_from_yaml_string_parses_stale_pr_days(self):
        """Should parse stalePRDays from YAML configuration"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
stalePRDays: 14
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.stale_pr_days == 14

    def test_from_yaml_string_stale_pr_days_is_none_when_not_specified(self):
        """Should have None stale_pr_days when not specified in YAML"""
        # Arrange
        project = Project("my-project")
        yaml_content = """
assignee: alice
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.stale_pr_days is None

    def test_get_stale_pr_days_returns_config_value_when_set(self):
        """Should return config's stale_pr_days when it is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            stale_pr_days=14
        )

        # Act
        result = config.get_stale_pr_days()

        # Assert
        assert result == 14

    def test_get_stale_pr_days_returns_default_when_not_set(self):
        """Should return default (7 days) when stale_pr_days is not set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            stale_pr_days=None
        )

        # Act
        result = config.get_stale_pr_days()

        # Assert
        assert result == DEFAULT_STALE_PR_DAYS

    def test_get_stale_pr_days_accepts_custom_default(self):
        """Should accept custom default value"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            stale_pr_days=None
        )

        # Act
        result = config.get_stale_pr_days(default=10)

        # Assert
        assert result == 10

    def test_to_dict_includes_stale_pr_days_when_set(self):
        """Should include stalePRDays in dict when stale_pr_days is set"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            stale_pr_days=14
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "stalePRDays" in result
        assert result["stalePRDays"] == 14

    def test_to_dict_excludes_stale_pr_days_when_not_set(self):
        """Should not include stalePRDays in dict when stale_pr_days is None"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration(
            project=project,
            stale_pr_days=None
        )

        # Act
        result = config.to_dict()

        # Assert
        assert "stalePRDays" not in result

    def test_default_creates_config_with_no_stale_pr_days(self):
        """Should create default config with no stale_pr_days override"""
        # Arrange
        project = Project("my-project")

        # Act
        config = ProjectConfiguration.default(project)

        # Assert
        assert config.stale_pr_days is None

    def test_default_get_stale_pr_days_returns_default_value(self):
        """Default config should return the default stale_pr_days value"""
        # Arrange
        project = Project("my-project")
        config = ProjectConfiguration.default(project)

        # Act
        stale_pr_days = config.get_stale_pr_days()

        # Assert
        assert stale_pr_days == DEFAULT_STALE_PR_DAYS


class TestProjectConfigurationIntegration:
    """Integration tests for ProjectConfiguration with various scenarios"""

    def test_full_config_with_all_fields(self):
        """Should handle configuration with all fields set"""
        # Arrange
        project = Project("full-config-test")
        yaml_content = """
assignee: alice
baseBranch: develop
allowedTools: Read,Write,Edit,Bash(npm test:*)
stalePRDays: 14
"""

        # Act
        config = ProjectConfiguration.from_yaml_string(project, yaml_content)

        # Assert
        assert config.project.name == "full-config-test"
        assert config.assignee == "alice"
        assert config.base_branch == "develop"
        assert config.allowed_tools == "Read,Write,Edit,Bash(npm test:*)"
        assert config.stale_pr_days == 14

        # Verify all getters work correctly
        assert config.get_base_branch("main") == "develop"
        assert config.get_allowed_tools("Write,Read,Bash,Edit") == "Read,Write,Edit,Bash(npm test:*)"
        assert config.get_stale_pr_days() == 14

        # Verify to_dict includes all fields
        result = config.to_dict()
        assert result["assignee"] == "alice"
        assert result["baseBranch"] == "develop"
        assert result["allowedTools"] == "Read,Write,Edit,Bash(npm test:*)"
        assert result["stalePRDays"] == 14
