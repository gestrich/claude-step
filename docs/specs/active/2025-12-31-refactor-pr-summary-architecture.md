## Background

This refactoring addresses several architectural violations in the PR summary and cost tracking implementation:

### Current Issues

1. **`extract_cost.py` not pulling its weight**: The file contains only utility functions that should live in domain models following our "parse once into well-formed models" principle.

2. **Low-level parsing in CLI commands**: `cmd_post_pr_comment` manually parses the summary file and extracts costs. This violates our architecture - parsing should happen in domain models, not CLI layer.

3. **Environment variable access in commands**: `prepare_summary.py` directly reads environment variables (lines 27-33) instead of receiving them as parameters, violating our "commands use explicit parameters" principle.

4. **Duplicated magic strings**: The path `/tmp/pr-summary.md` is hardcoded in multiple places (action.yml, summary_prompt.md) instead of being defined once and passed around.

5. **Missing domain models**: There's no `SummaryFile` model to encapsulate summary file parsing, and no `CostBreakdown` model to encapsulate cost extraction logic.

### Architecture Principles Applied

From `docs/general-architecture/python-style.md`:
- **Parse once into well-formed models**: Domain models should own parsing logic
- **Commands use explicit parameters**: CLI commands receive parameters, not environment variables
- **Services don't read environment variables**: Configuration flows from entry point
- **Single source of truth**: Define constants once, pass them around

## Phases

- [x] Phase 1: Create domain models for cost and summary data ✅

Create two new domain models in `src/claudestep/domain/`:

**1. Create `src/claudestep/domain/cost_breakdown.py`:**
```python
@dataclass
class CostBreakdown:
    """Domain model for Claude Code execution cost breakdown."""
    main_cost: float
    summary_cost: float

    @property
    def total_cost(self) -> float:
        """Calculate total cost."""
        return self.main_cost + self.summary_cost

    @classmethod
    def from_execution_files(
        cls,
        main_execution_file: str,
        summary_execution_file: str
    ) -> 'CostBreakdown':
        """Parse cost information from execution files.

        This encapsulates all the file reading and JSON parsing logic
        that currently lives in prepare_summary.py.
        """
        main_cost = cls._extract_from_file(main_execution_file)
        summary_cost = cls._extract_from_file(summary_execution_file)
        return cls(main_cost=main_cost, summary_cost=summary_cost)

    @staticmethod
    def _extract_from_file(execution_file: str) -> float:
        """Extract cost from a single execution file."""
        # Move logic from _extract_cost_from_file in prepare_summary.py
        # Move logic from extract_cost_from_execution in extract_cost.py
        pass

    def format_for_github(self, repo: str, run_id: str) -> str:
        """Format cost breakdown as markdown table for GitHub PR comment."""
        # Move logic from format_unified_comment in post_pr_comment.py
        pass
```

**2. Create `src/claudestep/domain/summary_file.py`:**
```python
@dataclass
class SummaryFile:
    """Domain model for PR summary file content."""
    content: str | None

    @classmethod
    def from_file(cls, file_path: str) -> 'SummaryFile':
        """Read and parse summary file.

        Args:
            file_path: Path to summary file

        Returns:
            SummaryFile with content, or None content if file missing/empty
        """
        # Move file reading logic from cmd_post_pr_comment
        pass

    @property
    def has_content(self) -> bool:
        """Check if summary has content."""
        return self.content is not None and bool(self.content.strip())

    def format_with_cost(
        self,
        cost_breakdown: CostBreakdown,
        repo: str,
        run_id: str
    ) -> str:
        """Combine summary and cost into unified PR comment."""
        # Move logic from format_unified_comment in post_pr_comment.py
        pass
```

**Files to create:**
- `src/claudestep/domain/cost_breakdown.py`
- `src/claudestep/domain/summary_file.py`

**Why domain layer:**
- These models encapsulate parsing logic (file I/O, JSON parsing)
- They provide type-safe APIs for cost and summary data
- They enable reuse across multiple commands
- They follow "parse once into well-formed models" principle

**Technical Notes (Phase 1 Completion):**
- Created `src/claudestep/domain/cost_breakdown.py` with full implementation
  - Moved logic from `_extract_cost_from_file()` in `prepare_summary.py`
  - Moved logic from `extract_cost_from_execution()` in `extract_cost.py`
  - Moved logic from `format_unified_comment()` in `post_pr_comment.py` (cost section)
- Created `src/claudestep/domain/summary_file.py` with full implementation
  - Encapsulates file reading logic from `cmd_post_pr_comment`
  - Implements `format_with_cost()` combining summary and cost breakdown
- Both files compile successfully with Python 3
- Used TYPE_CHECKING for type hints to avoid circular import issues

- [x] Phase 2: Create constants file for shared paths ✅

Create `src/claudestep/domain/constants.py` to define magic strings once:

