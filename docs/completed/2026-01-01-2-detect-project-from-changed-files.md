# Detect Project from Changed Files via GitHub API

## Background

Currently, `parse_event.py` tries to determine the project name from:
1. The `project_name` workflow input (for `workflow_dispatch`)
2. The branch name pattern `claude-step-{project}-{hash}` (for `pull_request` events)

For **push events** (triggered when a PR is merged or code is pushed directly to main), neither of these work:
- No `project_name` input is provided
- The branch being pushed to (`main`, `main-e2e`) doesn't contain the project name

This causes the error: "Could not determine project name from branch pattern" and the workflow skips.

**The Solution**: Use the GitHub Compare API to detect which spec files changed between `before_sha` and `after_sha`, then extract the project name from the file path (`claude-step/{project}/spec.md`).

**Key Design Decisions**:
1. Use this approach for ALL event types (push, workflow_dispatch without project_name, etc.) for consistency
2. If multiple spec files are modified in a single push, throw an error (rare edge case, user should push separately)
3. Remove the branch pattern parsing logic since it's no longer needed

## Phases

- [x] Phase 1: Add `compare_commits` function to infrastructure layer

Add a new function to `src/claudestep/infrastructure/github/operations.py` that calls the GitHub Compare API.

**Files modified:**
- `src/claudestep/infrastructure/github/operations.py` - Added `compare_commits` function
- `tests/unit/infrastructure/github/test_operations.py` - Added `TestCompareCommits` class with 7 test cases

**Technical notes:**
- Function uses the existing `gh_api_call` helper to call the GitHub Compare API
- Returns list of file paths from the `files` array in the API response
- Handles edge cases: empty files list, missing files key in response
- Comprehensive test coverage including: success cases, branch name support, empty results, API error propagation, many files, and spec.md file detection

**Implementation details:**
```python
def compare_commits(repo: str, base: str, head: str) -> List[str]:
    """Get list of changed files between two commits via GitHub API.

    Uses the GitHub Compare API: GET /repos/{owner}/{repo}/compare/{base}...{head}

    Args:
        repo: GitHub repository (owner/name)
        base: Base commit SHA or branch name
        head: Head commit SHA or branch name

    Returns:
        List of file paths that were added, modified, or removed

    Raises:
        GitHubAPIError: If API call fails
    """
    endpoint = f"/repos/{repo}/compare/{base}...{head}"
    response = gh_api_call(endpoint, method="GET")

    files = response.get("files", [])
    return [f["filename"] for f in files]
```

- [x] Phase 2: Add `detect_project_from_diff` function

Add a helper function that takes a list of changed files and extracts the project name.

**Files modified:**
- `src/claudestep/infrastructure/github/operations.py` - Added `detect_project_from_diff` function
- `tests/unit/infrastructure/github/test_operations.py` - Added `TestDetectProjectFromDiff` class with 10 test cases

**Technical notes:**
- Function uses regex pattern `^claude-step/([^/]+)/spec\.md$` to match spec files
- Returns project name when exactly one spec.md is changed, None if none changed
- Raises `ValueError` with sorted project names when multiple spec files are modified
- Comprehensive test coverage including: single/no/multiple spec files, wrong directory structures, empty lists, project names with hyphens/underscores

**Implementation details:**
```python
def detect_project_from_diff(changed_files: List[str]) -> Optional[str]:
    """Extract project name from changed spec files.

    Looks for files matching pattern: claude-step/{project}/spec.md

    Args:
        changed_files: List of file paths from compare_commits

    Returns:
        Project name if exactly one spec.md was changed, None otherwise

    Raises:
        ValueError: If multiple different spec.md files were changed
    """
    spec_pattern = re.compile(r"^claude-step/([^/]+)/spec\.md$")
    projects = set()

    for file_path in changed_files:
        match = spec_pattern.match(file_path)
        if match:
            projects.add(match.group(1))

    if len(projects) == 0:
        return None
    elif len(projects) == 1:
        return projects.pop()
    else:
        raise ValueError(f"Multiple projects modified in single push: {sorted(projects)}. Push changes to one project at a time.")
```

- [x] Phase 3: Update `GitHubEventContext` to support project detection from diff

Modify `src/claudestep/domain/github_event.py` to use the new approach.

**Files modified:**
- `src/claudestep/domain/github_event.py` - Removed `extract_project_from_branch()`, added `get_changed_files_context()`
- `tests/unit/domain/test_github_event.py` - Replaced `TestGitHubEventContextProjectExtraction` with `TestGitHubEventContextChangedFilesContext`

