# Trigger and Base Branch Refactor

## Background

The current trigger and base branch logic has several issues that need to be addressed:

1. **Branch name dependency**: Current logic relies on branch naming conventions (e.g., `claude-{project}-{hash}`) to detect projects, but the initial spec merge from a user may use any branch name
2. **Label dependency for triggers**: Current workflow requires the `claudechain` label to be present, but the initial spec PR won't have this label
3. **Configuration fetching**: Currently fetches configuration via GitHub API, but should use local filesystem after checkout for merge events
4. **Base branch validation**: Need to verify that the merge target branch matches the project's configured base branch
5. **Multiple project support**: A single PR could modify specs for multiple projects, requiring multiple workflow runs

The goal is to create a robust trigger system that:
- Triggers automatically when spec files are changed (initial or subsequent merges)
- Uses changed files (not branch names) to detect which project(s) are affected
- Validates base branch matches before executing
- Supports manual workflow triggers with explicit project + base_branch inputs
- Maintains compatibility with statistics gathering

## Decision Flow Diagrams

### PR Merge Trigger Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PR Merged to Any Branch                          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Did files in claude-chain/   │
                    │ directory change?            │
                    └──────────────────────────────┘
                         │                    │
                        YES                   NO
                         │                    │
                         ▼                    ▼
          ┌─────────────────────────┐    ┌──────────┐
          │ Detect project(s) from  │    │   SKIP   │
          │ changed spec.md files   │    └──────────┘
          └─────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ For each detected       │
          │ project:                │◄────────────────────┐
          └─────────────────────────┘                     │
                         │                                │
                         ▼                                │
          ┌─────────────────────────┐                     │
          │ Read local config file  │                     │
          │ (claude-chain/{project}/│                     │
          │  configuration.yml)     │                     │
          └─────────────────────────┘                     │
                         │                                │
                         ▼                                │
          ┌─────────────────────────┐                     │
          │ Resolve base_branch:    │                     │
          │ 1. config.baseBranch    │                     │
          │ 2. default_base_branch  │                     │
          │    (from workflow)      │                     │
          │ 3. "main" (constant)    │                     │
          └─────────────────────────┘                     │
                         │                                │
                         ▼                                │
          ┌─────────────────────────┐                     │
          │ Does resolved base      │                     │
          │ branch == merge target  │                     │
          │ branch?                 │                     │
          └─────────────────────────┘                     │
                │               │                         │
               YES              NO                        │
                │               │                         │
                ▼               ▼                         │
     ┌──────────────────┐  ┌──────────────┐              │
     │ EXECUTE workflow │  │ SKIP (branch │              │
     │ - Add label to   │  │  mismatch)   │              │
     │   merged PR      │  └──────────────┘              │
     │ - Find next task │                                │
     │ - Create new PR  │                                │
     └──────────────────┘                                │
                │                                         │
                ▼                                         │
     ┌──────────────────┐                                │
     │ More projects?   │────YES─────────────────────────┘
     └──────────────────┘
                │
               NO
                │
                ▼
           ┌──────────┐
           │   DONE   │
           └──────────┘
```

### Manual Workflow Dispatch Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│         User triggers workflow_dispatch from GitHub UI              │
│         Inputs: project_name (required), base_branch (required)     │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Checkout base_branch         │
                    └──────────────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │ Does project exist at        │
                    │ claude-chain/{project}/?     │
                    └──────────────────────────────┘
                         │                    │
                        YES                   NO
                         │                    │
                         ▼                    ▼
          ┌─────────────────────────┐   ┌─────────────────────┐
          │ Read local config file  │   │ ERROR: Project not  │
          │ (configuration.yml)     │   │ found on branch     │
          └─────────────────────────┘   └─────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ Resolve config's        │
          │ base_branch (if set)    │
          └─────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────┐
          │ Does config base_branch │
          │ match input base_branch?│
          │ (or config has none)    │
          └─────────────────────────┘
                │               │
               YES              NO
                │               │
                ▼               ▼
     ┌──────────────────┐  ┌──────────────────────────┐
     │ EXECUTE workflow │  │ ERROR: base_branch       │
     │ - Find next task │  │ mismatch (config says X, │
     │ - Create new PR  │  │ but input says Y)        │
     └──────────────────┘  └──────────────────────────┘
```

## Phases

- [x] Phase 1: Read configuration from local filesystem (post-checkout)

**Goal**: After checkout, read project configuration from local filesystem instead of fetching via GitHub API.

