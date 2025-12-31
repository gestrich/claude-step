# GitHub PR Service Abstraction

## Background

Currently, business logic for working with GitHub PRs is scattered across multiple services. Code that directly queries the GitHub API and parses PR data (branch names, title prefixes, etc.) appears in multiple places, violating the Single Responsibility Principle and making the code harder to maintain.

**Current Problems:**

1. **Business logic in wrong layer**: Services like `ReviewerManagementService` and `StatisticsService` contain code that:
   - Calls GitHub API operations directly (`list_pull_requests()`, `list_open_pull_requests()`)
   - Parses branch names to extract project and task index
   - Strips "ClaudeStep: " prefix from PR titles
   - Constructs PR info dictionaries manually

2. **Duplicated parsing logic**: The same patterns appear in multiple services:
   ```python
   # Extract task description from PR title
   task_description = pr.title
   if task_description.startswith("ClaudeStep: "):
       task_description = task_description[len("ClaudeStep: "):]
   ```

3. **Mixed concerns**: Services mix PR data retrieval with business logic (reviewer capacity, statistics collection)

4. **Poor type safety**: Services work with dictionaries (`{"pr_number": ..., "task_index": ...}`) instead of domain models

**Desired Architecture:**

Following the Service Layer pattern documented in `docs/architecture/architecture.md`, we need:

- **Infrastructure Layer** (`src/claudestep/infrastructure/github/operations.py`): Already exists, handles raw GitHub API calls
- **Domain Layer** (`src/claudestep/domain/github_models.py`): Already has `GitHubPullRequest`, needs enhancement
- **EXISTING Service Layer** (`src/claudestep/services/pr_operations_service.py`): Extend to provide comprehensive PR querying with typed domain models
- **Application Services** (ReviewerManagementService, StatisticsService, TaskManagementService): Call through PROperationsService

This aligns with the "Parse Once Into Well-Formed Models" principle from `docs/architecture/python-code-style.md`.

**User Requirements:**

- Hide GitHub API details behind a service
- Centralize PR data retrieval and parsing
- Remove business logic (branch parsing, title prefix handling) from application services
- Services should ask for PR data through a clean API, not parse raw GitHub responses
- Type-safe domain models instead of dictionaries

## Phases

- [x] Phase 1: Refactor PROperationsService to use typed domain models

Refactor the existing `PROperationsService` to use typed `GitHubPullRequest` domain models instead of raw dictionaries, and add new querying methods.

**Tasks:**
- Refactor existing `get_project_prs()` method to return `List[GitHubPullRequest]` instead of `List[dict]`
  - Change infrastructure call from `run_gh_command()` to `list_pull_requests()` for consistency
  - Parse JSON response into `GitHubPullRequest` domain models
  - Keep existing filtering by project name (branch prefix)
- Add method `get_open_prs_for_project(project: str, label: str = "claudestep") -> List[GitHubPullRequest]`
  - Convenience wrapper for `get_project_prs(project, state="open", label=label)`
- Add method `get_open_prs_for_reviewer(username: str, label: str = "claudestep") -> List[GitHubPullRequest]`
  - Calls `list_open_pull_requests()` with `assignee` parameter
  - Returns typed domain models
- Add method `get_all_prs(label: str = "claudestep", state: str = "all", limit: int = 500) -> List[GitHubPullRequest]`
  - Calls `list_pull_requests()` from infrastructure layer
  - Returns all PRs with the label (for statistics and project discovery)
- Add method `get_unique_projects(label: str = "claudestep") -> Set[str]`
  - Calls `get_all_prs()` internally
  - Extracts unique project names from branch names using `parse_branch_name()`
  - Used by statistics service for multi-project discovery

**Files modified:**
- `src/claudestep/services/pr_operations_service.py` - Refactored to use typed domain models and added new querying methods
- `tests/unit/services/test_pr_operations.py` - Updated tests to mock infrastructure layer instead of removed `run_gh_command` import

