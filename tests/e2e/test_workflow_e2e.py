"""End-to-End tests for ClaudeStep workflow.

This module contains E2E integration tests that verify the ClaudeStep workflow
creates PRs correctly, generates AI summaries, includes cost information, and
handles reviewer capacity limits.

The tests use a recursive workflow pattern where the claude-step repository
tests itself by triggering the claudestep-test.yml workflow.
"""

import time
import pytest
from typing import List

from .helpers.github_helper import GitHubHelper
from .helpers.project_manager import TestProjectManager


def test_basic_workflow_creates_pr(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep workflow creates a PR for the first task.

    This test:
    1. Creates a test project with a spec containing tasks
    2. Commits and pushes the project to main
    3. Triggers the claudestep-test.yml workflow
    4. Waits for workflow completion
    5. Verifies a PR was created
    6. Verifies the PR has expected content
    7. Cleans up test resources

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        test_project: Test project name from fixture
        cleanup_prs: PR cleanup fixture
    """
    # Commit and push the test project
    project_manager.commit_and_push_project(test_project, branch="main")

    # Trigger the claudestep-test workflow
    gh.trigger_workflow(
        workflow_name="claudestep-test.yml",
        inputs={"project_name": test_project},
        ref="main"
    )

    # Wait a moment for workflow to start
    time.sleep(5)

    # Wait for workflow to complete
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudestep-test.yml",
        timeout=600  # 10 minutes
    )

    assert workflow_run["conclusion"] == "success", \
        "Workflow should complete successfully"

    # Expected branch name for first task
    expected_branch = f"refactor/{test_project}-1"

    # Get the PR that was created
    pr = gh.get_pull_request(expected_branch)

    assert pr is not None, f"PR should be created on branch {expected_branch}"
    assert pr["state"] == "open", "PR should be open"

    # Track PR for cleanup
    cleanup_prs.append(pr["number"])

    # Verify PR has a title
    assert pr["title"], "PR should have a title"

    # Verify PR has a body
    assert pr["body"], "PR should have a body/description"

    # Clean up: remove test project from repository
    project_manager.remove_and_commit_project(test_project, branch="main")

    # Clean up: delete the PR branch
    gh.delete_branch(expected_branch)


def test_pr_has_ai_summary(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep adds an AI-generated summary comment to PRs.

    This test verifies that the workflow posts a comment with an AI-generated
    summary of the changes to the PR.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        test_project: Test project name from fixture
        cleanup_prs: PR cleanup fixture
    """
    # Commit and push the test project
    project_manager.commit_and_push_project(test_project, branch="main")

    # Trigger the workflow
    gh.trigger_workflow(
        workflow_name="claudestep-test.yml",
        inputs={"project_name": test_project},
        ref="main"
    )

    # Wait for workflow completion
    time.sleep(5)
    gh.wait_for_workflow_completion(
        workflow_name="claudestep-test.yml",
        timeout=600
    )

    # Get the PR
    expected_branch = f"refactor/{test_project}-1"
    pr = gh.get_pull_request(expected_branch)

    assert pr is not None, "PR should exist"
    cleanup_prs.append(pr["number"])

    # Get PR comments
    comments = gh.get_pr_comments(pr["number"])

    # Verify there's at least one comment (AI summary)
    assert len(comments) > 0, "PR should have at least one comment"

    # Look for AI summary indicators in comments
    # The AI summary typically mentions "Summary" or similar
    comment_bodies = [c.get("body", "") for c in comments]
    has_summary = any("Summary" in body or "Changes" in body for body in comment_bodies)

    assert has_summary, "PR should have an AI-generated summary comment"

    # Clean up
    project_manager.remove_and_commit_project(test_project, branch="main")
    gh.delete_branch(expected_branch)


def test_pr_has_cost_information(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep includes cost information in PR comments.

    This test verifies that the workflow posts cost/usage information
    for the AI API calls made during PR generation.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        test_project: Test project name from fixture
        cleanup_prs: PR cleanup fixture
    """
    # Commit and push the test project
    project_manager.commit_and_push_project(test_project, branch="main")

    # Trigger the workflow
    gh.trigger_workflow(
        workflow_name="claudestep-test.yml",
        inputs={"project_name": test_project},
        ref="main"
    )

    # Wait for workflow completion
    time.sleep(5)
    gh.wait_for_workflow_completion(
        workflow_name="claudestep-test.yml",
        timeout=600
    )

    # Get the PR
    expected_branch = f"refactor/{test_project}-1"
    pr = gh.get_pull_request(expected_branch)

    assert pr is not None, "PR should exist"
    cleanup_prs.append(pr["number"])

    # Get PR comments
    comments = gh.get_pr_comments(pr["number"])

    # Look for cost information in comments
    # Cost info typically includes words like "cost", "tokens", "usage", or "$"
    comment_bodies = [c.get("body", "") for c in comments]
    has_cost_info = any(
        "cost" in body.lower() or
        "token" in body.lower() or
        "usage" in body.lower() or
        "$" in body
        for body in comment_bodies
    )

    assert has_cost_info, "PR should have cost/usage information in comments"

    # Clean up
    project_manager.remove_and_commit_project(test_project, branch="main")
    gh.delete_branch(expected_branch)


def test_reviewer_capacity_limits(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    project_id: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep respects reviewer capacity limits.

    This test creates a project with multiple tasks and a reviewer capacity
    limit, then verifies that the workflow only creates PRs up to the limit.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        project_id: Unique project ID fixture
        cleanup_prs: PR cleanup fixture
    """
    # Create a project with multiple tasks and capacity limit of 2
    spec_content = """# Test Project Spec

## Tasks

- [ ] Task 1: First task - First task description.
- [ ] Task 2: Second task - Second task description.
- [ ] Task 3: Third task - Third task description.
- [ ] Task 4: Fourth task - Fourth task description.
"""

    config_content = """reviewers:
  - username: octocat
    maxOpenPRs: 2
"""

    project_name = project_manager.create_test_project(
        project_id=project_id,
        spec_content=spec_content,
        config_content=config_content
    )

    try:
        # Commit and push the test project
        project_manager.commit_and_push_project(project_name, branch="main")

        # Trigger the workflow
        gh.trigger_workflow(
            workflow_name="claudestep-test.yml",
            inputs={"project_name": project_name},
            ref="main"
        )

        # Wait for workflow completion
        time.sleep(5)
        gh.wait_for_workflow_completion(
            workflow_name="claudestep-test.yml",
            timeout=600
        )

        # Check how many PRs were created
        # With max_prs_per_reviewer=2, only 2 PRs should be created
        created_prs = []
        for i in range(1, 5):  # Check for tasks 1-4
            branch = f"refactor/{project_name}-{i}"
            pr = gh.get_pull_request(branch)
            if pr:
                created_prs.append(pr)
                cleanup_prs.append(pr["number"])

        # Verify only 2 PRs were created (respecting capacity limit)
        assert len(created_prs) == 2, \
            f"Expected 2 PRs (capacity limit), but found {len(created_prs)}"

        # Clean up branches
        for i in range(1, len(created_prs) + 1):
            branch = f"refactor/{project_name}-{i}"
            gh.delete_branch(branch)

    finally:
        # Clean up: remove test project
        project_manager.remove_and_commit_project(project_name, branch="main")


def test_merge_triggered_workflow(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test that merging a PR triggers creation of the next PR.

    This test verifies the workflow is triggered when a PR is merged,
    creating a PR for the next task in the spec.

    Note: This test is more complex as it requires actually merging a PR,
    which may require specific repository permissions. This is a placeholder
    implementation that documents the expected behavior.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        test_project: Test project name from fixture
        cleanup_prs: PR cleanup fixture
    """
    pytest.skip("Merge-triggered workflow test requires PR merge permissions")

    # TODO: Implement this test when we have the ability to merge PRs
    # The test should:
    # 1. Create a test project with multiple tasks
    # 2. Trigger workflow to create first PR
    # 3. Merge the first PR
    # 4. Verify workflow is triggered on merge
    # 5. Verify second PR is created
    # 6. Clean up


def test_workflow_handles_empty_spec(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    project_id: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep handles a spec with no tasks gracefully.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        project_id: Unique project ID fixture
        cleanup_prs: PR cleanup fixture
    """
    # Create a project with no incomplete tasks
    spec_content = """# Test Project Spec

## Tasks

- [x] Completed task - This task is already done.
"""

    project_name = project_manager.create_test_project(
        project_id=project_id,
        spec_content=spec_content
    )

    try:
        # Commit and push the test project
        project_manager.commit_and_push_project(project_name, branch="main")

        # Trigger the workflow
        gh.trigger_workflow(
            workflow_name="claudestep-test.yml",
            inputs={"project_name": project_name},
            ref="main"
        )

        # Wait for workflow completion
        time.sleep(5)
        workflow_run = gh.wait_for_workflow_completion(
            workflow_name="claudestep-test.yml",
            timeout=600
        )

        # Workflow should complete (though it might not create PRs)
        assert workflow_run["conclusion"] == "success", \
            "Workflow should complete successfully even with no tasks"

        # Verify no PRs were created
        pr = gh.get_pull_request(f"refactor/{project_name}-1")
        assert pr is None, "No PR should be created when there are no tasks"

    finally:
        # Clean up
        project_manager.remove_and_commit_project(project_name, branch="main")
