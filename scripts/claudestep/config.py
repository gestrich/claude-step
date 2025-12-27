"""Configuration file loading and validation"""

import json
import os
import re
from typing import Any, Dict

import yaml

from claudestep.exceptions import ConfigurationError, FileNotFoundError


def load_config(file_path: str) -> Dict[str, Any]:
    """Load configuration file (YAML or JSON) and return parsed content

    Args:
        file_path: Path to configuration file (.yml or .json)

    Returns:
        Parsed configuration as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ConfigurationError: If file is invalid
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            if file_path.endswith('.yml') or file_path.endswith('.yaml'):
                return yaml.safe_load(f)
            else:
                return json.load(f)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {file_path}: {str(e)}")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in {file_path}: {str(e)}")


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return parsed content

    Deprecated: Use load_config() instead

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ConfigurationError: If file is invalid JSON
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in {file_path}: {str(e)}")


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

    has_checklist_item = False

    with open(spec_file, "r") as f:
        for line in f:
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
