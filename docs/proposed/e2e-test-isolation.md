# E2E Test Isolation Plan

## Problem

E2E tests pollute the main branch by:
- Creating test projects in `claude-step/` directory on main
- Test-specific workflows (statistics, merge triggers) exist on main but only used for tests
- Causing git push conflicts during concurrent test runs
- Leaving test artifacts in repository history
- Creating merge conflicts with development work

## Solution

Use an **ephemeral `e2e-test` branch** that is deleted and recreated fresh for each test run.

### What Lives on Main Branch

**E2E test code lives on main** (like any other code):
- `tests/e2e/` - All test files and helpers
- `.github/workflows/e2e-test.yml` - Workflow that orchestrates test execution
- Test fixtures, utilities, and helper classes

### What Lives on Ephemeral Test Branch

**Test execution happens on isolated branch** (created fresh each run):
- `claude-step/` - Test projects created during test execution
- `.github/workflows/claudestep-test.yml` - Workflow triggered by tests (written dynamically)
- `.github/workflows/statistics/` - Statistics workflow triggered on PR merge (written dynamically)
- Test-specific workflows that trigger on git events (push, merge, etc.)

### Key Principle

**Code on main, execution on ephemeral branch**:
- Test code is version-controlled on main
- Test execution (pushing projects, creating PRs, merging) happens on e2e-test branch
- Main branch stays clean - no test execution artifacts

## Implementation Phases

- [ ] **Phase 1: Clean Main Branch**
  - Remove `claude-step/` directory from main
  - Remove test-specific workflows from main (statistics.yml, claudestep-test.yml)
  - Commit: "Remove E2E test infrastructure from main - moving to ephemeral test branches"
  - Push to main

- [ ] **Phase 2: Add Test Setup Helper**
  - Create `tests/e2e/helpers/test_branch_manager.py` to manage ephemeral branch
  - Implement: `setup_test_branch()` - deletes and recreates e2e-test branch
  - Implement: `create_test_workflows()` - writes test-specific workflows to branch
  - Implement: `cleanup_test_branch()` - deletes branch after tests

- [ ] **Phase 3: Update E2E Test Workflow**
  - Update `.github/workflows/e2e-test.yml` to:
    - Delete e2e-test branch if exists (clean slate)
    - Create fresh e2e-test branch from main
    - Write test workflows (statistics.yml, claudestep-test.yml) to branch
    - Run tests on the e2e-test branch
    - Optionally delete branch after tests complete

- [ ] **Phase 4: Update Test Code**
  - `tests/e2e/helpers/project_manager.py`: Change default branch to `e2e-test`
  - `tests/e2e/helpers/github_helper.py`: Change default ref to `e2e-test`
  - `tests/e2e/test_workflow_e2e.py`: Update workflow triggers to use `e2e-test`
  - Add test fixtures that call `setup_test_branch()` before tests

- [ ] **Phase 5: Test and Document**
  - Run E2E tests to verify clean branch creation works
  - Verify main branch has no test execution artifacts (claude-step/, test workflows)
  - Create/update `docs/architecture/e2e-testing.md` documenting the ephemeral branch approach
  - Document test isolation architecture and workflow

## Detailed Implementation

### Phase 1: Clean Main Branch

**Remove from main**:
- `claude-step/` directory (entire)
- `.github/workflows/claudestep-test.yml` (test-only workflow)
- `.github/workflows/statistics/action.yml` if it's test-specific

**Commands**:
```bash
git checkout main
git pull origin main
git rm -rf claude-step/
git rm .github/workflows/claudestep-test.yml
# Remove other test-specific workflows if any
git commit -m "Remove E2E test infrastructure from main - moving to ephemeral test branches"
git push origin main
```

### Phase 2: Create Test Branch Manager

**Create `tests/e2e/helpers/test_branch_manager.py`**:

```python
"""Manager for ephemeral E2E test branch lifecycle."""

import subprocess
from pathlib import Path
from typing import Optional

class TestBranchManager:
    """Manages creation and cleanup of ephemeral test branch."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True
            )
            repo_root = Path(result.stdout.strip())
        self.repo_root = repo_root
        self.test_branch = "e2e-test"

    def delete_remote_branch(self) -> None:
        """Delete e2e-test branch from remote if it exists."""
        # Check if branch exists on remote
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", self.test_branch],
            capture_output=True, text=True, cwd=self.repo_root
        )

        if result.stdout.strip():
            # Branch exists, delete it
            subprocess.run(
                ["git", "push", "origin", "--delete", self.test_branch],
                cwd=self.repo_root, check=True
            )

    def create_fresh_branch(self) -> None:
        """Create fresh e2e-test branch from current main."""
        # Ensure we're on main and up to date
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "pull", "origin", "main"], cwd=self.repo_root, check=True)

        # Delete local branch if exists
        subprocess.run(
            ["git", "branch", "-D", self.test_branch],
            cwd=self.repo_root, capture_output=True
        )

        # Create new branch
        subprocess.run(
            ["git", "checkout", "-b", self.test_branch],
            cwd=self.repo_root, check=True
        )

    def create_test_workflows(self) -> None:
        """Write test-specific workflows to the test branch."""
        workflows_dir = self.repo_root / ".github" / "workflows"

        # Create claudestep-test.yml
        claudestep_test = workflows_dir / "claudestep-test.yml"
        claudestep_test.write_text(self._get_claudestep_test_workflow())

        # Create statistics workflow if needed
        # ... add other test-specific workflows

        # Commit the workflows
        subprocess.run(
            ["git", "add", ".github/workflows/"],
            cwd=self.repo_root, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add test-specific workflows for E2E testing"],
            cwd=self.repo_root, check=True
        )

    def create_test_workspace(self) -> None:
        """Create claude-step/ directory for test projects."""
        workspace = self.repo_root / "claude-step"
        workspace.mkdir(exist_ok=True)

        readme = workspace / "README.md"
        readme.write_text("""# E2E Test Workspace

This directory is used exclusively for E2E testing on ephemeral test branches.
Test projects are created here during test runs and cleaned up afterwards.

**This branch is ephemeral** - it's deleted and recreated for each test run.
""")

        subprocess.run(
            ["git", "add", "claude-step/"],
            cwd=self.repo_root, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Create test workspace directory"],
            cwd=self.repo_root, check=True
        )

    def push_test_branch(self) -> None:
        """Push the test branch to remote."""
        subprocess.run(
            ["git", "push", "-u", "origin", self.test_branch],
            cwd=self.repo_root, check=True
        )

    def setup_test_branch(self) -> None:
        """Complete setup: delete old branch, create fresh one with workflows."""
        print("Setting up ephemeral E2E test branch...")
        self.delete_remote_branch()
        self.create_fresh_branch()
        self.create_test_workflows()
        self.create_test_workspace()
        self.push_test_branch()
        print(f"✓ Test branch '{self.test_branch}' ready for testing")

    def cleanup_test_branch(self) -> None:
        """Delete the test branch after tests complete."""
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True)
        self.delete_remote_branch()
        subprocess.run(
            ["git", "branch", "-D", self.test_branch],
            cwd=self.repo_root, capture_output=True
        )
        print(f"✓ Cleaned up test branch '{self.test_branch}'")

    def _get_claudestep_test_workflow(self) -> str:
        """Return claudestep-test.yml workflow content."""
        return """name: ClaudeStep Test

on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name in claude-step directory'
        required: true
      base_branch:
        description: 'Base branch for pull requests'
        required: false
        default: 'e2e-test'

jobs:
  run-claudestep:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: e2e-test

      - name: Run ClaudeStep action
        uses: ./
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: ${{ github.event.inputs.project_name }}
          base_branch: ${{ github.event.inputs.base_branch || 'e2e-test' }}
"""
```

### Phase 3: Update E2E Test Workflow

**Modify `.github/workflows/e2e-test.yml`**:

```yaml
name: E2E Integration Tests

on:
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  actions: write

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
          git config --global user.name 'ClaudeStep E2E Tests'
          git config --global user.email 'claudestep-e2e@users.noreply.github.com'

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

      # Leave branch for debugging on failure
      - name: Branch left for debugging
        if: failure()
        run: echo "Test branch 'e2e-test' left intact for debugging"
```

### Phase 4: Update Test Code

**`tests/e2e/conftest.py`** (add fixture):
```python
import pytest
from .helpers.test_branch_manager import TestBranchManager

@pytest.fixture(scope="session", autouse=True)
def test_branch():
    """Ensure test branch exists before running tests."""
    # Branch should already be set up by workflow, but verify it exists
    manager = TestBranchManager()
    # Could add validation here
    yield
    # Cleanup handled by workflow
```

**Update default branch in helpers**:
- `tests/e2e/helpers/project_manager.py`: `branch: str = "e2e-test"`
- `tests/e2e/helpers/github_helper.py`: `ref: str = "e2e-test"`

### Phase 5: Workflow Content Templates

**Test-specific workflows to be written during setup**:

1. **claudestep-test.yml** - Manual trigger for ClaudeStep on test projects
2. **statistics.yml** - PR merge trigger for statistics collection (if needed)

These are **not on main**, only created on the ephemeral e2e-test branch.

## Benefits

1. **Completely clean main branch** - No test infrastructure at all
2. **Consistent test environment** - Every test starts from known state
3. **No conflicts** - Each test run has its own isolated branch
4. **Easy debugging** - Failed test branches can be left for investigation
5. **True isolation** - Test workflows can't accidentally trigger on main

## Test Workflow Flow

1. E2E test workflow starts
2. Deletes old e2e-test branch (if exists)
3. Creates fresh e2e-test branch from main
4. Writes test-specific workflows to e2e-test branch
5. Creates claude-step/ workspace
6. Pushes e2e-test branch
7. Runs E2E tests (which trigger test workflows on e2e-test branch)
8. On success: Deletes e2e-test branch
9. On failure: Leaves branch for debugging

## Migration Checklist

- [ ] Review and approve this plan
- [ ] Execute Phase 1 (clean main)
- [ ] Execute Phase 2 (create test branch manager)
- [ ] Execute Phase 3 (update e2e-test.yml workflow)
- [ ] Execute Phase 4 (update test code)
- [ ] Execute Phase 5 (test and document)
- [ ] Verify main branch is clean
- [ ] Verify tests work with ephemeral branch