**Technical notes:**
- Successfully migrated from dict-based return values to typed `GitHubPullRequest` domain models
- All existing tests updated and passing (573 tests pass)
- New methods follow consistent naming and API patterns
- Infrastructure layer properly abstracted through `list_pull_requests()` and `list_open_pull_requests()`

**Expected outcome:** ✅ COMPLETED - PROperationsService returns typed domain models and has comprehensive querying methods.

- [ ] Phase 2: Enhance GitHubPullRequest domain model

Extend the existing `GitHubPullRequest` domain model to include parsed project and task information as properties, eliminating the need for services to parse these manually.

**Tasks:**
- Add `@property` methods to `GitHubPullRequest` in `src/claudestep/domain/github_models.py`:
  - `project_name: Optional[str]` - Parses branch name, returns project (uses `PROperationsService.parse_branch_name()`)
  - `task_index: Optional[int]` - Parses branch name, returns task index
  - `task_description: str` - Returns title with "ClaudeStep: " prefix stripped if present
  - `is_claudestep_pr: bool` - Checks if branch name matches ClaudeStep pattern
- Add helper method `_parse_branch_info()` that calls `PROperationsService.parse_branch_name()` once and caches result

**Files to modify:**
- `src/claudestep/domain/github_models.py`

**Technical considerations:**
- Properties should compute on each access (no caching to avoid weird issues)
- Handle edge cases: invalid branch names, missing titles
- Reuse existing `PROperationsService.parse_branch_name()` - don't duplicate logic

**Expected outcome:** `GitHubPullRequest` model has typed properties for project, task index, and cleaned task description.

- [ ] Phase 3: Add reviewer-specific convenience methods to PROperationsService

Add convenience methods to `PROperationsService` for reviewer capacity checking operations.

**Tasks:**
- Add `get_reviewer_prs_for_project(username: str, project: str, label: str = "claudestep") -> List[GitHubPullRequest]`
  - Calls `get_open_prs_for_reviewer(username)`
  - Filters by `pr.project_name == project` (using domain model property)
  - Returns list of typed `GitHubPullRequest` models (not dicts!)
  - Used by ReviewerManagementService to get PR info for capacity checking
- Add `get_reviewer_pr_count(username: str, project: str, label: str = "claudestep") -> int`
  - Convenience method returning count of open PRs for reviewer on project
  - Internally calls `get_reviewer_prs_for_project()` and returns `len()`
  - Used for capacity checking

**Files to modify:**
- `src/claudestep/services/pr_operations_service.py`

**Expected outcome:** PROperationsService provides typed domain models for all operations, not dictionaries.

- [ ] Phase 4: Update ReviewerManagementService to use PROperationsService

Refactor `ReviewerManagementService` to use the enhanced `PROperationsService` instead of calling GitHub API operations directly.

**Tasks:**
- Update `ReviewerManagementService.__init__()` to accept `pr_operations_service: PROperationsService` as dependency
- Replace direct calls to `list_pull_requests()` with `pr_operations_service.get_reviewer_prs_for_project()`
- Use domain model properties instead of manual parsing: `pr.number`, `pr.task_index`, `pr.task_description`
- Remove manual branch parsing and title prefix stripping code
- Remove manual dictionary construction for PR info (work with typed `GitHubPullRequest` objects)
- Update all call sites in CLI commands to instantiate and pass `PROperationsService`

**Files to modify:**
- `src/claudestep/services/reviewer_management_service.py`
- `src/claudestep/cli/commands/prepare.py`
- Any other commands that instantiate `ReviewerManagementService`

**Technical considerations:**
- Follow dependency injection pattern: CLI creates `PROperationsService`, passes to `ReviewerManagementService`
- Maintain backward compatibility: method signatures should stay the same
- Remove the code snippet from the user's example (branch parsing, title prefix stripping)

