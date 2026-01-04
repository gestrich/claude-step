"""Common pytest fixtures for ClaudeChain tests

This module provides shared fixtures used across the test suite.
Fixtures are organized by category: file system, git, GitHub, and configuration.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import MagicMock, Mock
import subprocess

import pytest

from tests.builders import ConfigBuilder, SpecFileBuilder, PRDataBuilder


# ==============================================================================
# File System Fixtures
# ==============================================================================


@pytest.fixture
def tmp_project_dir(tmp_path):
    """Fixture providing a temporary project directory structure

    Creates:
        - claude-chain/ directory
        - claude-chain/project-name/ subdirectory

    Returns:
        Path to the claude-chain directory
    """
    claude_chain_dir = tmp_path / "claude-chain"
    claude_chain_dir.mkdir()

    project_dir = claude_chain_dir / "project-name"
    project_dir.mkdir()

    return claude_chain_dir


@pytest.fixture
def sample_spec_file(tmp_path):
    """Fixture providing a sample spec.md file with various task states

    Uses SpecFileBuilder for cleaner test data creation.

    Returns:
        Path to the spec.md file
    """
    return (SpecFileBuilder()
            .with_title("Project Specification")
            .with_overview("This is a sample project for testing.")
            .add_section("## Tasks")
            .add_completed_task("Task 1 - Completed task")
            .add_completed_task("Task 2 - Another completed task")
            .add_task("Task 3 - Next task to do")
            .add_task("Task 4 - Future task")
            .add_task("Task 5 - Another future task")
            .write_to(tmp_path))


@pytest.fixture
def empty_spec_file(tmp_path):
    """Fixture providing an empty spec.md file (no tasks)

    Uses SpecFileBuilder for cleaner test data creation.

    Returns:
        Path to the empty spec.md file
    """
    return (SpecFileBuilder()
            .with_title("Project Specification")
            .with_overview("This project has no tasks yet.")
            .write_to(tmp_path))


@pytest.fixture
def all_completed_spec_file(tmp_path):
    """Fixture providing a spec.md file with all tasks completed

    Uses SpecFileBuilder for cleaner test data creation.

    Returns:
        Path to the spec.md file
    """
    return (SpecFileBuilder()
            .with_title("Project Specification")
            .add_section("## Tasks")
            .add_completed_task("Task 1 - Completed")
            .add_completed_task("Task 2 - Completed")
            .add_completed_task("Task 3 - Completed")
            .write_to(tmp_path))


@pytest.fixture
def sample_config_file(tmp_path):
    """Fixture providing a sample configuration.yml file

    Returns:
        Path to the configuration.yml file with sample reviewer configuration
    """
    config_content = """reviewers:
  - username: alice
    maxOpenPRs: 2
  - username: bob
    maxOpenPRs: 3
  - username: charlie
    maxOpenPRs: 1

project: sample-project
"""
    config_file = tmp_path / "configuration.yml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def config_with_deprecated_field(tmp_path):
    """Fixture providing a config file with deprecated branchPrefix field

    Returns:
        Path to the invalid configuration.yml file
    """
    config_content = """reviewers:
  - username: alice
    maxOpenPRs: 2

branchPrefix: custom-prefix
"""
    config_file = tmp_path / "configuration.yml"
    config_file.write_text(config_content)
    return config_file


# ==============================================================================
# Git Fixtures
# ==============================================================================


@pytest.fixture
def mock_git_repo(tmp_path):
    """Fixture providing a mock git repository

    Creates a real temporary git repository initialized with a main branch.
    Useful for tests that need actual git operations.

    Returns:
        Path to the git repository root
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)

    # Create initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repository")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


@pytest.fixture
def mock_subprocess():
    """Fixture providing a mocked subprocess module

    Returns:
        MagicMock configured for subprocess operations with successful defaults
    """
    mock = MagicMock()
    mock.run.return_value = Mock(
        returncode=0,
        stdout="",
        stderr=""
    )
    return mock


# ==============================================================================
# GitHub Fixtures
# ==============================================================================


@pytest.fixture
def mock_github_api():
    """Fixture providing a mocked GitHub API client

    Returns:
        MagicMock with common GitHub API methods pre-configured
    """
    mock = MagicMock()

    # Default successful responses
    mock.get_open_prs.return_value = []
    mock.create_pull_request.return_value = "123"
    mock.add_pr_comment.return_value = True
    mock.close_pull_request.return_value = True

    return mock


