## Background

The statistics report formatter refactoring ([2026-01-03-4-statistics-report-formatter.md](../completed/2026-01-03-4-statistics-report-formatter.md)) introduced a clean separation between report data elements and formatting logic. This pattern should also apply to other Slack and GitHub markdown outputs in ClaudeStep:

1. **PR Creation Notification** ([format_slack_notification.py](src/claudestep/cli/commands/format_slack_notification.py)) - Slack message sent when a new PR is created. Currently uses inline string building.

2. **PR Comment** ([summary_file.py](src/claudestep/domain/summary_file.py) + [cost_breakdown.py](src/claudestep/domain/cost_breakdown.py)) - GitHub markdown comment posted on PRs with AI summary and cost breakdown. Uses inline `format_for_github()` method.

3. **Workflow Summary** ([post_pr_comment.py](src/claudestep/cli/commands/post_pr_comment.py) `_write_workflow_summary()`) - GitHub Actions step summary showing cost breakdown.

These all build formatted strings directly rather than using the report element/formatter pattern.

### Proposed Design

Create a `PullRequestCreatedReport` domain model (similar to `StatisticsReport`) that:
- Holds all PR creation data (PR number, URL, project, task, cost breakdown, summary)
- Provides element-building methods for each output section
- Can be formatted for Slack (notification) or GitHub markdown (PR comment, workflow summary)

This consolidates the scattered formatting logic into one cohesive domain model.

## Phases

- [x] Phase 1: Extend report elements for PR notifications

Add any new element types needed for PR notifications to `src/claudestep/domain/formatters/report_elements.py`:
- `CodeBlock` - for inline code like project names (renders as backticks in markdown, may differ in Slack)
- `Emoji` - for platform-appropriate emoji handling (Slack uses `:emoji:` syntax vs unicode)
- Review existing elements (Header, Link, TextBlock, Table) for reuse

- [x] Phase 2: Create PullRequestCreatedReport domain model

Create `src/claudestep/domain/pr_created_report.py`:
- `PullRequestCreatedReport` dataclass with fields: `pr_number`, `pr_url`, `project_name`, `task`, `cost_breakdown`, `summary_content`, `repo`, `run_id`
- Element-building methods:
  - `build_notification_elements()` - for Slack notification (PR link, project, task, cost)
  - `build_comment_elements()` - for PR comment (summary + cost breakdown table)
  - `build_workflow_summary_elements()` - for GitHub Actions step summary
- Factory method `from_components()` to construct from existing data

- [ ] Phase 3: Refactor PR creation notification

Update `src/claudestep/cli/commands/format_slack_notification.py`:
- Use `PullRequestCreatedReport` and `SlackReportFormatter`
- Keep `format_pr_notification()` as thin wrapper for backward compatibility

- [ ] Phase 4: Refactor PR comment posting

Update `src/claudestep/cli/commands/post_pr_comment.py`:
- Use `PullRequestCreatedReport.build_comment_elements()` with `MarkdownReportFormatter`
- Use `PullRequestCreatedReport.build_workflow_summary_elements()` for step summary
- Remove `_write_workflow_summary()` helper (logic moves to domain model)

Update `src/claudestep/domain/summary_file.py`:
- Simplify to just parse file content; formatting moves to `PullRequestCreatedReport`

Update `src/claudestep/domain/cost_breakdown.py`:
- Remove `format_for_github()` and `format_model_breakdown()` (logic moves to report)
- Keep `to_json()` / `from_json()` for serialization

- [ ] Phase 5: Validation

Run full test suite to ensure no regressions:
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v --cov=src/claudestep --cov-report=term-missing
```

Verify:
- All existing tests pass
- Slack notification format unchanged (compare output strings)
- PR comment format unchanged
- Workflow summary format unchanged
- New `PullRequestCreatedReport` class has unit tests
- Coverage remains above 85%
