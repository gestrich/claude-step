"""End-to-End tests for ClaudeChain workflow.

This module contains E2E integration tests that verify the ClaudeChain workflow
creates PRs correctly, generates AI summaries, and includes cost information.

The tests use a recursive workflow pattern where the claude-chain repository
tests itself by running the actual claudechain.yml workflow against the main-e2e
branch with dynamically generated test projects.

Note: Workflows are triggered via workflow_dispatch (not push events) because
pushes made with GITHUB_TOKEN don't trigger workflows (GitHub security feature
to prevent infinite loops). Since Sep 2022, GITHUB_TOKEN can trigger
workflow_dispatch events.

TESTS IN THIS MODULE:

1. test_auto_start_workflow
   - What: Verifies claudechain.yml creates a PR for a new project
   - Why E2E: Tests the full workflow including AI summary and cost breakdown

2. test_merge_triggered_workflow
   - What: Verifies workflow creates next PR after first PR is merged
   - Why E2E: Tests multi-task progression through the spec
"""

from .helpers.github_helper import GitHubHelper


def test_auto_start_workflow(
    gh: GitHubHelper,
    setup_test_project: str
) -> None:
    """Test that claudechain.yml creates a PR when triggered for a new project.

    This test validates the workflow creates a PR correctly when triggered
    via workflow_dispatch with a project name.

    Note: The fixture explicitly triggers the workflow via workflow_dispatch
    because pushes made with GITHUB_TOKEN don't trigger push events (GitHub
    security feature). Since Sep 2022, GITHUB_TOKEN can trigger workflow_dispatch.

    The test verifies:
    1. Workflow completes successfully
    2. Workflow creates a PR for the first task
    3. PR has "claudechain" label
    4. PR targets main-e2e branch
    5. PR has AI summary comment with cost breakdown

    Cleanup happens at test START (not end) to allow manual inspection.

    Args:
        gh: GitHub helper fixture
        setup_test_project: Test project created, pushed, and workflow triggered
    """
    from claudechain.domain.constants import DEFAULT_PR_LABEL
    from tests.e2e.constants import E2E_TEST_BRANCH

    test_project = setup_test_project

    # Wait for claudechain workflow to start (triggered by fixture via workflow_dispatch)
    gh.wait_for_workflow_to_start(
        workflow_name="claudechain.yml",
        timeout=60,
        branch=E2E_TEST_BRANCH
    )

    # Wait for workflow to complete
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudechain.yml",
        timeout=900,  # 15 minutes
        branch=E2E_TEST_BRANCH
    )

    assert workflow_run.conclusion == "success", \
        f"Workflow should complete successfully. Run URL: {workflow_run.url}"

    # Get all PRs for this project
    project_prs = gh.get_pull_requests_for_project(test_project)

    assert len(project_prs) > 0, \
        f"At least one PR should be created for project '{test_project}'. Workflow run: {workflow_run.url}"

    # Get the first (most recent) PR
    pr = project_prs[0]
    pr_url = f"https://github.com/gestrich/claude-chain/pull/{pr.number}"

    # Verify PR is open
    assert pr.state == "open", \
        f"PR #{pr.number} should be open but is {pr.state}. PR URL: {pr_url}"

    # Verify PR has claudechain label
    assert DEFAULT_PR_LABEL in [label.lower() for label in pr.labels], \
        f"PR #{pr.number} should have '{DEFAULT_PR_LABEL}' label. PR URL: {pr_url}"

    # Verify PR targets main-e2e branch
    assert pr.base_ref_name == E2E_TEST_BRANCH, \
        f"PR #{pr.number} should target '{E2E_TEST_BRANCH}' branch but targets '{pr.base_ref_name}'. PR URL: {pr_url}"

    # Verify PR has a title
    assert pr.title, f"PR #{pr.number} should have a title. PR URL: {pr_url}"

    # Get PR comments for summary and cost verification
    comments = gh.get_pr_comments(pr.number)

    # Verify there's at least one comment
    assert len(comments) > 0, \
        f"PR #{pr.number} should have at least one comment. PR URL: {pr_url}"

    # Extract comment bodies for analysis
    comment_bodies = [c.body for c in comments]

    # Verify PR has a combined comment with both summary and cost breakdown
    has_combined_comment = any(
        "## AI-Generated Summary" in body and "## 💰 Cost Breakdown" in body
        for body in comment_bodies
    )
    assert has_combined_comment, \
        f"PR #{pr.number} should have a combined comment with both '## AI-Generated Summary' and '## 💰 Cost Breakdown' headers. " \
        f"Found {len(comments)} comment(s). PR URL: {pr_url}"


