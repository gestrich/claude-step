"""Shared fixtures for E2E integration tests.

This module provides pytest fixtures used across E2E tests, including
GitHub helper instances, test project management, and cleanup utilities.
"""

import uuid
import pytest
from pathlib import Path
from typing import Generator, List

from .helpers.github_helper import GitHubHelper
from .helpers.project_manager import TestProjectManager
from .helpers.test_branch_manager import TestBranchManager


@pytest.fixture
def gh() -> GitHubHelper:
    """Provide a GitHubHelper instance for tests.

    Returns:
        Configured GitHubHelper instance for claude-step repository
    """
    return GitHubHelper(repo="gestrich/claude-step")


@pytest.fixture
def project_id() -> str:
    """Generate a unique project ID for test isolation.

    Returns:
        Unique 8-character hex string
    """
    return uuid.uuid4().hex[:8]


@pytest.fixture
def project_manager() -> TestProjectManager:
    """Provide a TestProjectManager instance.

    Returns:
        Configured TestProjectManager instance
    """
    return TestProjectManager()


@pytest.fixture
def test_project() -> str:
    """Provide the permanent E2E test project name.

    This fixture returns the name of the permanent test project that exists
    in the main branch at claude-step/e2e-test-project/.

    With the new spec-file-source-of-truth design, test projects must exist
    in the main branch. Instead of creating temporary projects, E2E tests now
    use a permanent test project with 300+ tasks.

    Returns:
        Project name: "e2e-test-project"
    """
    return "e2e-test-project"


@pytest.fixture
def cleanup_prs(gh: GitHubHelper) -> Generator[List[int], None, None]:
    """Track and cleanup PRs created during tests.

    Usage in tests:
        def test_something(cleanup_prs):
            # Create PR
            pr_number = create_pr()
            cleanup_prs.append(pr_number)
            # Test continues...

    Yields:
        List to append PR numbers to for cleanup
    """
    pr_numbers: List[int] = []

    try:
        yield pr_numbers
    finally:
        # Cleanup: close all tracked PRs
        for pr_number in pr_numbers:
            try:
                gh.close_pull_request(pr_number)
            except Exception as e:
                print(f"Warning: Failed to close PR #{pr_number}: {e}")


@pytest.fixture(scope="session", autouse=True)
def test_branch():
    """Ensure test branch exists before running tests.

    This fixture validates that the e2e-test branch has been set up
    by the E2E test workflow before tests run. The branch should already
    be created and configured by the workflow.

    Yields:
        None - Just ensures branch validation happens
    """
    # Branch should already be set up by workflow
    # This fixture provides a place to add validation if needed in the future
    manager = TestBranchManager()
    # Could add validation here to ensure branch exists
    yield
    # Cleanup handled by workflow


@pytest.fixture(scope="session", autouse=True)
def cleanup_previous_test_runs():
    """Clean up resources from previous failed test runs.

    This fixture runs once before all tests to ensure a clean state,
    making tests more reliable by cleaning up leftover branches and PRs
    from previous failed runs.

    Yields:
        None - Just ensures cleanup happens before tests
    """
    gh = GitHubHelper(repo="gestrich/claude-step")

    # Clean up test branches from previous failed runs
    gh.cleanup_test_branches(pattern_prefix="claude-step-test-")

    # Clean up test PRs from previous failed runs
    gh.cleanup_test_prs(title_prefix="ClaudeStep")

    yield
    # Post-test cleanup handled by individual test fixtures
