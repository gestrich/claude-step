"""Shared fixtures for E2E integration tests.

This module provides pytest fixtures used across E2E tests, including
GitHub helper instances, test project management, and cleanup utilities.
"""

import uuid
import pytest


# =============================================================================
# E2E TESTS TEMPORARILY DISABLED
# =============================================================================
# These tests are disabled because they require a specific GitHub Actions
# environment and workflow setup that is not always available. The tests
# interact with real GitHub workflows and can fail due to external factors
# (workflow timeouts, GitHub API issues, etc.).
#
# To re-enable: Remove this hook function.
# =============================================================================
def pytest_collection_modifyitems(config, items):
    """Skip all E2E tests - temporarily disabled."""
    skip_e2e = pytest.mark.skip(reason="E2E tests temporarily disabled - see conftest.py")
    for item in items:
        if "/e2e/" in str(item.fspath):
            item.add_marker(skip_e2e)
from pathlib import Path
from typing import Generator, List

from .helpers.github_helper import GitHubHelper
from .helpers.project_manager import TestProjectManager
from .helpers.test_branch_manager import TestBranchManager
from .constants import E2E_TEST_BRANCH


@pytest.fixture
def gh() -> GitHubHelper:
    """Provide a GitHubHelper instance for tests.

    Returns:
        Configured GitHubHelper instance for claude-chain repository
    """
    return GitHubHelper(repo="gestrich/claude-chain")


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
def test_spec_content() -> str:
    """Return spec.md content for E2E tests with minimal AI cost.

    Uses simple print statements to minimize AI processing time and cost.
    Each task just prints a variation of "Hello World" - no actual code changes needed.
    """
    return """# E2E Test Project

**NOTE**: This is a test spec designed to minimize AI processing cost.
No actual code changes are required - just print statements to verify the workflow.

## Tasks

- [ ] Task 1: Print hello - Use the AI to print "Hello, World!" to the console. No code files needed.
- [ ] Task 2: Print greeting - Use the AI to print "Hello, E2E Test!" to the console. No code files needed.
- [ ] Task 3: Print farewell - Use the AI to print "Goodbye, World!" to the console. No code files needed.
"""


@pytest.fixture
def test_config_content() -> str:
    """Return configuration.yml content for E2E tests."""
    return """reviewers:
  - username: gestrich
    maxOpenPRs: 5
baseBranch: main-e2e
"""


@pytest.fixture
def test_pr_template_content() -> str:
    """Return pr-template.md content for E2E tests."""
    return """## Changes

{changes}

## Testing

This is an E2E test PR - no manual testing required.
"""


@pytest.fixture
def test_project(project_id: str) -> str:
    """Generate a unique test project name for this test run.

    This fixture generates a dynamic project name instead of using a permanent
    test project. The generated project will be created on the main-e2e branch
    during test setup.

    Args:
        project_id: Unique 8-character hex string from project_id fixture

    Returns:
        Project name: "e2e-test-{uuid}"
    """
    return f"e2e-test-{project_id}"


@pytest.fixture
def setup_test_project(
    test_project: str,
    test_spec_content: str,
    test_config_content: str,
    test_pr_template_content: str,
    project_manager: TestProjectManager,
    gh: GitHubHelper
) -> str:
    """Create and push a test project to main-e2e branch, then trigger workflow.

    This fixture dynamically generates a test project from the content fixtures
    and commits it to the main-e2e branch. It then explicitly triggers the
    claudechain.yml workflow via workflow_dispatch.

    Note: We must explicitly trigger the workflow because pushes made with
    GITHUB_TOKEN do not trigger push events (GitHub security feature to prevent
    infinite loops). Since Sep 2022, GITHUB_TOKEN can trigger workflow_dispatch.

    Args:
        test_project: Unique project name from test_project fixture
        test_spec_content: Content for spec.md
        test_config_content: Content for configuration.yml
        test_pr_template_content: Content for pr-template.md
        project_manager: TestProjectManager instance
        gh: GitHubHelper instance for triggering workflow

    Returns:
        Project name that was created
    """
    # Create project with provided content
    project_manager.create_test_project(
        project_name=test_project,
        spec_content=test_spec_content,
        config_content=test_config_content,
        pr_template_content=test_pr_template_content
    )

    # Commit and push to main-e2e branch
    project_manager.commit_and_push_project(
        project_name=test_project,
        branch=E2E_TEST_BRANCH
    )

    # Explicitly trigger claudechain.yml via workflow_dispatch
    # Push events from GITHUB_TOKEN don't trigger workflows (GitHub security feature)
    gh.trigger_workflow(
        workflow_name="claudechain.yml",
        inputs={"project_name": test_project},
        ref=E2E_TEST_BRANCH
    )

    return test_project


@pytest.fixture(scope="session", autouse=True)
def test_branch():
    """Ensure test branch exists before running tests.

    This fixture validates that the main-e2e branch has been set up
    by the E2E test workflow before tests run. The branch should already
    be created and configured by the workflow.

    The branch name is defined by the E2E_TEST_BRANCH constant to ensure
    consistency across all E2E test helpers and fixtures.

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
    """Clean up resources from previous test runs at test start.

    This fixture runs once before all tests to ensure a clean state.
    Cleanup at test START (not end) allows manual inspection of test results.

    Cleanup tasks:
    - Delete old main-e2e branch if it exists
    - Create fresh main-e2e branch from main
    - Close any open PRs with "claudechain" label
    - Remove "claudechain" label from ALL PRs (open and closed)
    - Clean up test branches from previous failed runs

    Yields:
        None - Just ensures cleanup happens before tests
    """
    gh = GitHubHelper(repo="gestrich/claude-chain")
    from .helpers.test_branch_manager import TestBranchManager

    # Delete old main-e2e branch and create a fresh one
    branch_manager = TestBranchManager()
    try:
        branch_manager.setup_test_branch()
    except Exception as e:
        print(f"Warning: Failed to set up test branch: {e}")
        # Continue anyway - the branch might already exist
        pass

    # Clean up test branches from previous failed runs
    gh.cleanup_test_branches(pattern_prefix="claude-chain-test-")

    # Get all PRs with claudechain label (both open and closed)
    from claudechain.domain.constants import DEFAULT_PR_LABEL
    from claudechain.infrastructure.github.operations import list_pull_requests

    # Close open PRs with claudechain label
    try:
        open_prs = list_pull_requests(
            repo=gh.repo,
            state="open",
            label=DEFAULT_PR_LABEL,
            limit=100
        )
        for pr in open_prs:
            try:
                gh.close_pull_request(pr.number)
            except Exception as e:
                print(f"Warning: Failed to close PR #{pr.number}: {e}")
    except Exception as e:
        print(f"Warning: Failed to list open PRs: {e}")

    # Remove claudechain label from ALL PRs (open and closed)
    try:
        all_prs = list_pull_requests(
            repo=gh.repo,
            state="all",
            label=DEFAULT_PR_LABEL,
            limit=100
        )
        for pr in all_prs:
            try:
                gh.remove_label_from_pr(pr.number, DEFAULT_PR_LABEL)
            except Exception as e:
                # Label might not exist on the PR, which is fine
                pass
    except Exception as e:
        print(f"Warning: Failed to remove labels from PRs: {e}")

    yield
    # No post-test cleanup - artifacts remain for manual inspection