**Current behavior** (in `prepare.py`):
- Fetches configuration.yml via GitHub API using `get_file_from_branch()`
- This requires knowing the base branch upfront and makes an API call

**New behavior**:
- After checkout (which happens in action.yml), read configuration from disk
- Path: `claude-chain/{project}/configuration.yml`
- Parse configuration and extract `baseBranch` if present

**Existing APIs to leverage**:
- `Project` domain model - has `config_path`, `spec_path` properties
- `ProjectConfiguration.from_yaml_string(project, yaml_content)` - parses YAML config
- `ProjectConfiguration.default(project)` - creates default config when no file exists
- `ProjectConfiguration.get_base_branch(default_base_branch)` - resolves base branch with fallback

**Changes to `src/claudechain/infrastructure/repositories/project_repository.py`**:
- Add `load_local_configuration(project: Project) -> ProjectConfiguration`
- Read from `project.config_path` on disk
- If file doesn't exist, return `ProjectConfiguration.default(project)`
- Reuse existing `ProjectConfiguration.from_yaml_string()` for parsing

**Changes to `src/claudechain/cli/commands/prepare.py`**:
- Replace GitHub API fetch with call to `project_repository.load_local_configuration()`

**Why this first**:
- Smallest change with clear boundaries
- No workflow trigger changes yet
- Existing tests can verify behavior doesn't regress
- Foundation for subsequent phases that need local config

---

- [x] Phase 2: Validate base branch matches merge target

**Goal**: Before executing, verify that the merge target branch matches the project's expected base branch.

**Logic**:
1. From PR merge event: extract `base_ref` (the branch PR merged INTO)
2. From local config (Phase 1): extract `baseBranch` (or use `default_base_branch` input, or fallback to "main")
3. Compare: if they don't match, skip with clear message

**Changes to `src/claudechain/cli/commands/prepare.py`**:
- After loading local config, compare resolved base branch with actual merge target
- Output clear skip reason if mismatch: "Project {name} expects base branch '{expected}' but PR merged into '{actual}'"

**Error cases**:
- Config says `baseBranch: develop` but PR merged into `main` → SKIP
- Config says `baseBranch: main` and PR merged into `main` → EXECUTE
- Config has no `baseBranch`, default is `main`, PR merged into `main` → EXECUTE
- Config has no `baseBranch`, default is `main`, PR merged into `feature` → SKIP

---

- [x] Phase 3: Update workflow triggers to use changed files

**Goal**: Trigger on any PR merge that changes files in `claude-chain/` directory, regardless of labels or branch naming.

**New function: `detect_projects_from_merge(changed_files: List[str]) -> List[Project]`**

This focused function:
- Takes list of changed file paths from the merge
- Filters to files matching `claude-chain/*/spec.md` pattern
- Returns list of `Project` domain objects
- Caller can then use `project_repository.load_local_configuration(project)` to get config
- Caller can then use `config.get_base_branch(default)` to resolve base branch

**Location**: `src/claudechain/services/core/project_service.py` (or new module)

**Signature**:
```python
def detect_projects_from_merge(changed_files: List[str]) -> List[Project]:
    """Detect projects from changed files in a merge.

    Args:
        changed_files: List of file paths that changed in the merge

    Returns:
        List of Project objects for projects with changed spec.md files
    """
```

**Changes to `.github/workflows/claudechain.yml`** (this repo):
- Remove `branches:` filter (currently restricts to `main`, `main-e2e`)
- Keep `paths: ['claude-chain/**']` filter
- Remove label requirement from `should_skip()` for PR merge events

**Changes to `/Users/bill/Developer/personal/claude-chain-demo/.github/workflows/`** (demo repo):
- Update workflow to match changes in this repo
- This serves as the example workflow for users adopting ClaudeChain

**Changes to `src/claudechain/domain/github_event.py`**:
- Modify `should_skip()` to NOT require labels for `pull_request` events when triggered by spec file changes
- Label check should only apply when explicitly requested

**Changes to `src/claudechain/cli/commands/parse_event.py`**:
- Call `detect_projects_from_merge(changed_files)` to get `List[Project]`
- For each project, load config and resolve base branch
- Branch name pattern matching (`BranchInfo.from_branch_name`) becomes fallback only

**Key behavior**:
- Initial spec merge: User creates PR with spec.md, merges it, workflow triggers and detects project from changed files
- Subsequent merges: System-created PRs merge, workflow triggers same way

---

- [x] Phase 4: Support multiple projects in single PR

**Goal**: When a PR modifies specs for multiple projects, the action should process each project sequentially.

