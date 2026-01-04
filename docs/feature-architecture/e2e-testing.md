# End-to-End Testing Guide

This guide explains how to run the ClaudeChain end-to-end integration tests.

## Overview

The E2E tests are located in this repository at `tests/e2e/` and use a **recursive workflow pattern** where ClaudeChain tests itself. The tests validate the complete ClaudeChain workflow in a real GitHub environment:
- Creates test projects in the same repository (`claude-chain/test-*`)
- Triggers the `claudechain-test.yml` workflow which runs the action on itself
- Verifies PRs are created correctly
- Verifies AI-generated PR summaries are posted as comments
- Verifies cost information in PR comments
- Tests reviewer capacity limits
- Tests merge trigger functionality
- Cleans up all created resources

## Test Isolation Architecture

To prevent test pollution of the main branch, ClaudeChain uses an **ephemeral test branch** strategy:

### Branch Isolation Model

**Main Branch** - Clean and production-ready:
- Contains all test code (`tests/e2e/`)
- Contains the E2E test orchestration workflow (`.github/workflows/e2e-test.yml`)
- NO test execution artifacts
- NO test projects (`claude-chain/` directory)
- NO test-specific workflows (`claudechain-test.yml`)

**Ephemeral `main-e2e` Branch** - Created fresh for each test run:
- Created from main at test start
- Contains test projects (`claude-chain/e2e-test-*`)
- Uses the production `claudechain.yml` workflow (no test-specific workflows needed)
- Used for all test execution (commits, pushes, PRs)
- **Deleted after successful tests** or left for debugging on failure

> **Note:** ClaudeChain workflows are generic and work on ANY branch automatically. Workflows automatically target the correct branch for PRs without any configuration. This eliminates the need for test-specific workflows.

### Test Branch Lifecycle

Each E2E test run follows this lifecycle:

1. **Setup Phase**:
   - Delete old `main-e2e` branch if it exists (cleanup from previous runs)
   - Create fresh `main-e2e` branch from current `main`
   - Create `claude-chain/` workspace directory
   - Push `main-e2e` branch to remote

2. **Execution Phase**:
   - Tests run and operate on the `main-e2e` branch
   - Test projects are created in `claude-chain/e2e-test-*`
   - PRs are created with `main-e2e` as base branch
   - Production workflows automatically adapt to `main-e2e`

3. **Cleanup Phase**:
   - On success: Delete `main-e2e` branch completely
   - On failure: Leave branch for debugging

### Benefits of Ephemeral Branches

1. **Clean main branch**: No test artifacts ever committed to main
2. **Test isolation**: Each run starts from a known clean state
3. **No conflicts**: Parallel test runs can't interfere with each other
4. **Easy debugging**: Failed test branches preserved for investigation
5. **True separation**: Test workflows can't accidentally trigger on main

### Code vs. Execution Separation

| Aspect | Lives on Main | Lives on main-e2e |
|--------|---------------|-------------------|
| Test code files | ✅ Yes | No |
| Test helpers | ✅ Yes | No |
| E2E orchestration workflow | ✅ Yes | No |
| Test projects (`claude-chain/`) | ❌ No | ✅ Yes |
| Test execution (git ops) | ❌ No | ✅ Yes |

> **Note:** Unlike earlier designs, test-specific workflows are no longer needed. The production workflows are generic and automatically work on any branch, including `main-e2e`.

### Recursive Workflow Pattern

The key innovation is that the `claude-chain` repository tests itself:

1. **E2E Test Workflow** (`.github/workflows/e2e-test.yml`) sets up ephemeral `main-e2e` branch
2. **Tests create** temporary projects in `claude-chain/e2e-test-{id}/` on the `main-e2e` branch
3. **Tests trigger** the ClaudeChain workflow via `workflow_dispatch` or PR merge
4. **Action creates PRs** in the same repository for the test project tasks (base branch: `main-e2e`)
5. **Tests verify** the PRs were created correctly with summaries
6. **Tests clean up** all test resources (projects, PRs, branches)
7. **E2E Test Workflow** deletes the ephemeral `main-e2e` branch (on success)

## Prerequisites

The e2e tests are executed remotely on GitHub's infrastructure. To trigger and monitor tests, you need:

### 1. GitHub CLI (gh)

```bash
# Check if gh is installed
gh --version

# Install on macOS
brew install gh

# Authenticate with GitHub
gh auth login
```

### 2. Repository Access

You need write access to the `claude-chain` repository to trigger the e2e-test.yml workflow:
- The tests will create/delete the ephemeral `main-e2e` branch
- The tests will create/delete test projects in `claude-chain/e2e-test-*` on the `main-e2e` branch
- The tests will create and close test PRs (with `main-e2e` as base branch)
- The tests will create and delete test branches for each PR

**Note:** Python 3, pytest, and git configuration are NOT required locally. The test runner script (`run_test.sh`) triggers remote execution on GitHub's infrastructure where these dependencies are already configured.

## Running the Tests

### Remote Execution Model

**Important:** The `run_test.sh` script now triggers remote execution on GitHub's infrastructure. This means:

- **Zero local git mutations** - All test execution happens on GitHub's runners
- **No local Python/pytest required** - Dependencies are configured on GitHub
- **Clean separation** - Your local branch remains untouched during test execution
- **Live monitoring** - The script streams workflow logs to your terminal in real-time

### Using the Test Runner Script

The recommended way to run the tests:

```bash
# From the claude-chain repository root
cd /path/to/claude-chain
./tests/e2e/run_test.sh
```

This script will:
1. **Check prerequisites** - Verify gh CLI is installed and authenticated
2. **Trigger workflow** - Run `gh workflow run e2e-test.yml --ref <current-branch>` to start tests on GitHub
3. **Monitor execution** - Stream live logs from the workflow run to your terminal
4. **Report results** - Display success/failure with colored output and proper exit codes

The workflow runs on GitHub's infrastructure using the code from your current branch. Tests execute via pytest on GitHub's runners, creating the ephemeral `e2e-test` branch and running all test scenarios remotely.

### Monitoring Remote Test Execution

When you run `./tests/e2e/run_test.sh`, you'll see:

```
========================================
ClaudeChain E2E Test Runner
========================================

Checking prerequisites...
✓ GitHub CLI (gh) is installed
✓ GitHub CLI is authenticated
✓ Current branch: main

========================================
Triggering E2E Tests on GitHub
========================================

Branch: main
Workflow: e2e-test.yml

✓ Workflow triggered successfully!

Waiting for workflow run to start...
Workflow run ID: 12345678

========================================
Monitoring Workflow Execution
========================================

Streaming logs from GitHub Actions...
[Live workflow logs appear here...]

========================================
Workflow Execution Complete
========================================

✓ E2E Tests PASSED
```

You can press **Ctrl+C** to stop monitoring at any time - the workflow will continue running on GitHub.

### Manual Workflow Monitoring

If you prefer to monitor the workflow separately:

```bash
# Trigger the workflow
gh workflow run e2e-test.yml --ref main

# List recent runs
gh run list --workflow=e2e-test.yml

# Watch a specific run
gh run watch <run-id> --exit-status

# View run details
gh run view <run-id>

# View run logs
gh run view <run-id> --log
```

Or visit the GitHub Actions UI:
`https://github.com/<owner>/<repo>/actions/workflows/e2e-test.yml`

## What the Tests Do

### test_workflow_e2e.py

This file contains comprehensive tests of the main ClaudeChain workflow:

**test_creates_pr_with_summary:**
1. Creates a test project with 3 tasks in `claude-chain/test-project-<id>/`
2. Commits and pushes to the claude-chain repo's main branch
3. Triggers the `claudechain-test.yml` workflow manually
4. Waits for workflow to complete (usually 60-120 seconds)
5. Verifies PR was created for the first task
6. Verifies AI-generated summary comment appears on the PR
7. Verifies cost information appears in the summary

**test_creates_pr_with_cost_info:**
- Validates that cost information is included in PR comments
- Checks for token usage and estimated cost

**test_reviewer_capacity:**
- Creates multiple test projects
- Triggers workflows to test `maxOpenPRs` limits
- Verifies reviewers don't exceed capacity

**test_merge_triggers_next_pr:**
- Creates a PR and merges it
- Verifies merge triggers the next workflow run
- Confirms the next task's PR is created automatically