def test_merge_triggered_workflow(
    gh: GitHubHelper,
    setup_test_project: str
) -> None:
    """Test that merging a PR and triggering workflow creates the next PR.

    This test verifies that after a ClaudeChain PR is merged, triggering the
    workflow creates a PR for the next task in the spec.

    Note: We explicitly trigger the workflow after merge because merges done
    with GITHUB_TOKEN don't trigger push events (GitHub security feature).
    Since Sep 2022, GITHUB_TOKEN can trigger workflow_dispatch events.

    The test verifies:
    1. First workflow (triggered by fixture) creates first PR
    2. Merging the first PR + explicit workflow trigger creates second PR
    3. Second PR has "claudechain" label
    4. Second PR targets main-e2e branch

    Cleanup happens at test START (not end) to allow manual inspection.

    Args:
        gh: GitHub helper fixture
        setup_test_project: Test project created and pushed to main-e2e (has 3 tasks)
    """
    from claudechain.domain.constants import DEFAULT_PR_LABEL
    from tests.e2e.constants import E2E_TEST_BRANCH

    test_project = setup_test_project

    # Wait for claudechain workflow to start (triggered by fixture via workflow_dispatch)
    gh.wait_for_workflow_to_start(
        workflow_name="claudechain.yml",
        timeout=60,
        branch=E2E_TEST_BRANCH
    )

    # Wait for workflow to complete (creates first PR)
    first_workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudechain.yml",
        timeout=900,  # 15 minutes
        branch=E2E_TEST_BRANCH
    )

    assert first_workflow_run.conclusion == "success", \
        f"First workflow run should complete successfully. Run URL: {first_workflow_run.url}"

    # Get the first PR that was created
    project_prs = gh.get_pull_requests_for_project(test_project)
    assert len(project_prs) > 0, \
        f"At least one PR should be created for project '{test_project}'. Workflow run: {first_workflow_run.url}"

    first_pr = project_prs[0]
    first_pr_url = f"https://github.com/gestrich/claude-chain/pull/{first_pr.number}"

    # Verify first PR is open
    assert first_pr.state == "open", \
        f"First PR #{first_pr.number} should be open. PR URL: {first_pr_url}"

    # Merge the first PR
    gh.merge_pull_request(first_pr.number)

    # Explicitly trigger workflow via workflow_dispatch after merge
    # Merges done with GITHUB_TOKEN don't trigger push events (GitHub security feature)
    gh.trigger_workflow(
        workflow_name="claudechain.yml",
        inputs={"project_name": test_project},
        ref=E2E_TEST_BRANCH
    )

    # Wait for the workflow to start
    gh.wait_for_workflow_to_start(
        workflow_name="claudechain.yml",
        timeout=60,
        branch=E2E_TEST_BRANCH
    )

    # Wait for the second workflow run to complete (creates second PR)
    second_workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudechain.yml",
        timeout=900,  # 15 minutes
        branch=E2E_TEST_BRANCH
    )

    assert second_workflow_run.conclusion == "success", \
        f"Second workflow run should complete successfully. Run URL: {second_workflow_run.url}"

    # Get all PRs for this project again
    project_prs = gh.get_pull_requests_for_project(test_project)

    # We should now have 2 PRs: first one (merged) and second one (open)
    assert len(project_prs) >= 2, \
        f"At least 2 PRs should exist for project '{test_project}' after merge. " \
        f"Found {len(project_prs)} PR(s). Second workflow run: {second_workflow_run.url}"

    # Find the second PR (should be open, not the merged one)
    open_prs = [pr for pr in project_prs if pr.state == "open"]
    assert len(open_prs) > 0, \
        f"At least one open PR should exist after merging first PR. " \
        f"Found {len(open_prs)} open PR(s). Second workflow run: {second_workflow_run.url}"

    second_pr = open_prs[0]
    second_pr_url = f"https://github.com/gestrich/claude-chain/pull/{second_pr.number}"

    # Verify second PR has claudechain label
    assert DEFAULT_PR_LABEL in [label.lower() for label in second_pr.labels], \
        f"Second PR #{second_pr.number} should have '{DEFAULT_PR_LABEL}' label. PR URL: {second_pr_url}"

    # Verify second PR targets main-e2e branch
    assert second_pr.base_ref_name == E2E_TEST_BRANCH, \
        f"Second PR #{second_pr.number} should target '{E2E_TEST_BRANCH}' branch but targets '{second_pr.base_ref_name}'. " \
        f"PR URL: {second_pr_url}"

    # Verify second PR is different from first PR
    assert second_pr.number != first_pr.number, \
        f"Second PR should be different from first PR. Both have number {first_pr.number}"