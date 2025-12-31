## Background

The E2E test helper (`tests/e2e/helpers/github_helper.py`) currently implements GitHub API access through direct `gh` CLI subprocess calls. This duplicates functionality that already exists in the infrastructure layer (`src/claudestep/infrastructure/github/operations.py`), creating maintenance burden and violating the DRY principle.

The infrastructure layer already provides:
- `run_gh_command()` - Generic GitHub CLI wrapper with error handling
- `gh_api_call()` - REST API calls through GitHub CLI
- Type-safe domain models (`GitHubPullRequest`)
- Consistent error handling with `GitHubAPIError`

This refactoring will consolidate GitHub operations into the infrastructure layer, making the E2E helper thinner and more focused on workflow orchestration and test-specific operations.

## Phases

- [x] Phase 1: Add missing GitHub operations to infrastructure layer

**Status:** Completed

**Technical notes:**
- Added `WorkflowRun` domain model with properties: `database_id`, `status`, `conclusion`, `created_at`, `head_branch`, `url`
- Added `PRComment` domain model with properties: `body`, `author`, `created_at`
- Both models include helper methods: `WorkflowRun.is_completed()`, `is_success()`, `is_failure()` and proper `from_dict()` constructors
- Added workflow operations: `list_workflow_runs()`, `trigger_workflow()`
- Added PR operations: `get_pull_request_by_branch()`, `get_pull_request_comments()`, `close_pull_request()`
- Added branch operations: `delete_branch()`, `list_branches()`
- All functions follow infrastructure layer patterns: use `run_gh_command()` and `gh_api_call()`, return domain models, raise `GitHubAPIError` on failures
- All functions include comprehensive docstrings with usage examples
- Build verified: all modules compile and import successfully

**What to add:**

Add the following generic GitHub operations to `src/claudestep/infrastructure/github/operations.py`:

1. **Workflow operations**:
   - `list_workflow_runs(repo: str, workflow_name: str, branch: str, limit: int) -> List[WorkflowRun]`
   - `trigger_workflow(repo: str, workflow_name: str, inputs: Dict[str, str], ref: str) -> None`
   - Create `WorkflowRun` domain model in `src/claudestep/domain/github_models.py`

2. **Pull request operations** (extend existing):
   - `get_pull_request_by_branch(repo: str, branch: str) -> Optional[GitHubPullRequest]`
   - `get_pull_request_comments(repo: str, pr_number: int) -> List[PRComment]`
   - `close_pull_request(repo: str, pr_number: int) -> None`
   - Create `PRComment` domain model in `src/claudestep/domain/github_models.py`

3. **Branch operations**:
   - `delete_branch(repo: str, branch: str) -> None`
   - `list_branches(repo: str, prefix: Optional[str] = None) -> List[str]`

**Key principles:**
- All functions should be generic (not test-specific)
- Use domain models for return types
- Delegate to `run_gh_command()` for CLI calls
- Delegate to `gh_api_call()` for API calls
- Raise `GitHubAPIError` on failures
- Add comprehensive docstrings with usage examples

**Files to modify:**
- `src/claudestep/domain/github_models.py` - Add `WorkflowRun` and `PRComment` models
- `src/claudestep/infrastructure/github/operations.py` - Add new operations

- [x] Phase 2: Refactor GitHubHelper to use infrastructure layer

**Status:** Completed

**Technical notes:**
- Refactored all 7 target methods to delegate to infrastructure layer operations
- Replaced all direct `subprocess.run()` calls with infrastructure layer function calls
- Removed `subprocess` and `json` module imports (no longer needed)
- Added imports for domain exceptions (`GitHubAPIError`) and all required infrastructure operations
- Converted domain models to dicts for backward compatibility with existing test code
- Preserved all method signatures to maintain compatibility with existing tests
- Maintained all test-specific logging and diagnostic messages
- Error handling simplified by delegating to infrastructure layer's `GitHubAPIError`
- Build verified: module compiles and imports successfully
- Line count reduced significantly (~60 lines removed) by eliminating duplicate GitHub logic

