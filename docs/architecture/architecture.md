# ClaudeStep Architecture

This document describes the architectural decisions and conventions used in the ClaudeStep project.

## Table of Contents

- [Action Organization](#action-organization)
- [Python-First Approach](#python-first-approach)
- [Command Dispatcher Pattern](#command-dispatcher-pattern)
- [Spec File Source of Truth](#spec-file-source-of-truth)
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
├── src/
│   └── claudestep/               # Modern Python package (layered architecture)
└── scripts/
    └── claudestep/               # Legacy compatibility layer (deprecated)
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

**Package Structure**:
- Modern code lives in `src/claudestep/` following layered architecture
- Legacy code in `scripts/claudestep/` for backward compatibility
- PYTHONPATH includes both directories during migration

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
3. **Keep Python logic** in `src/claudestep/` following layered architecture
4. **Add command** to `src/claudestep/cli/` directory
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
  slack_webhook_url:
    description: 'Slack webhook URL for notifications (optional)'
    required: false
    default: ''
outputs:
  slack_message:
    value: ${{ steps.stats.outputs.slack_message }}
  slack_webhook_url:
    value: ${{ steps.stats.outputs.slack_webhook_url }}

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
        SLACK_WEBHOOK_URL: ${{ inputs.slack_webhook_url }}
        ACTION_PATH: ${{ github.action_path }}

    - name: Post to Slack
      if: steps.stats.outputs.has_statistics == 'true' && steps.stats.outputs.slack_webhook_url != ''
      uses: slackapi/slack-github-action@v2
      with:
        webhook: ${{ steps.stats.outputs.slack_webhook_url }}
        webhook-type: incoming-webhook
        payload: |
          {
            "text": ${{ toJSON(steps.stats.outputs.slack_message) }}
          }
      continue-on-error: true
```

**Python (All Logic)**:
```python
# scripts/claudestep/commands/statistics.py
def cmd_statistics(args, gh):
    """All business logic lives here"""
    days_back = int(os.environ.get("STATS_DAYS_BACK", "30"))
    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")

    report = collect_all_statistics(days_back=days_back)
    slack_text = report.format_for_slack()

    gh.write_output("slack_message", slack_text)
    gh.write_output("slack_webhook_url", slack_webhook_url)
    gh.write_output("has_statistics", "true" if report.has_data else "false")
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

## Spec File Source of Truth

### Convention: Spec Files Must Live in Base Branch

ClaudeStep follows a **base branch source of truth** pattern where:

- **Spec files** (`spec.md`, `configuration.yml`) must exist in the base branch (typically `main`)
- **All operations** fetch spec files via GitHub API, never from filesystem
- **PRs do not modify** spec files - they only contain code changes
- **Base branch is configurable** via `base_branch` input (defaults to `main`)

### Why Base Branch as Source of Truth?

**Benefits**:
1. **Consistency** - Single source of truth for all workflow runs
2. **Reliability** - No "file not found" errors from missing specs in test branches
3. **Simplicity** - Users create/update specs once, merge to base, then run workflows
4. **Scalability** - Statistics and discovery work across all projects without filesystem dependencies
5. **Clear Workflow** - Create spec → Merge to base → Run ClaudeStep (easy to understand)

**Comparison**:

❌ **Filesystem-based approach** (what we avoid):
```python
# BAD: Reading from local filesystem
with open("claude-step/my-project/spec.md", "r") as f:
    spec_content = f.read()
# Problem: File might not exist if not merged to current branch
```

✅ **GitHub API approach** (what we use):
```python
# GOOD: Fetching from base branch via API
spec_content = get_file_from_branch(
    repo="owner/repo",
    branch="main",
    file_path="claude-step/my-project/spec.md"
)
# Always fetches from base branch, regardless of current context
```

### Implementation

**Validation** (`prepare.py`):
```python
# Before proceeding, validate spec files exist in base branch
base_branch = os.getenv("BASE_BRANCH", "main")

if not file_exists_in_branch(repo, base_branch, f"claude-step/{project}/spec.md"):
    print(f"Error: spec.md not found in branch '{base_branch}'")
    print(f"Please merge your spec files to '{base_branch}' before running ClaudeStep.")
    sys.exit(1)
```

**Loading Specs** (`prepare.py`, `statistics_collector.py`):
```python
# Fetch spec content from base branch
spec_content = get_file_from_branch(
    repo=repo,
    branch=base_branch,
    file_path=f"claude-step/{project}/spec.md"
)

# Parse tasks from content string (not file path)
tasks = find_next_available_task(spec_content=spec_content)
```

**GitHub API Helpers** (`infrastructure/github/operations.py`):
```python
def get_file_from_branch(repo: str, branch: str, file_path: str) -> Optional[str]:
    """Fetch file content from specific branch via GitHub API"""
    response = gh_api_call(f"/repos/{repo}/contents/{file_path}?ref={branch}")
    content = base64.b64decode(response["content"]).decode("utf-8")
    return content

def file_exists_in_branch(repo: str, branch: str, file_path: str) -> bool:
    """Check if file exists in specific branch"""
    return get_file_from_branch(repo, branch, file_path) is not None
```

### User Workflow

**Step 1**: Create spec files in project directory:
```bash
mkdir -p claude-step/my-project
# Create spec.md and configuration.yml
```

**Step 2**: Merge to base branch:
```bash
git add claude-step/my-project/
git commit -m "Add ClaudeStep project: my-project"
git push origin main
```

**Step 3**: Run ClaudeStep workflow:
- Workflow fetches specs from base branch via API
- Creates PR with code changes (does not modify specs)
- Users merge PR when ready
- Next workflow run fetches updated specs from base branch

### Error Handling

**Missing Spec Files**:
```
Error: Spec files not found in branch 'main'
Required files:
  - claude-step/my-project/spec.md
  - claude-step/my-project/configuration.yml

Please merge your spec files to the 'main' branch before running ClaudeStep.
```

**Custom Base Branch**:
```yaml
# .github/workflows/claudestep.yml
- uses: gestrich/claude-step@v1
  with:
    project_name: 'my-project'
    base_branch: 'master'  # For repos using 'master' instead of 'main'
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
│  • Validate spec files exist in base    │
│    branch (via GitHub API)              │
│  • Load configuration from base branch  │
│  • Check reviewer capacity              │
│  • Find next task                       │
│  • Create branch                        │
│  • Generate Claude prompt               │
│                                         │
│  finalize:                              │
│  • Commit changes                       │
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
│  • Collect project stats from base      │
│    branch (via GitHub API)              │
│  • Collect team stats (GitHub API)      │
│  • Generate reports                     │
│  • Format for Slack                     │
│  • Output slack_webhook_url             │
│  • Output JSON data                     │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│  Outputs → Internal Slack Step         │
│                                         │
│  • slack_message (formatted text)       │
│  • slack_webhook_url (from input)       │
│  • has_statistics (boolean)             │
│                                         │
│  If has_statistics && slack_webhook_url:│
│  → Post to Slack (continue-on-error)    │
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
   - Template stored in `src/claudestep/resources/prompts/summary_prompt.md`
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

**Modern Structure** (`src/claudestep/` - Layered Architecture):
```
src/claudestep/
├── __init__.py
├── __main__.py              # Entry point
│
├── domain/                  # Layer 1: Core business logic
│   ├── models.py            # Data models
│   ├── exceptions.py        # Custom exceptions
│   └── config.py            # Configuration models
│
├── infrastructure/          # Layer 2: External dependencies
│   ├── git/
│   │   └── operations.py    # Git command wrappers
│   ├── github/
│   │   ├── operations.py    # GitHub CLI wrappers
│   │   └── actions.py       # GitHub Actions integration
│   └── filesystem/
│       └── operations.py    # File I/O operations
│
├── application/             # Layer 3: Business logic services
│   ├── services/
│   │   ├── reviewer_management.py
│   │   ├── task_management.py
│   │   ├── project_detection.py
│   │   ├── pr_operations.py
│   │   ├── artifact_operations.py
│   │   ├── metadata_service.py
│   │   └── statistics_service.py
│   └── formatters/
│       └── table_formatter.py
│
└── cli/                     # Layer 4: Presentation layer
    ├── commands/
    │   ├── discover.py
    │   ├── discover_ready.py
    │   ├── prepare.py
    │   ├── finalize.py
    │   ├── prepare_summary.py
    │   └── statistics.py
    └── parser.py
```

**Legacy Structure** (`scripts/claudestep/` - For backward compatibility):
- Maintained during migration
- Will be removed in future releases
- Contains compatibility shims that import from new structure

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

**Services** (`*_service.py`, `*_management.py`):
- Orchestrate business logic across multiple infrastructure components
- Gather and aggregate data from external sources (GitHub API, metadata storage)
- Implement use cases required by CLI commands
- Process and transform data using domain models
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
