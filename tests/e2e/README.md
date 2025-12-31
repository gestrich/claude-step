# End-to-End Test Suite

This directory contains end-to-end integration tests for ClaudeStep using a recursive workflow pattern where the action tests itself.

## E2E Testing Philosophy

### What to Test

E2E tests should verify **integration points**, not individual features:

- **Integration between ClaudeStep components** - How the action coordinates prepare → claude_code → finalize → summary steps
- **GitHub API interactions** - PR creation, comments, branch management, workflow triggers
- **End-to-end workflow execution** - Complete workflow runs from trigger to PR creation
- **Critical integration scenarios** - Reviewer assignment, capacity limits, merge triggers

### What NOT to Test

These belong in unit or integration tests for faster feedback and better isolation:

- **Individual function behavior** - Pure business logic and data transformations (unit tests in `tests/unit/`)
- **AI response quality** - Mock Claude API responses in unit tests
- **Complex business logic** - Statistics calculation, cost parsing, progress tracking (unit tests in `tests/unit/`)
- **Command orchestration** - CLI command workflows (integration tests in `tests/integration/`)
- **Edge cases and error handling** - Empty data, missing files, API errors (unit tests)
- **Formatting and presentation** - Report generation, leaderboards, output formatting (unit tests)

### Speed Guidelines

E2E tests are expensive (time, API costs, real GitHub operations):

- **E2E suite should complete in < 10-12 minutes** (current target after optimizations)
- **Each test should complete in < 3 minutes** (except multi-workflow tests)
- **If a test takes longer**, consider:
  - Splitting into separate unit tests
  - Mocking external dependencies
  - Consolidating with other tests to avoid redundant workflow runs

### Test Consolidation Strategy

To minimize redundant workflow runs:

- **Consolidate related validations** - One workflow run, multiple assertions
- **Example**: Instead of 3 tests (PR created + has summary + has cost), use 1 test that checks all three
- **Saves time and API costs** - Reduces 3 workflow runs (~7min) to 1 (~2min)

### Unit and Integration Test Coverage

For comprehensive coverage without E2E overhead:

- **Unit Tests** (`tests/unit/`): 337 tests covering domain, infrastructure, and application layers
  - Domain logic, data models, configuration parsing
  - Infrastructure operations (git, GitHub API, filesystem) with mocked external dependencies
  - Business logic (statistics, reviewer management, cost calculation)
- **Integration Tests** (`tests/integration/`): 169 tests covering CLI command orchestration
  - Command workflows that coordinate multiple components
  - CLI commands like prepare, finalize, discover with mocked external dependencies
- **Use mocks extensively** - Mock GitHub API, Claude API, file system operations

## Quick Start

```bash
# From the claude-step repository root
./tests/e2e/run_test.sh
```

## Overview

The E2E tests validate the complete ClaudeStep workflow by:
- Creating temporary test projects in `claude-step/test-*`
- Triggering the ClaudeStep workflow on itself via `claudestep.yml`
- Verifying PRs are created with AI-generated summaries and cost info
- Testing reviewer capacity limits and merge triggers
- Automatically cleaning up all test resources

### Recursive Workflow Pattern

Unlike traditional testing approaches that require a separate demo repository, these tests use a **recursive pattern** where ClaudeStep tests itself:

1. **E2E Test** creates a test project and commits it to the repository
2. **E2E Test** triggers `.github/workflows/claudestep.yml`
3. **Workflow** runs ClaudeStep using `uses: ./` (the current repository)
4. **ClaudeStep** creates PRs for the test project's tasks
5. **E2E Test** verifies the PRs and cleans up

This enables self-contained testing without external dependencies.

## Prerequisites

Before running the tests, ensure you have:

1. **GitHub CLI (`gh`)**
   ```bash
   # Check installation
   gh --version

   # Install on macOS
   brew install gh

   # Authenticate
   gh auth login
   ```

2. **Python 3.11+**
   ```bash
   python3 --version
   ```

3. **pytest and dependencies**
   ```bash
   pip install pytest pyyaml
   ```

4. **Git configuration**
   ```bash
   git config user.name
   git config user.email

   # Configure if needed
   git config --global user.name "Your Name"
   git config --global user.email "your.email@example.com"
   ```

5. **Repository access**
   - Write access to `gestrich/claude-step` repository
   - Tests will create/delete branches, PRs, and test projects

