## Background

The `StatisticsReport` class in [models.py](src/claudestep/domain/models.py) currently mixes data representation with formatting logic. It has multiple `format_*` methods that handle both Slack (`mrkdwn`) and GitHub markdown formats using a `for_slack: bool` flag pattern. This creates:

1. **Tight coupling** - The report class knows about rendering details for multiple output formats
2. **Code duplication** - Similar formatting logic appears in multiple places with conditional branching
3. **Difficult testing** - Testing format variations requires going through the full StatisticsReport class
4. **Hard to extend** - Adding a new format (e.g., plain text, HTML) requires modifying the domain model

The proposed refactoring separates concerns:
- **Report data elements** - Abstract representations (tables, lists, headers, text blocks) that describe *what* to show
- **Report formatters** - Classes that know *how* to render elements for a specific output format (Slack, Markdown)

This follows the existing pattern where `TableFormatter` already abstracts table rendering.

## Phases

- [x] Phase 1: Define report element types

Create data classes in `src/claudestep/domain/formatters/report_elements.py` to represent abstract report components:
- `Header` - title text with level (h1, h2, h3)
- `Table` - headers, rows, column alignments (leverage existing `TableFormatter`)
- `TextBlock` - plain or styled text (bold, italic, code)
- `List` - bullet/numbered list items
- `Link` - text with URL
- `Section` - container grouping elements with optional header
- `ProgressBar` - visual progress indicator with percentage

These are pure data classes with no formatting logic. They represent the semantic structure of what we want to display.

- [x] Phase 2: Create StatisticsReportData class

Create `src/claudestep/domain/statistics_report_data.py` with a new class that builds report elements:
- Extract current data-building logic from `StatisticsReport.format_for_slack()` and related methods
- Return structured `Section`/`Table`/`List` elements instead of formatted strings
- Methods like `build_leaderboard_section()`, `build_project_progress_section()`, `build_warnings_section()`
- Keep `StatisticsReport` as the data container, add methods to produce elements

Key insight: Don't over-engineer. The `StatisticsReport` class should get new methods that return element structures (e.g., `to_leaderboard_elements()`, `to_project_progress_elements()`). These methods replace the current `format_*` methods' data-gathering logic.

- [ ] Phase 3: Create ReportFormatter base and implementations

Create formatters in `src/claudestep/domain/formatters/`:
- `report_formatter.py` - Base `ReportFormatter` class with abstract methods for each element type
- `slack_formatter.py` - `SlackReportFormatter` implementation using Slack mrkdwn syntax
- `markdown_formatter.py` - `MarkdownReportFormatter` implementation using GitHub-flavored markdown

Each formatter takes report elements and produces a string. The existing `MarkdownFormatter` helper class in models.py can be refactored into these formatters.

- [ ] Phase 4: Refactor StatisticsReport to use new system

Update `StatisticsReport` in [models.py](src/claudestep/domain/models.py):
- Replace `format_for_slack()` with element-building methods
- Replace `format_leaderboard()`, `format_warnings_section()`, `format_project_details()` similarly
- Create thin wrapper methods that use formatters for backward compatibility if needed
- Remove `MarkdownFormatter` helper class (logic moves to formatters)
- Keep `format_for_pr_comment()` and `to_json()` as they serve different purposes

Files to modify:
- `src/claudestep/domain/models.py` - Refactor StatisticsReport
- `src/claudestep/cli/commands/statistics.py` - Update to use new formatter pattern

- [ ] Phase 5: Validation

Run full test suite to ensure no regressions:
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v --cov=src/claudestep --cov-report=term-missing
```

Verify:
- All existing tests pass
- Slack output format unchanged (compare output strings)
- GitHub markdown output format unchanged
- New formatter classes have unit tests
- Coverage remains above 85%