```python
"""Shared constants used across ClaudeStep."""

# PR Summary file path (used by action.yml and commands)
PR_SUMMARY_FILE_PATH = "/tmp/pr-summary.md"

# Other shared constants can go here
```

**Files to create:**
- `src/claudestep/domain/constants.py`

**Files to update:**
- `src/claudestep/resources/prompts/summary_prompt.md` - Replace hardcoded `/tmp/pr-summary.md` with reference to constant (in code that uses it)
- Eventually `action.yml` - Will use constant via command outputs (Phase 5)

**Why:**
- Single source of truth for file paths
- Easy to change in one place
- Self-documenting code

**Technical Notes (Phase 2 Completion):**
- Added `PR_SUMMARY_FILE_PATH = "/tmp/pr-summary.md"` constant to existing `src/claudestep/domain/constants.py` file
- The constants file already existed with other domain constants (DEFAULT_PR_LABEL, DEFAULT_BASE_BRANCH, etc.)
- File compiles successfully with Python 3
- Constant is now available for use in future phases (Phase 3, 4, and 5 will consume this constant)

- [x] Phase 3: Refactor prepare_summary.py to use domain models and explicit parameters ✅

**Update `src/claudestep/cli/commands/prepare_summary.py`:**

Change from:
```python
def cmd_prepare_summary(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    # Reads env vars directly
    pr_number = os.environ.get("PR_NUMBER", "")
    task = os.environ.get("TASK", "")
    # ... more env vars
```

To:
```python
def cmd_prepare_summary(
    gh: GitHubActionsHelper,
    pr_number: str,
    task: str,
    repo: str,
    run_id: str,
    action_path: str,
    main_execution_file: str,
    summary_execution_file: str
) -> int:
    """Handle 'prepare-summary' subcommand.

    All parameters passed explicitly, no environment variable access.
    """
    # Use domain models
    from claudestep.domain.cost_breakdown import CostBreakdown
    from claudestep.domain.constants import PR_SUMMARY_FILE_PATH

    # Parse cost breakdown using domain model
    cost_breakdown = CostBreakdown.from_execution_files(
        main_execution_file,
        summary_execution_file
    )

    # Output cost values
    gh.write_output("main_cost", f"{cost_breakdown.main_cost:.6f}")
    gh.write_output("summary_cost", f"{cost_breakdown.summary_cost:.6f}")
    gh.write_output("total_cost", f"{cost_breakdown.total_cost:.6f}")
    gh.write_output("summary_file", PR_SUMMARY_FILE_PATH)

    # ... rest of logic
```

**Update `src/claudestep/__main__.py`:**

Add adapter code to read environment variables and pass to command:
```python
elif args.command == "prepare-summary":
    return cmd_prepare_summary(
        gh=gh,
        pr_number=os.environ.get("PR_NUMBER", ""),
        task=os.environ.get("TASK", ""),
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        action_path=os.environ.get("ACTION_PATH", ""),
        main_execution_file=os.environ.get("MAIN_EXECUTION_FILE", ""),
        summary_execution_file=os.environ.get("SUMMARY_EXECUTION_FILE", "")
    )
```

**Files to update:**
- `src/claudestep/cli/commands/prepare_summary.py` - Signature and implementation
- `src/claudestep/__main__.py` - Add adapter code for prepare-summary command

**Delete helper functions:**
- Remove `_extract_cost_from_file()` function (logic moved to `CostBreakdown._extract_from_file()`)

**Why:**
- Commands receive explicit parameters (architecture principle)
- Only `__main__.py` reads environment variables (adapter layer)
- Domain models handle parsing (separation of concerns)

**Technical Notes (Phase 3 Completion):**
- Refactored `cmd_prepare_summary()` to accept explicit parameters instead of reading environment variables
- Updated function signature to accept 8 explicit parameters: `gh`, `pr_number`, `task`, `repo`, `run_id`, `action_path`, `main_execution_file`, `summary_execution_file`
- Removed the `args: argparse.Namespace` parameter (no longer needed)
- Integrated `CostBreakdown.from_execution_files()` domain model for cost extraction
- Added `summary_file` output using `PR_SUMMARY_FILE_PATH` constant
- Removed `_extract_cost_from_file()` helper function (logic moved to domain model)
- Updated `__main__.py` to read environment variables and pass them as explicit parameters to the command
- Updated all 9 integration tests to use the new signature
- All tests pass successfully (658 passed, 4 pre-existing failures unrelated to this change)
- No new test failures introduced by this refactoring

- [x] Phase 4: Refactor post_pr_comment.py to use domain models ✅

**Update `src/claudestep/cli/commands/post_pr_comment.py`:**