6. **API Key (optional)**
   - `ANTHROPIC_API_KEY` environment variable or GitHub secret
   - Tests will prompt if not set

## Running Tests

### Run All Tests

```bash
./tests/e2e/run_test.sh
```

### Run Specific Tests

```bash
# Run only workflow tests
pytest tests/e2e/test_workflow_e2e.py -v -s

# Run only statistics tests
pytest tests/e2e/test_statistics_e2e.py -v -s

# Run a specific test function
pytest tests/e2e/test_workflow_e2e.py::test_creates_pr_with_summary -v -s

# Run with pattern matching
pytest tests/e2e/ -k "summary" -v -s
```

### Pytest Flags

- `-v` : Verbose output (show test names)
- `-s` : Show print statements (important for progress)
- `-k <pattern>` : Run tests matching pattern
- `--pdb` : Drop into debugger on failure
- `-x` : Stop on first failure

## Test Files

### test_workflow_e2e.py

Tests the main ClaudeStep workflow functionality:

- **test_creates_pr_with_summary** - Verifies PR creation with AI summary
- **test_creates_pr_with_cost_info** - Validates cost information in PRs
- **test_reviewer_capacity** - Tests `maxOpenPRs` capacity limits
- **test_merge_triggers_next_pr** - Verifies merge-triggered workflows
- **test_empty_spec** - Tests projects with no tasks
- **test_handles_multiple_reviewers** - Tests multi-reviewer assignment
- **test_respects_reviewer_capacity_limits** - Validates capacity enforcement

### test_statistics_e2e.py

Tests the statistics collection workflow:

- **test_statistics_workflow_runs_successfully** - Verifies basic execution
- **test_statistics_workflow_with_custom_days** - Tests with default config
- **test_statistics_output_format** - Validates output format

## Test Structure

```
tests/e2e/
├── README.md                   # This file
├── __init__.py                 # Package marker
├── conftest.py                 # Shared pytest fixtures
├── run_test.sh                 # Test runner script
├── helpers/
│   ├── __init__.py
│   ├── github_helper.py        # GitHub API operations
│   └── project_manager.py      # Test project management
├── test_workflow_e2e.py        # Main workflow tests
└── test_statistics_e2e.py      # Statistics tests
```

## Fixtures (conftest.py)

The tests use pytest fixtures for setup and cleanup:

- **`gh`** - GitHubHelper instance for API operations
- **`project_id`** - Generates unique test project IDs
- **`test_project`** - Creates and cleans up test projects
- **`cleanup_prs`** - Ensures PRs are closed after tests

## Helper Classes

### GitHubHelper (helpers/github_helper.py)

Provides methods for:
- Triggering workflows
- Monitoring workflow status
- Finding and verifying PRs
- Closing PRs and deleting branches

### TestProjectManager (helpers/project_manager.py)

Provides methods for:
- Creating test projects with tasks
- Committing and pushing projects
- Cleaning up test resources
- Safety checks to prevent accidental deletion

## Expected Test Duration

After reliability improvements (Phases 4-7), expected timings are:

- **Full test suite**: 10-12 minutes (optimized from previous 20-30 minutes)
- **Single workflow test**: 2-3 minutes (simple workflow with one task)
- **Multi-workflow test** (e.g., reviewer capacity): 10-15 minutes (3 sequential workflow runs)
- **Per workflow run**: 5-8 minutes (including main task + PR summary generation)
- **Statistics test**: 1-2 minutes
- **Cleanup per test**: 5-10 seconds

### Timeout Configuration

E2E tests use the following timeout values (configured in tests/e2e/test_workflow_e2e.py):

- **Per-workflow timeout**: 900 seconds (15 minutes)
  - Provides buffer for Claude API latency, GitHub Actions overhead, and network variability
  - Increased from original 600s (10 minutes) to improve reliability (Phase 4)
- **Workflow start detection**: 30 seconds
  - Smart polling waits for workflow to appear in GitHub API (Phase 7)
- **Poll intervals**:
  - Workflow start: 2 seconds
  - Workflow status: 10 seconds

### Performance Notes

- Each workflow run executes Claude Code Action **twice**:
  1. Main task execution (variable time based on task complexity)
  2. PR summary generation (requires fetching and analyzing PR diff)
