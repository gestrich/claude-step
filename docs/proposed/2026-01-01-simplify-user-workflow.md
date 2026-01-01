## Background

Currently, users must maintain a complex `claudestep.yml` workflow file with significant bash logic to:
1. Determine project name from branch patterns or inputs
2. Infer base branch from GitHub event context
3. Check for 'claudestep' label on PRs
4. Decide whether to skip execution
5. Handle different event types (workflow_dispatch, pull_request:closed, push)

This complexity lives in the user's workflow file, making it:
- Hard to maintain (users must update their workflow when logic changes)
- Error-prone (copy-paste mistakes)
- Difficult to upgrade (changes require all users to update their workflows)

**Proposed solution**: Move all event-handling logic INTO the `action.yml` composite action. Users pass the GitHub event context to the action, and the action handles everything internally.

**User workflow simplification**:

Before (~100+ lines):
```yaml
jobs:
  run-claudestep:
    steps:
      - name: Determine project and base branch
        id: project
        run: |
          # 50+ lines of bash logic...
      - name: Checkout
        uses: actions/checkout@v4
        with:
          ref: ${{ steps.project.outputs.checkout_ref }}
      - uses: gestrich/claude-step@v1
        with:
          project_name: ${{ steps.project.outputs.name }}
          base_branch: ${{ steps.project.outputs.base_branch }}
```

After (~20 lines):
```yaml
jobs:
  run-claudestep:
    steps:
      - uses: gestrich/claude-step@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          # Pass event context - action handles the rest
          github_event: ${{ toJson(github.event) }}
          event_name: ${{ github.event_name }}
          # For workflow_dispatch only
          project_name: ${{ github.event.inputs.project_name || '' }}
```

**Key insight**: The action can do the checkout itself (composite actions support this), eliminating the need for users to determine checkout_ref.

**Related work**: The `baseBranch` configuration support (2026-01-01-unify-workflow-triggers.md) should be completed first, as this refactor will use that resolution logic.

## Phases

- [x] Phase 1: Design new action.yml inputs

Design the new input schema for `action.yml` that accepts event context:

**New inputs:**
```yaml
inputs:
  # Existing
  anthropic_api_key:
    description: 'Anthropic API key'
    required: true
  github_token:
    description: 'GitHub token for API calls'
    required: false
    default: ${{ github.token }}

  # New: Event context
  github_event:
    description: 'GitHub event payload (pass ${{ toJson(github.event) }})'
    required: true
  event_name:
    description: 'GitHub event name (pass ${{ github.event_name }})'
    required: true

  # Optional overrides (for workflow_dispatch)
  project_name:
    description: 'Project name override (for workflow_dispatch)'
    required: false
  default_base_branch:
    description: 'Default base branch if not in project config'
    required: false
    default: 'main'
```

**Outputs:**
```yaml
outputs:
  skipped:
    description: 'Whether execution was skipped (no claudestep label, etc.)'
  skip_reason:
    description: 'Reason for skipping if skipped'
  project_name:
    description: 'Detected/resolved project name'
  base_branch:
    description: 'Resolved base branch'
  pr_number:
    description: 'Created PR number if any'
  pr_url:
    description: 'Created PR URL if any'
```

**Completed:** Updated `action.yml` with:
- New inputs: `github_event`, `event_name`, `default_base_branch` (all optional for backward compatibility)
- New outputs: `skipped`, `skip_reason`, `project_name`, `base_branch`
- Made `project_name` optional (required only if `github_event` is not provided)
- The outputs reference `steps.parse` which will be added in Phase 3
- All 736 tests pass

- [x] Phase 2: Create event parsing module

Create a new Python module to parse GitHub event context and extract required information.

**New file: `src/claudestep/domain/github_event.py`**

```python
@dataclass
class GitHubEventContext:
    """Parsed GitHub event with extracted fields for ClaudeStep"""
    event_name: str  # workflow_dispatch, pull_request, push

    # For pull_request events
    pr_number: Optional[int] = None
    pr_merged: bool = False
    pr_labels: List[str] = field(default_factory=list)
    base_ref: Optional[str] = None  # Branch PR targets
    head_ref: Optional[str] = None  # Branch PR comes from

    # For push events
    ref_name: Optional[str] = None  # Branch pushed to
    before_sha: Optional[str] = None
    after_sha: Optional[str] = None

    # For workflow_dispatch
    inputs: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, event_name: str, event_json: str) -> 'GitHubEventContext':
        """Parse GitHub event JSON into structured context"""
        # Parse and extract relevant fields based on event_name
        ...

    def should_skip(self) -> Tuple[bool, str]:
        """Determine if ClaudeStep should skip this event"""
        # Check for claudestep label, merged state, etc.
        ...

    def get_checkout_ref(self) -> str:
        """Determine which ref to checkout"""
        ...

    def get_default_base_branch(self) -> str:
        """Get default base branch from event context"""
        ...

    def extract_project_from_branch(self) -> Optional[str]:
        """Extract project name from branch name pattern"""
        ...
```

**Unit tests**: `tests/unit/domain/test_github_event.py`
- Test parsing workflow_dispatch event
- Test parsing pull_request:closed event (merged)
- Test parsing pull_request:closed event (not merged)
- Test parsing push event
- Test should_skip logic (missing label, not merged, etc.)
- Test checkout_ref determination
- Test project extraction from branch name