@pytest.fixture
def sample_pr_data():
    """Fixture providing sample PR data structures

    Uses PRDataBuilder for cleaner test data creation.

    Returns:
        Dict containing sample PR response data from GitHub API
    """
    return (PRDataBuilder()
            .with_number(123)
            .with_task(3, "Implement feature", "my-project")
            .with_user("alice")
            .with_created_at("2025-01-15T10:00:00Z")
            .build())


@pytest.fixture
def mock_github_actions_helper():
    """Fixture providing a mocked GitHubActionsHelper

    Returns:
        MagicMock with GitHub Actions helper methods
    """
    from claudechain.infrastructure.github.actions import GitHubActionsHelper

    mock = MagicMock(spec=GitHubActionsHelper)
    mock.write_output = MagicMock()
    mock.write_step_summary = MagicMock()
    mock.set_failed = MagicMock()
    mock.set_notice = MagicMock()

    return mock


@pytest.fixture
def github_env_vars(tmp_path):
    """Fixture providing GitHub Actions environment variables

    Sets up temporary files for GITHUB_OUTPUT and GITHUB_STEP_SUMMARY
    and returns a dict of environment variables to use with patch.dict.

    Returns:
        Dict of environment variables suitable for os.environ patching
    """
    output_file = tmp_path / "github_output.txt"
    summary_file = tmp_path / "github_summary.txt"

    output_file.touch()
    summary_file.touch()

    return {
        "GITHUB_OUTPUT": str(output_file),
        "GITHUB_STEP_SUMMARY": str(summary_file),
        "GITHUB_REPOSITORY": "owner/repo",
        "GITHUB_RUN_ID": "123456789",
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_WORKSPACE": str(tmp_path)
    }


# ==============================================================================
# Configuration Fixtures
# ==============================================================================


@pytest.fixture
def sample_config_dict():
    """Fixture providing a sample configuration dictionary

    Uses ConfigBuilder for cleaner test data creation.

    Returns:
        Dict with valid configuration data
    """
    return ConfigBuilder.default()


@pytest.fixture
def single_reviewer_config():
    """Fixture providing configuration with a single reviewer

    Uses ConfigBuilder for cleaner test data creation.

    Returns:
        Dict with single reviewer configuration
    """
    return ConfigBuilder.single_reviewer()


@pytest.fixture
def no_reviewers_config():
    """Fixture providing configuration with no reviewers

    Returns:
        Dict with empty reviewers list
    """
    return {
        "reviewers": [],
        "project": "sample-project"
    }


# ==============================================================================
# Domain Model Fixtures
# ==============================================================================


@pytest.fixture
def sample_reviewer_config():
    """Fixture providing sample ReviewerConfig objects

    Returns:
        List of reviewer configuration dicts
    """
    return [
        {"username": "alice", "maxOpenPRs": 2},
        {"username": "bob", "maxOpenPRs": 3},
        {"username": "charlie", "maxOpenPRs": 1}
    ]


@pytest.fixture
def sample_task_metadata():
    """Fixture providing sample task metadata

    Returns:
        Dict with task metadata structure
    """
    return {
        "task_index": 3,
        "task_description": "Implement feature X",
        "project": "my-project",
        "reviewer": "alice",
        "branch": "claude-chain-my-project-3",
        "created_at": "2025-01-15T10:00:00Z"
    }


# ==============================================================================
# Test Data Fixtures
# ==============================================================================


@pytest.fixture
def sample_pr_list():
    """Fixture providing a list of sample PRs for testing

    Returns:
        List of PR data dicts with various states
    """
    return [
        {
            "number": 101,
            "title": "Task 1 - First task",
            "state": "closed",
            "merged": True,
            "head": {"ref": "claude-chain-my-project-1"},
            "labels": [{"name": "claude-chain"}]
        },
        {
            "number": 102,
            "title": "Task 2 - Second task",
            "state": "open",
            "merged": False,
            "head": {"ref": "claude-chain-my-project-2"},
            "labels": [{"name": "claude-chain"}]
        },
        {
            "number": 103,
            "title": "Task 3 - Third task",
            "state": "open",
            "merged": False,
            "head": {"ref": "claude-chain-my-project-3"},
            "labels": [{"name": "claude-chain"}]
        }
    ]


@pytest.fixture
def sample_prompt_template():
    """Fixture providing a sample prompt template with placeholders

    Returns:
        String with template placeholders
    """
    return """You are analyzing a pull request.

## Context
- Task: {TASK_DESCRIPTION}
- PR: #{PR_NUMBER}
- Project: {PROJECT}
- Workflow: {WORKFLOW_URL}

## Instructions
Review the changes and provide feedback.
"""