- Tests with multiple sequential workflows (e.g., `test_reviewer_capacity_limits`) legitimately take 10-15 minutes
- The 15-minute per-workflow timeout allows for 50% buffer over typical 5-8 minute execution time

## Example Test Output

```
tests/e2e/test_workflow_e2e.py::test_creates_pr_with_summary
Creating test project: test-project-a1b2c3d4
Committing and pushing test project...
Triggering workflow: claudestep.yml
Workflow run ID: 12345678
Waiting for workflow completion...
  Status: queued
  Status: in_progress
  Status: completed (success)
Checking for PR on branch: refactor/test-project-a1b2c3d4-1
  ✓ Found PR #123
  ✓ AI-generated summary found
  ✓ Cost information found ($0.XX)
Cleaning up test resources...
  ✓ Closed PR #123
  ✓ Deleted branch refactor/test-project-a1b2c3d4-1
  ✓ Removed test project
PASSED                                                    [100%]

=============================== 1 passed in 142.35s ================================
```

## Troubleshooting

### "gh CLI not found"
```bash
brew install gh
gh auth login
```

### "pytest not found"
```bash
pip install pytest pyyaml
```

### "git user.name not configured"
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### "Permission denied"
- Ensure you have write access to the repository
- Check that `gh auth status` shows you're authenticated

### "Workflow not found"
- Ensure `.github/workflows/claudestep.yml` exists
- Check that you're on the correct branch

### "Test hangs during workflow wait"
- Check workflow logs: `gh run view <run_id> --log`
- Verify ANTHROPIC_API_KEY is configured as a GitHub secret
- Check GitHub Actions status page for service issues

### "Cleanup failed"
- Tests use fixtures to ensure cleanup even on failure
- Manually check for leftover resources:
  ```bash
  # List test PRs
  gh pr list --label claude-step

  # List test branches
  git branch -r | grep refactor/test-project-

  # Check for test projects
  ls -la claude-step/ | grep test-project-
  ```

## Debugging E2E Test Failures

### Overview of Diagnostic Features (Phase 6)

The E2E test suite includes comprehensive diagnostics added in Phase 6:

1. **Detailed Logging**: Timestamped logs of all GitHub API operations with timing
2. **Workflow URLs**: Direct links to workflow runs in error messages and logs
3. **Artifact Upload**: Full test output and diagnostics uploaded on failure
4. **Enhanced Assertions**: Clear error messages with context about expected vs actual state
5. **Smart Polling**: Logs poll count and elapsed time for performance analysis

### Reading Test Output

Test output includes detailed logging of all operations:

```
2025-12-28 10:15:23 [INFO] Triggering workflow 'claudestep.yml' with inputs: {'projectId': 'test-project-abc123', ...}
2025-12-28 10:15:24 [INFO] Workflow triggered successfully. Run ID: 12345678
2025-12-28 10:15:24 [INFO] Workflow URL: https://github.com/gestrich/claude-step/actions/runs/12345678
2025-12-28 10:15:24 [DEBUG] Waiting for workflow to start (timeout: 30s)...
2025-12-28 10:15:26 [DEBUG] Workflow started (poll 1, elapsed 2.1s)
2025-12-28 10:15:26 [INFO] Waiting for workflow completion (timeout: 900s)...
2025-12-28 10:15:36 [DEBUG] Workflow status: in_progress (poll 1, elapsed 10.0s)
2025-12-28 10:20:24 [DEBUG] Workflow status changed: in_progress → completed
2025-12-28 10:20:24 [INFO] Workflow completed with conclusion: success (total time: 298.3s)
```

### Understanding Test Failures

#### 1. Timeout Errors

**Symptom**: `TimeoutError: Workflow did not complete within 900 seconds`

**Diagnostic Steps**:
1. **Check workflow URL** in the error message:
   ```
   TimeoutError: Workflow did not complete within 900 seconds.
   Workflow URL: https://github.com/gestrich/claude-step/actions/runs/12345678
   ```
2. **View workflow logs**:
   ```bash
   gh run view 12345678 --log
   ```
3. **Check for stuck steps**:
   - Look for steps that are taking unusually long
   - Claude Code Action steps typically take 3-7 minutes
   - PR summary generation typically takes 1-3 minutes
