## Background

Users want the ability to specify custom GitHub labels to be applied to PRs created by ClaudeChain. This feature follows the same override pattern as `claude_allowed_tools` / `allowedTools`:

1. **Workflow level**: A new `pr_labels` input in action.yml provides the default labels
2. **Project level**: A new `labels` field in `configuration.yml` overrides the workflow default

The labels serve no functional purpose within ClaudeChain—they are simply applied to PRs when created for the user's organizational needs (e.g., filtering, categorization, team workflows).

**Note**: This is distinct from the existing `pr_label` input (singular), which is used internally for identifying/filtering ClaudeChain PRs. The new `pr_labels` (plural) feature is purely for user-defined organizational labels.

## Phases

- [ ] Phase 1: Add domain model support

**Files to modify:**
- `src/claudechain/domain/project_configuration.py`

**Tasks:**
1. Add `labels: Optional[str] = None` field to `ProjectConfiguration` dataclass
2. Parse `labels` from YAML in `from_yaml_string()` factory method
3. Add `get_labels(default_labels: str) -> str` resolution method following the pattern of `get_allowed_tools()`
4. Update docstrings to document the new field

**Pattern to follow (from `allowed_tools`):**
```python
def get_labels(self, default_labels: str) -> str:
    """Resolve labels from project config or fall back to default.

    Args:
        default_labels: Default from workflow/CLI (required, no default here)

    Returns:
        Project's labels if set, otherwise the default
    """
    if self.labels:
        return self.labels
    return default_labels
```

- [ ] Phase 2: Add workflow input and constants

**Files to modify:**
- `action.yml`
- `src/claudechain/domain/constants.py`

**Tasks:**
1. Add `pr_labels` input to action.yml with empty string default (no labels by default):
   ```yaml
   pr_labels:
     description: 'Comma-separated list of additional labels to apply to PRs (optional)'
     required: false
     default: ''
   ```
2. Add `DEFAULT_PR_LABELS = ""` constant in constants.py (empty = no additional labels)
3. Pass `PR_LABELS` environment variable to prepare step in action.yml

- [ ] Phase 3: Wire through CLI layer

**Files to modify:**
- `src/claudechain/__main__.py`
- `src/claudechain/cli/commands/prepare.py`

**Tasks:**
1. In `__main__.py`: Read `PR_LABELS` env var and pass to `cmd_prepare()` as `default_pr_labels` parameter
2. In `prepare.py`:
   - Add `default_pr_labels: str` parameter to `cmd_prepare()`
   - Call `config.get_labels(default_pr_labels)` to resolve labels
   - Log override if project config differs from default
   - Write resolved labels to output: `gh.write_output("pr_labels", labels)`

- [ ] Phase 4: Apply labels in finalize

**Files to modify:**
- `action.yml` (finalize step env vars)
- `src/claudechain/cli/commands/finalize.py`

**Tasks:**
1. In action.yml finalize step: Add `PR_LABELS: ${{ steps.prepare.outputs.pr_labels }}` to env
2. In `finalize.py`:
   - Read `PR_LABELS` from environment
   - Parse comma-separated labels into list
   - Add each label to PR creation command using multiple `--label` args
   - Only add labels if non-empty string

**Implementation detail:**
```python
# Parse labels from env (comma-separated, may be empty)
pr_labels_str = os.environ.get("PR_LABELS", "")
pr_labels = [l.strip() for l in pr_labels_str.split(",") if l.strip()]

# In PR creation, add each label
for label in pr_labels:
    pr_create_args.extend(["--label", label])
```

- [ ] Phase 5: Update documentation

**Files to modify:**
- `docs/feature-guides/setup.md` (Action Reference section)
- `docs/feature-guides/projects.md` (configuration.yml Format section)

**Tasks:**
1. Add `pr_labels` to the Inputs table in setup.md
2. Add `labels` field documentation to configuration.yml schema in projects.md
3. Add example showing both workflow-level and project-level configuration

- [ ] Phase 6: Validation

**Tests to add/modify:**

1. **Unit tests** (`tests/unit/domain/test_project_configuration.py`):
   - Test `labels` field parsing from YAML
   - Test `get_labels()` returns config value when set
   - Test `get_labels()` returns default when not set
   - Test empty string handling

2. **Integration tests** (`tests/integration/cli/commands/test_prepare.py`):
   - Test labels output is written correctly
   - Test project config override is applied
   - Test default is used when no project config

3. **Integration tests** (`tests/integration/cli/commands/test_finalize.py`):
   - Test multiple labels are added to PR creation command
   - Test empty labels string doesn't add any labels
   - Test single label works correctly

**Run commands:**
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/domain/test_project_configuration.py -v
pytest tests/integration/cli/commands/test_prepare.py -v
pytest tests/integration/cli/commands/test_finalize.py -v

# Full test suite with coverage
pytest tests/unit/ tests/integration/ --cov=src/claudechain --cov-report=term-missing
```

**Success criteria:**
- All existing tests pass
- New tests achieve 100% coverage for added code
- Overall coverage remains above 85%