**Current limitation**: `detect_project_from_diff()` in `operations.py` raises `ValueError` if multiple projects are detected.

**New behavior**:
- Detect ALL projects with changed spec files
- For each project: validate base branch, prepare, execute Claude, finalize
- Process sequentially within a single action invocation
- Users call the action once; it handles multiple projects automatically

### Constraint

**GitHub Actions `uses:` steps cannot be called dynamically or in a loop.** This means we cannot call `anthropics/claude-code-action@v1` multiple times from within a single composite action run. The action processes ONE project per invocation.

### Implementation: Single Project + Detection Output

**Default behavior**:
- Detect all projects with changed spec files
- Process the first project (alphabetically)
- Log warning about additional projects
- Output full list for advanced users who want parallel processing

**Changes to `parse_event.py`**:
```python
# Detect all projects
projects = ProjectService.detect_projects_from_merge(changed_files)

if len(projects) > 1:
    print(f"::warning::Multiple projects detected: {[p.name for p in projects]}. "
          f"Processing '{projects[0].name}'. Others require separate workflow runs.")

# Output all detected projects as JSON for matrix workflows
print(f"detected_projects={json.dumps([{'name': p.name, 'base_branch': ...} for p in projects])}")

# Continue with first project
project = projects[0]
```

**New output in `action.yml`**:
```yaml
outputs:
  detected_projects:
    description: 'JSON array of all detected projects (for matrix workflows)'
    value: ${{ steps.parse.outputs.detected_projects }}
```

**Example advanced workflow for parallel multi-project**:
```yaml
jobs:
  detect:
    runs-on: ubuntu-latest
    outputs:
      projects: ${{ steps.cc.outputs.detected_projects }}
      first_skipped: ${{ steps.cc.outputs.skipped }}
    steps:
      - uses: gestrich/claude-chain@main
        id: cc
        with:
          github_event: ${{ toJSON(github.event) }}
          event_name: ${{ github.event_name }}
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}

  # Run remaining projects in parallel (if any beyond the first)
  execute-additional:
    needs: detect
    if: needs.detect.outputs.projects != '[]' && length(fromJSON(needs.detect.outputs.projects)) > 1
    strategy:
      matrix:
        # Skip first project (already processed above)
        project: ${{ fromJSON(needs.detect.outputs.projects)[1:] }}
      fail-fast: false
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gestrich/claude-chain@main
        with:
          project_name: ${{ matrix.project.name }}
          default_base_branch: ${{ matrix.project.base_branch }}
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Changes Required

| File | Change |
|------|--------|
| `parse_event.py` | Detect all projects, warn if multiple, output JSON list |
| `action.yml` | Add `detected_projects` output |
| `README.md` | Document single-project default, add advanced multi-project example |

### Behavior Summary

| Scenario | Behavior |
|----------|----------|
| Single project changed | Process normally |
| Multiple projects changed | Process first, warn about others, output full list |
| User wants parallel | Use matrix workflow with `detected_projects` output |

---

- [x] Phase 5: Add base_branch input for workflow_dispatch

**Goal**: For manual workflow triggers, require both `project_name` AND `base_branch` inputs, with strict validation.

**Key principle**: We do NOT trust the user's branch selection. The workflow must validate that the selected branch matches the project's configured base branch and throw an error if mismatched.

**Changes to `.github/workflows/claudechain.yml`**:
```yaml
workflow_dispatch:
  inputs:
    project_name:
      description: 'Project name (folder under claude-chain/)'
      required: true
      type: string
    base_branch:
      description: 'Base branch where spec file lives'
      required: true
      type: string
      default: 'main'
