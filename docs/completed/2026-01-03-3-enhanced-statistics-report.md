# Enhanced Statistics Report with Task-PR Mapping

## Background

The current `StatisticsReport` shows aggregate counts (total tasks, completed, in-progress, pending) but lacks detail about individual tasks and their associated PRs. This makes it difficult to:

1. See which specific tasks have been completed and which PRs completed them
2. Identify "orphaned" PRs - those that were merged/opened but whose corresponding task was removed from spec.md
3. Track the relationship between spec tasks and GitHub PRs

The user wants the statistics report (in both GitHub workflow summaries and Slack messages) to show:
- Each task from the spec with its status and associated PR (if any)
- Orphaned PRs that no longer have corresponding spec tasks

The key insight is that `StatisticsReport` should be the **single source of truth** for all reporting data, initialized with the detailed task/PR mappings needed for any output format.

## Phases

- [x] Phase 1: Extend Domain Models for Task-PR Mapping

Add new domain models and extend `ProjectStats` to hold detailed task-PR relationships:

**New models to add to `src/claudechain/domain/models.py`:**
- `TaskStatus` - Enum for task states: PENDING, IN_PROGRESS, COMPLETED
- `TaskWithPR` - A task from spec.md linked to its associated PR (if any):
  - `task_hash: str` - Hash from spec task
  - `description: str` - Task description
  - `status: TaskStatus`
  - `pr: Optional[GitHubPullRequest]` - Associated PR if any

**Extend `ProjectStats`:**
- Add `tasks: List[TaskWithPR]` - All tasks with their PR associations
- Add `orphaned_prs: List[GitHubPullRequest]` - PRs with no matching spec task

The `task_hash` from `SpecTask` is already computed - we need to match it against PR branch names which contain the hash (e.g., `claude-chain-project-name-a1b2c3d4`).

- [x] Phase 2: Update Statistics Service to Collect Task-PR Mappings

Modify `StatisticsService.collect_project_stats()` to:

1. Parse spec.md to get all tasks with their hashes
2. Fetch all PRs (open and merged) for the project
3. For each PR, extract the task hash from the branch name pattern `claude-chain-{project}-{hash}`
4. Match PRs to tasks by hash:
   - If task exists in spec and has matching PR: create `TaskWithPR` with status based on PR state
   - If task exists in spec with no PR: create `TaskWithPR` with PENDING status
   - If PR has no matching task in spec: add to `orphaned_prs`

**Key files to modify:**
- `src/claudechain/services/composite/statistics_service.py`
- May need to add method to `PRService` to fetch merged PRs for a project (currently only fetches open PRs)

- [x] Phase 3: Add Merged PRs Fetching to PRService

Currently `PRService.get_open_prs_for_project()` only returns open PRs. We need to also fetch merged PRs to:
- Count how many tasks are completed
- Identify orphaned merged PRs

Add new method to `src/claudechain/services/core/pr_service.py`:
- `get_merged_prs_for_project(project_name: str, label: str, days_back: int) -> List[GitHubPullRequest]`

This will use the GitHub API to fetch recently merged PRs with the claudechain label for the project.

- [x] Phase 4: Update Report Formatting for Detailed Task View

Added `format_project_details(for_slack: bool = False) -> str` method to `StatisticsReport` in `src/claudechain/domain/models.py`.

Output format:
```
## print-line-count (5/20 complete)

### Tasks
- [x] `echo "Hello World!"` - PR #31 (Merged)
- [ ] `echo "Hello World!!"` - PR #32 (Open, 2d)
- [ ] `echo "Hello World!!!"` - (no PR)
...

### Orphaned PRs
- PR #25 (Merged) - Task removed from spec
- PR #28 (Open, 5d) - Task removed from spec
```

**TODO:** Update GitHub Step Summary in `statistics.py` CLI command to include this detailed view.

- [x] Phase 5: Update Slack Report Format

Implemented actionable "Needs Attention" section in Slack with clickable PR links:

**Changes made:**
- Added `url` field to `GitHubPullRequest` model and fetch from GitHub API
- Rewrote `_format_warnings_section()` to show all open PRs needing action:
  - Clickable links using Slack mrkdwn: `<url|#123>`
  - Days open, assignee, and stale indicator for each PR
  - Open orphaned PRs labeled with "orphaned"
  - "No open PRs" warning when tasks remain
- Updated `projects_needing_attention()` to only consider **open** orphaned PRs (merged ones don't need action)
- Updated Slack footer to "See details in" (points to workflow report for full details)

**Output format:**
```
*⚠️ Needs Attention*
*my-project*
• <https://github.com/.../pull/123|#123> (10d, alice, stale)
• <https://github.com/.../pull/124|#124> (3d, unassigned)
• <https://github.com/.../pull/99|#99> (5d, orphaned)
• No open PRs (17 tasks remaining)
```

- [ ] Phase 6: Validation

**Unit Tests (DONE):**
- [x] Test `TaskWithPR` model creation and status determination
- [x] Test task-PR matching logic (by hash) - `TestTaskPRMappings` class (7 tests)
- [x] Test orphaned PR detection
- [x] Test formatting of detailed task view - `TestFormatProjectDetails` class (7 tests)

**Integration Tests:**
- Run statistics against swift-lambda-sample to verify:
  - Tasks are correctly matched to PRs
  - The orphaned PR (from removed spec task) is detected
  - Output format is readable

**Manual Verification:**
- Trigger statistics workflow on swift-lambda-sample
- Verify GitHub Step Summary shows detailed task list
- Verify orphaned PRs are identified

Run: `python3 -m pytest tests/unit/services/composite/test_statistics_service.py -v`