Change from:
```python
def cmd_post_pr_comment(args, gh):
    # Manual env var reading
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    summary_file = os.environ.get("SUMMARY_FILE", "").strip()
    # ... manual file reading and parsing

    # Manual comment formatting
    comment = format_unified_comment(...)
```

To:
```python
def cmd_post_pr_comment(
    gh: GitHubActionsHelper,
    pr_number: str,
    summary_file_path: str,
    main_cost: float,
    summary_cost: float,
    total_cost: float,
    repo: str,
    run_id: str
) -> int:
    """Post unified PR comment with summary and cost breakdown.

    All parameters passed explicitly, no environment variable access.
    """
    from claudestep.domain.summary_file import SummaryFile
    from claudestep.domain.cost_breakdown import CostBreakdown

    # Use domain models for parsing
    summary = SummaryFile.from_file(summary_file_path)
    cost_breakdown = CostBreakdown(
        main_cost=main_cost,
        summary_cost=summary_cost
    )

    # Use domain model for formatting
    comment = summary.format_with_cost(cost_breakdown, repo, run_id)

    # Post comment (subprocess call stays here - infrastructure boundary)
    # ... rest of logic
```

**Update `src/claudestep/__main__.py`:**

Add adapter code:
```python
elif args.command == "post-pr-comment":
    return cmd_post_pr_comment(
        gh=gh,
        pr_number=os.environ.get("PR_NUMBER", "").strip(),
        summary_file_path=os.environ.get("SUMMARY_FILE", "").strip(),
        main_cost=float(os.environ.get("MAIN_COST", "0")),
        summary_cost=float(os.environ.get("SUMMARY_COST", "0")),
        total_cost=float(os.environ.get("TOTAL_COST", "0")),
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        run_id=os.environ.get("GITHUB_RUN_ID", "")
    )
```

**Files to update:**
- `src/claudestep/cli/commands/post_pr_comment.py` - Signature and implementation
- `src/claudestep/__main__.py` - Add adapter code for post-pr-comment command

**Delete helper functions:**
- Remove `format_unified_comment()` function (logic moved to `SummaryFile.format_with_cost()`)

**Why:**
- No manual file reading in CLI layer
- No manual string formatting in CLI layer
- Domain models encapsulate all parsing and formatting logic

**Technical Notes (Phase 4 Completion):**
- Refactored `cmd_post_pr_comment()` to accept 8 explicit parameters: `gh`, `pr_number`, `summary_file_path`, `main_cost`, `summary_cost`, `total_cost`, `repo`, `run_id`
- Removed the `args` parameter (no longer needed)
- Integrated `SummaryFile.from_file()` for reading summary files
- Integrated `CostBreakdown` domain model for cost tracking
- Used `SummaryFile.format_with_cost()` for PR comment formatting (replaced `format_unified_comment()` function)
- Deleted `format_unified_comment()` helper function (logic moved to domain model)
- Updated `__main__.py` to read environment variables and pass them as explicit parameters
- Updated all 21 integration tests to use the new signature
- Tests migrated to use domain models (SummaryFile and CostBreakdown) directly in assertions
- All tests pass successfully (30 total: 9 prepare_summary + 21 post_pr_comment)
- No new test failures introduced by this refactoring
- Added validation for whitespace-only PR numbers (skip gracefully)

- [x] Phase 5: Update summary_prompt.md to reference constant ✅

**Update `src/claudestep/resources/prompts/summary_prompt.md`:**

The prompt template can't directly reference Python constants, but we can make the path a template variable:

Change line 17 from:
```markdown
4. Write the summary to `/tmp/pr-summary.md` in this exact format:
```

To:
```markdown
4. Write the summary to `{SUMMARY_FILE_PATH}` in this exact format:
```

**Update `prepare_summary.py` template substitution:**
```python
from claudestep.domain.constants import PR_SUMMARY_FILE_PATH

# Load and substitute template
summary_prompt = template.replace("{TASK_DESCRIPTION}", task)
summary_prompt = summary_prompt.replace("{PR_NUMBER}", pr_number)
summary_prompt = summary_prompt.replace("{WORKFLOW_URL}", workflow_url)
summary_prompt = summary_prompt.replace("{SUMMARY_FILE_PATH}", PR_SUMMARY_FILE_PATH)
```

**Update `action.yml`:**

Change hardcoded path to use output from prepare-summary:
```yaml
env:
  SUMMARY_FILE: ${{ steps.prepare_summary.outputs.summary_file }}
```

**Files to update:**
- `src/claudestep/resources/prompts/summary_prompt.md` - Use template variable
- `src/claudestep/cli/commands/prepare_summary.py` - Add template substitution
- `action.yml` - Use output instead of hardcoded path

**Why:**
- Single source of truth (constant defined once in constants.py)
- Easy to change file path in one place
- No magic strings duplicated across files