```

**Changes to `action.yml`**:
- Ensure `base_branch` input flows through to parse-event and prepare steps

**Changes to `parse_event.py`**:
- For `workflow_dispatch`: use provided `base_branch` input directly
- Validate project exists on that branch after checkout
- **CRITICAL**: Validate config's `baseBranch` (if set) matches input - throw ERROR (not skip) if mismatched

**Validation behavior for workflow_dispatch** (different from PR merge):
- PR merge events: SKIP silently if base branch mismatch (the PR just merged to a different branch)
- workflow_dispatch events: ERROR if base branch mismatch (user explicitly chose wrong branch, this is a configuration error)

**Error case examples**:
- User selects `feature` branch but config says `baseBranch: main` → ERROR: "Base branch mismatch: project '{name}' expects 'main' but workflow was triggered on 'feature'"
- User selects `main` branch and config says `baseBranch: main` → EXECUTE
- User selects `main` branch and config has no `baseBranch` → EXECUTE (default matches)

---

- [x] Phase 6: Add label to merged PR on successful execution

**Goal**: When workflow executes successfully for a merged PR, add the `claudechain` label to that PR.

**Purpose**:
- Helps with statistics queries (find all ClaudeChain-related PRs)
- Provides visual indicator that PR was processed
- Makes it easy to find initial spec PRs

**Implementation**:
- After successful task detection in `prepare.py`, add label to the merged PR
- Use `gh pr edit {pr_number} --add-label {label}` or GitHub API
- Only add if not already present

**Changes to `src/claudechain/cli/commands/prepare.py`**:
- Accept `merged_pr_number` parameter
- After successful preparation, add label to merged PR

---

- [x] Phase 7: Update statistics to work with new trigger model

**Goal**: Ensure statistics can find all ClaudeChain projects across branches, including projects with non-main base branches.

### Key Insight: PR Contains Base Branch Info

When a PR is merged, the GitHub API response includes the **base branch** it was merged into (`baseRefName`). Since Phase 6 adds the `claudechain` label to merged PRs, we can:

1. Query all PRs with `claudechain` label (current behavior)
2. Extract the base branch from each PR's `baseRefName` field
3. Load spec/config from that specific branch via GitHub API (existing code)

**This is simpler than a config-based approach** because:
- The PR itself tells us which branch to query - no guessing
- We already have code for fetching spec/config via GitHub API
- Label-based discovery already works
- No two-pass loading needed

### Implementation Plan

**Changes to `GitHubPullRequest` model** (`github_models.py`):
```python
@dataclass
class GitHubPullRequest:
    # ... existing fields ...
    base_ref_name: Optional[str] = None  # Branch PR was merged into

    @classmethod
    def from_dict(cls, data: dict) -> 'GitHubPullRequest':
        # ... existing parsing ...
        base_ref_name = data.get("baseRefName")
        # ...
```

**Changes to `list_pull_requests()`** (`operations.py`):
- Add `baseRefName` to the `--json` fields list

**Changes to `PRService.get_unique_projects()`**:
- Return `Dict[str, str]` (project_name -> base_branch) instead of `Set[str]`
- Extract base branch from each PR

```python
def get_unique_projects(self, label: str = "claudechain") -> Dict[str, str]:
    """Extract unique project names and their base branches from labeled PRs."""
    all_prs = self.get_all_prs(label=label)
    projects: Dict[str, str] = {}  # project_name -> base_branch

    for pr in all_prs:
        if pr.head_ref_name and pr.base_ref_name:
            parsed = self.parse_branch_name(pr.head_ref_name)
            if parsed:
                # Use the base branch from the PR
                # If multiple PRs for same project, any should work (same base)
                projects[parsed.project_name] = pr.base_ref_name

    return projects
```

**Changes to `StatisticsService.collect_all_statistics()`**:
```python
def collect_all_statistics(self, ...):
    # Get projects with their base branches
    project_branches = self.pr_service.get_unique_projects(label=label)

    for project_name, base_branch in project_branches.items():
        # Load config and spec from the project's actual base branch
        config = self._load_project_config(project_name, base_branch)
        # ... rest of collection using base_branch ...