**Completed:** Created `GitHubEventContext` dataclass with:
- `from_json()` class method that parses workflow_dispatch, pull_request, and push events
- `should_skip()` method that checks for merged state and required labels on PRs
- `get_checkout_ref()` method that determines the appropriate git ref for checkout
- `get_default_base_branch()` method that returns the target branch for new PRs
- `extract_project_from_branch()` method that parses ClaudeStep branch names (claude-step-{project}-{hash})
- `has_label()` helper method for label checking
- 40 comprehensive unit tests covering all parsing scenarios, skip logic, and edge cases
- All 776 tests pass

- [x] Phase 3: Update action.yml to handle checkout and event parsing

Modify `action.yml` to:
1. Parse the event context using new Python module
2. Determine if should skip
3. Do the checkout itself
4. Continue with prepare/finalize flow

**Changes to `action.yml`:**

```yaml
runs:
  using: 'composite'
  steps:
    - name: Parse event and determine action
      id: parse
      shell: bash
      run: |
        python3 -m claudestep parse-event \
          --event-name "${{ inputs.event_name }}" \
          --event-json '${{ inputs.github_event }}' \
          --project-name "${{ inputs.project_name }}"
      env:
        GITHUB_OUTPUT: ${{ github.output }}

    - name: Skip if not applicable
      if: steps.parse.outputs.skip == 'true'
      shell: bash
      run: |
        echo "Skipping: ${{ steps.parse.outputs.skip_reason }}"

    - name: Checkout repository
      if: steps.parse.outputs.skip != 'true'
      uses: actions/checkout@v4
      with:
        ref: ${{ steps.parse.outputs.checkout_ref }}
        fetch-depth: 0

    # ... rest of existing steps with conditions
```

**New CLI command**: `python3 -m claudestep parse-event`
- Parses event JSON
- Outputs: skip, skip_reason, checkout_ref, project_name, base_branch

**Completed:** Updated `action.yml` with:
- New `parse` step (id: `parse`) that runs `python3 -m claudestep parse-event` when `github_event` is provided
- Environment variables: `EVENT_NAME`, `EVENT_JSON`, `PROJECT_NAME`, `DEFAULT_BASE_BRANCH`, `PR_LABEL`
- New `Log skip reason` step that outputs a GitHub notice and step summary when skipping
- New `Checkout repository` step using `actions/checkout@v4` with parsed `checkout_ref`
- Updated `prepare` step with conditional execution (`if: inputs.github_event == '' || steps.parse.outputs.skip != 'true'`)
- Updated `prepare` step environment to use parsed values with fallback: `PROJECT_NAME`, `MERGED_PR_NUMBER`, `BASE_BRANCH`
- Updated `finalize` step with skip-aware conditional and parsed `BASE_BRANCH`
- All steps gracefully handle both simplified workflow (with `github_event`) and legacy workflow (without)
- All 776 unit/integration tests pass
- Note: Phase 4 will implement the actual `parse-event` CLI command that this step invokes

- [ ] Phase 4: Add parse-event CLI command

Add new CLI command to handle event parsing.

**Changes to `src/claudestep/cli/parser.py`:**
- Add `parse-event` subcommand with arguments:
  - `--event-name`: GitHub event name
  - `--event-json`: GitHub event JSON payload
  - `--project-name`: Optional project name override

**New file: `src/claudestep/cli/commands/parse_event.py`:**
```python
def cmd_parse_event(
    gh: GitHubActionsHelper,
    event_name: str,
    event_json: str,
    project_name: Optional[str] = None,
    default_base_branch: str = "main"
) -> int:
    """Parse GitHub event and output action parameters"""
    context = GitHubEventContext.from_json(event_name, event_json)

    # Check if should skip
    should_skip, reason = context.should_skip()
    if should_skip:
        gh.write_output("skip", "true")
        gh.write_output("skip_reason", reason)
        return 0

    # Determine project
    resolved_project = project_name or context.extract_project_from_branch()
    if not resolved_project:
        gh.write_output("skip", "true")
        gh.write_output("skip_reason", "Could not determine project name")
        return 0

    # Output results
    gh.write_output("skip", "false")
    gh.write_output("project_name", resolved_project)
    gh.write_output("checkout_ref", context.get_checkout_ref())
    gh.write_output("base_branch", context.get_default_base_branch())

    return 0
```

**Integration tests**: `tests/integration/cli/commands/test_parse_event.py`

- [ ] Phase 5: Create simplified example workflow

Create an example workflow file showing the simplified usage.

**New file: `examples/claudestep-simplified.yml`:**
```yaml
name: ClaudeStep

on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name'
        required: true
  pull_request:
    types: [closed]
  push:
    paths:
      - 'claude-step/*/spec.md'

permissions:
  contents: write
  pull-requests: write

jobs:
  run-claudestep:
    runs-on: ubuntu-latest
    steps:
      - uses: gestrich/claude-step@v2
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_event: ${{ toJson(github.event) }}
          event_name: ${{ github.event_name }}
          project_name: ${{ github.event.inputs.project_name || '' }}
```

**Update documentation:**
- Update README.md with new simplified setup
- Document migration path from old workflow to new

- [ ] Phase 6: Validation

**Automated testing:**
- Run unit tests: `pytest tests/unit/`
- Run integration tests: `pytest tests/integration/`
- Run E2E tests: `./tests/e2e/run_test.sh` (do NOT run pytest directly - the script triggers GitHub workflows that can be monitored locally)

**Manual verification scenarios:**
1. workflow_dispatch with project_name input → should work as before
2. pull_request:closed with 'claudestep' label → should detect project and continue
3. pull_request:closed without label → should skip with reason
4. pull_request:closed but not merged → should skip
5. push to spec.md → should trigger auto-start flow

**Success criteria:**
- All existing tests pass
- New event parsing tests pass
- Example workflow works for all trigger types
- User workflow reduced from ~100 lines to ~20 lines
- No regression in existing functionality