**test_empty_spec:**
- Tests handling of projects with no tasks
- Verifies workflow completes successfully without creating PRs

### test_statistics_e2e.py

Tests the statistics collection workflow:

**test_statistics_workflow_runs_successfully:**
1. Triggers the `claudechain-statistics.yml` workflow
2. Waits for workflow completion
3. Verifies workflow succeeds or is skipped appropriately

**test_statistics_workflow_with_custom_days:**
- Tests statistics with default configuration
- Verifies workflow accepts the days_back parameter

**test_statistics_output_format:**
- Validates statistics workflow produces expected output
- Checks for proper completion status

## Expected Duration

- **Total test time**: 5-10 minutes (for full suite)
- **Per workflow run**: 60-120 seconds
- **PR summary posting**: Usually within 60 seconds of PR creation
- **Cleanup**: 5-10 seconds per test

## Understanding Test Output

The tests provide detailed progress output using pytest's verbose mode:

```
tests/e2e/test_workflow_e2e.py::test_creates_pr_with_summary
Creating test project: test-project-abc123
Workflow run ID: 12345678
Waiting for workflow completion...
  Status: queued
  Status: in_progress
  Status: completed (success)
Checking for PR...
  ✓ PR #42 created: refactor/test-project-abc123-1
  ✓ AI-generated summary found
  ✓ Cost information found
Cleaning up test resources...
  ✓ Closed PR #42
  ✓ Deleted branch refactor/test-project-abc123-1
  ✓ Removed test project
PASSED

tests/e2e/test_statistics_e2e.py::test_statistics_workflow_runs_successfully
Workflow run ID: 87654321
Waiting for workflow completion...
  Status: completed (success)
PASSED
```

## Common Issues and Solutions

### Issue: "gh CLI not authenticated"

```bash
# Solution: Authenticate with GitHub
gh auth login
# Follow the prompts to authenticate
```

### Issue: "Failed to trigger workflow"

This usually means:
1. You don't have write access to the repository
2. The workflow file doesn't exist on your branch
3. GitHub API is experiencing issues

**Solution:** Verify repository access and that `.github/workflows/e2e-test.yml` exists on your branch.

### Issue: "No AI-generated summary found"

This usually means:
1. The PR summary feature is not enabled in the workflow (check `add_pr_summary` input)
2. The ANTHROPIC_API_KEY secret is not configured
3. The workflow step failed (check workflow logs)

**Solution:** Check the workflow run logs:
```bash
# Get the workflow run ID from test output
gh run view <run_id> --repo gestrich/claude-chain --log | grep -i summary
```

### Issue: Test hangs or times out

- Check your network connection
- Verify GitHub Actions is not experiencing issues
- The demo repository may have rate limits

### Issue: "Updates were rejected" during cleanup

This is usually harmless - it means another test or process modified the repo during cleanup. The test will still pass if PRs were verified correctly.

## Viewing Test Results in GitHub

After the test completes, you can view the actual PRs and workflow runs:

```bash
# View a specific PR (number from test output)
gh pr view <pr_number> --repo gestrich/claude-chain

# View PR comments (including AI summary)
gh pr view <pr_number> --repo gestrich/claude-chain --json comments

# View workflow run logs
gh run view <run_id> --repo gestrich/claude-chain --log
```

## Test Configuration

The tests use fixtures defined in `tests/e2e/conftest.py`:

- **Repository**: `gestrich/claude-chain` (configured in `GitHubHelper`)
- **Test branch**: `main-e2e` (ephemeral branch created by E2E workflow)
- **Workflow**: Uses production `claudechain.yml` (workflows are generic and work on any branch)
- **Base branch for PRs**: `main-e2e` (all test PRs merge to test branch, not main)
- **Reviewer capacity**: 2 PRs (configured in test projects)
- **Workflow timeout**: 300 seconds (5 minutes)
- **Test project naming**: `e2e-test-{uuid}` for isolation
- **Branch manager**: `TestBranchManager` handles ephemeral branch lifecycle

## CI/CD Integration

E2E tests can be run in GitHub Actions using the `.github/workflows/e2e-test.yml` workflow:

```yaml
name: E2E Integration Tests

on:
  workflow_dispatch:  # Manual trigger

permissions:
  contents: write      # Needed to create/delete e2e-test branch
  pull-requests: write # Needed to create test PRs
  actions: write       # Needed to trigger workflows

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install pytest pyyaml

      - name: Configure Git
        run: |
          git config --global user.name 'ClaudeChain E2E Tests'
          git config --global user.email 'claudechain-e2e@users.noreply.github.com'

      - name: Set up ephemeral test branch
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python3 << 'EOF'
          import sys
          sys.path.insert(0, 'tests/e2e/helpers')
          from test_branch_manager import TestBranchManager

          manager = TestBranchManager()
          manager.setup_test_branch()
          EOF

      - name: Run E2E tests
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: ./tests/e2e/run_test.sh

      - name: Cleanup test branch (on success)
        if: success()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python3 << 'EOF'
          import sys
          sys.path.insert(0, 'tests/e2e/helpers')
          from test_branch_manager import TestBranchManager

          manager = TestBranchManager()
          manager.cleanup_test_branch()
          EOF

      - name: Branch left for debugging
        if: failure()
        run: echo "Test branch 'main-e2e' left intact for debugging"
```

**Note:** E2E tests are typically run manually due to API costs and execution time. They can be triggered via:
- Manual workflow dispatch from GitHub UI
- On-demand via `gh workflow run e2e-test.yml`
- Optionally on PR merges to main

## Important Notes

1. **Remote Execution**: The `run_test.sh` script triggers remote execution on GitHub - no local git mutations occur
2. **Real GitHub Operations**: Tests create real PRs and trigger real workflows in the claude-chain repository (on GitHub's runners)
3. **Ephemeral Test Branch**: All test execution happens on the `main-e2e` branch, which is created fresh and deleted after each run
4. **Main Branch Protection**: The main branch never contains test artifacts - it stays completely clean
5. **No Local Requirements**: Python, pytest, and git configuration are NOT needed locally - everything runs on GitHub
6. **API Costs**: Each test run uses Claude API credits (using cheapest model: claude-3-haiku-20240307)
7. **Cleanup**: Tests clean up after themselves automatically using pytest fixtures and `TestBranchManager`
8. **Test Isolation**: Each test uses unique project IDs (`e2e-test-{uuid}`) to prevent conflicts
9. **Self-Testing**: The action tests itself using the recursive workflow pattern (`uses: ./`)
10. **Test Artifacts**: All test projects, PRs, and branches are temporary and cleaned up automatically
11. **Debugging Failed Tests**: On test failure, the `main-e2e` branch is left intact for investigation
12. **Live Monitoring**: The script streams workflow logs in real-time; you can Ctrl+C to stop watching without stopping the workflow
13. **Generic Workflows**: Production workflows work on any branch automatically - no test-specific workflow configuration needed

## Troubleshooting Failed Tests

If a test fails:

1. **Check the test output** - It shows which step failed and why
2. **View the workflow logs** - Use the run ID from test output
3. **Check the PRs** - Look at the actual PRs created to see what went wrong
4. **Check GitHub Actions status** - Sometimes GitHub has service issues
5. **Try again** - Transient network issues can cause failures

## Next Steps

After running the tests successfully:
- Review the test output to understand the workflow
- Check workflow logs via GitHub UI or `gh run view`
- Review created PRs (before cleanup) to see AI-generated summaries
- Extend tests to cover additional scenarios
- Contribute improvements to the test suite

## References

- Test files: `tests/e2e/test_workflow_e2e.py`, `tests/e2e/test_statistics_e2e.py`
- Test runner: `tests/e2e/run_test.sh`
- Helper modules:
  - `tests/e2e/helpers/github_helper.py` - GitHub API interactions
  - `tests/e2e/helpers/project_manager.py` - Test project management
  - `tests/e2e/helpers/test_branch_manager.py` - Ephemeral branch lifecycle
- Fixtures: `tests/e2e/conftest.py`
- E2E workflow: `.github/workflows/e2e-test.yml` (on main branch)
- Production workflows: `.github/workflows/claudechain.yml`, `.github/workflows/claudechain-auto-start.yml` (generic, work on any branch)
- Implementation plan: `docs/completed/2025-12-28-e2e-test-isolation.md`
- E2E test redesign: `docs/completed/2026-01-01-redesign-e2e-tests.md`
