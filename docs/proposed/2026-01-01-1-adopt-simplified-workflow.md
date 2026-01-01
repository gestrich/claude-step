## Background

The project's own `claudestep.yml` workflow file contains ~100 lines of bash logic to handle:
- Determining project name from branch patterns or inputs
- Inferring base branch from GitHub event context
- Checking for 'claudestep' label on PRs
- Deciding whether to skip execution
- Handling different event types (workflow_dispatch, pull_request:closed)

This complexity was addressed in `docs/completed/2026-01-01-simplify-user-workflow.md`, which added:
- `github_event` and `event_name` inputs to `action.yml`
- A `parse-event` CLI command that handles all event parsing logic
- Internal checkout handling within the action
- Skip logic with proper outputs

The simplified example workflow (`examples/claudestep-simplified.yml`) was created to demonstrate the new approach. However, the project's own `claudestep.yml` has not yet been updated to use this simplified approach.

**Goal:** Update `claudestep.yml` to use the simplified workflow pattern, then delete the `examples/` directory since `claudestep.yml` itself will serve as the canonical example.

## Phases

- [ ] Phase 1: Update claudestep.yml to simplified workflow

Replace the current workflow with the simplified approach:

**Current structure (~140 lines):**
- `Determine project and base branch` step (50+ lines of bash)
- `Validate base branch` step
- `Checkout repository` step (manual)
- `Run ClaudeStep action` step

**New structure (~40 lines):**
```yaml
jobs:
  run-claudestep:
    runs-on: ubuntu-latest
    steps:
      - uses: ./
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          github_event: ${{ toJson(github.event) }}
          event_name: ${{ github.event_name }}
          project_name: ${{ github.event.inputs.project_name || '' }}
          claude_model: 'claude-3-haiku-20240307'
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Key changes:**
1. Remove `Determine project and base branch` step entirely
2. Remove `Validate base branch` step entirely
3. Remove manual `Checkout repository` step (action handles this)
4. Update action invocation to pass `github_event` and `event_name`
5. Keep `workflow_dispatch` inputs for manual triggering (project_name only - base_branch and checkout_ref are no longer needed as inputs since action infers them)
6. Preserve existing secrets usage (ANTHROPIC_API_KEY, GITHUB_TOKEN, SLACK_WEBHOOK_URL)
7. Keep header comments but update to reflect simplified approach

**File to modify:** `.github/workflows/claudestep.yml`

- [ ] Phase 2: Simplify triggers and workflow_dispatch inputs

**Change triggers from `pull_request:closed` to `push`:**

The current workflow uses `pull_request: types: [closed]` to continue after PR merges. However, `push` events are simpler and cover the same use case - when a PR is merged, it creates a push to the base branch.

**Current triggers:**
```yaml
on:
  workflow_dispatch:
    inputs:
      project_name: ...
      base_branch: ...
      checkout_ref: ...
  pull_request:
    types: [closed]
```

**New triggers:**
```yaml
on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name (folder under claude-step/)'
        required: true
        type: string
        default: 'e2e-test-project'
  push:
    branches:
      - main
      - main-e2e
```

**Benefits of using `push` instead of `pull_request:closed`:**
- Simpler - no need to check if PR was merged vs closed without merge
- No need to check for `claudestep` label (branch name pattern is sufficient)
- Covers direct pushes and PR merges equally
- The action's `parse-event` already handles push events

**Removed workflow_dispatch inputs:**
- `base_branch` - resolved from project's `configuration.yml` or defaults to the branch the workflow runs on
- `checkout_ref` - determined automatically by the action based on event type

- [ ] Phase 3: Update header comments

Update the workflow header comments to reflect the simplified design:

```yaml
# ClaudeStep Workflow
#
# This workflow handles all event types automatically by passing the GitHub
# event context to the action. The action determines:
# - Whether to execute or skip
# - Which ref to checkout
# - The project name (from branch pattern or input)
# - The base branch for PR creation (from project config or default)
#
# Trigger modes:
# - workflow_dispatch: Manual trigger with project_name input
# - push: Continues processing after PR merge (or direct push)
#
# Security: workflow_dispatch requires repository write access.
```

- [ ] Phase 4: Delete examples directory

Remove the `examples/` directory since `claudestep.yml` now serves as the canonical example:

```bash
rm -rf examples/
```

The `examples/claudestep-simplified.yml` file was a temporary demonstration. Now that our own workflow uses the simplified approach, users can reference `.github/workflows/claudestep.yml` directly.

**Files to delete:**
- `examples/claudestep-simplified.yml`
- `examples/` directory

- [ ] Phase 5: Update README references

Check if README.md references the examples directory and update accordingly:
- Remove references to `examples/claudestep-simplified.yml`
- Point users to `.github/workflows/claudestep.yml` as the reference implementation

**File to modify:** `README.md` (if it references examples)

- [ ] Phase 6: Validation

**Automated testing:**
- Run unit tests: `pytest tests/unit/`
- Run integration tests: `pytest tests/integration/`

**⚠️ IMPORTANT: Do NOT run E2E tests (`./tests/e2e/run_test.sh`)**
- E2E tests trigger actual GitHub workflows which can cause issues
- The E2E infrastructure has known issues (documented in completed specs)
- Unit and integration tests provide sufficient coverage for this change

**Manual verification (optional, not required):**
- Review the updated workflow file for correctness
- Verify YAML syntax is valid

**Success criteria:**
- All unit tests pass
- All integration tests pass
- `claudestep.yml` reduced from ~140 lines to ~40 lines
- No bash complexity in workflow file
- `examples/` directory removed
- README updated to reference `claudestep.yml` instead of examples
- Workflow uses `push` trigger instead of `pull_request:closed`
- Workflow still supports workflow_dispatch for manual triggers
