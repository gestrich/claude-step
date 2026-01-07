## Background

Currently, users of the ClaudeChain action must pass GitHub event context as explicit inputs:

```yaml
- uses: gestrich/claude-chain@main
  with:
    github_event: ${{ toJson(github.event) }}
    event_name: ${{ github.event_name }}
    project_name: ${{ github.event.inputs.project_name || '' }}
```

This is redundant because GitHub Actions provides these values through the `github` context, which is available inside composite actions via `${{ github.event }}` and `${{ github.event_name }}`. The action can access these internally without requiring users to pass them explicitly.

**Benefits of this change:**
- Simpler workflow configuration for users
- Less error-prone (users can't accidentally pass wrong values)
- Cleaner action interface
- `inputs.project_name` for workflow_dispatch can be extracted from `github.event.inputs.project_name` internally

## Phases

- [x] Phase 1: Update action.yml to use github context directly

Remove the `github_event` and `event_name` inputs from action.yml. Update the parse-event step to read from the github context instead of inputs:

**Files to modify:**
- `action.yml`

**Changes:**
1. Remove the `github_event` input definition (lines 19-21)
2. Remove the `event_name` input definition (lines 22-24)
3. Update the condition `if: inputs.github_event != ''` to a new mechanism (see Phase 2 discussion below)
4. Update the parse step environment variables:
   - Change `EVENT_NAME: ${{ inputs.event_name }}` to `EVENT_NAME: ${{ github.event_name }}`
   - Change `EVENT_JSON: ${{ inputs.github_event }}` to `EVENT_JSON: ${{ toJson(github.event) }}`
5. For `project_name`, extract from `github.event.inputs.project_name` when available

**Important consideration:** The current design uses `inputs.github_event != ''` to detect "simplified workflow mode" vs "direct mode" where users call prepare/finalize themselves. We need to determine if this distinction is still needed or if we can always run the parse-event step.

- [x] Phase 2: Determine new approach for simplified vs direct mode

Currently, the action supports two modes:
1. **Simplified mode** (github_event is provided): Runs parse-event step, handles checkout internally
2. **Direct mode** (github_event not provided): Skips parse-event, user handles checkout

Options:
- **Option A**: Always run parse-event (simplest, may break existing direct-mode users)
- **Option B**: Add a new input like `auto_parse: true/false` to explicitly control this
- **Option C**: Detect based on whether checkout has already happened (check if .git exists)

**Recommended approach**: Option A - Always run parse-event. Review existing workflows to confirm this doesn't break anything. The parse-event step already handles various event types gracefully.

- [x] Phase 3: Update claudechain.yml workflow

Update the repository's own workflow to use the simplified interface:

**Files to modify:**
- `.github/workflows/claudechain.yml`

**Changes:**
1. Remove the `github_event` and `event_name` input lines
2. Keep `project_name` input for workflow_dispatch (or also remove if we read it internally)

- [ ] Phase 4: Update documentation

Update any documentation that shows how to configure the action:

**Files to check:**
- `README.md` - Update usage examples
- `docs/feature-guides/` - Check for workflow configuration examples

- [ ] Phase 5: Validation

**Automated testing:**
1. Run existing unit tests: `pytest tests/unit/ -v`
2. Run integration tests: `pytest tests/integration/ -v`

**Manual validation:**
1. Trigger workflow_dispatch to test manual execution
2. Create and merge a test PR to verify pull_request event handling works
3. Verify skip logic still works correctly (non-claudechain PRs should be skipped)