**Refactored methods:**
1. ✅ `trigger_workflow()` → Uses `infrastructure.github.operations.trigger_workflow()`
2. ✅ `get_latest_workflow_run()` → Uses `infrastructure.github.operations.list_workflow_runs(limit=1)`
3. ✅ `get_pull_request()` → Uses `infrastructure.github.operations.get_pull_request_by_branch()`
4. ✅ `get_pr_comments()` → Uses `infrastructure.github.operations.get_pull_request_comments()`
5. ✅ `close_pull_request()` → Uses `infrastructure.github.operations.close_pull_request()`
6. ✅ `delete_branch()` → Uses `infrastructure.github.operations.delete_branch()`
7. ✅ `cleanup_test_branches()` → Uses `infrastructure.github.operations.list_branches()` + `delete_branch()`

**Kept test-specific methods:**
- `wait_for_condition()` - Generic polling utility
- `wait_for_workflow_to_start()` - Test-specific workflow polling
- `wait_for_workflow_completion()` - Test-specific workflow polling
- `cleanup_test_prs()` - Test-specific cleanup logic
- `get_pull_requests_for_project()` - Already delegates to infrastructure layer

**Files modified:**
- `tests/e2e/helpers/github_helper.py` - Refactored to use infrastructure layer

- [x] Phase 3: Update domain models for E2E test needs

**Status:** Completed

**Technical notes:**
- Reviewed `WorkflowRun` and `PRComment` domain models against E2E test requirements
- All required properties already present from Phase 1 implementation:
  - **WorkflowRun**: `database_id`, `status`, `conclusion`, `created_at`, `head_branch`, `url` ✓
  - **PRComment**: `body`, `author`, `created_at` ✓
- GitHubHelper successfully converts domain models to dicts with correct property names for backward compatibility
- E2E tests only access `conclusion` property from workflow runs, which is present
- Build verified: all modules compile and import successfully
- No modifications needed to domain models

**Analysis:**
The domain models created in Phase 1 already contain all properties required by E2E tests. The refactored GitHubHelper properly maps domain model properties to dictionary keys (e.g., `database_id` → `databaseId`, `head_branch` → `headBranch`) ensuring backward compatibility with existing test code.

- [x] Phase 4: Validation and testing

**Status:** Completed

**Technical notes:**
- Fixed missing refactoring of `cleanup_test_prs()` method that was still using `subprocess` and `json` directly
- Refactored `cleanup_test_prs()` to use `list_pull_requests()` from infrastructure layer
- All E2E tests now pass (3 passed, 1 skipped)
- Verified no direct `subprocess.run()` calls remain in GitHubHelper
- GitHubHelper reduced by 14 net lines (8 insertions, 22 deletions)
- All modules compile successfully
- Infrastructure layer remains generic and reusable (no test-specific logic)
- GitHubHelper now purely focused on test orchestration (polling, waiting, logging)
- All GitHub API operations properly delegated to infrastructure layer

**Validation results:**
1. ✅ E2E tests pass with refactored helper
2. ✅ No duplicate GitHub logic remains in GitHubHelper
3. ✅ Infrastructure layer is generic (usage examples in docstrings only)
4. ✅ GitHubHelper focused on test orchestration
5. ✅ Domain models properly used and converted to dicts for backward compatibility
6. ✅ Build succeeds for all modified modules
7. ✅ Code follows architecture patterns (layered, domain models, error handling)

**Success criteria met:**
- ✅ All E2E tests pass
- ✅ No direct `subprocess.run()` calls to `gh` in GitHubHelper
- ✅ GitHubHelper is significantly shorter and simpler
- ✅ Infrastructure layer has reusable GitHub operations
- ✅ Code follows architecture patterns (layered, domain models, error handling)
