# E2E Tests: Local Execution with GitHub API File Creation

## Background

The current E2E test architecture runs tests remotely via a GitHub Actions workflow (`e2e-test.yml`). This was designed to avoid corrupting local git state when running tests. However, this approach has significant limitations:

1. **Push events don't trigger workflows** - When code is pushed using `GITHUB_TOKEN` from within a workflow, GitHub suppresses push events (security feature to prevent infinite loops). This means we can't test the real push-triggered workflow behavior.

2. **Workarounds are superficial** - Using `workflow_dispatch` to manually trigger workflows doesn't test the actual user flow where pushing a spec to `main` triggers automatic PR creation.

3. **Nobody runs E2E tests remotely** - In practice, developers run tests locally. The remote execution adds complexity without real benefit.

**The Solution**: Run E2E tests locally, but use the GitHub API to create files on remote branches instead of local git operations. When files are created via the GitHub Contents API (using a PAT or `gh` CLI), push events ARE triggered because these are real pushes, not workflow-internal operations.

### Key Insight

The `gh` CLI running locally uses your personal authentication (PAT or OAuth), not `GITHUB_TOKEN`. This means:
- Pushes via GitHub API from local machine **DO trigger** push events
- The `claudestep.yml` workflow will trigger naturally when we push spec files to `main-e2e`

## Phases

- [ ] Phase 1: Add `create_or_update_file` to Infrastructure Layer

Add a new function to `src/claudestep/infrastructure/github/operations.py` that creates or updates files via the GitHub Contents API.

**Files to modify:**
- `src/claudestep/infrastructure/github/operations.py` - Add `create_or_update_file()` function

**Implementation details:**
- Use `gh api` with PUT method to `/repos/{repo}/contents/{path}`
- Accept parameters: `repo`, `branch`, `file_path`, `content`, `commit_message`
- Handle base64 encoding of content
- Return the commit SHA on success
- Follow existing patterns in the file (error handling, docstrings, etc.)

**API Reference:**
```bash
gh api /repos/{owner}/{repo}/contents/{path} \
  --method PUT \
  -f message="commit message" \
  -f content="$(echo -n 'file content' | base64)" \
  -f branch="branch-name"
```

- [ ] Phase 2: Add `create_branch_from_ref` to Infrastructure Layer

Add a function to create a new branch from an existing ref via the GitHub API.

**Files to modify:**
- `src/claudestep/infrastructure/github/operations.py` - Add `create_branch_from_ref()` function

**Implementation details:**
- Use `gh api` with POST to `/repos/{repo}/git/refs`
- Accept parameters: `repo`, `new_branch`, `source_ref` (branch or SHA)
- First get the SHA of the source ref, then create the new branch pointing to it
- Follow existing patterns in the file

- [ ] Phase 3: Update `setup_test_project` Fixture to Use GitHub API

Modify the fixture to create test project files via GitHub API instead of local git operations.

**Files to modify:**
- `tests/e2e/conftest.py` - Update `setup_test_project` fixture

**New approach:**
1. Push current HEAD to `main-e2e` (handled by session fixture)
2. Use `create_or_update_file()` to push `spec.md`, `configuration.yml`, `pr-template.md` to `main-e2e`
3. This triggers `claudestep.yml` naturally via push event
4. Remove the explicit `trigger_workflow()` call (no longer needed)

**Key changes:**
- Remove dependency on `TestProjectManager` (which uses local git)
- Use `GitHubHelper` with new infrastructure functions
- Files are created directly on remote `main-e2e` branch

- [ ] Phase 4: Move `run_test.sh` Logic into Session Fixtures

Move the setup logic from `run_test.sh` into pytest session-scoped fixtures.

**Files to modify:**
- `tests/e2e/conftest.py` - Update session fixtures
- `tests/e2e/run_test.sh` - Simplify or remove

**Logic to move:**
1. Force push current HEAD to `main-e2e` branch
2. Clean up old test PRs and branches

**New fixture structure:**
```python
@pytest.fixture(scope="session", autouse=True)
def setup_e2e_environment():
    """Push current HEAD to main-e2e and clean up old test artifacts."""
    # Force push HEAD to main-e2e
    subprocess.run(["git", "push", "origin", "HEAD:main-e2e", "--force"], check=True)

    # Clean up old PRs/branches
    gh = GitHubHelper(repo="gestrich/claude-step")
    gh.cleanup_test_branches(...)
    gh.cleanup_test_prs(...)

    yield
    # Optional: cleanup after tests
```

- [ ] Phase 5: Update Test Files to Remove workflow_dispatch

Revert the recent changes that added explicit `workflow_dispatch` triggering and update docstrings.

**Files to modify:**
- `tests/e2e/test_workflow_e2e.py` - Remove `trigger_workflow()` calls, update docstrings
- `tests/e2e/conftest.py` - Remove `trigger_workflow()` from fixture

**Changes:**
- Tests now rely on natural push-triggered workflow execution
- Update docstrings to reflect new architecture
- Simplify test logic (just wait for workflow, don't trigger it)

- [ ] Phase 6: Remove `TestProjectManager` and Simplify Helpers

Remove the now-unused `TestProjectManager` class and simplify the helper structure.

**Files to modify/delete:**
- `tests/e2e/helpers/project_manager.py` - Delete (no longer needed)
- `tests/e2e/helpers/test_branch_manager.py` - Possibly simplify or remove
- `tests/e2e/conftest.py` - Remove `project_manager` fixture

**Rationale:**
- `TestProjectManager` used local git operations which we're replacing with GitHub API
- `TestBranchManager` may still be useful for the force-push logic, or can be inlined

- [ ] Phase 7: Delete E2E Workflow File

Remove the GitHub Actions workflow that ran E2E tests remotely.

**Files to delete:**
- `.github/workflows/e2e-test.yml`

**Rationale:**
- E2E tests now run locally via `pytest tests/e2e/`
- No need for remote execution workflow

- [ ] Phase 8: Update Documentation

Update documentation to reflect the new E2E test architecture.

**Files to modify:**
- `tests/e2e/README.md` - Update with new instructions
- `docs/general-architecture/testing-philosophy.md` - Update E2E section if needed
- `tests/e2e/run_test.sh` - Either delete or simplify to just run pytest

**New instructions:**
```bash
# Run E2E tests locally
cd /path/to/claude-step
pytest tests/e2e/ -v

# Prerequisites:
# - gh CLI authenticated
# - Write access to repository
# - ANTHROPIC_API_KEY set (for AI generation)
```

- [ ] Phase 9: Validation

**Automated testing:**
1. Run unit tests to ensure infrastructure changes don't break anything:
   ```bash
   pytest tests/unit/ -v
   ```

2. Run E2E tests locally to verify the new architecture works:
   ```bash
   pytest tests/e2e/ -v
   ```

**Manual verification:**
1. Verify push to `main-e2e` triggers `claudestep.yml` (check GitHub Actions)
2. Verify PRs are created with correct labels and comments
3. Verify merge-triggered workflow still works

**Success criteria:**
- All unit tests pass
- E2E tests complete successfully when run locally
- `claudestep.yml` triggers naturally on push (not via `workflow_dispatch`)
- No local git state corruption (tests only use GitHub API for file operations)
