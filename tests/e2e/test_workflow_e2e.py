"""End-to-End tests for ClaudeStep workflow.

This module contains E2E integration tests that verify the ClaudeStep workflow
creates PRs correctly, generates AI summaries, includes cost information, and
handles edge cases like empty specs.

The tests use a recursive workflow pattern where the claude-step repository
tests itself by triggering the claudestep.yml workflow.

Note: These tests have been optimized to reduce redundant workflow executions.
The main workflow test (test_basic_workflow_end_to_end) validates PR creation,
AI summaries, and cost information in a single test run.

TESTS IN THIS MODULE:

1. test_basic_workflow_end_to_end
   - What: Verifies complete workflow execution (spec → PR with summary + cost)
   - Why E2E: Tests integration of all workflow steps and GitHub API interactions

2. test_reviewer_capacity_limits
   - What: Verifies reviewer maxOpenPRs capacity enforcement across multiple runs
   - Why E2E: Tests integration between reviewer management and PR creation

3. test_merge_triggered_workflow (SKIPPED)
   - What: Would verify merge triggers next PR creation
   - Why E2E: Would test GitHub Actions trigger-on-merge integration

4. test_workflow_handles_empty_spec
   - What: Verifies workflow gracefully handles specs with no tasks
   - Why E2E: Tests edge case in complete workflow execution
"""

import time
import pytest
from typing import List

from .helpers.github_helper import GitHubHelper
from .helpers.project_manager import TestProjectManager


