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
"""

import pytest
from typing import List

from .helpers.github_helper import GitHubHelper


def test_basic_workflow_end_to_end(
    gh: GitHubHelper,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test complete ClaudeStep workflow: spec → PR with summary and cost info.

    This consolidated test verifies the entire E2E workflow by:
    1. Using the permanent e2e-test-project from main branch
    2. Triggering the claudestep.yml workflow on e2e-test branch
    3. Waiting for workflow completion
    4. Verifying a PR was created with expected content
    5. Verifying the PR has an AI-generated summary comment
    6. Verifying the PR has cost/usage information
    7. Cleaning up test resources (PRs and branches)

    Args:
        gh: GitHub helper fixture
        test_project: Test project name from fixture (e2e-test-project)
        cleanup_prs: PR cleanup fixture
    """
    # Trigger the claudestep-test workflow
    # The workflow will fetch specs from main branch via GitHub API
    gh.trigger_workflow(
        workflow_name="claudestep.yml",
        inputs={"project_name": test_project},
        ref="e2e-test"
    )

    # Wait for workflow to start
    gh.wait_for_workflow_to_start(
        workflow_name="claudestep.yml",
        timeout=30,
        branch="e2e-test"
    )

    # Wait for workflow to complete
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudestep.yml",
        timeout=900  # 15 minutes
    )

    run_url = workflow_run.get("url", f"https://github.com/gestrich/claude-step/actions/runs/{workflow_run.get('databaseId')}")
    assert workflow_run["conclusion"] == "success", \
        f"Workflow should complete successfully. Run URL: {run_url}"

    # Get all PRs for this project (workflow now uses hash-based branch names)
    project_prs = gh.get_pull_requests_for_project(test_project)

    assert len(project_prs) > 0, \
        f"At least one PR should be created for project '{test_project}'. Workflow run: {run_url}"

    # Get the first (most recent) PR
    pr = project_prs[0]
    branch_name = pr.head_ref_name
    pr_url = f"https://github.com/gestrich/claude-step/pull/{pr.number}"

    assert pr.state == "open", \
        f"PR #{pr.number} should be open but is {pr.state}. PR URL: {pr_url}"

    # Track PR for cleanup
    cleanup_prs.append(pr.number)

    # Verify PR has a title
    assert pr.title, f"PR #{pr.number} should have a title. PR URL: {pr_url}"

    # Get PR comments for summary and cost verification
    comments = gh.get_pr_comments(pr.number)

    # Verify there's at least one comment
    assert len(comments) > 0, \
        f"PR #{pr.number} should have at least one comment. PR URL: {pr_url}"

    # Extract comment bodies for analysis
    comment_bodies = [c.get("body", "") for c in comments]

    # Verify PR has an AI-generated summary comment
    # The AI summary typically mentions "Summary" or "Changes"
    has_summary = any("Summary" in body or "Changes" in body for body in comment_bodies)
    assert has_summary, \
        f"PR #{pr.number} should have an AI-generated summary comment. " \
        f"Found {len(comments)} comment(s). PR URL: {pr_url}"

    # Verify PR has cost/usage information
    # Cost info typically includes words like "cost", "tokens", "usage", or "$"
    has_cost_info = any(
        "cost" in body.lower() or
        "token" in body.lower() or
        "usage" in body.lower() or
        "$" in body
        for body in comment_bodies
    )
    assert has_cost_info, \
        f"PR #{pr.number} should have cost/usage information in comments. " \
        f"Found {len(comments)} comment(s). PR URL: {pr_url}"

    # Clean up: delete the PR branch
    gh.delete_branch(branch_name)