**Expected outcome:** `ReviewerManagementService` uses clean service API, no GitHub API calls or parsing logic.

- [ ] Phase 5: Update TaskManagementService to use PROperationsService

Refactor `TaskManagementService` to use `PROperationsService` instead of calling GitHub API operations directly.

**Tasks:**
- Update `TaskManagementService.__init__()` to accept `pr_operations_service: PROperationsService` as dependency
- Replace direct call to `list_open_pull_requests()` in `get_in_progress_task_indices()` with `pr_operations_service.get_open_prs_for_project()`
- Remove manual branch parsing code (use domain model properties)
- Update all call sites in CLI commands to instantiate and pass `PROperationsService`

**Files to modify:**
- `src/claudestep/services/task_management_service.py`
- CLI commands that use `TaskManagementService` (likely `prepare.py`, `discover.py`)

**Expected outcome:** `TaskManagementService` uses service abstraction, no direct GitHub API calls.

- [ ] Phase 6: Update StatisticsService to use PROperationsService

Refactor `StatisticsService` to use `PROperationsService` instead of calling GitHub API operations directly.

**Tasks:**
- Update `StatisticsService.__init__()` to accept `pr_operations_service: PROperationsService` as dependency
- Replace direct calls to `list_pull_requests()`, `list_open_pull_requests()` with service methods
- Use `pr_operations_service.get_unique_projects()` for project discovery instead of manual branch parsing
- Remove manual branch parsing and title prefix stripping
- Update all call sites in CLI commands to instantiate and pass `PROperationsService`

**Files to modify:**
- `src/claudestep/services/statistics_service.py`
- `src/claudestep/cli/commands/statistics.py`

**Expected outcome:** `StatisticsService` uses service abstraction, no direct GitHub API calls.

- [ ] Phase 7: Search for other GitHub API usage in services

Find and refactor any remaining services that directly call GitHub API operations.

**Tasks:**
- Use `Grep` to search for `list_pull_requests`, `list_open_pull_requests`, `list_merged_pull_requests` in `src/claudestep/services/`
- Identify any services still calling infrastructure layer directly (excluding `PROperationsService` itself)
- Refactor each to use `PROperationsService`
- Update their constructors and call sites

**Files to potentially modify:**
- Any service files found with direct GitHub API usage
- Their corresponding CLI command files

**Note:** Based on current codebase analysis, the main services using GitHub API directly are:
- `ReviewerManagementService` (Phase 4)
- `TaskManagementService` (Phase 5)
- `StatisticsService` (Phase 6)

**Expected outcome:** All services use `PROperationsService`, no direct infrastructure calls (except PROperationsService itself).

- [ ] Phase 8: Add unit tests for PROperationsService enhancements

Add comprehensive unit tests for the new and refactored methods in PROperationsService.