def test_basic_workflow_end_to_end(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test complete ClaudeStep workflow: spec → PR with summary and cost info.

    This consolidated test verifies the entire E2E workflow by:
    1. Creating a test project with a spec containing tasks
    2. Committing and pushing the project to e2e-test branch
    3. Triggering the claudestep.yml workflow
    4. Waiting for workflow completion
    5. Verifying a PR was created with expected content
    6. Verifying the PR has an AI-generated summary comment
    7. Verifying the PR has cost/usage information
    8. Cleaning up test resources

    This test replaces three separate tests (test_basic_workflow_creates_pr,
    test_pr_has_ai_summary, test_pr_has_cost_information) to reduce redundant
    workflow executions and speed up the E2E test suite.

    Args:
        gh: GitHub helper fixture
        project_manager: Test project manager fixture
        test_project: Test project name from fixture
        cleanup_prs: PR cleanup fixture
    """
    # Commit and push the test project
    project_manager.commit_and_push_project(test_project, branch="e2e-test")

    # Trigger the claudestep-test workflow
    gh.trigger_workflow(
        workflow_name="claudestep.yml",
        inputs={"project_name": test_project},
        ref="e2e-test"
    )

    # Wait a moment for workflow to start
    time.sleep(5)

    # Wait for workflow to complete
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudestep.yml",
        timeout=600  # 10 minutes
    )

    assert workflow_run["conclusion"] == "success", \
        "Workflow should complete successfully"

    # Expected branch name for first task
    expected_branch = f"claude-step-{test_project}-1"

    # Get the PR that was created
    pr = gh.get_pull_request(expected_branch)

    assert pr is not None, f"PR should be created on branch {expected_branch}"
    assert pr["state"] == "OPEN", "PR should be open"

    # Track PR for cleanup
    cleanup_prs.append(pr["number"])

    # Verify PR has a title and body
    assert pr["title"], "PR should have a title"
    assert pr["body"], "PR should have a body/description"

    # Get PR comments for summary and cost verification
    comments = gh.get_pr_comments(pr["number"])

    # Verify there's at least one comment
    assert len(comments) > 0, "PR should have at least one comment"

    # Extract comment bodies for analysis
    comment_bodies = [c.get("body", "") for c in comments]

    # Verify PR has an AI-generated summary comment
    # The AI summary typically mentions "Summary" or "Changes"
    has_summary = any("Summary" in body or "Changes" in body for body in comment_bodies)
    assert has_summary, "PR should have an AI-generated summary comment"

    # Verify PR has cost/usage information
    # Cost info typically includes words like "cost", "tokens", "usage", or "$"
    has_cost_info = any(
        "cost" in body.lower() or
        "token" in body.lower() or
        "usage" in body.lower() or
        "$" in body
        for body in comment_bodies
    )
    assert has_cost_info, "PR should have cost/usage information in comments"

    # Clean up: remove test project from repository
    project_manager.remove_and_commit_project(test_project, branch="e2e-test")

    # Clean up: delete the PR branch
    gh.delete_branch(expected_branch)


def test_reviewer_capacity_limits(
    gh: GitHubHelper,
    project_manager: TestProjectManager,
    project_id: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep respects reviewer capacity limits.

    This test creates a project with multiple tasks and a reviewer capacity
    limit of 2, then verifies that:
    1. The workflow creates PRs up to the capacity limit (2 PRs)
    2. The workflow skips PR creation when reviewer is at capacity

    Note: Each workflow run creates ONE PR. The workflow must be triggered
    multiple times to create multiple PRs up to the capacity limit.

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
  - username: gestrich
    maxOpenPRs: 2
"""

    project_name = project_manager.create_test_project(
        project_id=project_id,
        spec_content=spec_content,
        config_content=config_content
    )

    try:
        # Commit and push the test project
        project_manager.commit_and_push_project(project_name, branch="e2e-test")

        # === First workflow run: should create PR for task 1 ===
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": project_name},
            ref="e2e-test"
        )
        time.sleep(5)
        workflow_run_1 = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=600
        )
        assert workflow_run_1["conclusion"] == "success", \
            "First workflow run should succeed"

        # Verify first PR was created
        pr1 = gh.get_pull_request(f"claude-step-{project_name}-1")
        assert pr1 is not None, "First PR should be created"
        cleanup_prs.append(pr1["number"])

        # === Second workflow run: should create PR for task 2 ===
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": project_name},
            ref="e2e-test"
        )
        time.sleep(5)
        workflow_run_2 = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=600
        )
        assert workflow_run_2["conclusion"] == "success", \
            "Second workflow run should succeed"

        # Verify second PR was created
        pr2 = gh.get_pull_request(f"claude-step-{project_name}-2")
        assert pr2 is not None, "Second PR should be created"
        cleanup_prs.append(pr2["number"])

        # === Third workflow run: should NOT create PR (at capacity) ===
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": project_name},
            ref="e2e-test"
        )
        time.sleep(5)
        workflow_run_3 = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=600
        )
        # Workflow should still succeed, but not create a PR
        assert workflow_run_3["conclusion"] == "success", \
            "Third workflow run should succeed (but not create PR)"

        # Verify third PR was NOT created (reviewer at capacity)
        pr3 = gh.get_pull_request(f"claude-step-{project_name}-3")
        assert pr3 is None, \
            "Third PR should NOT be created (reviewer at capacity: 2/2)"

        # Verify only 2 PRs exist (respecting capacity limit)
        created_prs = []
        for i in range(1, 5):  # Check for tasks 1-4
            branch = f"claude-step-{project_name}-{i}"
            pr = gh.get_pull_request(branch)
            if pr:
                created_prs.append(pr)

        assert len(created_prs) == 2, \
            f"Expected exactly 2 PRs (capacity limit), but found {len(created_prs)}"

        # Clean up branches
        for i in range(1, len(created_prs) + 1):
            branch = f"claude-step-{project_name}-{i}"
            gh.delete_branch(branch)

    finally:
        # Clean up: remove test project
        project_manager.remove_and_commit_project(project_name, branch="e2e-test")


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
        project_manager.commit_and_push_project(project_name, branch="e2e-test")

        # Trigger the workflow
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": project_name},
            ref="e2e-test"
        )

        # Wait for workflow completion
        time.sleep(5)
        workflow_run = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=600
        )

        # Workflow should complete (though it might not create PRs)
        assert workflow_run["conclusion"] == "success", \
            "Workflow should complete successfully even with no tasks"

        # Verify no PRs were created
        pr = gh.get_pull_request(f"claude-step-{project_name}-1")
        assert pr is None, "No PR should be created when there are no tasks"

    finally:
        # Clean up
        project_manager.remove_and_commit_project(project_name, branch="main")
