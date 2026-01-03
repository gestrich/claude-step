# Statistics Improvements

## Background

The current statistics feature provides both project-level and reviewer-level (leaderboard) statistics. For V1, we're refocusing the statistics to prioritize project visibility over team metrics. The key insight is that reviewer leaderboards only provide value when multiple people are assigned to PRs, which may not be the common case initially.

The goals for this plan:
1. **Project-focused statistics** - Show project completion, open PRs, and stale indicators
2. **Actionable alerts** - Highlight projects needing attention (stale PRs, no open PRs)
3. **Reviewer leaderboard as opt-in** - Hide by default, enable via flag for teams
4. **Open PR details** - Show assignee and age for each open PR

Key existing components:
- `StatisticsService` ([services/composite/statistics_service.py](src/claudestep/services/composite/statistics_service.py)) - Collects project and team stats
- `StatisticsReport` ([domain/models.py](src/claudestep/domain/models.py)) - Domain model with formatting methods
- `ProjectStats` ([domain/models.py](src/claudestep/domain/models.py)) - Per-project statistics
- `ProjectConfiguration` ([domain/project_configuration.py](src/claudestep/domain/project_configuration.py)) - Project config schema
- `GitHubPullRequest` ([domain/github_models.py](src/claudestep/domain/github_models.py)) - PR domain model with `created_at`

## Phases

- [x] Phase 1: Add flag to disable reviewer leaderboard

Add `show_reviewer_stats` parameter to control whether reviewer statistics are shown. Default to `false` (disabled).

**Files to modify:**
- [src/claudestep/cli/commands/statistics.py](src/claudestep/cli/commands/statistics.py) - Add `--show-reviewer-stats` CLI flag
- [src/claudestep/services/composite/statistics_service.py](src/claudestep/services/composite/statistics_service.py) - Add `show_reviewer_stats` parameter to `collect_all_statistics()`
- [src/claudestep/domain/models.py](src/claudestep/domain/models.py) - Update `format_for_slack()` and `format_leaderboard()` to conditionally include leaderboard
- [statistics/action.yml](statistics/action.yml) - Add `show_reviewer_stats` input (default: `false`)

**Implementation details:**
- When `show_reviewer_stats=False`:
  - Skip team member stats collection (performance optimization)
  - Don't render leaderboard section in Slack output
  - Don't render team member section in GitHub step summary
- When `show_reviewer_stats=True`:
  - Current behavior (collect and show all stats)

**Service layer changes:**
```python
def collect_all_statistics(
    self,
    config_path: Optional[str] = None,
    days_back: int = 30,
    label: str = DEFAULT_PR_LABEL,
    show_reviewer_stats: bool = False  # New parameter
) -> StatisticsReport:
```

- [x] Phase 2: Add `stalePRDays` to project configuration

Add new configuration field to define when PRs are considered stale.

**Files to modify:**
- [src/claudestep/domain/project_configuration.py](src/claudestep/domain/project_configuration.py) - Add `stale_pr_days` field to `ProjectConfiguration`

**Implementation details:**
- Add `stale_pr_days: Optional[int] = None` field to `ProjectConfiguration`
- Parse `stalePRDays` from YAML in `from_yaml_string()`
- Add `get_stale_pr_days(default: int = 7) -> int` method
- Default to 7 days if not specified

**Schema update (configuration.yml):**
```yaml
reviewers:
  - username: alice
    maxOpenPRs: 2

# Optional: Days before a PR is considered stale (default: 7)
stalePRDays: 7
```

- [x] Phase 3: Add stale PR tracking to statistics

Extend statistics collection to identify stale PRs and include them in reports.

**Files to modify:**
- [src/claudestep/domain/models.py](src/claudestep/domain/models.py) - Add `OpenPRInfo` dataclass and update `ProjectStats`
- [src/claudestep/services/composite/statistics_service.py](src/claudestep/services/composite/statistics_service.py) - Collect open PR details with age calculation

**New domain model:**
```python
@dataclass
class OpenPRInfo:
    """Information about an open PR for statistics display"""
    pr_number: int
    title: str
    assignee: Optional[str]  # First assignee username, or None
    created_at: datetime
    days_open: int
    is_stale: bool
```

**Update ProjectStats:**
```python
class ProjectStats:
    # ... existing fields ...
    open_prs: List[OpenPRInfo] = field(default_factory=list)
    stale_pr_count: int = 0
```