**Technical Notes (Phase 5 Completion):**
- Updated `summary_prompt.md` to use `{SUMMARY_FILE_PATH}` template variable in two locations (lines 17 and 29)
- Added template substitution in `prepare_summary.py` at line 74: `summary_prompt = summary_prompt.replace("{SUMMARY_FILE_PATH}", PR_SUMMARY_FILE_PATH)`
- Updated `action.yml` line 190 to use `${{ steps.prepare_summary.outputs.summary_file }}` instead of hardcoded `/tmp/pr-summary.md`
- The `PR_SUMMARY_FILE_PATH` constant is imported from `claudestep.domain.constants` (already present from Phase 3)
- All 9 integration tests pass successfully
- No build errors, Python compilation successful

- [x] Phase 6: Delete extract_cost.py ✅

Now that all cost extraction logic lives in `CostBreakdown` domain model, the `extract_cost.py` file is no longer needed.

**Files to delete:**
- `src/claudestep/cli/commands/extract_cost.py`

**Files to check for imports:**
- Search for `from claudestep.cli.commands.extract_cost import` and verify no remaining imports exist
- The only import should have been in `prepare_summary.py`, which we already refactored

**Verification:**
```bash
# Should return no results after this phase
grep -r "from claudestep.cli.commands.extract_cost" src/
grep -r "import extract_cost" src/
```

**Why:**
- File no longer serves a purpose
- All functionality moved to domain layer
- Reduces codebase complexity

**Technical Notes (Phase 6 Completion):**
- Verified no imports of `extract_cost.py` exist in source code
  - `grep -r "from claudestep.cli.commands.extract_cost" src/` returned no results
  - `grep -r "import extract_cost" src/` returned no results
- Deleted `src/claudestep/cli/commands/extract_cost.py` successfully
- Cleaned up `__pycache__` artifact for the deleted file
- All 30 integration tests pass (9 prepare_summary + 21 post_pr_comment)
- Python compilation succeeds for entire codebase
- The file has been completely removed with no remaining references in production code

- [ ] Phase 7: Update tests

**Unit tests to create:**

1. **`tests/unit/domain/test_cost_breakdown.py`:**
   - Test `CostBreakdown.from_execution_files()` with various execution file formats
   - Test `_extract_from_file()` edge cases (missing file, empty file, invalid JSON)
   - Test `total_cost` property calculation
   - Test `format_for_github()` markdown output

2. **`tests/unit/domain/test_summary_file.py`:**
   - Test `SummaryFile.from_file()` with valid, empty, and missing files
   - Test `has_content` property
   - Test `format_with_cost()` markdown output (with and without summary content)

**Integration tests to update:**

3. **`tests/integration/cli/commands/test_prepare_summary.py`:**
   - Update tests to use new explicit parameter signature
   - Verify domain model usage
   - Test cost output values

4. **`tests/integration/cli/commands/test_post_pr_comment.py`:**
   - Update tests to use new explicit parameter signature
   - Mock `SummaryFile.from_file()` and `CostBreakdown`
   - Verify comment formatting

**Files to create:**
- `tests/unit/domain/test_cost_breakdown.py`
- `tests/unit/domain/test_summary_file.py`

**Files to update:**
- `tests/integration/cli/commands/test_prepare_summary.py`
- `tests/integration/cli/commands/test_post_pr_comment.py`

**Test considerations:**
- Domain model tests should NOT mock file I/O (use real temp files)
- CLI tests SHOULD mock domain models (test orchestration, not parsing)
- Follow Arrange-Act-Assert pattern
- Test edge cases (missing files, invalid data)

- [ ] Phase 8: Validation

Run comprehensive test suite to ensure refactoring didn't break anything:

**1. Run unit tests:**
```bash
PYTHONPATH=src:scripts pytest tests/unit/ -v
```

**2. Run integration tests:**
```bash
PYTHONPATH=src:scripts pytest tests/integration/ -v
```

**3. Run specific command tests:**
```bash
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_prepare_summary.py -v
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_post_pr_comment.py -v
```

**4. Verify no imports of deleted file:**
```bash
grep -r "extract_cost" src/
grep -r "extract_cost" tests/
```

**5. Check coverage:**
```bash
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing
```

**6. Manual verification:**
- Trigger a test workflow that creates a PR with summary
- Verify the PR comment appears correctly with:
  - AI-generated summary (if available)
  - Cost breakdown table
  - Proper formatting
- Verify costs are calculated correctly

**Success criteria:**
- All tests pass (493+ tests)
- Coverage remains at 85%+
- No references to `extract_cost.py` remain
- Commands use explicit parameters (no direct `os.environ.get()` calls)
- Domain models handle all parsing logic
- Constants defined once in `constants.py`
- PR comments format correctly in production

**Expected test count increase:**
- +10-15 tests for new domain models
- ~5 tests updated for refactored CLI commands
- Total: ~508 tests
