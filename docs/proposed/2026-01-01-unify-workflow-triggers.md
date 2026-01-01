## Background

ClaudeStep needs to support per-project base branch configuration. Currently, base branch is inferred from GitHub event context (e.g., `github.ref_name`, `github.base_ref`), but there's no way for a project to specify its own target branch in `configuration.yml`.

**Goal**: Add optional `baseBranch` field to project configuration files, allowing projects to override the default base branch.

Example `configuration.yml`:
```yaml
reviewers:
  - username: gestrich
    maxOpenPRs: 5
baseBranch: develop  # Optional: PRs will target 'develop' instead of workflow default
```

**Base branch resolution logic** (follows "configuration flows downward" principle):
1. Workflow determines `default_base_branch` from GitHub event context
2. CLI command passes `default_base_branch` to services
3. Service loads `ProjectConfiguration` which may have `baseBranch` override
4. Service calls `config.get_base_branch(default_base_branch)` to resolve final value

**Additional bug fix**: The auto-start logic incorrectly uses `state="all"` when checking for existing PRs. This means completed projects (with only closed PRs) don't auto-trigger when new tasks are added. The fix is to change to `state="open"`.

## Phases

- [x] Phase 1: Add baseBranch to ProjectConfiguration domain model

Add `baseBranch` field support to the `ProjectConfiguration` domain model. Per architecture principles, domain models encapsulate parsing logic and provide type-safe APIs.

**Changes to `src/claudestep/domain/project_configuration.py`:**

1. Add `base_branch` field to dataclass:
   ```python
   base_branch: Optional[str] = None  # Optional override for target base branch
   ```

2. Update `from_yaml_string()` to parse `baseBranch` from YAML:
   ```python
   base_branch = config.get("baseBranch")
   ```

3. Add `get_base_branch()` method for resolution logic:
   ```python
   def get_base_branch(self, default_base_branch: str) -> str:
       """Resolve base branch from project config or fall back to default.

       Args:
           default_base_branch: Default from workflow/CLI (required, no default here)

       Returns:
           Project's baseBranch if set, otherwise the default
       """
       if self.base_branch:
           return self.base_branch
       return default_base_branch
   ```

4. Update `to_dict()` to include `baseBranch` when set (omit if None)

**Unit tests to add** (`tests/unit/domain/test_project_configuration.py`):
- `test_from_yaml_string_parses_base_branch`
- `test_from_yaml_string_base_branch_is_none_when_not_specified`
- `test_get_base_branch_returns_config_value_when_set`
- `test_get_base_branch_returns_default_when_not_set`
- `test_to_dict_includes_base_branch_when_set`
- `test_to_dict_excludes_base_branch_when_not_set`
- `test_base_branch_with_special_characters` (e.g., `feature/my-branch`)

**Completed:** All changes implemented and 7 new unit tests added. All 599 unit tests pass.

- [x] Phase 2: Update prepare command to use resolved base branch

The `prepare` command currently reads `BASE_BRANCH` directly from environment. Update to use project configuration's base branch if set.

**Architecture principle**: CLI layer reads env vars, passes to services. Services use domain models for resolution.

**Changes to `src/claudestep/cli/commands/prepare.py`:**

Current flow (line ~83):
```python
base_branch = os.environ.get("BASE_BRANCH", "main")
```

New flow:
```python
# Get default from environment (workflow provides this)
default_base_branch = os.environ.get("BASE_BRANCH", "main")

# Load project configuration
config = project_repository.load_configuration(project, default_base_branch)

# Resolve actual base branch (config override or default)
base_branch = config.get_base_branch(default_base_branch)

print(f"Base branch: {base_branch} (default: {default_base_branch})")
```

**Note**: The `load_configuration()` call needs the base branch to fetch the config file. This creates a chicken-and-egg situation. Resolution:
- Use `default_base_branch` to fetch the config file (config lives on the default branch)
- Then use the config's `baseBranch` to determine where PRs target

**Integration tests to update** (`tests/integration/cli/commands/test_prepare.py`):
- Add test for project with `baseBranch` override
- Add test for project without `baseBranch` (uses default)
- Verify correct base branch flows through to PR creation

**Completed:** Updated prepare command to:
1. Read `default_base_branch` from environment variable `BASE_BRANCH`
2. Use `default_base_branch` to load config files (spec.md and configuration.yml)
3. Call `config.get_base_branch(default_base_branch)` to resolve final base branch
4. Print informative message when base branch is overridden vs using default
5. Output resolved `base_branch` for downstream workflow steps

Added 4 new integration tests in `tests/integration/cli/commands/test_prepare.py`:
- `test_prepare_uses_config_base_branch_when_set`
- `test_prepare_uses_default_base_branch_when_config_not_set`
- `test_prepare_uses_default_branch_to_load_config_files`
- `test_prepare_outputs_base_branch_for_downstream_steps`

All 599 unit tests and 133 integration tests pass.

- [ ] Phase 3: Fix auto-start for completed projects

Fix the bug where completed projects (only closed PRs) don't auto-trigger when new tasks are added.

**Changes to `src/claudestep/services/composite/auto_start_service.py`:**

1. In `determine_new_projects()` (~line 120):
   - Change `state="all"` to `state="open"`
   - Update log message: "has no open PRs, ready for auto-start"

2. In `should_auto_trigger()` (~line 172):
   - Change `state="all"` to `state="open"`
   - Update reason: "No open PRs, ready for work"

**Unit tests to add/update** (`tests/unit/services/composite/test_auto_start_service.py`):
- `test_determine_new_projects_treats_completed_project_as_ready`
- `test_should_auto_trigger_approves_completed_project`
- Update existing tests to verify `state="open"` is used

- [ ] Phase 4: Update E2E tests

Update E2E test fixtures to use `baseBranch` configuration.

**Changes to `tests/e2e/conftest.py`:**

Update `test_config_content` fixture to include `baseBranch: main-e2e`:
```yaml
reviewers:
  - username: gestrich
    maxOpenPRs: 5
baseBranch: main-e2e
```

This ensures E2E tests explicitly specify their base branch, which is the expected pattern for any non-main branch usage.

- [ ] Phase 5: Validation

**Automated testing:**
- Run unit tests: `pytest tests/unit/`
- Run integration tests: `pytest tests/integration/`
- Run E2E tests: `./tests/e2e/run_test.sh` (do NOT run pytest directly on e2e tests - the script triggers GitHub workflows that can be monitored locally)

**Manual verification scenarios:**
1. Project with `baseBranch: develop` → PR should target `develop`
2. Project without `baseBranch` → PR should target workflow default
3. Completed project with new task added → should auto-trigger (bug fix)
4. Active project (has open PRs) → should be skipped by auto-start

**Success criteria:**
- All tests pass
- `baseBranch` in configuration.yml is respected
- Completed projects can start new tasks (bug fixed)
- No regression in existing functionality
