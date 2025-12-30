## Background

The current architecture has both CLI commands and services that read environment variables directly using `os.environ.get()`. This violates best practices documented in `docs/architecture/python-code-style.md` and creates several issues.

**Current Issues at CLI Layer:**
- Commands have implicit dependencies on environment variables (not visible in function signatures)
- Local usage requires setting env vars: `GITHUB_REPOSITORY=owner/repo python -m claudestep statistics`
- Function signatures use `argparse.Namespace` which hides what parameters are actually needed
- Testing requires mocking environment variables
- Type safety is limited with `Namespace` objects

**Current Issues at Service Layer:**
- `StatisticsService` reads `BASE_BRANCH` environment variable directly on line 52
- Hidden dependencies not obvious from the service API
- Poor testability - tests must mock environment variables
- Tight coupling to deployment environment (GitHub Actions)
- Hard to reuse in different contexts (CLI, web app, scripts, tests)

**Proposed Solution:**
Implement a consistent pattern across both CLI and Service layers where environment variable reading is isolated to a single adapter layer (`__main__.py`):

```
GitHub Actions env vars → __main__.py (adapter) → cmd_*(explicit params) → Services(explicit params)
```

**Benefits:**
- Commands and services become pure functions with explicit type signatures
- Works naturally for both GitHub Actions (env vars) and local development (CLI args)
- Better type safety and IDE support
- Easier testing (no environment mocking needed)
- Discoverable via `--help` flags
- Consistent pattern across all layers

**User Requirements:**
- Commands should be callable with CLI arguments for local development
- Services should receive all configuration explicitly
- Must maintain backward compatibility with GitHub Actions (env vars)
- Environment variable reading should be isolated to a single adapter layer
- Follow the pattern documented in `docs/architecture/python-code-style.md`

## Phases

- [x] Phase 1: Add CLI arguments to parser for statistics command

Update `src/claudestep/cli/parser.py` to add argument definitions for the statistics command:
- `--repo`: GitHub repository (owner/name)
- `--base-branch`: Base branch to fetch specs from (default: main)
- `--config-path`: Path to configuration file
- `--days-back`: Days to look back for statistics (default: 30)
- `--format`: Output format (choices: slack, json; default: slack)

Each argument should have a help message describing its purpose.

**Expected outcome:** `python -m claudestep statistics --help` shows all available options including `--base-branch`

**Status: ✅ Completed**
- Added all five CLI arguments to `parser_statistics` in `src/claudestep/cli/parser.py:58-79`
- All arguments include descriptive help messages
- The `--format` argument uses `choices=["slack", "json"]` for validation
- The `--days-back` argument uses `type=int` for proper type conversion
- Verified help text displays correctly with `python -m claudestep statistics --help`
- Parser module imports and builds successfully

- [x] Phase 2: Refactor cmd_statistics to use explicit parameters

Update `src/claudestep/cli/commands/statistics.py`:

**Old signature:**
```python
def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
```

**New signature:**
```python
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str = "main",
    config_path: Optional[str] = None,
    days_back: int = 30,
    format_type: str = "slack",
    slack_webhook_url: str = ""
) -> int:
```

Changes needed:
- Remove `argparse` and `os` imports (no longer needed)
- Update function signature to explicit parameters
- Remove all `os.environ.get()` calls
- Use parameters directly instead of extracting from `args` or environment
- Update docstring to document the new parameters

**Expected outcome:** Command function is pure with no environment variable access

**Status: ✅ Completed**
- Updated function signature to use explicit parameters instead of `argparse.Namespace`
- Removed `argparse` and `os` imports from the module
- Removed all `os.environ.get()` calls from lines 35-41
- Parameters now used directly throughout the function body
- Updated docstring to document all seven parameters with their types and defaults
- Added `from typing import Optional` for proper type annotation
- Verified the module compiles and can be imported successfully
- Function is now a pure function with explicit dependencies visible in the signature

- [x] Phase 3: Update __main__.py adapter for statistics command

Update `src/claudestep/__main__.py` to add the adapter logic for statistics:

```python
elif args.command == "statistics":
    return cmd_statistics(
        gh=gh,
        repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        base_branch=args.base_branch or os.environ.get("BASE_BRANCH", "main"),
        config_path=args.config_path or os.environ.get("CONFIG_PATH"),
        days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30")),
        format_type=args.format or os.environ.get("STATS_FORMAT", "slack"),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", "")
    )
```