**Service changes:**
- In `collect_project_stats()`, after getting open PRs:
  - Calculate days open: `(now - pr.created_at).days`
  - Determine stale status based on project's `stalePRDays` config
  - Create `OpenPRInfo` for each open PR
  - Count stale PRs

- [x] Phase 4: Add "no open PRs" warning

Alert when a project has remaining tasks but no open PRs.

**Files to modify:**
- [src/claudestep/domain/models.py](src/claudestep/domain/models.py) - Add warning tracking to `ProjectStats` and `StatisticsReport`

**Implementation details:**
- Add `has_remaining_capacity: bool` property to `ProjectStats`:
  - True if `pending_tasks > 0 and in_progress_tasks == 0`
- Add `projects_needing_attention()` method to `StatisticsReport`:
  - Returns list of projects with stale PRs OR no open PRs with remaining tasks
- Include in formatted output as warnings section

- [x] Phase 5: Update statistics output formatting

Update Slack and GitHub output to show stale indicators and warnings.

**Files to modify:**
- [src/claudestep/domain/models.py](src/claudestep/domain/models.py) - Update formatting methods

**Output changes:**

**Project Progress table - add Status column:**
```
📊 Project Progress
┌──────────────────┬──────┬────────┬───────┬─────────────────┬───────┬────────────┐
│ Project          │ Open │ Merged │ Total │ Progress        │ Cost  │ Status     │
├──────────────────┼──────┼────────┼───────┼─────────────────┼───────┼────────────┤
│ auth-migration   │    1 │      4 │    10 │ ████░░░░░░  40% │ $0.45 │            │
│ api-cleanup      │    2 │      8 │    15 │ █████░░░░░  53% │ $0.72 │ ⚠️ 1 stale │
│ docs-update      │    0 │      3 │    20 │ █░░░░░░░░░  15% │     - │ ⚠️ no PRs  │
└──────────────────┴──────┴────────┴───────┴─────────────────┴───────┴────────────┘
```

**Detailed warnings section:**
```
⚠️ Projects Needing Attention
┌──────────────────┬───────────────────────────────────────────────┐
│ Project          │ Issue                                         │
├──────────────────┼───────────────────────────────────────────────┤
│ docs-update      │ No open PRs (17 tasks remaining)              │
│ api-cleanup      │ PR #123 stale (open 12 days, assigned: alice) │
└──────────────────┴───────────────────────────────────────────────┘
```

- [x] Phase 6: Update documentation

Update user-facing documentation to reflect the changes.

**Files to update:**
- [docs/feature-guides/notifications.md](docs/feature-guides/notifications.md):
  - Update statistics section to show new output format
  - Add note about leaderboard being opt-in
  - Document `show_reviewer_stats` input
- [docs/feature-guides/projects.md](docs/feature-guides/projects.md):
  - Add `stalePRDays` to configuration.yml schema documentation
- [docs/feature-architecture/api-reference.md](docs/feature-architecture/api-reference.md):
  - Update statistics command reference

**Files to potentially remove content from:**
- Remove/minimize leaderboard examples in documentation since it's opt-in now

- [x] Phase 7: Validation

**Unit tests to add/update:**
- Test `ProjectConfiguration.stale_pr_days` parsing and default
- Test `OpenPRInfo` creation and stale calculation
- Test `ProjectStats.stale_pr_count` calculation
- Test `StatisticsReport.projects_needing_attention()`
- Test `format_for_slack()` with stale indicators
- Test `collect_all_statistics()` with `show_reviewer_stats=False`

**Integration test:**
- Run statistics against test project with known state
- Verify output includes stale warnings when appropriate
- Verify leaderboard is hidden by default

**Manual verification:**
- Run against real project, verify formatting looks correct in terminal
- Test Slack webhook output format (if webhook configured)

**Test commands:**
```bash
# Run unit tests
python3 -m pytest tests/unit/domain/test_models.py -v
python3 -m pytest tests/unit/domain/test_project_configuration.py -v
python3 -m pytest tests/unit/services/test_statistics_service.py -v

# Run statistics with different options
python -m claudestep statistics --repo "gestrich/claude-step" --format slack
python -m claudestep statistics --repo "gestrich/claude-step" --show-reviewer-stats --format slack
```
