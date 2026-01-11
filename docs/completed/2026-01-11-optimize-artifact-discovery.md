# Optimize Artifact Discovery

## Background

The statistics action shows `$0.00` cost on busy repos like ff-ios because the current artifact discovery fails to find ClaudeChain artifacts when they get pushed out of the "top 50 workflow runs" window.

### How It Currently Works

The current implementation in `find_project_artifacts()` (`src/claudechain/services/composite/artifact_service.py`):

```
1. Query PRs with claudechain label → get_project_prs(project, state, label)
2. Query top N workflow runs from ENTIRE repo → /repos/{repo}/actions/runs?status=completed&per_page=50
3. For each successful run, get its artifacts → /repos/{repo}/actions/runs/{run_id}/artifacts
4. Filter artifacts by project name prefix → task-metadata-{project}-*
5. Optionally download metadata JSON
```

**The problem is step 2**: It queries the most recent workflow runs from the **entire repository**, not filtered by workflow type or PR. The PR query in step 1 is essentially unused - it prints info but doesn't influence which workflow runs are checked.

On busy repos with frequent CI (builds, tests, linting), ClaudeChain's workflow runs get pushed out of the top 50 within minutes. For ff-ios:
- ClaudeChain run created at 16:05:10
- Oldest run in top 50 was from 16:14:48 (~9 minutes later)
- By the time statistics ran at 17:40, the ClaudeChain runs were long gone from the top 50

### Parameters Currently Passed But Not Effective

- `label`: Used to query PRs, but PR results don't filter workflow runs
- `pr_state`: Same - used for PR query but doesn't affect artifact discovery
- `limit`: Controls how many workflow runs to check (default 50), but these are ALL runs, not ClaudeChain-specific

## Proposed Solutions

### Option A: Query Artifacts API Directly

Query all artifacts and filter by name prefix:

```
1. Query artifacts API → /repos/{repo}/actions/artifacts?per_page=100
2. Filter by name prefix → task-metadata-{project}-*
3. Paginate until we have enough matches
```

**Pros:**
- Simple implementation
- Artifacts sorted newest-first
- Works regardless of workflow run volume

**Cons:**
- Scans ALL artifacts in repo (including build logs, test results, etc.)
- On repos with many artifact-producing workflows, may need many pages

### Option B: Query Workflow Runs by Workflow Name

Query only Claude Chain workflow runs using the workflow-specific API:

```
1. Query workflow runs for specific workflow → /repos/{repo}/actions/workflows/{workflow_name}/runs
2. For each run, get artifacts → /repos/{repo}/actions/runs/{run_id}/artifacts
3. Filter by project name
```

**Pros:**
- Only queries Claude Chain workflow runs (skips all other CI)
- More targeted than Option A
- Fewer irrelevant API responses to process

**Cons:**
- Requires knowing workflow name
- Statistics workflow is separate from PR-creating workflow, so can't use `github.workflow`

### Option C: Hybrid - Use Label to Find PRs, Then Trace to Artifacts

```
1. Query PRs with claudechain label
2. For each PR, get head_sha
3. Query workflow runs by commit → /repos/{repo}/actions/runs?head_sha={sha}
4. Get artifacts from those runs
```

**Cons:**
- Artifacts are created DURING the prepare step, BEFORE the PR exists
- head_sha mapping won't work because the workflow run creates the PR
- Complex and likely broken

## Decision

**Option B: Query Workflow Runs by Workflow Name** with workflow name as a required input parameter.

The statistics action is separate from the PR-creating workflow, so we can't use `github.workflow`. Instead, the user provides the workflow name as a required input.

## Phases

- [x] Phase 1: Add `workflow_name` input to statistics action

Update `statistics/action.yml` to add a new required input:

```yaml
inputs:
  workflow_name:
    description: 'Name of the workflow that creates PRs (from the workflow name: property in your claude-chain.yml)'
    required: true
```

User configuration example:
```yaml
- uses: gestrich/claude-chain/statistics@main
  with:
    workflow_name: "Claude Chain"  # Must match the name: property in their PR-creating workflow
```

The statistics command in `__main__.py` will read this from environment and pass it explicitly to the command function (following the "Configuration flows from entry point" principle from python-style.md).

- [x] Phase 2: Update artifact_service.py to use workflow name

Following the Service Layer pattern, update `find_project_artifacts()` in `src/claudechain/services/composite/artifact_service.py`:

**Function signature change:**
```python
def find_project_artifacts(
    repo: str,
    project: str,
    workflow_name: str,  # NEW: Required - name of workflow to query
    limit: int = 50,
    download_metadata: bool = False,
) -> List[ProjectArtifact]:
```

**Algorithm change:**
```python
# OLD: Query all workflow runs (broken on busy repos)
api_response = gh_api_call(f"/repos/{repo}/actions/runs?status=completed&per_page={limit}")

# NEW: Query only the specific workflow's runs
workflow_name_encoded = urllib.parse.quote(workflow_name)
api_response = gh_api_call(
    f"/repos/{repo}/actions/workflows/{workflow_name_encoded}/runs?status=completed&per_page={limit}"
)
```

**Remove unused parameters:**
- Remove `label` parameter (was used for PR query that didn't affect artifact discovery)
- Remove `pr_state` parameter (same reason)
- Remove `PRService` import and usage (no longer needed)

**Update dependent functions:**
- `find_in_progress_tasks()` - add `workflow_name` parameter
- `get_assignee_assignments()` - add `workflow_name` parameter

- [x] Phase 3: Update statistics_service.py

Update `StatisticsService._get_costs_by_pr()` in `src/claudechain/services/composite/statistics_service.py`:

**Add workflow_name to constructor** (following dependency injection pattern):
```python
class StatisticsService:
    def __init__(
        self,
        repo: str,
        project_repository: ProjectRepository,
        pr_service: PRService,
        workflow_name: str,  # NEW
    ):
        self.repo = repo
        self.project_repository = project_repository
        self.pr_service = pr_service
        self.workflow_name = workflow_name  # Store for use in methods
```

**Update _get_costs_by_pr():**
```python
def _get_costs_by_pr(self, project_name: str) -> Dict[int, float]:
    artifacts = find_project_artifacts(
        repo=self.repo,
        project=project_name,
        workflow_name=self.workflow_name,  # Pass stored value
        download_metadata=True,
    )
    # ... rest unchanged
```

- [x] Phase 4: Update CLI layer

Update `src/claudechain/__main__.py` to read environment variable and pass explicitly (following "Services should not read environment variables" principle):

```python
elif args.command == "statistics":
    workflow_name = os.environ.get("INPUT_WORKFLOW_NAME", "")
    if not workflow_name:
        print("Error: workflow_name input is required")
        return 1

    return cmd_statistics(
        gh=gh,
        repo=repo,
        workflow_name=workflow_name,  # Pass explicitly
        # ... other params
    )
```

Update `src/claudechain/cli/commands/statistics.py`:
```python
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    workflow_name: str,  # NEW: Required parameter
    # ... other params
) -> int:
    # Create service with workflow_name
    statistics_service = StatisticsService(
        repo=repo,
        project_repository=project_repository,
        pr_service=pr_service,
        workflow_name=workflow_name,
    )
```

- [x] Phase 5: Update tests

Following the testing philosophy (mock at boundaries, test behavior not implementation):

**Unit tests for artifact_service.py:**
- Update existing tests to pass `workflow_name` parameter
- Add test verifying correct API endpoint is called with URL-encoded workflow name
- Test edge cases: workflow name with spaces, special characters

**Unit tests for statistics_service.py:**
- Update tests to provide `workflow_name` in constructor
- Verify `workflow_name` is passed through to `find_project_artifacts()`

**Integration tests:**
- Update CLI integration tests for statistics command
- Test error case: missing `workflow_name` input

```bash
# Run tests
export PYTHONPATH=src:scripts
pytest tests/unit/services/composite/test_artifact_service.py -v
pytest tests/unit/services/composite/test_statistics_service.py -v
pytest tests/integration/cli/commands/test_statistics.py -v
```

- [x] Phase 6: Update documentation

Update README and action documentation:
- Document new required `workflow_name` input for statistics action
- Explain that this should match the `name:` property in their PR-creating workflow
- Add example configuration

- [x] Phase 7: Validation

1. Run full test suite:
   ```bash
   export PYTHONPATH=src:scripts
   pytest tests/unit/ tests/integration/ -v --cov=src/claudechain --cov-report=term-missing
   ```

2. Test against ff-ios with live data:
   - Run statistics command with `workflow_name: "Claude Chain"`
   - Verify artifacts found (should find 10+ instead of 0)
   - Verify costs calculated correctly (should show actual costs instead of $0.00)

3. Verify the workflow-specific API is being called:
   ```bash
   # Check that this endpoint returns Claude Chain runs
   gh api "/repos/jeppesen-foreflight/ff-ios/actions/workflows/Claude%20Chain/runs?per_page=5"
   ```
