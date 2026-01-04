"""Unit tests for configuration loading and validation"""

import pytest
from pathlib import Path

from claudechain.domain.config import (
    load_config,
    substitute_template,
    validate_spec_format,
)
from claudechain.domain.exceptions import ConfigurationError, FileNotFoundError


class TestLoadConfig:
    """Test suite for YAML configuration loading"""

    def test_load_valid_config_file(self, tmp_path):
        """Should load and parse valid YAML configuration"""
        # Arrange
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
""")

        # Act
        config = load_config(str(config_file))

        # Assert
        assert "reviewers" in config
        assert len(config["reviewers"]) == 2
        assert config["reviewers"][0]["username"] == "alice"
        assert config["reviewers"][0]["maxOpenPRs"] == 2

    def test_load_config_raises_error_when_file_not_found(self, tmp_path):
        """Should raise FileNotFoundError when config file doesn't exist"""
        # Arrange
        missing_file = tmp_path / "missing.yml"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="File not found"):
            load_config(str(missing_file))

    def test_load_config_raises_error_for_invalid_yaml(self, tmp_path):
        """Should raise ConfigurationError for malformed YAML"""
        # Arrange
        config_file = tmp_path / "bad_config.yml"
        config_file.write_text("""
reviewers:
  - username: alice
    invalid yaml syntax here: [missing bracket
""")

        # Act & Assert
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            load_config(str(config_file))

    def test_load_config_rejects_deprecated_branch_prefix(self, tmp_path):
        """Should reject configuration with deprecated branchPrefix field"""
        # Arrange
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
branchPrefix: custom-prefix
reviewers:
  - username: alice
    maxOpenPRs: 2
""")

        # Act & Assert
        with pytest.raises(
            ConfigurationError,
            match="'branchPrefix' field is no longer supported"
        ):
            load_config(str(config_file))

    def test_load_config_error_message_explains_branch_prefix_removal(self, tmp_path):
        """Should provide helpful error message about branchPrefix removal"""
        # Arrange
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
branchPrefix: custom
reviewers: []
""")

        # Act & Assert
        with pytest.raises(
            ConfigurationError,
            match="claude-chain-{project}-{index}"
        ):
            load_config(str(config_file))

    def test_load_config_accepts_empty_reviewers_list(self, tmp_path):
        """Should load config with empty reviewers list (validation happens elsewhere)"""
        # Arrange
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
reviewers: []
""")

        # Act
        config = load_config(str(config_file))

        # Assert
        assert "reviewers" in config
        assert config["reviewers"] == []

    def test_load_config_with_additional_fields(self, tmp_path):
        """Should preserve additional configuration fields"""
        # Arrange
        config_file = tmp_path / "config.yml"
        config_file.write_text("""
reviewers:
  - username: alice
    maxOpenPRs: 2
slackWebhook: https://hooks.slack.com/services/xxx
customField: customValue
""")

        # Act
        config = load_config(str(config_file))

        # Assert
        assert config["slackWebhook"] == "https://hooks.slack.com/services/xxx"
        assert config["customField"] == "customValue"


class TestSubstituteTemplate:
    """Test suite for template variable substitution"""

    def test_substitute_single_variable(self):
        """Should substitute a single variable in template"""
        # Arrange
        template = "Hello {{NAME}}"

        # Act
        result = substitute_template(template, NAME="Alice")

        # Assert
        assert result == "Hello Alice"

    def test_substitute_multiple_variables(self):
        """Should substitute multiple variables in template"""
        # Arrange
        template = "Project: {{PROJECT}}, Task: {{TASK_ID}}"

        # Act
        result = substitute_template(template, PROJECT="my-project", TASK_ID="5")

        # Assert
        assert result == "Project: my-project, Task: 5"

    def test_substitute_variable_multiple_times(self):
        """Should substitute the same variable appearing multiple times"""
        # Arrange
        template = "{{NAME}} is working on {{NAME}}'s task"

        # Act
        result = substitute_template(template, NAME="Alice")

        # Assert
        assert result == "Alice is working on Alice's task"

    def test_substitute_with_no_variables(self):
        """Should return template unchanged when no variables provided"""
        # Arrange
        template = "Static text without variables"

        # Act
        result = substitute_template(template)

        # Assert
        assert result == "Static text without variables"

    def test_substitute_leaves_unknown_variables_unchanged(self):
        """Should leave placeholders unchanged if variable not provided"""
        # Arrange
        template = "Hello {{NAME}}, your task is {{TASK_ID}}"

        # Act
        result = substitute_template(template, NAME="Alice")

        # Assert
        assert result == "Hello Alice, your task is {{TASK_ID}}"

    def test_substitute_with_numeric_values(self):
        """Should convert numeric values to strings during substitution"""
        # Arrange
        template = "Task {{INDEX}} of {{TOTAL}}"

        # Act
        result = substitute_template(template, INDEX=5, TOTAL=10)

        # Assert
        assert result == "Task 5 of 10"

    def test_substitute_with_empty_string(self):
        """Should substitute empty string values"""
        # Arrange
        template = "Value: {{VAR}}"

        # Act
        result = substitute_template(template, VAR="")

        # Assert
        assert result == "Value: "

    def test_substitute_preserves_multiline_templates(self):
        """Should preserve newlines in multiline templates"""
        # Arrange
        template = """Line 1: {{VAR1}}
