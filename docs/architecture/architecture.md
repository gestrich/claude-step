# ClaudeStep Architecture

This document describes the architectural decisions and conventions used in the ClaudeStep project.

## Table of Contents

- [Action Organization](#action-organization)
- [Python-First Approach](#python-first-approach)
- [Command Dispatcher Pattern](#command-dispatcher-pattern)
- [Data Flow](#data-flow)
- [Module Organization](#module-organization)

---

## Action Organization

### Convention: Multiple Actions in One Repository

ClaudeStep provides **three GitHub Actions** in a single repository:

1. **Main Action** (`action.yml`) - Core refactoring automation
2. **Discovery Action** (`discovery/action.yml`) - Project discovery
3. **Statistics Action** (`statistics/action.yml`) - Reporting and analytics

### Directory Structure

```
claude-refactor-chain/
├── action.yml                    # Main action (root for backwards compatibility)
├── discovery/
│   └── action.yml                # Discovery action
├── statistics/
│   └── action.yml                # Statistics action
└── scripts/
    └── claudestep/               # Shared Python package
```

### Naming Convention

**Rule**: Each action should be in its own directory with a standard `action.yml` filename.

- ✅ **Correct**: `statistics/action.yml`
- ❌ **Incorrect**: `statistics-action.yml` (at root level)
- ✅ **Exception**: Root `action.yml` for the primary/main action

**Rationale**:
- Standard GitHub Actions pattern for multi-action repositories
- Enables clean publishing as separate actions (e.g., `@org/repo/statistics@v1`)
- Consistent naming makes it clear where to find action definitions
- Separates concerns while sharing common code

### Usage Patterns

**Main Action** (Primary use case):
```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    project_name: 'my-refactor'
```

**Discovery Action** (Project detection):
```yaml
- uses: gestrich/claude-step/discovery@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
```

**Statistics Action** (Reporting):
```yaml
- uses: gestrich/claude-step/statistics@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}
    days_back: 7
```

### Adding New Actions

When adding new actions to this repository:

1. **Create a subdirectory** with a descriptive name (e.g., `validation/`, `metrics/`)
2. **Add `action.yml`** in that subdirectory (not `action-name.yml`)
3. **Keep Python logic** in `scripts/claudestep/` (shared codebase)
4. **Add command** to `scripts/claudestep/__main__.py` dispatcher
5. **Update this document** with the new action

**Example for a hypothetical "validate" action**:
```
validate/
└── action.yml    # Calls: python3 -m claudestep validate
```

---

## Python-First Approach

### Convention: Minimal YAML, Maximal Python

ClaudeStep follows a **Python-first architecture** where:

- **GitHub Actions YAML files** are lightweight wrappers
- **Python code** contains all business logic
- **Actions invoke Python** via `python3 -m claudestep <command>`

### Why Python-First?

**Benefits**:
1. **Testability** - Python code can be unit tested; YAML cannot
2. **Local Development** - Run and debug commands locally without GitHub Actions
3. **Code Reuse** - All actions share the same Python package
4. **Type Safety** - Python supports type hints and better error handling
5. **Maintainability** - Complex logic is easier to read and maintain in Python
6. **Flexibility** - Easy to refactor and extend without YAML limitations

**Comparison**:

❌ **YAML-heavy approach** (what we avoid):
```yaml
# action.yml - BAD: Business logic in YAML
runs:
  using: 'composite'
  steps:
    - run: |
        # 50+ lines of bash script
        # Complex conditionals
        # String manipulation
        # API calls
        # Error handling
```

✅ **Python-first approach** (what we use):
```yaml
# action.yml - GOOD: Minimal wrapper
runs:
  using: 'composite'
  steps:
    - run: python3 -m claudestep statistics
      env:
        CONFIG_PATH: ${{ inputs.config_path }}
```

### Action YAML Responsibilities

Action YAML files should **only**:

1. **Define inputs and outputs** - The action's interface
2. **Set up environment** - Install Python, set PYTHONPATH
3. **Invoke Python commands** - Call the appropriate command
4. **Pass parameters** - Map action inputs to environment variables

Action YAML files should **never**:

- ❌ Contain business logic or complex bash scripts
- ❌ Parse JSON or manipulate data structures
- ❌ Make API calls or database queries
- ❌ Implement algorithms or decision trees
- ❌ Duplicate code across multiple actions

### Example: Statistics Action

**YAML (Minimal)**:
```yaml
# statistics/action.yml
name: 'ClaudeStep Statistics'
inputs:
  days_back:
    description: 'Days to look back'
    default: '30'
outputs:
  slack_message:
    value: ${{ steps.stats.outputs.slack_message }}

runs:
  using: 'composite'
  steps:
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'

    - name: Generate statistics
      id: stats
      run: python3 -m claudestep statistics
      env:
        STATS_DAYS_BACK: ${{ inputs.days_back }}
        ACTION_PATH: ${{ github.action_path }}
```

**Python (All Logic)**:
```python
# scripts/claudestep/commands/statistics.py
def cmd_statistics(args, gh):
    """All business logic lives here"""
    days_back = int(os.environ.get("STATS_DAYS_BACK", "30"))
    report = collect_all_statistics(days_back=days_back)
    slack_text = report.format_for_slack()
    gh.write_output("slack_message", slack_text)
    # ... full implementation
```

### Testing Strategy

Because logic is in Python, we can test it:

```python
# tests/test_statistics.py
def test_progress_bar():
    stats = ProjectStats("test", "/path")
    stats.total_tasks = 10
    stats.completed_tasks = 5
    bar = stats.format_progress_bar(10)
    assert "█████░░░░░" in bar
    assert "50%" in bar
```

**Cannot test YAML**: You'd have to run the entire GitHub Action workflow to verify behavior.

---

## Command Dispatcher Pattern

### Entry Point: `__main__.py`

ClaudeStep uses a **command dispatcher** pattern with a single Python entry point:

```
python3 -m claudestep <command>
```

### Available Commands

| Command | Description | Used By |
|---------|-------------|---------|
| `discover` | List all refactor projects | Discovery action |
| `discover-ready` | List projects with capacity | Discovery action |
| `prepare` | Setup before Claude Code execution | Main action |
| `finalize` | Commit changes and create PR | Main action |
| `prepare-summary` | Generate prompt for PR summary | Main action |
| `statistics` | Generate reports and statistics | Statistics action |

### Command Structure

**Dispatcher** (`scripts/claudestep/__main__.py`):
```python
def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    parser_statistics = subparsers.add_parser("statistics")
    # ... other commands

    if args.command == "statistics":
        return cmd_statistics(args, gh)
    # ... route to other commands
```

**Command Implementation** (`scripts/claudestep/commands/statistics.py`):
```python
def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Command logic - returns exit code (0 = success)"""
    # 1. Read environment variables
    # 2. Call business logic functions
    # 3. Write outputs via GitHub Actions helper
    # 4. Return exit code
```

### Benefits of Command Dispatcher

1. **Single entry point** - Easy to understand and debug
2. **Consistent interface** - All commands have same signature
3. **Shared utilities** - GitHubActionsHelper, config loading, etc.
4. **Easy extension** - Add new commands without touching existing ones
5. **Local testing** - Run commands outside GitHub Actions:
   ```bash
   PYTHONPATH=scripts python3 -m claudestep statistics
   ```

---

## Data Flow

### Main Action Flow

```
┌─────────────────┐
│  User Workflow  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  action.yml (Composite Action)          │
│                                         │
│  1. Setup Python                        │
│  2. python3 -m claudestep prepare       │
│  3. anthropics/claude-code-action@v1    │
│  4. python3 -m claudestep finalize      │
│  5. Upload artifacts                    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Python Commands                        │
│                                         │
│  prepare:                               │
│  • Detect project                       │
│  • Load configuration                   │
│  • Check reviewer capacity              │
│  • Find next task                       │
│  • Create branch                        │
│  • Generate Claude prompt               │
│                                         │
│  finalize:                              │
│  • Commit changes                       │
│  • Mark task complete in spec.md        │
│  • Create pull request                  │
│  • Upload metadata artifact             │
│  • Generate summary                     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Outputs                                │
│                                         │
│  • pr_number, pr_url                    │
│  • reviewer, task_completed             │
│  • GitHub Step Summary                  │
│  • Artifact (task metadata JSON)        │
└─────────────────────────────────────────┘
```

### Statistics Action Flow

```
┌─────────────────┐
│  User Workflow  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  statistics/action.yml                  │
│                                         │
│  1. Setup Python                        │
│  2. python3 -m claudestep statistics    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Python Command                         │
│                                         │
│  statistics:                            │
│  • Collect project stats (spec.md)      │
│  • Collect team stats (GitHub API)      │
│  • Generate reports                     │
│  • Format for Slack                     │
│  • Output JSON data                     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Outputs → User's Slack Action          │
│                                         │
│  • slack_message (formatted text)       │
│  • statistics_json (raw data)           │
│  • has_statistics (boolean)             │
└─────────────────────────────────────────┘
```

### PR Summary Flow

The PR summary feature adds AI-generated comments to PRs explaining what was changed and why.

```
┌─────────────────────────────────────────┐
│  Main Action (after finalize)           │
│                                         │
│  1. finalize step completes             │
│     → Outputs pr_number                 │
│                                         │
│  2. prepare-summary step                │
│     → python3 -m claudestep prepare-summary
│     → Outputs summary_prompt            │
│                                         │
│  3. claude-code-action step             │
│     → Receives summary_prompt           │
│     → Runs gh pr diff {pr_number}       │
│     → Analyzes changes                  │
│     → Posts comment via gh pr comment   │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Python Command: prepare-summary        │
│                                         │
│  • Load prompt template                 │
│  • Substitute variables:                │
│    - {TASK_DESCRIPTION}                 │
│    - {PR_NUMBER}                        │
│    - {WORKFLOW_URL}                     │
│  • Output: summary_prompt               │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Claude Code Action                     │
│                                         │
│  1. Fetch PR diff (gh pr diff)          │
│  2. Analyze changes                     │
│  3. Generate <200 word summary          │
│  4. Post as PR comment                  │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  PR Comment Posted                      │
│                                         │
│  ## AI-Generated Summary                │
│  [What was changed and why]             │
│                                         │
│  ---                                    │
│  Generated by ClaudeStep • [link]       │
└─────────────────────────────────────────┘
```

**Key Design Decisions:**

1. **Reuses claude-code-action**: Same action used for both refactoring and summary generation
   - Consistency with existing workflow pattern
   - No new Python modules or API client code needed
   - Claude Code handles all diff fetching and comment posting

2. **Two-step process**: Separate prompt preparation from Claude Code execution
   - Keeps prompt template readable and maintainable
   - Template stored in `prompts/summary_prompt.md`
   - Variables substituted by `prepare-summary` command

3. **Graceful degradation**: Summary failures don't fail the workflow
   - PR creation is the critical operation
   - Summary is nice-to-have
   - Uses `continue-on-error: true` on both steps

4. **Template-based prompts**: Markdown template with variable substitution
   - Easy to read, edit, and version control
   - Simple string replacement for variables
   - No complex prompt engineering in YAML

**Error Handling:**
- Missing PR_NUMBER: Step skipped gracefully (notice logged)
- Missing required env vars: Error logged, step fails but workflow continues
- Template file not found: Error logged, step fails but workflow continues
- Claude Code failure: Workflow continues due to `continue-on-error: true`

---

## Module Organization

### Python Package Structure

```
scripts/claudestep/
├── __init__.py              # Package definition
├── __main__.py              # Entry point (command dispatcher)
│
├── commands/                # Command implementations
│   ├── __init__.py
│   ├── discover.py          # Project discovery
│   ├── discover_ready.py    # Ready project discovery
│   ├── prepare.py           # Pre-execution setup
│   ├── finalize.py          # Post-execution PR creation
│   ├── prepare_summary.py   # PR summary prompt generation
│   └── statistics.py        # Statistics generation
│
├── prompts/                 # Prompt templates
│   └── summary_prompt.md    # PR summary generation prompt
│
├── models.py                # Data models (ReviewerCapacityResult, ProjectStats, etc.)
├── config.py                # Configuration loading and validation
├── exceptions.py            # Custom exception hierarchy
│
├── github_actions.py        # GitHub Actions integration (outputs, summaries)
├── github_operations.py     # GitHub CLI/API wrappers
├── git_operations.py        # Git command wrappers
│
├── task_management.py       # Task finding, marking, tracking
├── reviewer_management.py   # Reviewer capacity checking
├── project_detection.py     # Project path resolution
└── statistics_collector.py  # Statistics data collection
```

### Module Responsibilities

**Commands** (`commands/`):
- Orchestrate workflow steps
- Handle argument parsing
- Read environment variables
- Call business logic functions
- Write GitHub Actions outputs
- Return exit codes

**Models** (`models.py`):
- Data structures (dataclasses, simple classes)
- Formatting methods (Slack, JSON, markdown)
- Properties and computed values
- No external dependencies (GitHub API, file I/O)

**Collectors** (`*_collector.py`, `*_management.py`):
- Gather data from external sources
- GitHub API calls
- File parsing
- Artifact processing
- Return model instances

**Operations** (`*_operations.py`):
- Low-level wrappers around external tools
- Git commands
- GitHub CLI (`gh`)
- Error handling for subprocess calls

**Utilities** (`config.py`, `github_actions.py`):
- Cross-cutting concerns
- Configuration loading
- GitHub Actions environment integration
- Template substitution

### Design Principles

1. **Separation of Concerns**: Each module has a single, clear responsibility
2. **Dependency Direction**: Commands depend on utilities, not vice versa
3. **Testability**: Models and collectors can be tested independently
4. **Reusability**: Multiple commands can use the same utilities
5. **Error Handling**: Each layer handles its own errors appropriately

---

## Summary

**ClaudeStep Architecture** follows these key principles:

✅ **Python-First**: Business logic in Python, YAML as thin wrapper
✅ **Command Dispatcher**: Single entry point with subcommands
✅ **Multiple Actions**: Organized in subdirectories (`statistics/`, `discovery/`)
✅ **Shared Codebase**: All actions use the same Python package
✅ **Testable**: Unit tests for Python code, not YAML
✅ **Modular**: Clear separation between commands, models, and utilities

This architecture enables rapid development, easy testing, and maintainable code as the project grows.