4. **Check poll logs** to identify when workflow got stuck:
   ```
   [DEBUG] Workflow status: in_progress (poll 45, elapsed 450.0s)
   [DEBUG] Workflow status: in_progress (poll 46, elapsed 460.0s)
   ```

**Common Causes**:
- **Claude API latency**: Claude API calls taking longer than usual
  - Solution: Retry the test; API latency varies
- **GitHub Actions queue**: Workflow waiting for available runner
  - Solution: Check GitHub Actions status page; retry later
- **Large PR diffs**: PR summary analyzing very large changes
  - Solution: Reduce task complexity in test; consider smaller test cases
- **Network issues**: Connectivity problems to GitHub or Claude API
  - Solution: Check network connection; retry test

**Resolution**:
- For legitimate slow operations: Test timeout is already generous (15 minutes)
- For infrastructure issues: Retry the test
- For persistent issues: Investigate workflow logs at the provided URL

#### 2. Missing AI Summary

**Symptom**: `AssertionError: PR should have an AI-generated summary comment`

**Diagnostic Steps**:
1. **Check PR URL** in error message for comment count:
   ```
   AssertionError: PR should have an AI-generated summary comment.
   Found 1 comments on PR https://github.com/gestrich/claude-step/pull/123
   ```
2. **View PR comments**:
   ```bash
   gh pr view 123 --comments
   ```
3. **Check workflow logs** for summary generation step:
   ```bash
   gh run view <run_id> --log | grep -A 20 "Generate and post PR summary"
   ```
4. **Look for errors** in the summary step:
   - Missing ANTHROPIC_API_KEY
   - Tool access issues (requires Bash and Write tools)
   - gh CLI authentication failures

**Common Causes** (Fixed in Phase 2):
- **Missing Write tool**: Claude Code needs Write tool to create temp file for comment body
  - Fixed: action.yml now includes `--allowedTools Bash,Write` (line 191)
- **Silent failures**: Errors were being suppressed by `continue-on-error: true`
  - Fixed: Removed continue-on-error flag to surface errors (line 193)
- **API authentication**: Missing or invalid ANTHROPIC_API_KEY
  - Solution: Verify secret is configured in repository settings

**Resolution**:
- Phase 2 fixes should prevent this issue
- If still occurring, check workflow logs for specific error in summary step

#### 3. Test Flakiness and Race Conditions

**Symptom**: Tests pass sometimes but fail intermittently

**Improvements Made** (Phase 7):
- **Smart polling**: Replaced fixed `time.sleep(5)` with condition-based waiting
  - Waits for workflow to actually appear in API before proceeding
  - Eliminates race conditions from checking too early
- **Pre-test cleanup**: Automatically cleans up resources from previous failed runs
  - Prevents state pollution between test runs
  - Makes tests idempotent and safe to retry
- **Condition-based waiting**: `wait_for_condition()` helper adapts to timing variations
  - Polls until condition is met instead of assuming fixed timing
  - Logs poll count and elapsed time for visibility

**Diagnostic Steps**:
1. **Check for timing-related patterns** in logs:
   ```
   [DEBUG] Workflow started (poll 3, elapsed 6.2s)  # Good: detected in 6s
   [DEBUG] Workflow started (poll 1, elapsed 2.1s)  # Good: detected quickly
   ```
2. **Look for cleanup warnings**:
   ```
   [INFO] Cleaned up 2 test branches from previous runs
   [INFO] Cleaned up 1 test PR from previous runs
   ```
3. **Check elapsed times** for workflow detection and completion

**Resolution**:
- Phase 7 improvements should significantly reduce flakiness
- If still flaky, check for environmental issues (network, GitHub API status)

#### 4. Assertion Failures with Context

Error messages now include full diagnostic context:

```python
# Example: PR state assertion
AssertionError: Expected PR to be open
  PR #123: https://github.com/gestrich/claude-step/pull/123
  Actual state: closed
  Workflow: https://github.com/gestrich/claude-step/actions/runs/12345678

# Example: Comment verification
AssertionError: PR should have an AI-generated summary comment
  Found 1 comments on PR https://github.com/gestrich/claude-step/pull/123
  Workflow: https://github.com/gestrich/claude-step/actions/runs/12345678
```

### Accessing Workflow Artifacts

When tests fail in GitHub Actions, diagnostic artifacts are automatically uploaded:

1. **View failed workflow run** in GitHub Actions UI
2. **Download artifacts**:
   - e2e-test-diagnostics.zip contains:
     - Full test output log (e2e-test-output.log)
     - E2E workflow configuration
     - All test files for reference
3. **Review artifacts**:
   ```bash
   unzip e2e-test-diagnostics.zip
   cat e2e-test-output.log  # Full test output with timestamps
   ```

### Manually Inspecting Test State

During or after a test run:

```bash
# View workflow run with logs
gh run view <run_id> --log

# List recent workflow runs
gh run list --workflow=claudestep.yml --limit 10

# View specific PR
gh pr view <pr_number> --comments

# Check PR diff
gh pr diff <pr_number>

# List test branches
git branch -r | grep "refactor/test-project-"

# List test PRs
gh pr list --search "ClaudeStep" --state all --limit 20
```

### Common Debugging Workflow

1. **Read the error message** - includes workflow URL, PR URL, and diagnostic context
2. **Check workflow logs** - `gh run view <run_id> --log`
3. **Review test output** - look for timing, status changes, and poll counts
4. **Inspect PR state** - `gh pr view <pr_number> --comments`
5. **Check for infrastructure issues** - GitHub Actions status, API availability
6. **Retry if transient** - network, API latency, runner queue issues
7. **Report persistent failures** - with workflow URL and diagnostics

### Performance Analysis

Use logged timing information to identify bottlenecks:

```bash
# Find slow workflow runs
grep "Workflow completed" e2e-test-output.log
# Example output: "Workflow completed with conclusion: success (total time: 543.2s)"

# Track poll counts (indicates how long waits took)
grep "poll" e2e-test-output.log
# High poll counts may indicate slow operations

# Find workflow status changes
grep "status changed" e2e-test-output.log
# Shows when workflow transitioned between states
```

**Expected Performance**:
- Workflow start detection: 2-10 seconds (1-5 polls)
- Workflow completion: 300-500 seconds (30-50 polls at 10s interval)
- Total test time (single workflow): 2-3 minutes
- Total test time (3 workflows): 10-15 minutes

**Concerning Performance**:
- Workflow start detection: >30 seconds (indicates API latency or runner queue)
- Workflow completion: >900 seconds (timeout threshold, indicates stuck workflow)
- Very high poll counts: May indicate inefficient polling or stuck operations

## Test Isolation

Each test run is isolated:

1. **Unique project IDs**: `test-project-{uuid}` prevents conflicts
2. **Unique branches**: `refactor/test-project-{uuid}-{index}`
3. **Independent workflows**: Each test triggers separate workflow runs
4. **Automatic cleanup**: Fixtures ensure resources are removed even on failure

## CI/CD Integration

Tests can run in GitHub Actions via `.github/workflows/e2e-test.yml`:

```bash
# Trigger manually
gh workflow run e2e-test.yml

# Check status
gh run list --workflow=e2e-test.yml
```

**Note:** E2E tests are typically run manually due to:
- API costs (Claude API credits)
- Execution time (5-10 minutes)
- Real repository operations

## Important Notes

1. **Real Operations**: Tests create actual PRs, branches, and workflow runs
2. **API Costs**: Each run uses Claude API credits for:
   - Task execution
   - PR summary generation
   - Cost estimation
3. **Cleanup**: All resources are cleaned up automatically
4. **Self-Testing**: The action tests itself using `uses: ./`
5. **Test Artifacts**: Projects named `test-project-*` are temporary and gitignored

## Contributing

When adding new tests:

1. Use the existing fixtures (`gh`, `project_id`, `test_project`)
2. Ensure cleanup happens even on failure
3. Use unique test project names
4. Add docstrings explaining what the test validates
5. Follow the existing pattern of create → trigger → verify → cleanup

## Further Documentation

- [E2E Testing Guide](../../docs/feature-architecture/e2e-testing.md) - Comprehensive guide
- [Testing Philosophy](../../docs/general-architecture/testing-philosophy.md) - Testing approach and requirements
- [Migration Plan](../../docs/specs/archive/2025-12-28-e2e-test-migration.md) - Background and design

## Need Help?

- Check the [troubleshooting section](#troubleshooting) above
- Review workflow logs: `gh run view <run_id> --log`
- See [docs/feature-architecture/e2e-testing.md](../../docs/feature-architecture/e2e-testing.md) for details
- Open an issue with test output and workflow logs