**Tasks:**
- Update existing `tests/unit/services/test_pr_operations_service.py` (or create if doesn't exist)
- Test refactored `get_project_prs()`:
  - Returns typed `GitHubPullRequest` models (not dicts)
  - Filters by project name correctly
  - Handles invalid branch names
- Test new `get_open_prs_for_project()`:
  - Calls `get_project_prs()` with state="open"
  - Returns typed domain models
- Test new `get_open_prs_for_reviewer()`:
  - Filters by reviewer/assignee
  - Handles empty results
- Test new `get_all_prs()`:
  - Calls infrastructure layer with correct parameters
  - Returns all PRs with label
- Test new `get_unique_projects()`:
  - Extracts unique project names from branch names
  - Handles invalid branch names
  - Returns empty set when no projects found
- Test new `get_reviewer_prs_for_project()`:
  - Filters PRs by reviewer and project correctly
  - Returns typed `GitHubPullRequest` models
  - Handles reviewers with no PRs
- Test new `get_reviewer_pr_count()`:
  - Counts correctly
  - Returns 0 for reviewers with no PRs
- Mock infrastructure layer (`list_pull_requests()`, `list_open_pull_requests()` etc.)

**Files to modify:**
- `tests/unit/services/test_pr_operations_service.py` (update existing or create)

**Expected outcome:** PROperationsService has 90%+ test coverage with passing tests for all methods.

- [ ] Phase 9: Add tests for GitHubPullRequest domain model enhancements

Add unit tests for the new properties on `GitHubPullRequest`.

**Tasks:**
- Update `tests/unit/domain/test_github_models.py` (or create if doesn't exist)
- Test `project_name` property:
  - Parses valid branch names
  - Returns None for invalid formats
- Test `task_index` property:
  - Extracts task index from branch name
  - Returns None for invalid formats
- Test `task_description` property:
  - Strips "ClaudeStep: " prefix
  - Handles titles without prefix
  - Handles empty titles
- Test `is_claudestep_pr` property:
  - Returns True for valid ClaudeStep branch names
  - Returns False for other branch names

**Files to modify:**
- `tests/unit/domain/test_github_models.py` (create if doesn't exist)

**Expected outcome:** Domain model enhancements are fully tested.

- [ ] Phase 10: Update integration tests for refactored services

Update integration tests for `ReviewerManagementService`, `TaskManagementService`, and `StatisticsService` to mock the `PROperationsService` dependency.

**Tasks:**
- Update `tests/integration/cli/commands/test_prepare.py`:
  - Mock `PROperationsService` instead of infrastructure layer
  - Verify service instantiation with correct dependencies
- Update `tests/integration/cli/commands/test_discover.py`:
  - Mock `PROperationsService` for TaskManagementService
  - Verify correct service usage
- Update `tests/integration/cli/commands/test_statistics.py`:
  - Mock `PROperationsService`
  - Verify correct service usage
- Update any other integration tests affected by the refactoring

**Files to modify:**
- `tests/integration/cli/commands/test_prepare.py`
- `tests/integration/cli/commands/test_discover.py`
- `tests/integration/cli/commands/test_statistics.py`
- Any other affected integration tests

**Expected outcome:** All integration tests pass with updated mocking strategy.

- [ ] Phase 11: Validation

Validate the refactoring with comprehensive testing.

**Validation approach:**

1. **Run full test suite:**
   ```bash
   PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v
   ```
   - All tests must pass (493+ tests)
   - Coverage must remain ≥85%

2. **Manual verification:**
   - Review `src/claudestep/services/` - no services should call infrastructure GitHub operations directly (except `PROperationsService`)
   - Confirm `PROperationsService` is the only service calling `list_pull_requests()` etc.
   - Verify no manual branch parsing or "ClaudeStep: " prefix stripping outside domain models and `PROperationsService`

3. **Architecture compliance:**
   - CLI commands instantiate `PROperationsService` and pass to other services (dependency injection)
   - Domain models own parsing logic (branch names, title prefixes)
   - Infrastructure layer only called by `PROperationsService`
   - Services work with typed domain models, not dictionaries
   - `PROperationsService.get_project_prs()` returns typed models (breaking change for consumers)

4. **Code review checklist:**
   - [ ] No `list_pull_requests()` calls outside `PROperationsService`
   - [ ] No manual `parse_branch_name()` calls in services except `PROperationsService` (use domain model properties)
   - [ ] No `startswith("ClaudeStep: ")` checks in services (use domain model `task_description`)
   - [ ] All services follow dependency injection pattern
   - [ ] `PROperationsService.get_project_prs()` returns `List[GitHubPullRequest]` not `List[dict]`
   - [ ] Test coverage ≥90% for new code

**Success criteria:**
- All tests passing
- Coverage maintained at ≥85%
- Architecture clean: GitHub API hidden behind `PROperationsService`
- Business logic in domain models, not scattered across services
- Type-safe APIs using domain models instead of dictionaries
- All services depend on `PROperationsService` for PR data (dependency injection)
- `PROperationsService` is single source of truth for PR querying operations
