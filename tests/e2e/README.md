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

- **Full test suite**: 5-10 minutes
- **Single workflow test**: 2-3 minutes
- **Statistics test**: 1-2 minutes
- **Per workflow run**: 60-120 seconds
- **Cleanup per test**: 5-10 seconds

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

- [E2E Testing Guide](../../docs/architecture/e2e-testing.md) - Comprehensive guide
- [Local Testing Setup](../../docs/architecture/local-testing.md) - Development setup
- [Migration Plan](../../docs/proposed/e2e-test-migration.md) - Background and design

## Need Help?

- Check the [troubleshooting section](#troubleshooting) above
- Review workflow logs: `gh run view <run_id> --log`
- See [docs/architecture/e2e-testing.md](../../docs/architecture/e2e-testing.md) for details
- Open an issue with test output and workflow logs
