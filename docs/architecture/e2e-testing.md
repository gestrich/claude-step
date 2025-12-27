# End-to-End Testing Guide

This guide explains how to run the ClaudeStep end-to-end integration tests.

> **Note:** The E2E tests are located in the demo project at `claude-step-demo/tests/integration/`. See `claude-step-demo/tests/integration/README.md` for the latest documentation.

## Overview

The e2e tests validate the complete ClaudeStep workflow in a real GitHub environment:
- Creates test projects in the demo repository
- Triggers actual GitHub Actions workflows
- Verifies PRs are created correctly
- **Verifies AI-generated PR summaries are posted as comments**
- Tests reviewer capacity limits
- Tests merge trigger functionality
- Cleans up all created resources

## Prerequisites

The e2e tests require several tools and access to GitHub:

### 1. Python 3 and pytest

```bash
# Check Python version
python3 --version

# Install pytest (may require --break-system-packages on macOS)
python3 -m pip install pytest --break-system-packages
```

### 2. GitHub CLI (gh)

```bash
# Check if gh is installed
gh --version

# Install on macOS
brew install gh

# Authenticate with GitHub
gh auth login
```

### 3. Git Configuration

```bash
# Check git config
git config user.name
git config user.email

# Configure if needed
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### 4. Repository Access

You need write access to the test repository:
- Default: `gestrich/claude-step-demo`
- The tests will create/delete test projects and PRs

## Running the Tests

### Option 1: Use the Test Runner Script (Recommended)

The easiest way to run the tests:

```bash
# From the demo repository root
cd /path/to/claude-step-demo
./tests/integration/run_test.sh
```

This script will:
- Check all prerequisites automatically
- Install pytest if needed
- Configure git if needed
- Run the integration tests with proper settings
- Display colored output for easy reading

### Option 2: Run pytest Directly

If you prefer to run pytest directly:

```bash
# From the demo repository root
cd /path/to/claude-step-demo
pytest tests/integration/test_workflow_e2e.py -v -s -m integration
```

**Flags explained:**
- `-v` - Verbose output (shows test names)
- `-s` - Show print statements (important for test progress)
- `-m integration` - Only run tests marked as integration tests

## What the Tests Do

The e2e test (`test_claudestep_workflow_e2e`) performs these steps:

### Step 1: Create First PR
1. Creates a test project with 3 tasks in `claude-step/test-project-<id>/`
2. Commits and pushes to the demo repo's main branch
3. Triggers the ClaudeStep workflow manually
4. Waits for workflow to complete (usually 60-90 seconds)
5. Verifies PR #1 was created for the first task
6. **NEW: Verifies AI-generated summary comment appears on PR #1** (90s timeout)

### Step 2: Create Second PR
1. Triggers workflow again (tests concurrent capacity)
2. Waits for workflow to complete
3. Verifies PR #2 was created for the second task
4. **NEW: Verifies AI-generated summary comment appears on PR #2** (90s timeout)
5. Verifies reviewer is at capacity (2 open PRs)

### Step 3: Test Merge Trigger
1. Merges PR #1
2. Waits for merge trigger to start new workflow run (10-20 seconds)
3. Waits for workflow to complete
4. Verifies PR #3 was created for the third task
5. **NEW: Verifies AI-generated summary comment appears on PR #3** (90s timeout)

### Step 4: Cleanup
1. Closes remaining test PRs (PR #2, PR #3)
2. Removes test project from demo repo
3. Reports success/failure

## Expected Duration

- **Total test time**: 6-10 minutes
- **Per workflow run**: 60-120 seconds
- **PR summary posting**: Usually within 60 seconds of PR creation
- **Cleanup**: 10-20 seconds

## Understanding Test Output

The test provides detailed progress output:

```
============================================================
Testing ClaudeStep workflow with project: test-project-abc123
============================================================

[STEP 1] Triggering workflow for first task...
  Workflow run ID: 12345678