Add `os` import to `__main__.py` if not already present.

**Expected outcome:**
- GitHub Actions usage works unchanged (reads env vars)
- CLI usage works: `python -m claudestep statistics --repo owner/repo --days-back 90`
- Hybrid usage works: `GITHUB_REPOSITORY=owner/repo python -m claudestep statistics --days-back 90`

**Status: ✅ Completed**
- Added `import os` to the imports in `src/claudestep/__main__.py:9`
- Updated the statistics command handler in `src/claudestep/__main__.py:55-64` to use the adapter pattern
- All seven parameters are now passed explicitly to `cmd_statistics`:
  - `gh`: Passed directly (no env var fallback needed)
  - `repo`: Falls back to `GITHUB_REPOSITORY` env var
  - `base_branch`: Falls back to `BASE_BRANCH` env var (default: "main")
  - `config_path`: Falls back to `CONFIG_PATH` env var
  - `days_back`: Falls back to `STATS_DAYS_BACK` env var (default: 30)
  - `format_type`: Falls back to `STATS_FORMAT` env var (default: "slack")
  - `slack_webhook_url`: Reads from `SLACK_WEBHOOK_URL` env var (default: "")
- CLI arguments take precedence over environment variables using the `or` pattern
- Verified syntax with `python3 -m py_compile` - no errors
- Verified module imports successfully
- This completes the adapter layer pattern: env vars are only read in `__main__.py`, not in the command function

- [ ] Phase 4: Refactor StatisticsService to use explicit parameters

Update `src/claudestep/services/statistics_service.py`:

**Changes to constructor:**
```python
def __init__(
    self,
    repo: str,
    metadata_service: MetadataService,
    base_branch: str = "main"  # NEW parameter
):
    """Initialize the statistics service

    Args:
        repo: GitHub repository (owner/name)
        metadata_service: MetadataService instance for accessing metadata
        base_branch: Base branch to fetch specs from (default: "main")
    """
    self.repo = repo
    self.metadata_service = metadata_service
    self.base_branch = base_branch  # Store as instance variable
```

**Changes to collect_all_statistics method:**
1. Remove line 52: `base_branch = os.environ.get("BASE_BRANCH", "main")`
2. Replace with: `base_branch = self.base_branch`