```

### Dependency on Phase 6

This approach depends on Phase 6 (labeling merged PRs) being complete:
- Without labels, we can't discover projects
- Initial spec PRs get labeled when they trigger ClaudeChain
- All subsequent PRs already get labeled (existing behavior)

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| PR merged to `develop`, labeled | Load spec from `develop` |
| PR merged to `main`, labeled | Load spec from `main` (current behavior) |
| Multiple PRs for same project on different branches | Use most recent PR's base branch |
| Unlabeled PR (pre-Phase 6) | Not discovered (acceptable during transition) |

### Files to Modify

| File | Change |
|------|--------|
| `src/claudechain/domain/github_models.py` | Add `base_ref_name` field to `GitHubPullRequest` |
| `src/claudechain/infrastructure/github/operations.py` | Add `baseRefName` to PR query fields |
| `src/claudechain/services/core/pr_service.py` | Update `get_unique_projects()` return type |
| `src/claudechain/services/composite/statistics_service.py` | Use per-project base branch |
| `tests/unit/services/core/test_pr_service.py` | Update tests for new return type |
| `tests/unit/services/composite/test_statistics_service.py` | Tests for multi-branch scenarios |

### Testing

**Unit tests**:
- `GitHubPullRequest.from_dict()` parses `baseRefName`
- `PRService.get_unique_projects()` returns project->branch mapping
- `StatisticsService` loads specs from correct branches

**Integration tests**:
- Multi-project scenario with different base branches
- Verify stats report includes projects from multiple branches

---

- [ ] Phase 8: Update documentation

**Goal**: Update all documentation to reflect the new trigger and base branch behavior.

**Documentation to update**:

1. **README.md** - Update workflow setup instructions:
   - Remove mention of branch filters
   - Explain changed-files-based triggering
   - Document `base_branch` input for workflow_dispatch

2. **docs/feature-guides/** - Update user-facing guides:
   - How triggering works (changed files, not labels for initial PR)
   - Base branch configuration and validation
   - Manual workflow trigger with project + base_branch

3. **docs/feature-architecture/** - Update technical docs:
   - New `detect_projects_from_merge()` function
   - Local config loading vs API fetch
   - Base branch validation flow

4. **claude-chain-demo README** - Update demo repo documentation to match

**Key concepts to document**:
- Initial spec merge triggers automatically (no label needed)
- Base branch is validated against config before execution
- Multiple projects in single PR are supported
- Manual trigger requires both project_name and base_branch

**Statistics/Notifications documentation note**:
- Document that project discovery for statistics relies on PR branch names matching the `claude-chain-{project}-{hash}` pattern
- This means statistics only discover projects after ClaudeChain creates the first task PR
- The initial spec PR (manually created) won't appear in multi-project discovery since its branch name doesn't follow the pattern
- Single-project mode (via `config_path`) bypasses this and works for any project

---

- [ ] Phase 9: Validation (each phase)

**Unit tests**:
- `test_parse_event.py`: Test project detection from changed files
- `test_parse_event.py`: Test base branch validation logic
- `test_parse_event.py`: Test multiple project detection
- `test_github_event.py`: Test `should_skip()` without label requirement for PR merges
- `test_project_configuration.py`: Test local config loading

**Integration tests**:
- Test full flow: PR merge with changed spec → project detection → base branch validation → execution
- Test workflow_dispatch with project + base_branch inputs
- Test skip cases: base branch mismatch, no spec changes, etc.

**Manual verification**:
- Create test PR that adds new spec to non-main branch
- Verify workflow triggers and validates correctly
- Test workflow_dispatch with explicit inputs

---

## Alternative Considered: Label-Based Triggering

An alternative approach was considered where all triggering would be based on the `claudechain` label:

**Pros**:
- Simple query model (all related PRs have the label)
- User can manually trigger by adding label to any merged PR
- Clear visual indicator of processed PRs

**Cons**:
- Initial spec PR wouldn't have label until user adds it manually
- Requires user action for first trigger (not fully automatic)
- Label addition to merged PR might not trigger workflow (GitHub limitation)

**Decision**: Proceed with changed-files approach for automatic triggering, but still add labels for query/statistics purposes (Phase 6).

---

## Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `src/claudechain/infrastructure/repositories/project_repository.py` | 1 | Add `load_local_configuration(project) -> ProjectConfiguration` |
| `src/claudechain/cli/commands/prepare.py` | 1, 2, 6 | Use local config, base branch validation, label addition |
| `src/claudechain/services/core/project_service.py` | 3 | Add `detect_projects_from_merge(changed_files) -> List[Project]` |
| `.github/workflows/claudechain.yml` | 3, 5 | Remove branch filter, add base_branch input for workflow_dispatch |
| `claude-chain-demo/.github/workflows/` | 3, 5 | Update demo repo workflow to match (separate repo) |
| `src/claudechain/domain/github_event.py` | 3 | Update `should_skip()` label logic |
| `src/claudechain/cli/commands/parse_event.py` | 3, 4 | Use `detect_projects_from_merge()`, multi-project support |
| `action.yml` | 5 | Ensure base_branch input flows through |
| `README.md` | 8 | Update workflow setup instructions |
| `docs/feature-guides/` | 8 | Update user-facing trigger/base branch guides |
| `docs/feature-architecture/` | 8 | Update technical architecture docs |
| `claude-chain-demo/README.md` | 8 | Update demo repo documentation (separate repo) |
| `tests/unit/domain/test_github_event.py` | 3 | Tests for updated skip logic |
| `tests/unit/services/test_project_service.py` | 3 | Tests for `detect_projects_from_merge()` |
| `tests/integration/cli/commands/test_parse_event.py` | 3, 4 | Tests for changed files detection |
| `tests/integration/cli/commands/test_prepare.py` | 1, 2 | Tests for local config, base branch validation |