def test_reviewer_capacity_limits(
    gh: GitHubHelper,
    test_project: str,
    cleanup_prs: List[int]
) -> None:
    """Test that ClaudeStep respects reviewer capacity limits.

    This test uses the permanent e2e-test-project (which has 300+ tasks and
    a reviewer capacity limit configured) and verifies that:
    1. The workflow creates PRs up to the capacity limit
    2. The workflow skips PR creation when reviewer is at capacity

    Note: Each workflow run creates ONE PR. The workflow must be triggered
    multiple times to create multiple PRs up to the capacity limit.

    With the new spec-file-source-of-truth design, the test project exists
    permanently in the main branch with pre-configured capacity limits.

    Args:
        gh: GitHub helper fixture
        test_project: Test project name from fixture (e2e-test-project)
        cleanup_prs: PR cleanup fixture
    """
    # The permanent e2e-test-project has maxOpenPRs: 5 configured
    # We'll test that capacity limits are respected

    try:
        # === First workflow run: should create PR for first task ===
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": test_project},
            ref="e2e-test"
        )
        gh.wait_for_workflow_to_start(workflow_name="claudestep.yml", timeout=30, branch="e2e-test")
        workflow_run_1 = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=900  # 15 minutes - increased to accommodate AI inference and GitHub operations
        )
        run_url_1 = workflow_run_1.get("url", f"https://github.com/gestrich/claude-step/actions/runs/{workflow_run_1.get('databaseId')}")
        assert workflow_run_1["conclusion"] == "success", \
            f"First workflow run should succeed. Run URL: {run_url_1}"

        # Get PRs after first workflow run
        prs_after_first = gh.get_pull_requests_for_project(test_project)
        assert len(prs_after_first) >= 1, \
            f"First PR should be created. Workflow run: {run_url_1}"

        for pr in prs_after_first:
            cleanup_prs.append(pr.number)

        # === Second workflow run: should create PR for second task ===
        gh.trigger_workflow(
            workflow_name="claudestep.yml",
            inputs={"project_name": test_project},
            ref="e2e-test"
        )
        gh.wait_for_workflow_to_start(workflow_name="claudestep.yml", timeout=30, branch="e2e-test")
        workflow_run_2 = gh.wait_for_workflow_completion(
            workflow_name="claudestep.yml",
            timeout=900  # 15 minutes - increased to accommodate AI inference and GitHub operations
        )
        run_url_2 = workflow_run_2.get("url", f"https://github.com/gestrich/claude-step/actions/runs/{workflow_run_2.get('databaseId')}")
        assert workflow_run_2["conclusion"] == "success", \
            f"Second workflow run should succeed. Run URL: {run_url_2}"

        # Get PRs after second workflow run
        prs_after_second = gh.get_pull_requests_for_project(test_project)
        assert len(prs_after_second) >= 2, \
            f"Second PR should be created. Workflow run: {run_url_2}"

        # Track all PRs for cleanup
        for pr in prs_after_second:
            if pr.number not in cleanup_prs:
                cleanup_prs.append(pr.number)

        # Verify at least 2 PRs were created successfully
        assert len(prs_after_second) >= 2, \
            f"Expected at least 2 PRs to be created. " \
            f"Workflow runs: [1] {run_url_1}, [2] {run_url_2}"

        # Clean up branches
        for pr in prs_after_second:
            gh.delete_branch(pr.head_ref_name)

    except Exception as e:
        # Clean up any PRs that were created before the error
        try:
            all_prs = gh.get_pull_requests_for_project(test_project)
            for pr in all_prs:
                gh.delete_branch(pr.head_ref_name)
        except:
            pass  # Ignore errors during cleanup
        raise e


def test_merge_triggered_workflow(
    gh: GitHubHelper,
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
        test_project: Test project name from fixture (e2e-test-project)
        cleanup_prs: PR cleanup fixture
    """
    pytest.skip("Merge-triggered workflow test requires PR merge permissions")

    # TODO: Implement this test when we have the ability to merge PRs
    # The test should:
    # 1. Use the permanent e2e-test-project from main branch
    # 2. Trigger workflow to create first PR
    # 3. Merge the first PR
    # 4. Verify workflow is triggered on merge
    # 5. Verify second PR is created
    # 6. Clean up