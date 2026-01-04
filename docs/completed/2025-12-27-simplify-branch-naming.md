# Simplify Branch Naming Strategy

## Overview

Simplify ClaudeChain's branch naming by using a single, consistent format: `claude-chain-{project_name}-{index}`. This eliminates complexity from custom branch prefixes and date-based naming while making PR fetching more efficient and maintainable.

## Current Problems

1. **Multiple branch formats** confuse users and complicate code:
   - Default: `YYYY-MM-{project}-{index}` (e.g., `2025-12-my-refactor-1`)
   - Custom: `{branchPrefix}-{index}` (e.g., `refactor/swift-migration-1`)

2. **Duplicated PR fetching logic** across multiple files:
   - `reviewer_management.py` - fetches PRs to check reviewer capacity
   - `task_management.py` - fetches PRs to find in-progress tasks
   - `statistics_collector.py` - fetches PRs to collect costs
   - Each reimplements similar label/project filtering logic

3. **Complex project detection** requires parsing multiple branch formats

4. **Configuration overhead** with optional `branchPrefix` field adds complexity for minimal benefit

## Proposed Solution

### Single Branch Format

All ClaudeChain PR branches will use:
```
claude-chain-{project_name}-{index}
```

Examples:
- `claude-chain-my-refactor-1`
- `claude-chain-swift-migration-5`
- `claude-chain-api-refactor-12`

### Centralized PR Fetching

Create reusable utilities in a new module `pr_operations.py`:

```python
def get_project_prs(project_name: str, repo: str, state: str = "all") -> List[dict]:
    """Fetch all PRs for a project by branch prefix.

    Args:
        project_name: Project name (e.g., "my-refactor")
        repo: GitHub repository (owner/name)
        state: PR state filter ("open", "closed", "merged", "all")

    Returns:
        List of PR data dicts with number, state, labels, etc.
    """
    # Search for branches starting with claude-chain-{project_name}
    # Filter by state if needed
    # Return standardized PR data
```

All code that fetches PRs will use this centralized function instead of duplicating logic.

## Changes Required

### Phase 1: Create Centralized Utilities ✅
- [x] Create `scripts/claudechain/pr_operations.py` with `get_project_prs()` function
- [x] Add `format_branch_name(project_name: str, index: int) -> str` utility
- [x] Add `parse_branch_name(branch: str) -> Optional[Tuple[str, int]]` utility
- [x] Add tests for new utilities

**Technical Notes:**
- Created `scripts/claudechain/pr_operations.py` with three core utilities:
  - `format_branch_name()`: Generates branch names in format `claude-chain-{project}-{index}`
  - `parse_branch_name()`: Extracts project name and index from branch names
  - `get_project_prs()`: Fetches and filters PRs by project using branch name prefix matching
- All utilities include comprehensive docstrings with examples
- Created `tests/test_pr_operations.py` with 21 test cases covering:
  - Basic formatting and parsing
  - Complex project names with hyphens
  - Invalid input handling
  - PR fetching with various states (open, merged, all)
  - Error handling for API failures
  - Roundtrip testing (format → parse → verify)
- All new tests pass (21/21)
- No existing tests were broken by these changes

### Phase 2: Refactor PR Fetching to Use Centralized Code ✅
- [x] Update `reviewer_management.py` to use `get_project_prs()`
- [x] Update `task_management.py` to use `get_project_prs()`
- [x] Update `statistics_collector.py` to use `get_project_prs()`
- [x] Remove duplicated PR fetching logic from all files

**Technical Notes:**
- Refactored `artifact_operations.py` to use `get_project_prs()` from `pr_operations.py`
- Removed private `_get_prs_with_label()` function - this was the duplicated PR fetching logic
- Updated `find_project_artifacts()` to call `get_project_prs()` instead of duplicating the logic
- The other modules (`reviewer_management.py`, `task_management.py`, `statistics_collector.py`) already used the centralized `find_project_artifacts()` API, so no changes were needed there
- All existing tests continue to pass (107 passed)
- The 5 test failures in `test_prepare_summary.py` are pre-existing and unrelated to this refactoring

### Phase 3: Update Branch Creation and Project Detection ✅
- [x] Update `prepare.py` branch creation to use `format_branch_name()`
- [x] Update `project_detection.py` to use `parse_branch_name()` and new format
- [x] Remove date-based and custom prefix logic from branch creation
- [x] Update project detection to only check `claude-chain-{project}` format

