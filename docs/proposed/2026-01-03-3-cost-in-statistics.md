# Cost Data in Statistics Reports

## Background

ClaudeStep currently calculates and displays cost information when PRs are created (in PR comments, Slack notifications, and workflow summaries), but this cost data does **not** appear in statistics reports. The statistics command shows a "Cost" column that always displays "-".

**Current State:**
- Cost is calculated using `CostBreakdown.from_execution_files()` during PR creation
- Cost is displayed in PR comments with full per-model breakdown
- The `TaskMetadata` model in `domain/models.py` already supports cost tracking via `AITask` list
- `action.yml` has artifact upload infrastructure (lines 342-349) but `finalize.py` outputs empty `artifact_path`
- Statistics has a "Cost" column but `total_cost_usd` is hardcoded to `0.0`

**Key Finding:**
The `TaskMetadata` model already exists with full cost support:
```python
@dataclass
class TaskMetadata:
    # ... core fields ...
    ai_tasks: List[AITask]  # Contains cost per operation

@dataclass
class AITask:
    type: str  # "PRCreation", "PRSummary", etc.
    model: str
    cost_usd: float
    tokens_input: int
    tokens_output: int
    # ...
```

The artifact upload step exists in `action.yml` but is never triggered because `finalize.py` always outputs empty strings for `artifact_path` and `artifact_name`.

**Goal:**
1. Create and upload `TaskMetadata` artifact when PR is created
2. Download artifacts during statistics collection and aggregate costs
3. Display aggregated cost in Slack output and GitHub workflow summary

## Phases

- [ ] Phase 1: Create TaskMetadata Artifact in Finalize

Modify `finalize.py` to create a JSON artifact file with `TaskMetadata`:

**Tasks:**
1. After PR is created, build a `TaskMetadata` instance with:
   - Core fields: `task_index`, `task_description`, `project`, `branch_name`, `reviewer`, `pr_number`, etc.
   - Cost data: Create `AITask` entries from `CostBreakdown` data (main task + PR summary)
2. Write `TaskMetadata.to_dict()` to a JSON file (e.g., `/tmp/task-metadata-{project}-{task_hash}.json`)
3. Output `artifact_path` and `artifact_name` so the existing `action.yml` upload step triggers
4. Use the existing `domain.models.TaskMetadata` class (not the duplicate in `artifact_service.py`)

**Files to modify:**
- `src/claudestep/cli/commands/finalize.py`

**Artifact naming convention:**
- Name: `task-metadata-{project}-{task_hash}`
- File: `task-metadata-{project}-{task_hash}.json`

**Data structure:**
```json
{
  "task_index": 1,
  "task_description": "Add user authentication",
  "project": "auth-refactor",
  "branch_name": "claude-step-auth-refactor-a3f2b891",
  "reviewer": "alice",
  "created_at": "2026-01-03T10:30:00+00:00",
  "workflow_run_id": 12345678,
  "pr_number": 42,
  "pr_state": "open",
  "ai_tasks": [
    {
      "type": "PRCreation",
      "model": "claude-sonnet-4-5",
      "cost_usd": 0.15,
      "created_at": "2026-01-03T10:25:00+00:00",
      "tokens_input": 5000,
      "tokens_output": 2000,
      "duration_seconds": 45.2
    },
    {
      "type": "PRSummary",
      "model": "claude-sonnet-4-5",
      "cost_usd": 0.02,
      "created_at": "2026-01-03T10:28:00+00:00",
      "tokens_input": 1000,
      "tokens_output": 500,
      "duration_seconds": 8.1
    }
  ],
  "total_cost_usd": 0.17,
  "model": "claude-sonnet-4-5"
}
```

- [ ] Phase 2: Retrieve Artifacts in Statistics Service

Add artifact download and cost aggregation to `StatisticsService`:

**Tasks:**
1. Use existing `find_project_artifacts()` from `artifact_service.py` to discover artifacts
2. Download artifact JSON for each PR using `get_artifact_metadata()`
3. Parse JSON using `TaskMetadata.from_dict()` (from `domain.models`)
4. Sum `get_total_cost()` across all PRs in the project
5. Populate `stats.total_cost_usd` with the aggregated value

**Files to modify:**
- `src/claudestep/services/composite/statistics_service.py`

**Considerations:**
- Handle missing artifacts gracefully (legacy PRs won't have them)
- Rate limiting: Artifact API calls may hit limits for large projects
- Time window: Only count costs for PRs within the `days_back` period

- [ ] Phase 3: Verify Statistics Display

Ensure cost displays correctly in all statistics output formats:

**Tasks:**
1. Verify Slack message table shows cost (column already exists, just needs data)
2. Verify GitHub step summary shows cost
3. Handle edge cases: no artifacts found, parsing errors, API failures
4. Format cost consistently using existing `format_usd()` helper

**Files to check:**
- `src/claudestep/services/composite/statistics_service.py` (display logic)

**Expected output:**
```
*📊 Project Progress*
┌──────────────────┬──────┬────────┬───────┬─────────────────┬────────┬────────┐
│ Project          │ Open │ Merged │ Total │ Progress        │ Cost   │ Status │
├──────────────────┼──────┼────────┼───────┼─────────────────┼────────┼────────┤
│ auth-migration   │    1 │      4 │    10 │ ████░░░░░░  40% │ $0.45  │        │
│ api-cleanup      │    2 │      8 │    15 │ █████░░░░░  53% │ $1.23  │        │
└──────────────────┴──────┴────────┴───────┴─────────────────┴────────┴────────┘
```

- [ ] Phase 4: Add Unit Tests

Add tests for the new artifact creation and cost retrieval:

**Tasks:**
1. Test `TaskMetadata` creation with `AITask` list in finalize
2. Test artifact JSON serialization/deserialization roundtrip
3. Test cost aggregation across multiple artifacts
4. Test handling of missing/invalid artifacts (legacy PRs)
5. Test formatting of aggregated costs in statistics output

**Files to create/modify:**
- `tests/unit/cli/commands/test_finalize.py`
- `tests/unit/services/composite/test_statistics_service.py`

**Test scenarios:**
- Finalize creates valid artifact JSON with cost data
- Statistics aggregates costs from 3 PRs correctly
- Statistics handles PRs without artifacts (shows partial total)
- Statistics handles artifact download failures gracefully

- [ ] Phase 5: Validation

**Automated Testing:**
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/cli/commands/test_finalize.py -v
pytest tests/unit/services/composite/test_statistics_service.py -v
pytest tests/unit/ tests/integration/ -v
```

**Manual Verification:**
1. Run ClaudeStep on a test project to create a PR with artifact
2. Verify artifact is uploaded (check workflow run artifacts)
3. Run statistics command and verify cost appears:
   ```bash
   source .venv/bin/activate
   python -m claudestep statistics --repo "gestrich/swift-lambda-sample" --days-back 30
   ```
4. Verify Slack output format shows cost column with values
5. Verify GitHub step summary includes costs

**Success Criteria:**
- All existing tests pass
- New unit tests pass with >85% coverage on new code
- Artifacts are uploaded for new PRs
- Statistics output shows actual cost data aggregated from artifacts
- Legacy PRs without artifacts show "-" or partial totals gracefully
