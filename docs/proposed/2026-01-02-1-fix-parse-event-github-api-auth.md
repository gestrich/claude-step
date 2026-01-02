## Background

The parse-event step in `action.yml` is failing with error:
```
Event parsing failed: GitHub CLI command failed: api /repos/gestrich/claude-step/compare/e859865...15782fa --method GET
```

This was caused by commits `d5cb95b`, `4abca56`, and `5ae9cf0` which added project detection from changed files. The `compare_commits()` function calls `gh api` to use the GitHub Compare API, but the parse-event step in `action.yml` is missing the `GH_TOKEN` environment variable required for authentication.

**Current Architecture:**
- All GitHub API operations use the `gh` CLI via `run_gh_command()` and `gh_api_call()`
- The `gh` CLI requires `GH_TOKEN` environment variable for authentication
- Steps like `prepare`, `finalize`, `prepare_summary`, and `post_pr_comment` all set `GH_TOKEN`
- The `parse` step does NOT set `GH_TOKEN`, causing the API call to fail

**Decision Point:**
We could either:
1. Add `GH_TOKEN` to the parse-event step (quick fix)
2. Use Python's `urllib` with direct HTTP requests for operations in parse-event (avoids gh CLI dependency)

Since parse-event runs before checkout and is a lightweight operation, using `urllib` (stdlib) for just this operation keeps the step self-contained and doesn't require passing `GH_TOKEN` through the action input to an early step. However, this adds code complexity and diverges from the rest of the codebase.

**Recommendation:** Add `GH_TOKEN` to the parse-event step. This is consistent with how other steps work and is the minimal change to fix the issue.

## Phases

- [ ] Phase 1: Add GH_TOKEN to parse-event step

Add the `GH_TOKEN` environment variable to the parse-event step in `action.yml`:

**File to modify:** `action.yml`

**Change:** Add `GH_TOKEN: ${{ inputs.github_token }}` to the parse-event step's `env` block (around line 123-130).

The step currently has:
```yaml
env:
  EVENT_NAME: ${{ inputs.event_name }}
  EVENT_JSON: ${{ inputs.github_event }}
  PROJECT_NAME: ${{ inputs.project_name }}
  DEFAULT_BASE_BRANCH: ${{ inputs.default_base_branch }}
  PR_LABEL: ${{ inputs.pr_label }}
  ACTION_PATH: ${{ github.action_path }}
  GITHUB_REPOSITORY: ${{ github.repository }}
```

Add:
```yaml
  GH_TOKEN: ${{ inputs.github_token }}
```

- [ ] Phase 2: Validation

**Automated Testing:**
1. Run unit tests: `python -m pytest tests/unit/ -v`
2. Run integration tests: `python -m pytest tests/integration/ -v`

**Manual Verification:**
1. Push a change to a spec.md file in the target repository
2. Verify the ClaudeStep workflow runs successfully
3. Confirm the parse-event step can call the GitHub Compare API

**Success Criteria:**
- All existing tests pass
- Push events correctly detect the project from changed spec.md files
- No "GitHub CLI command failed" errors in parse-event step