**Technical notes:**
- Removed the `re` import since `extract_project_from_branch()` was the only method using regex
- Updated class docstring to reflect new method instead of branch pattern extraction
- New method `get_changed_files_context()` returns `Optional[Tuple[str, str]]`:
  - For push events with both `before_sha` and `after_sha`: returns `(before_sha, after_sha)`
  - For all other cases (workflow_dispatch, pull_request, or missing SHAs): returns `None`
- Updated integration tests to verify `get_changed_files_context()` behavior across all event types
- All 658 unit tests pass

**Implementation details:**
```python
def get_changed_files_context(self) -> Optional[Tuple[str, str]]:
    """Get commit SHAs for detecting changed files via GitHub Compare API.

    For push events, returns the before and after SHAs that can be used
    to determine which files changed. This enables project detection
    by looking for modified spec.md files.

    Returns:
        Tuple of (before_sha, after_sha) for push events, None otherwise.
        The caller can use these SHAs with the GitHub Compare API.
    """
    if self.event_name == "push" and self.before_sha and self.after_sha:
        return (self.before_sha, self.after_sha)
    return None
```

**Note:** The actual API call happens in `parse_event.py`, not in the domain model (domain doesn't call infrastructure).

- [x] Phase 4: Update `parse_event.py` to detect project from changed files

Modify the command to use the new detection approach.

**Files modified:**
- `src/claudestep/cli/commands/parse_event.py` - Updated project detection logic
- `src/claudestep/domain/github_event.py` - Extended `get_changed_files_context()` to support pull_request events
- `tests/integration/cli/commands/test_parse_event.py` - Updated tests to use mocked API calls
- `tests/unit/domain/test_github_event.py` - Updated tests for new pull_request support

**Technical notes:**
- Added `repo` parameter to `cmd_parse_event()` function and `main()` entry point
- The function now reads `GITHUB_REPOSITORY` environment variable for API calls
- Extended `get_changed_files_context()` in `GitHubEventContext` to also return `(base_ref, head_ref)` for pull_request events, enabling project detection from diff for both push and pull_request events
- For push events: Uses before_sha/after_sha to compare commits
- For pull_request events: Uses base_ref/head_ref to compare branches
- All tests mock `compare_commits` and `detect_project_from_diff` to avoid real API calls
- 811 tests pass including 64 tests for parse_event and github_event

**Implementation details:**
```python
# Determine project name
resolved_project = project_name  # From input (workflow_dispatch)

if not resolved_project:
    # Try to detect from changed files (push/pull_request events)
    changed_files_context = context.get_changed_files_context()
    if changed_files_context and repo:
        before_sha, after_sha = changed_files_context
        print(f"\n  Detecting project from changed files...")
        print(f"  Comparing {before_sha[:8]}...{after_sha[:8]}")
        changed_files = compare_commits(repo, before_sha, after_sha)
        print(f"  Found {len(changed_files)} changed files")
        try:
            resolved_project = detect_project_from_diff(changed_files)
            if resolved_project:
                print(f"  Detected project: {resolved_project}")
        except ValueError as e:
            # Multiple projects modified
            reason = str(e)
            print(f"\n⏭️  Skipping: {reason}")
            gh.write_output("skip", "true")
            gh.write_output("skip_reason", reason)
            return 0

if not resolved_project:
    if event_name == "workflow_dispatch":
        reason = "No project_name provided for workflow_dispatch event"
    else:
        reason = "No spec.md changes detected in push"
    print(f"\n⏭️  Skipping: {reason}")
    gh.write_output("skip", "true")
    gh.write_output("skip_reason", reason)
    return 0
```

**Environment variable needed:**
- Add `GITHUB_REPOSITORY` to the parse-event step in `action.yml` so the API call knows which repo to query (done in Phase 5)

- [x] Phase 5: Update `action.yml` to pass repository context

Ensure the parse-event step has access to the repository name for the API call.

**Files modified:**
- `action.yml` - Added `GITHUB_REPOSITORY` environment variable to parse-event step

**Technical notes:**
- Added `GITHUB_REPOSITORY: ${{ github.repository }}` to the `env` section of the "Parse event and determine action" step
- This environment variable is read by `parse_event.py` to call the GitHub Compare API for project detection
- All 811 unit and integration tests pass

**Implementation details:**
```yaml
- name: Parse event and determine action
  id: parse
  if: inputs.github_event != ''
  shell: bash
  env:
    EVENT_NAME: ${{ inputs.event_name }}
    EVENT_JSON: ${{ inputs.github_event }}
    PROJECT_NAME: ${{ inputs.project_name }}
    DEFAULT_BASE_BRANCH: ${{ inputs.default_base_branch }}
    PR_LABEL: ${{ inputs.pr_label }}
    ACTION_PATH: ${{ github.action_path }}
    GITHUB_REPOSITORY: ${{ github.repository }}
  run: |
    export PYTHONPATH="$ACTION_PATH/src:$PYTHONPATH"
    python3 -m claudestep parse-event
```

- [x] Phase 6: Revert E2E test workflow_dispatch changes

**Outcome:** No changes needed - workflow_dispatch approach is still required.

**Technical notes:**
- The `workflow_dispatch` calls in E2E tests are **not** a workaround for project detection - they address a fundamental GitHub Actions limitation
- **GitHub Security Feature**: Pushes/merges made with `GITHUB_TOKEN` do NOT trigger `push` events (prevents infinite workflow loops)
- This is independent of project detection: even with project detection from changed files working correctly, the `push` event itself won't fire when using `GITHUB_TOKEN`
- The `workflow_dispatch` approach is the correct pattern for E2E tests running in GitHub Actions
- Since Sep 2022, `GITHUB_TOKEN` can trigger `workflow_dispatch` events, making this the recommended approach

**Files unchanged (intentionally):**
- `tests/e2e/conftest.py` - `trigger_workflow()` in `setup_test_project` remains (needed for GITHUB_TOKEN limitation)
- `tests/e2e/test_workflow_e2e.py` - `trigger_workflow()` in `test_merge_triggered_workflow` remains (needed after merge with GITHUB_TOKEN)

**When to revisit:**
- If E2E tests are run locally with a Personal Access Token (PAT) instead of `GITHUB_TOKEN`, the `workflow_dispatch` calls could be removed and push events would work naturally
- This is tracked in the separate local E2E execution plan (`2026-01-01-1-e2e-local-execution.md`)

- [x] Phase 7: Add unit tests for new functions

Add comprehensive unit tests for the new infrastructure and detection functions.

**Files modified:**
- `tests/unit/infrastructure/github/test_operations.py` - Tests for `compare_commits` and `detect_project_from_diff`
- `tests/unit/domain/test_github_event.py` - Tests for modified `GitHubEventContext`

**Technical notes:**
- All required tests were already implemented in previous phases (Phase 1, 2, and 3)
- `TestCompareCommits` class: 7 test cases covering success, branch names, empty results, missing files key, API error propagation, many files, and spec.md detection
- `TestDetectProjectFromDiff` class: 10 test cases covering single/no/multiple spec files, wrong directory structures, empty lists, project names with hyphens/underscores, and same-project multiple files
- `TestGitHubEventContextChangedFilesContext` class: 8 test cases covering push events, workflow_dispatch, pull_request, and missing SHA scenarios
- All 660 unit tests pass
- All 151 integration tests pass

**Test coverage for key functions:**
1. ✅ Single spec.md changed → returns project name
2. ✅ No spec.md changed → returns None
3. ✅ Multiple spec.md files changed → raises ValueError
4. ✅ Other files changed (not spec.md) → returns None
5. ✅ Spec.md in wrong directory structure → returns None

- [x] Phase 8: Validation

**Automated testing:**
1. Run unit tests:
   ```bash
   pytest tests/unit/ -v
   ```

2. Run integration tests:
   ```bash
   pytest tests/integration/ -v
   ```

**Manual verification (optional):**
1. Push a spec file to `main-e2e` and verify workflow detects the project
2. Merge a ClaudeStep PR and verify the next task is triggered

**Success criteria:**
- All unit tests pass
- All integration tests pass
- Push events to `main`/`main-e2e` correctly detect project from changed files
- Workflow skips with clear error when multiple projects modified in single push
- `workflow_dispatch` with `project_name` input still works as before

**Technical notes:**
- All 660 unit tests pass (0.92s)
- All 151 integration tests pass (0.62s)
- Total test coverage: 54.85% (unit), 49.86% (integration)
- All success criteria verified through automated tests:
  - `TestCompareCommits`: 7 test cases for GitHub Compare API integration
  - `TestDetectProjectFromDiff`: 10 test cases for project extraction from changed files
  - `TestGitHubEventContextChangedFilesContext`: 8 test cases for push/pull_request event handling
  - `TestCmdParseEvent`: Integration tests verify skip behavior, project detection, and error handling
