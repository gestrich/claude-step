# Remove Push Event Support, Use Pull Request Merge Instead

## Background

The `anthropics/claude-code-action@v1` action does not support `push` events. When triggered by a push event, it throws:

```
Prepare step failed with error: Unsupported event type: push
```

Looking at the claude-code-action source code (`src/github/context.ts`), only these events are supported:
- `pull_request`
- `issue_comment`
- `issues`
- `workflow_dispatch`
- `workflow_run`

ClaudeStep was designed to handle push events internally (the `parse_event.py` command correctly parses push events and detects projects from changed files). However, this is incompatible with the upstream `claude-code-action` limitation.

**Solution:** Remove push event support from documentation and workflows. Use `pull_request: types: [closed]` instead, which:
1. IS supported by `claude-code-action`
2. Already has ClaudeStep logic to check for merged state and claudestep label
3. Detects projects from changed files via the GitHub Compare API

This is simpler than workarounds like re-triggering as workflow_dispatch.

## Phases

- [x] Phase 1: Update workflow file

Replace `push` trigger with `pull_request: types: [closed]`.

**Files to modify:**
- `.github/workflows/claudestep.yml`

**Changes:**
```yaml
# Before
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

# After
on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name (folder under claude-step/)'
        required: true
        type: string
        default: 'e2e-test-project'

  pull_request:
    types: [closed]
    branches:
      - main
      - main-e2e
```

Also update the header comments to reflect the new trigger modes.

- [x] Phase 2: Update documentation

Update all documentation to reflect the supported triggers.

**Files to modify:**
- `README.md`
- Explore `docs/` directory (excluding `docs/completed/`) to find other docs that may reference push events:
  - `docs/feature-guides/`
  - `docs/feature-architecture/`
  - `docs/general-architecture/`
  - `docs/proposed/`

**Changes:**
- Update workflow examples to show `pull_request: types: [closed]` instead of `push`
- Add note explaining that PRs must have the `claudestep` label and be merged
- Remove any references to push event triggering
- Search for "push" references in docs and update as needed

- [x] Phase 3: Keep push-specific code (no changes)

Keep the push event handling code for potential future use.

**Files unchanged:**
- `src/claudestep/domain/github_event.py` - Has push event parsing
- `src/claudestep/cli/commands/parse_event.py` - Has push event handling

**Rationale:**
- Push events work correctly in ClaudeStep itself
- The limitation is in the upstream `claude-code-action`
- If `claude-code-action` adds push support later, ClaudeStep will already work
- No harm in keeping the code

- [x] Phase 4: Validation

**Automated testing:**
```bash
pytest tests/unit/ -v
pytest tests/integration/ -v
```

**Manual verification:**
1. Create a PR with the `claudestep` label in the test repository
2. Merge the PR
3. Verify the workflow triggers and completes successfully

**Success criteria:**
- All unit tests pass
- All integration tests pass
- Documentation accurately reflects supported triggers
- PR merge with claudestep label triggers ClaudeStep successfully
