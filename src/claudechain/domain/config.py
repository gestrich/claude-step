"""Configuration file loading and validation

NOTE: This module currently contains I/O operations which violates domain layer principles.
The file loading logic should be refactored to infrastructure layer in a future phase.
For now, keeping as-is to complete Phase 2 migration.
"""

import os
import re
from typing import Any, Dict

import yaml

from claudechain.domain.exceptions import ConfigurationError, FileNotFoundError


def load_config(file_path: str) -> Dict[str, Any]:
    """Load YAML configuration file and return parsed content

    Args:
        file_path: Path to YAML configuration file (.yml or .yaml)

    Returns:
        Parsed configuration as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ConfigurationError: If file is invalid YAML or contains deprecated fields
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            content = f.read()
        return load_config_from_string(content, file_path)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {file_path}: {str(e)}")


def load_config_from_string(content: str, source_name: str = "config") -> Dict[str, Any]:
    """Load YAML configuration from string content

    Args:
        content: YAML content as string
        source_name: Name of the source (for error messages)

    Returns:
        Parsed configuration as dictionary

    Raises:
        ConfigurationError: If content is invalid YAML or contains deprecated fields
    """
    try:
        config = yaml.safe_load(content)

        # Validate configuration - reject deprecated fields
        if "branchPrefix" in config:
            raise ConfigurationError(
                f"The 'branchPrefix' field is no longer supported. "
                f"ClaudeChain now uses a standard branch format: claude-chain-{{project}}-{{index}}. "
                f"Please remove 'branchPrefix' from {source_name}"
            )

        return config
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {source_name}: {str(e)}")


def substitute_template(template: str, **kwargs) -> str:
    """Substitute {{VARIABLE}} placeholders in template

    Args:
        template: Template string with {{VAR}} placeholders
        **kwargs: Variables to substitute

    Returns:
        Template with substitutions applied
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def validate_spec_format(spec_file: str) -> bool:
    """Validate that spec.md contains checklist items in the correct format

    Args:
        spec_file: Path to spec.md file

    Returns:
        True if valid format (contains at least one checklist item)

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ConfigurationError: If spec file has invalid format
    """
    if not os.path.exists(spec_file):
        raise FileNotFoundError(f"Spec file not found: {spec_file}")

    with open(spec_file, "r") as f:
        content = f.read()

    return validate_spec_format_from_string(content, spec_file)


def validate_spec_format_from_string(content: str, source_name: str = "spec.md") -> bool:
    """Validate that spec content contains checklist items in the correct format

    Args:
        content: Spec content as string
        source_name: Name of the source (for error messages)

    Returns:
        True if valid format (contains at least one checklist item)

    Raises:
        ConfigurationError: If spec has invalid format
    """
    has_checklist_item = False

    for line in content.split('\n'):
        # Check for unchecked or checked task items
        if re.match(r'^\s*- \[[xX ]\]', line):
            has_checklist_item = True
            break

    if not has_checklist_item:
        raise ConfigurationError(
            f"Invalid spec.md format: No checklist items found. "
            f"The file must contain at least one '- [ ]' or '- [x]' item."
        )

    return True