**Technical Notes:**
- Updated `prepare.py` to use `format_branch_name()` from `pr_operations.py`
- Removed old branch creation logic that supported both date-based format (`YYYY-MM-{project}-{index}`) and custom prefix format (`{branchPrefix}-{index}`)
- All branch creation now uses the single standard format: `claude-chain-{project}-{index}`
- Removed unused `datetime` import from `prepare.py`
- Updated `project_detection.py` to use `parse_branch_name()` utility for extracting project names from branch names
- Simplified `detect_project_from_pr()` to directly parse branch names instead of checking multiple formats and scanning config files
- Removed complex logic that checked for `branchPrefix` in config files and tried multiple parsing strategies
- Removed unused imports from `project_detection.py` (`glob`, `os`)
- All existing tests continue to pass (107 passed)
- The 5 test failures in `test_prepare_summary.py` are pre-existing and unrelated to this refactoring
- All module imports verified successfully

### Phase 4: Remove branchPrefix Configuration ✅
- [x] Remove `branchPrefix` field from configuration.yml schema
- [x] Remove `branchPrefix` handling in `config.py`
- [x] Remove `branchPrefix` from `prepare.py` outputs
- [x] Update configuration validation to reject `branchPrefix` if present

**Technical Notes:**
- Removed `branchPrefix` field from `examples/configuration.yml`
- Added validation to `load_config()` in `config.py` to reject configurations containing `branchPrefix`
- The validation provides a clear error message explaining that `branchPrefix` is no longer supported and describes the new format
- Removed `branchPrefix` variable and related code from `prepare.py`:
  - Removed `branch_prefix = config.get("branchPrefix")` line
  - Removed `gh.write_output("branch_prefix", branch_prefix)` output
- All existing tests continue to pass (107 passed)
- The 5 test failures in `test_prepare_summary.py` are pre-existing and unrelated to this refactoring
- Created and verified validation test to ensure `branchPrefix` is properly rejected with helpful error message
- Configurations without `branchPrefix` continue to load normally

### Phase 5: Update Documentation and Tests ✅
- [x] Update README.md to remove `branchPrefix` references
- [x] Update `docs/architecture/architecture.md` with new branch format
- [x] Update all example configuration files
- [x] Update tests to use new branch format
- [x] Add migration note to CHANGELOG or release notes
- [ ] **Push all changes to the repo** (required before running e2e tests)
- [ ] Run end-to-end tests from demo project (`claude-chain-demo/tests/integration/`) to verify everything works

**Technical Notes:**
- Updated README.md:
  - Removed `branchPrefix` field from initial configuration example
  - Removed `branchPrefix` field from Configuration Reference table and example
  - Added new "Branch Naming" section documenting the standard `claude-chain-{project_name}-{index}` format
- Verified `docs/architecture/architecture.md` - already accurate, only mentions branch creation in general terms
- Verified `examples/configuration.yml` - already updated in Phase 4
- Updated `examples/advanced/workflow.yml`:
  - Changed branch parsing regex from `^[0-9]{4}-[0-9]{2}-([^-]+)-[0-9]+$` to `^claude-chain-([^-]+)-[0-9]+$`
  - Updated comment to reflect new format: `claude-chain-{project}-{index}`
- Verified tests - no test changes needed:
  - Tests already use the new branch format utilities
  - No hardcoded references to old date-based or custom prefix formats
- Migration notes already documented in the spec (no separate CHANGELOG file exists)
- All existing tests continue to pass (107 passed)
- The 5 test failures in `test_prepare_summary.py` are pre-existing and unrelated to this phase

## Benefits

1. **Simpler mental model** - one format, always predictable
2. **Easier PR filtering** - search for `claude-chain-{project}*` branches
3. **Less code** - eliminate custom prefix and date logic
4. **Maintainable** - centralized PR fetching reduces duplication
5. **Clearer** - branch name clearly indicates it's from ClaudeChain

## Migration Notes

No backward compatibility support needed. We treat this as if it was always the approach. Users on old versions will see their old PRs complete, but new PRs will use the new format.

## Files Affected

### Core Logic
- `scripts/claudechain/commands/prepare.py` - branch creation
- `scripts/claudechain/project_detection.py` - project detection from branch
- `scripts/claudechain/reviewer_management.py` - PR fetching for capacity
- `scripts/claudechain/task_management.py` - PR fetching for in-progress tasks
- `scripts/claudechain/statistics_collector.py` - PR fetching for costs
- `scripts/claudechain/config.py` - configuration validation

### New Files
- `scripts/claudechain/pr_operations.py` - centralized PR utilities (NEW)

### Documentation
- `README.md` - remove branchPrefix from configuration examples
- `docs/architecture/architecture.md` - update branch format documentation
- `examples/*/workflow.yml` - update any branch parsing logic

### Configuration
- `claude-chain/*/configuration.yml` - remove branchPrefix field from schema

### Tests
- All test files that reference branch names or branchPrefix