Waiting for workflow run 12345678...
  Status: queued, Conclusion:
  Status: in_progress, Conclusion:
  Status: completed, Conclusion: success
  ✓ Workflow completed successfully
  ✓ PR #42 created: ClaudeStep: Create test-file-1.txt
  Checking for AI-generated summary on PR #42...
  ✓ Found AI-generated summary on PR #42
  Waiting for PR to be fully indexed...

[STEP 2] Triggering workflow for second task...
  ...

============================================================
✓ All tests passed!
============================================================

Created PRs:
  - PR #42: ClaudeStep: Create test-file-1.txt (MERGED) - Summary: ✓
  - PR #43: ClaudeStep: Create test-file-2.txt (OPEN) - Summary: ✓
  - PR #44: ClaudeStep: Create test-file-3.txt (OPEN) - Summary: ✓
```

## Common Issues and Solutions

### Issue: "pytest not found"

```bash
# Solution: Install pytest
python3 -m pip install pytest --break-system-packages
```

### Issue: "gh CLI not authenticated"

```bash
# Solution: Authenticate with GitHub
gh auth login
# Follow the prompts to authenticate
```

### Issue: "git not configured"

```bash
# Solution: Configure git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Issue: "No AI-generated summary found after 90s"

This usually means:
1. The PR summary feature is not enabled in the workflow (check `add_pr_summary` input)
2. The workflow is using an old version without the feature
3. The claude-code-action step failed (check workflow logs)

**Solution:** Check the workflow run logs:
```bash
# Get the workflow run ID from test output
gh run view <run_id> --repo gestrich/claude-step-demo --log | grep -i summary
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
gh pr view <pr_number> --repo gestrich/claude-step-demo

# View PR comments (including AI summary)
gh pr view <pr_number> --repo gestrich/claude-step-demo --json comments

# View workflow run logs
gh run view <run_id> --repo gestrich/claude-step-demo --log
```

## Test Configuration

The test is configured via fixtures in `tests/integration/test_workflow_e2e.py`:

- **Repository**: `gestrich/claude-step-demo` (hardcoded in `GitHubHelper`)
- **Workflow**: `claudestep.yml`
- **Reviewer capacity**: 2 PRs (configured in test project)
- **PR summary timeout**: 90 seconds (can be adjusted in test)

## CI/CD Integration

These tests can be run in GitHub Actions or other CI systems. The `run_test.sh` script handles all prerequisites automatically, making it suitable for CI environments.

Example GitHub Actions workflow:

```yaml
name: E2E Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install pytest
        run: pip install pytest
      - name: Run e2e tests
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: ./tests/integration/run_test.sh
```

## Important Notes

1. **Real GitHub Operations**: These tests create real PRs and trigger real workflows in the demo repository
2. **API Costs**: Each test run uses Claude API credits for both the main workflow and PR summaries
3. **Cleanup**: Tests clean up after themselves, but check the demo repo if a test fails unexpectedly
4. **Parallelization**: Don't run multiple e2e tests in parallel - they may conflict when creating test projects
5. **Test Data**: Test projects are named `test-project-<random-id>` to avoid conflicts

## Troubleshooting Failed Tests

If a test fails:

1. **Check the test output** - It shows which step failed and why
2. **View the workflow logs** - Use the run ID from test output
3. **Check the PRs** - Look at the actual PRs created to see what went wrong
4. **Check GitHub Actions status** - Sometimes GitHub has service issues
5. **Try again** - Transient network issues can cause failures

## Next Steps

After running the tests successfully:
- Review the created PRs to see the PR summaries
- Check workflow logs to understand the complete flow
- Modify test projects to test different scenarios
- Contribute improvements to the test suite

## References

- Test file: `claude-step-demo/tests/integration/test_workflow_e2e.py`
- Test runner: `claude-step-demo/tests/integration/run_test.sh`
- Demo repository: https://github.com/gestrich/claude-step-demo
- Test documentation: https://github.com/gestrich/claude-step-demo/blob/main/tests/integration/README.md