**CLI layer update in `cmd_statistics`:**
After Phase 2, the command will already have `base_branch` as a parameter (we'll need to add it). Update service instantiation:
```python
statistics_service = StatisticsService(repo, metadata_service, base_branch)
```

**Expected outcome:** `StatisticsService` no longer reads environment variables directly

- [ ] Phase 5: Review other services for consistency

Review all other services in `src/claudestep/services/` to ensure they follow the pattern:
- `task_management_service.py`
- `pr_operations_service.py`
- `reviewer_management_service.py`
- `metadata_service.py`
- `project_detection_service.py`
- `artifact_operations_service.py`

**Verification steps:**
1. Confirm none of these services use `os.environ.get()` (already verified - only `statistics_service.py` does)
2. Review constructor signatures to ensure they follow the pattern of receiving configuration explicitly
3. Check that commonly used configuration values (like `repo`, `label`) are consistently handled

**Expected outcome:** Confirm all other services already follow the pattern, note any minor inconsistencies

- [ ] Phase 6: Update tests

**CLI tests:** Update `tests/unit/cli/commands/test_statistics.py`
- Update test calls to use new function signature with explicit parameters
- Remove any environment variable mocking
- Add tests for CLI argument parsing

**Service tests:** Update `tests/unit/services/test_statistics_service.py`
- Update all test instantiations of `StatisticsService` to pass `base_branch` parameter
- Add tests that verify custom `base_branch` values are used correctly
- Remove any environment variable mocking for `BASE_BRANCH`

**Expected outcome:** All tests pass and properly test the new explicit parameter approach

- [ ] Phase 7: Update documentation

Update `docs/architecture/python-code-style.md` to add a new section on CLI command patterns:

**New section after "Environment Variables and Configuration":**

```markdown
## CLI Command Pattern

### Principle: Commands Use Explicit Parameters, Not Environment Variables

CLI command functions should receive explicit parameters and never read environment variables directly. The adapter layer in `__main__.py` is responsible for translating CLI arguments and environment variables into parameters.

### Architecture Layers

```
GitHub Actions (env vars) → __main__.py (adapter) → commands (params) → services (params)
```

Only `__main__.py` reads environment variables in the CLI layer.

### Anti-Pattern (❌ Avoid)

```python
# BAD: Command reads environment variables
def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")  # Don't do this!
    config_path = args.config_path  # Mixing args and env is confusing
```

**Problems:**
- Hidden dependencies on environment variables
- Awkward local usage (must set env vars)
- Poor type safety with Namespace
- Harder to test

### Recommended Pattern (✅ Use This)

```python
# In cli/parser.py
parser_statistics.add_argument("--repo", help="GitHub repository (owner/name)")
parser_statistics.add_argument("--config-path", help="Path to configuration file")
parser_statistics.add_argument("--days-back", type=int, default=30)

# In cli/commands/statistics.py - Pure function with explicit parameters
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    config_path: Optional[str] = None,
    days_back: int = 30
) -> int:
    """Orchestrate statistics workflow.

    Args:
        gh: GitHub Actions helper instance
        repo: GitHub repository (owner/name)
        config_path: Optional path to configuration file
        days_back: Days to look back for statistics

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Use parameters directly - no environment access!
    metadata_store = GitHubMetadataStore(repo)
    ...

# In __main__.py - Adapter layer
elif args.command == "statistics":
    return cmd_statistics(
        gh=gh,
        repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        config_path=args.config_path or os.environ.get("CONFIG_PATH"),
        days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30"))
    )
```

**Benefits:**
- ✅ Explicit dependencies: Function signature shows exactly what's needed
- ✅ Type safety: IDEs can autocomplete and type-check
- ✅ Easy testing: Just pass parameters, no environment mocking
- ✅ Works for both GitHub Actions and local development
- ✅ Discoverable: `--help` shows all options
```

**Expected outcome:** Documentation clearly describes the CLI command pattern and adapter layer

**Also update `docs/architecture/architecture.md`:**
1. Find any code examples that instantiate `StatisticsService`
2. Update them to include the `base_branch` parameter
3. Ensure the Service Layer documentation reflects the environment variable handling pattern

**Expected outcome:** All documentation is consistent with implementation

- [ ] Phase 8: Validation

Run comprehensive tests and verify both CLI and service layers work correctly:

**1. Unit Tests:**
```bash
# Test statistics command
pytest tests/unit/cli/commands/test_statistics.py -v

# Test statistics service
pytest tests/unit/services/test_statistics_service.py -v

# Run full test suite
pytest tests/ -v
```
All tests should pass with the new signatures

**2. CLI Usage - GitHub Actions mode (env vars only):**
```bash
GITHUB_REPOSITORY="owner/repo" \
BASE_BRANCH="main" \
CONFIG_PATH="test/config.json" \
STATS_DAYS_BACK="7" \
STATS_FORMAT="slack" \
python -m claudestep statistics
```
Should work exactly as before

**3. CLI Usage - Local CLI mode (args only):**
```bash
python -m claudestep statistics \
  --repo owner/repo \
  --base-branch main \
  --config-path test/config.json \
  --days-back 7 \
  --format slack
```
Should produce same result as env var mode

**4. CLI Usage - Hybrid mode (mix of env vars and args):**
```bash
GITHUB_REPOSITORY="owner/repo" \
BASE_BRANCH="develop" \
python -m claudestep statistics --days-back 90
```
Args should override env vars where specified

**5. Test help text:**
```bash
python -m claudestep statistics --help
```
Should show all available arguments including `--base-branch` with descriptions

**6. Code verification:**
```bash
# Verify no environment variable access in services
grep -r "os.environ.get" src/claudestep/services/

# Should only show imports or comments, no actual usage
```

**7. Verify no regression:**
- GitHub Actions workflow should continue working unchanged
- No `os.environ.get()` calls in service methods (except infrastructure layer)
- No `os.environ.get()` calls in command functions
- Only `__main__.py` reads env vars for CLI/service configuration
- All service constructors receive configuration explicitly

**Success criteria:**
- ✅ All tests pass
- ✅ Both usage modes work (GitHub Actions env vars + local CLI args)
- ✅ No environment variable access in command functions
- ✅ No environment variable access in service layer (except infrastructure)
- ✅ `StatisticsService` receives `base_branch` as constructor parameter
- ✅ `cmd_statistics` receives all config as explicit parameters
- ✅ Documentation accurately reflects the new pattern
- ✅ `--help` text is informative and accurate
- ✅ No regressions in existing functionality