Line 2: {{VAR2}}
Line 3: {{VAR3}}"""

        # Act
        result = substitute_template(template, VAR1="A", VAR2="B", VAR3="C")

        # Assert
        assert result == """Line 1: A
Line 2: B
Line 3: C"""


class TestValidateSpecFormat:
    """Test suite for spec.md format validation"""

    def test_validate_spec_with_unchecked_tasks(self, tmp_path):
        """Should validate spec file with unchecked tasks"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Project Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_with_checked_tasks(self, tmp_path):
        """Should validate spec file with checked tasks"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Project Tasks

- [x] Completed task
- [X] Also completed (capital X)
- [ ] Pending task
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_with_mixed_tasks(self, tmp_path):
        """Should validate spec file with mix of checked and unchecked tasks"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
- [x] Done
- [ ] Not done
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_raises_error_when_file_not_found(self, tmp_path):
        """Should raise FileNotFoundError when spec file doesn't exist"""
        # Arrange
        missing_file = tmp_path / "missing_spec.md"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Spec file not found"):
            validate_spec_format(str(missing_file))

    def test_validate_spec_raises_error_for_no_checklist_items(self, tmp_path):
        """Should raise ConfigurationError when no checklist items found"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Project

This is just some text without any checklist items.
""")

        # Act & Assert
        with pytest.raises(
            ConfigurationError,
            match="No checklist items found"
        ):
            validate_spec_format(str(spec_file))

    def test_validate_spec_error_explains_required_format(self, tmp_path):
        """Should explain required format in error message"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("No tasks here")

        # Act & Assert
        with pytest.raises(
            ConfigurationError,
            match=r"- \[ \].*- \[x\]"
        ):
            validate_spec_format(str(spec_file))

    def test_validate_spec_with_indented_tasks(self, tmp_path):
        """Should validate indented checklist items"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Tasks

  - [ ] Indented task 1
    - [ ] Nested task
  - [x] Completed indented task
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_ignores_non_checklist_bullets(self, tmp_path):
        """Should ignore regular bullet points that aren't checklist items"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
# Notes

- This is a regular bullet point
- Another regular bullet

# Tasks

- [ ] This is a checklist item
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_with_task_at_start_of_line(self, tmp_path):
        """Should match tasks at the start of line without indentation"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("- [ ] Task without indentation")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_with_whitespace_variations(self, tmp_path):
        """Should handle various whitespace patterns in checklist items"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
- [ ] Normal spacing
-  [ ]  Extra spaces
-   [x]   Many spaces
""")

        # Act
        result = validate_spec_format(str(spec_file))

        # Assert
        assert result is True

    def test_validate_spec_with_empty_file(self, tmp_path):
        """Should raise error for empty spec file"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("")

        # Act & Assert
        with pytest.raises(ConfigurationError, match="No checklist items found"):
            validate_spec_format(str(spec_file))
