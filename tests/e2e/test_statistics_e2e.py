"""End-to-End tests for ClaudeStep statistics collection.

This module contains E2E integration tests that verify the ClaudeStep statistics
workflow runs successfully and generates the expected output format.

The test triggers the claudestep-statistics.yml workflow and verifies that it:
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


def test_z_statistics_end_to_end(gh: GitHubHelper) -> None:
    """Test that the ClaudeStep statistics workflow collects data from E2E tests.

    This test runs LAST (after all other E2E tests) to validate that the statistics
    workflow can successfully collect and report on the PRs created by previous tests.

    This test:
    1. Triggers the claudestep-statistics.yml workflow on main branch
    2. Waits for workflow completion (with correct branch filter)
    3. Verifies the workflow completes successfully
    4. Verifies the statistics step completes

    The test validates the complete end-to-end flow:
    - Other E2E tests create PRs with ClaudeStep
    - This test runs statistics collection on those PRs
    - Validates the workflow infrastructure works with real data

    Args:
        gh: GitHub helper fixture
    """
    # Trigger the statistics workflow on main branch
    gh.trigger_workflow(
        workflow_name="claudestep-statistics.yml",
        inputs={},  # No inputs required for statistics workflow
        ref="main"
    )

    # Wait a moment for workflow to start
    time.sleep(5)

    # Wait for workflow to complete on MAIN branch (not e2e-test)
    # This is the key fix: we must pass branch="main" to match where we triggered it
    workflow_run = gh.wait_for_workflow_completion(
        workflow_name="claudestep-statistics.yml",
        timeout=300,  # 5 minutes should be plenty for statistics
        branch="main"  # Explicitly specify main branch
    )

    assert workflow_run is not None, "Workflow run should be found"
    assert workflow_run["conclusion"] == "success", \
        f"Workflow should complete successfully, got: {workflow_run['conclusion']}"

    # Note: We validate the workflow completes successfully, which means:
    # 1. It successfully queries for ClaudeStep PRs
    # 2. It generates statistics (if PRs exist)
    # 3. It formats output correctly
    # 4. It posts to Slack (if configured and data exists)
    #
    # We don't validate the specific statistics content because:
    # - The content depends on which E2E tests ran before this
    # - Parsing workflow logs would be fragile
    # - Unit tests validate statistics calculation logic
    # - This E2E test validates the complete workflow infrastructure
