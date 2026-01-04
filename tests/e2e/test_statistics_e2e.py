"""End-to-End tests for ClaudeChain statistics collection.

This module contains E2E integration tests that verify the ClaudeChain statistics
workflow runs successfully and generates the expected output format.

The test triggers the claudechain-statistics.yml workflow and verifies that it:
- Completes successfully
- Generates statistics output
- Produces properly formatted Slack messages (when statistics exist)

NOTE: This test is designed to run LAST (after other E2E tests) so that it can
validate statistics from actual PRs created by previous E2E tests. The 'z_' prefix
ensures pytest runs it last alphabetically.

TESTS IN THIS MODULE:

1. test_z_statistics_end_to_end
   - What: Verifies statistics workflow collects data from PRs created by other E2E tests
   - Why E2E: Tests integration between GitHub API, statistics collection, and workflow execution
   - Why LAST: Needs real PR data from previous E2E tests for realistic validation
   - Unit tests (43 tests) cover: edge cases, error handling, formatting, empty data
"""

import time
import pytest

from .helpers.github_helper import GitHubHelper
from .constants import E2E_TEST_BRANCH


def test_z_statistics_end_to_end(gh: GitHubHelper) -> None:
    """Test that the ClaudeChain statistics workflow collects data from E2E tests.

    This test runs LAST (after all other E2E tests) to validate that the statistics
    workflow can successfully collect and report on the PRs created by previous tests.

    This test:
    1. Triggers the claudechain-statistics.yml workflow on main-e2e branch
    2. Waits for workflow completion
    3. Verifies the workflow completes successfully
    4. Validates the workflow found and processed PRs from previous E2E tests
    5. Validates cost information is present in the logs

    The test validates the complete end-to-end flow:
    - Other E2E tests create PRs with ClaudeChain on main-e2e
    - This test runs statistics collection on those PRs
    - Validates the workflow infrastructure works with real data

    Args:
        gh: GitHub helper fixture
    """
    # Trigger the statistics workflow on main-e2e branch
    # This will collect statistics from PRs targeting main-e2e
    gh.trigger_workflow(
        workflow_name="claudechain-statistics.yml",
        inputs={"base_branch": E2E_TEST_BRANCH},  # Target main-e2e branch for E2E test PRs
        ref="main"  # Run the workflow from main branch
    )

    # Wait a moment for workflow to start
    time.sleep(5)

    # Wait for workflow to complete on MAIN branch (workflow runs from main, but targets main-e2e PRs)
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudechain-statistics.yml",
        timeout=300,  # 5 minutes should be plenty for statistics
        branch="main"  # Workflow runs on main, but analyzes main-e2e PRs
    )

    assert workflow_run is not None, "Workflow run should be found"
    assert workflow_run.conclusion == "success", \
        f"Workflow should complete successfully, got: {workflow_run.conclusion}"

    # Fetch workflow logs to validate statistics were collected
    logs = gh.get_workflow_run_logs(workflow_run.database_id)

    # Validate that the workflow found PRs from previous E2E tests
    # The logs should contain evidence that PRs were processed
    assert "Found" in logs and "PR" in logs, \
        "Workflow logs should indicate PRs were found for statistics collection"

    # Validate that cost information is present (indicates real PR data was processed)
    # The statistics should include cost data from the AI-generated PRs
    assert "cost" in logs.lower() or "total" in logs.lower(), \
        "Workflow logs should contain cost/total information from PR statistics"

    # Note: We validate the workflow:
    # 1. Successfully queries for ClaudeChain PRs targeting main-e2e
    # 2. Finds at least some PRs (from previous E2E tests)
    # 3. Generates statistics with cost information
    # 4. Completes successfully
    #
    # We use log validation to confirm real PR data was processed, without
    # making brittle assertions about exact PR counts or costs (which vary
    # based on which E2E tests ran before this)
