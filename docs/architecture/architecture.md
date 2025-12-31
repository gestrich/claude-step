# ClaudeStep Architecture

This document describes the architectural decisions and conventions used in the ClaudeStep project.

## Table of Contents

- [Action Organization](#action-organization)
- [Python-First Approach](#python-first-approach)
- [Service Layer Pattern (Martin Fowler)](#service-layer-pattern-martin-fowler)
- [Command Dispatcher Pattern](#command-dispatcher-pattern)
- [Spec File Source of Truth](#spec-file-source-of-truth)
- [Data Flow](#data-flow)
- [Module Organization](#module-organization)
- [Services](#services)

---

## Action Organization

### Convention: Multiple Actions in One Repository

ClaudeStep provides **three GitHub Actions** in a single repository, plus an **auto-start workflow** for seamless onboarding:

1. **Main Action** (`action.yml`) - Core refactoring automation
2. **Discovery Action** (`discovery/action.yml`) - Project discovery
3. **Statistics Action** (`statistics/action.yml`) - Reporting and analytics
4. **Auto-Start Workflow** (`.github/workflows/claudestep-auto-start.yml`) - Automatic first-task triggering

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

## Service Layer Pattern (Martin Fowler)

### Convention: Layered Architecture with Service Layer

ClaudeStep follows Martin Fowler's **Service Layer pattern** from "Patterns of Enterprise Application Architecture" (2002). This architectural pattern defines the application's boundary with a layer of services that establishes available operations and coordinates responses.

**Reference**: [Service Layer - Martin Fowler's PoEAA Catalog](https://martinfowler.com/eaaCatalog/serviceLayer.html)

### What is Service Layer?

From Fowler's catalog:

> "Defines an application's boundary with a layer of services that establishes a set of available operations and coordinates the application's response in each operation."

The Service Layer pattern:
- **Encapsulates business logic** in service classes
- **Coordinates operations** across domain and infrastructure layers
- **Provides a unified API** for different client types (CLI, API, etc.)
- **Manages transactions** and orchestrates responses

### ClaudeStep's Implementation

ClaudeStep implements Service Layer with a **lightweight, pragmatic approach**:

✅ **We follow the spirit, not the letter** - Rough alignment with Fowler's principles, not dogmatic adherence
✅ **Service classes encapsulate business logic** - All operations coordinated through services
✅ **Layered architecture** - Clear separation between CLI, Service, Domain, and Infrastructure
✅ **Dependency injection** - Services receive dependencies via constructors
✅ **Python-first** - No framework overhead, just well-organized Python classes

❌ **We don't enforce strict boundaries** - Services can call infrastructure directly when practical
❌ **No transaction management** - Operations are simple enough not to require transaction coordination
❌ **No complex service contracts** - Services use simple Python methods, not formal interfaces

### Layer Responsibilities

ClaudeStep's architecture consists of four layers:

#### 1. CLI Layer (`cli/`)
- **Purpose**: Thin orchestration layer - entry point for user interactions
- **Responsibilities**:
  - Parse command-line arguments
  - Read environment variables
  - Instantiate services with their dependencies
  - Coordinate service method calls to fulfill commands
  - Write GitHub Actions outputs
  - Return exit codes
- **What it does NOT do**:
  - ❌ Implement business logic
  - ❌ Make API calls directly
  - ❌ Manipulate data structures
  - ❌ Store state

**Example**:
```python
def cmd_prepare(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    # Instantiate services
    task_service = TaskService(repo, metadata_service)
    reviewer_service = ReviewerService(repo, metadata_service)

    # Orchestrate operations
    task = task_service.find_next_available_task(spec_content)
    reviewer = reviewer_service.find_available_reviewer(reviewers, label, project)

    # Write outputs and return
    gh.write_output("task_description", task.description)
    return 0
```

#### 2. Service Layer (`services/`)
- **Purpose**: Business logic and use case orchestration
- **Responsibilities**:
  - Encapsulate business operations (task management, reviewer assignment, etc.)
  - Coordinate across domain models and infrastructure
  - Aggregate data from multiple sources (GitHub API, metadata store, filesystem)
  - Transform data using domain models
  - Maintain operation state through instance variables
- **What it does NOT do**:
  - ❌ Parse command-line arguments
  - ❌ Write GitHub Actions outputs
  - ❌ Implement low-level Git/GitHub operations (delegates to infrastructure)

**Example**:
```python
class TaskService:
    """Service Layer class for task management operations.

    Coordinates task finding, marking, and tracking across
    spec files and metadata storage.
    """

    def __init__(self, repo: str, metadata_service: MetadataService):
        self.repo = repo
        self.metadata_service = metadata_service

    def find_next_available_task(self, spec_content: str) -> TaskMetadata:
        # Business logic: parse spec, check metadata, find available task
        tasks = self._parse_tasks(spec_content)
        in_progress = self.metadata_service.get_in_progress_tasks()
        return self._find_next(tasks, in_progress)
```

#### 3. Domain Layer (`domain/`)
- **Purpose**: Core business models and rules
- **Responsibilities**:
  - Define data structures (dataclasses, models)
  - Implement formatting methods (Slack, JSON, markdown)
  - Define business exceptions
  - Store configuration schemas
  - Provide computed properties
- **What it does NOT do**:
  - ❌ Make API calls
  - ❌ Read/write files
  - ❌ Execute shell commands
  - ❌ Access external systems

**Example**:
```python
@dataclass
class ProjectMetadata:
    """Domain model for project metadata."""
    project: str
    spec_path: str
    total_tasks: int
    completed_tasks: int

    def format_for_slack(self) -> str:
        """Format project data for Slack display."""
        return f"*{self.project}*: {self.completed_tasks}/{self.total_tasks} tasks"
```

#### 4. Infrastructure Layer (`infrastructure/`)
- **Purpose**: External system integrations
- **Responsibilities**:
  - Wrap Git commands
  - Wrap GitHub CLI (`gh`) operations
  - Provide filesystem operations
  - Handle metadata storage (GitHub artifacts)
  - Execute subprocess calls
  - Handle infrastructure errors
- **What it does NOT do**:
  - ❌ Implement business logic
  - ❌ Coordinate multi-step operations
  - ❌ Make business decisions

**Example**:
```python
def get_file_from_branch(repo: str, branch: str, file_path: str) -> Optional[str]:
    """Infrastructure operation: fetch file via GitHub API."""
    response = gh_api_call(f"/repos/{repo}/contents/{file_path}?ref={branch}")
    content = base64.b64decode(response["content"]).decode("utf-8")
    return content
```

### Service Class Conventions

All services in ClaudeStep follow consistent patterns:

#### Constructor-Based Dependency Injection
```python
class ServiceName:
    def __init__(self, repo: str, metadata_service: MetadataService):
        """Initialize service with required dependencies."""
        self.repo = repo
        self.metadata_service = metadata_service
```

#### Services Encapsulate Related Operations
```python
class TaskService:
    """Groups all task-related operations."""

    def find_next_available_task(self, spec_content: str) -> TaskMetadata:
        pass

    def get_in_progress_task_indices(self, project: str) -> list[int]:
        pass

    def mark_task_complete(self, spec_content: str, task_index: int) -> str:
        pass
```

#### Services Can Depend on Other Services and Infrastructure
```python
class StatisticsService:
    def __init__(self, repo: str, metadata_service: MetadataService, base_branch: str = "main"):
        self.repo = repo
        self.metadata_service = metadata_service  # Service dependency
        self.base_branch = base_branch  # Configuration

    def collect_project_stats(self, project: str) -> ProjectStats:
        # Uses infrastructure directly with instance config
        spec_content = get_file_from_branch(self.repo, self.base_branch, f"claude-step/{project}/spec.md")

        # Uses other services
        metadata = self.metadata_service.get_project(project)

        # Business logic
        return self._aggregate_statistics(spec_content, metadata)
```

#### Commands Orchestrate Services, Don't Implement Business Logic
```python
# ✅ GOOD: Command orchestrates services with explicit parameters
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str = "main",
    config_path: Optional[str] = None,
    days_back: int = 30,
    format_type: str = "slack",
    slack_webhook_url: str = ""
) -> int:
    # Instantiate services with dependencies
    metadata_service = MetadataService(metadata_store)
    stats_service = StatisticsService(repo, metadata_service, base_branch)

    # Delegate to service
    report = stats_service.collect_all_statistics(config_path=config_path)

    # Output results
    gh.write_output("slack_message", report.format_for_slack())
    return 0

# ❌ BAD: Command implements business logic
def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    # Don't parse, aggregate, or compute in commands
    projects = find_all_projects()
    for project in projects:
        spec = parse_spec_file(project)
        tasks = count_tasks(spec)
        # ... more business logic in command
```

### Benefits of Service Layer Approach

1. **Clear Separation of Concerns** - Each layer has distinct responsibilities
2. **Testability** - Services can be tested independently with mocked dependencies
3. **Reusability** - Multiple commands can use the same services
4. **Maintainability** - Business logic consolidated in service classes, not scattered across commands
5. **Consistency** - All services follow the same architectural pattern
6. **Flexibility** - Easy to add new operations or refactor without changing CLI interface

### Example: Full Stack for Task Preparation

```python
# CLI Layer - Orchestrates the workflow
def cmd_prepare(args, gh):
    task_service = TaskService(repo, metadata_service)
    task = task_service.find_next_available_task(spec_content)
    gh.write_output("task_description", task.description)

# Service Layer - Implements business logic
class TaskService:
    def find_next_available_task(self, spec_content: str) -> TaskMetadata:
        tasks = self._parse_tasks(spec_content)
        in_progress = self._get_in_progress_tasks()
        return self._find_next(tasks, in_progress)

# Domain Layer - Models the data
@dataclass
class TaskMetadata:
    description: str
    index: int
    task_id: str

# Infrastructure Layer - Fetches the spec
def get_file_from_branch(repo: str, branch: str, path: str) -> str:
    return subprocess.check_output(["gh", "api", f"/repos/{repo}/contents/{path}"])
```

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
| `auto-start` | Detect new projects and trigger workflows | Auto-Start workflow |
| `auto-start-summary` | Generate summary for auto-start results | Auto-Start workflow |

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

## Hash-Based Task Identification

### Convention: Content-Based Task Hashing

ClaudeStep uses a **hash-based task identification** system where tasks are identified by content hash rather than position in the spec file. This enables flexible task management without breaking PR tracking.

### Why Hash-Based Identification?

**Benefits**:
1. **Flexible Task Management** - Insert, delete, or reorder tasks without breaking PR tracking
2. **No Manual ID Management** - Hashes generated automatically from task descriptions
3. **Self-Healing** - Orphaned PRs detected automatically, new PRs created when old ones closed
4. **Stable Identifiers** - Task hash remains constant as long as description unchanged
5. **Collision Resistant** - SHA-256 provides sufficient combinations for task lists

**Trade-offs**:
- Task hashes are not human-readable (but branch names include project for context)
- Changing task description invalidates existing PRs (user must close and restart)
- Need to handle orphaned PRs when descriptions change

### Hash Algorithm

**Implementation** (`src/claudestep/domain/spec_content.py`):
```python
def generate_task_hash(description: str) -> str:
    """Generate stable 8-character hash from task description"""
    # Normalize whitespace (strip and collapse)
    normalized = " ".join(description.strip().split())

    # SHA-256 hash
    hash_object = hashlib.sha256(normalized.encode('utf-8'))

    # Truncate to 8 hex characters (32 bits)
    return hash_object.hexdigest()[:8]
```

**Examples**:
- `generate_task_hash("Add user authentication")` → `"39b1209d"`
- `generate_task_hash("  Add user   authentication  ")` → `"39b1209d"` (whitespace normalized)
- `generate_task_hash("Add user authorization")` → `"f7c4d3e2"` (different description = different hash)

### Orphaned PR Detection

Orphaned PRs are pull requests whose task description has changed or been removed from spec.md.

**Example Scenario**:
```markdown
<!-- Original spec.md -->
- [ ] Add user authentication  ← PR created with hash 39b1209d

<!-- User modifies task description -->
- [ ] Add OAuth authentication  ← Hash changes to a8f3c2d1

<!-- Now PR with hash 39b1209d is "orphaned" -->
```

**Detection Logic**:
1. Extract all current task hashes from spec.md
2. Get all open PRs for the project
3. Find PRs with task_hash not in the current valid hashes
4. Report orphaned PRs to user with guidance

**User Guidance** (shown in console and GitHub Actions summary):
```
⚠️  Warning: Found 2 orphaned PR(s):
  - PR #123 (claude-step-auth-39b1209d) - task hash 39b1209d no longer matches any task
  - PR #125 (claude-step-auth-f7c4d3e2) - task hash f7c4d3e2 no longer matches any task

To resolve:
  1. Review these PRs and verify if they should be closed
  2. Close any PRs for modified/removed tasks
  3. ClaudeStep will automatically create new PRs for current tasks
```

---

## Branch Naming

### Convention: Standardized Branch Format

ClaudeStep uses a standardized branch naming convention that identifies pull requests by project and task hash, enabling stable task tracking regardless of task position in the spec file.

### Branch Format

All ClaudeStep branches follow this format:

```
claude-step-{project_name}-{task_hash}
```

**Components:**
- `claude-step`: Fixed prefix identifying ClaudeStep PRs
- `{project_name}`: Name of the project folder (e.g., "my-refactor", "auth-migration")
- `{task_hash}`: 8-character hexadecimal hash identifying the task (e.g., "a3f2b891")

**Examples:**
- `claude-step-my-refactor-a3f2b891`
- `claude-step-auth-migration-f7c4d3e2`
- `claude-step-swift-migration-39b1209d`

### Implementation

**Formatting Branch Names:**
```python
from claudestep.services.core.pr_service import PRService

branch_name = PRService.format_branch_name("my-refactor", "a3f2b891")
# Result: "claude-step-my-refactor-a3f2b891"
```

**Parsing Branch Names:**
```python
branch_info = PRService.parse_branch_name("claude-step-my-refactor-a3f2b891")
# Returns: BranchInfo(project_name='my-refactor', task_hash='a3f2b891', format_version='hash')

if branch_info:
    print(branch_info.project_name)  # 'my-refactor'
    print(branch_info.task_hash)     # 'a3f2b891'
```

The parser returns a `BranchInfo` domain model instance or `None` if the branch doesn't match the ClaudeStep pattern.

You can also parse directly using the domain model:
```python
from claudestep.domain.models import BranchInfo

branch_info = BranchInfo.from_branch_name("claude-step-my-refactor-a3f2b891")
```

### Format Detection

Branch names are validated using the pattern `^claude-step-(.+)-([a-z0-9]+)$` where:
- Task identifier must be exactly 8 lowercase hexadecimal characters
- Project names can contain hyphens (greedy matching up to the last hyphen)

### Integration with Task Hashing

Branch names use the same hash generated by the task identification system (see [Hash-Based Task Identification](#hash-based-task-identification)):

1. Task hash is generated from task description using SHA-256
2. First 8 characters of hex digest are used as task identifier
3. Branch name is created combining project name and task hash
4. PRs are tracked by this stable identifier

This creates a direct link: Task in spec.md → Task hash → Branch name → Pull request

### Benefits

1. **Stable Identification**: Task hash never changes even if task is reordered
2. **Project Isolation**: Project name in branch prevents naming conflicts
3. **Easy Filtering**: PRs can be filtered by project using branch name patterns
4. **Human Readable**: Branch names clearly show project and task identifier
5. **Parseable**: Structured format enables programmatic extraction of metadata

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

## Auto-Start Workflow

### Overview

The ClaudeStep Auto-Start workflow (`.github/workflows/claudestep-auto-start.yml`) automatically triggers the first task when a new project's spec.md is merged to the main branch. This eliminates the manual workflow trigger step and provides seamless onboarding.

### Workflow Trigger

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'claude-step/*/spec.md'

concurrency:
  group: claudestep-auto-start-${{ github.ref }}
  cancel-in-progress: false
```

**Key Design:**
- Triggers on any push to main that modifies spec.md files
- Uses concurrency control to prevent race conditions
- Both concurrent runs execute (they'll detect existing PRs and skip appropriately)

### Python-First Implementation

Following ClaudeStep's **Python-first architecture**, the auto-start workflow delegates all business logic to Python services, with YAML acting as a lightweight wrapper.

**YAML Workflow** (`.github/workflows/claudestep-auto-start.yml`):
```yaml
steps:
  - name: Setup Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.11'

  - name: Install ClaudeStep
    run: pip install -e .

  - name: Detect and trigger auto-start
    id: auto_start
    run: python3 -m claudestep auto-start
    env:
      GITHUB_REPOSITORY: ${{ github.repository }}
      BASE_BRANCH: main
      REF_BEFORE: ${{ github.event.before }}
      REF_AFTER: ${{ github.sha }}
      GH_TOKEN: ${{ github.token }}
      AUTO_START_ENABLED: ${{ vars.CLAUDESTEP_AUTO_START_ENABLED != 'false' }}

  - name: Generate summary
    if: always()
    run: python3 -m claudestep auto-start-summary
    env:
      TRIGGERED_PROJECTS: ${{ steps.auto_start.outputs.triggered_projects }}
      FAILED_PROJECTS: ${{ steps.auto_start.outputs.failed_projects }}
```

**Python Service Layer** (`src/claudestep/services/composite/auto_start_service.py`):
- `detect_changed_projects()` - Uses git operations to find changed spec files
- `determine_new_projects()` - Uses PRService to check for existing PRs
- `should_auto_trigger()` - Business logic for auto-start decision

**Python CLI Command** (`src/claudestep/cli/commands/auto_start.py`):
- Orchestrates service calls
- Writes GitHub Actions outputs
- Handles error cases

### Detection Flow

```
┌─────────────────────────────────────────┐
│  Push to main (spec.md changed)         │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Python: AutoStartService               │
│  detect_changed_projects()              │
│  • git diff via infrastructure layer    │
│  • Returns AutoStartProject models      │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Python: AutoStartService               │
│  determine_new_projects()               │
│  • Uses PRService.get_project_prs()     │
│  • Filters to new projects only         │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Python: AutoStartService               │
│  should_auto_trigger()                  │
│  • Returns AutoStartDecision model      │
│  • Checks auto_start_enabled config     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Python: WorkflowService                │
│  batch_trigger_claudestep_workflows()   │
│  • Uses gh workflow run                 │
│  • Passes project_name, base_branch     │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│  Python: cmd_auto_start_summary()       │
│  • Reads outputs from auto-start step   │
│  • Generates GitHub Actions summary     │
│  • Shows triggered/failed projects      │
└─────────────────────────────────────────┘
```

### New vs Existing Project Detection

The workflow uses hash-based branch naming to distinguish new projects from existing ones:

**Detection Logic:**
1. Query all PRs with `claudestep` label
2. Filter PRs by branch name pattern: `claude-step-{project}-*`
3. Count matching PRs for each project
4. If count = 0 → new project (auto-trigger)
5. If count > 0 → existing project (skip, relies on PR merge triggers)

**Branch Pattern:**
```bash
gh pr list \
  --label claudestep \
  --state all \
  --json headRefName \
  --jq "[.[] | select(.headRefName | startswith(\"claude-step-$project-\"))] | length"
```

### Edge Cases Handled

1. **Spec Deleted**: Detected via `git diff --diff-filter=D`, logged and skipped
2. **Multiple Projects**: Iterates over all detected projects, triggers each independently
3. **Existing Projects**: Skipped with clear message (relies on PR merge triggers)
4. **Invalid Spec**: Delegated to ClaudeStep action validation
5. **Missing Configuration**: Delegated to ClaudeStep action validation
6. **API Failures**: Error handling catches rate limits, projects skipped on failure
7. **Concurrent Pushes**: Concurrency group prevents race conditions

### User Experience

**For New Projects:**
```
User: git push origin main  (adds spec.md)
  ↓
Auto-Start Workflow: Detects new project "my-refactor"
  ↓
Auto-Start Workflow: Triggers ClaudeStep workflow
  ↓
ClaudeStep Workflow: Creates PR for first task
  ↓
User: Receives PR notification (no manual action needed)
```

**For Existing Projects:**
```
User: git push origin main  (updates spec.md)
  ↓
Auto-Start Workflow: Detects existing project "my-refactor"
  ↓
Auto-Start Workflow: Skips auto-trigger (existing PRs found)
  ↓
Summary: "Existing project, relies on PR merge triggers"
```

### Disabling Auto-Start

Users can disable auto-start using the `CLAUDESTEP_AUTO_START_ENABLED` repository variable:

**Via GitHub UI:**
1. Navigate to repository Settings > Secrets and variables > Actions > Variables
2. Add a new repository variable: `CLAUDESTEP_AUTO_START_ENABLED`
3. Set value to `false`

**Behavior:**
- When `CLAUDESTEP_AUTO_START_ENABLED` is set to `'false'`, the auto-start workflow still runs but skips triggering any workflows
- The workflow generates a summary explaining that auto-start is disabled
- Default behavior (if variable is not set or set to any other value): auto-start is enabled

**Alternative methods:**
1. Deleting `.github/workflows/claudestep-auto-start.yml`
2. Disabling the workflow in GitHub Actions settings
3. Manually triggering tasks via Actions > ClaudeStep > Run workflow

**Note:** Disabling only affects the first task trigger. Subsequent tasks continue to auto-trigger on PR merge.

**Implementation:**
The configuration is passed through the service layer following ClaudeStep's explicit parameter passing pattern:
- YAML workflow reads `vars.CLAUDESTEP_AUTO_START_ENABLED` and sets environment variable
- `__main__.py` adapter layer reads environment variable and passes to CLI command
- CLI command passes to `AutoStartService` constructor
- Service checks configuration before making auto-trigger decisions

### Integration with Main Action

The auto-start workflow is **completely additive**:
- Does not modify existing ClaudeStep action
- Does not change PR merge trigger behavior
- Can be removed without breaking existing functionality
- Uses same `claudestep.yml` workflow as manual triggers

**Rollback Plan:**
- Delete `.github/workflows/claudestep-auto-start.yml`
- Existing manual triggers continue to work
- No breaking changes to ClaudeStep action itself

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
├── services/                # Layer 3: Business logic services
│   ├── __init__.py
│   ├── core/                # Foundational services
│   │   ├── __init__.py
│   │   ├── pr_service.py
│   │   ├── project_service.py
│   │   ├── reviewer_service.py
│   │   └── task_service.py
│   ├── composite/           # Higher-level orchestration
│   │   ├── __init__.py
│   │   ├── artifact_service.py
│   │   └── statistics_service.py
│   └── formatters/          # Service layer utilities
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

## Service Layer Organization

### Convention: Two-Level Service Architecture

ClaudeStep organizes services into **two architectural levels**:

**Core Services** (`services/core/`) provide foundational operations for specific domain areas (PRs, tasks, reviewers, projects). These are building blocks with minimal dependencies that can be used independently or composed together. Examples include `PRService`, `TaskService`, `ReviewerService`, and `ProjectService`.

**Composite Services** (`services/composite/`) orchestrate complex multi-step operations by coordinating multiple core services. They aggregate data from various sources and implement higher-level business logic. Examples include `StatisticsService` and `ArtifactService`.

This organization provides clear dependency direction (Composite → Core → Infrastructure), makes the architecture visible in the filesystem, and enables independent testing of each layer. For implementation details, see the service source code in [`src/claudestep/services/`](../../src/claudestep/services/).

---

## Services

### Convention: Class-Based Services with Dependency Injection

ClaudeStep uses a **class-based service architecture** where:

- **Services are classes** with constructor-based dependency injection
- **Services encapsulate** business logic for a specific domain area
- **Services are instantiated** once per CLI command execution
- **Services share state** through instance variables (repo, metadata_service, etc.)

### Why Class-Based Services?

**Benefits**:
1. **Consistency** - All services follow the same pattern
2. **Dependency Injection** - Dependencies injected via constructor, not passed as function parameters
3. **Testability** - Easier to mock dependencies and control test setup
4. **Reduced Repetition** - Eliminates redundant object creation (e.g., GitHubMetadataStore)
5. **State Management** - Services cache configuration and avoid redundant API calls
6. **Future Flexibility** - Easier to add methods or refactor without changing signatures everywhere

### Service Architecture Pattern

All services follow this design:

```python
class ServiceName:
    """Service for handling domain-specific operations"""

    def __init__(self, repo: str, metadata_service: MetadataService):
        """Initialize service with required dependencies"""
        self.repo = repo
        self.metadata_service = metadata_service

    def instance_method(self, param: str) -> Result:
        """Instance methods use self.repo and self.metadata_service"""
        # Use injected dependencies
        data = self.metadata_service.get_data()
        return process(data, param)

    @staticmethod
    def static_method(param: str) -> Result:
        """Static methods for pure functions with no state dependency"""
        return pure_computation(param)
```

### Available Services

**Core Services** (`src/claudestep/services/core/`):

1. **TaskService** - Task finding, marking, and tracking
   - Constructor: `__init__(self, repo: str, metadata_service: MetadataService)`
   - Instance methods: `find_next_available_task()`, `get_in_progress_task_indices()`
   - Static methods: `generate_task_id()`, `mark_task_complete()`

2. **ReviewerService** - Reviewer capacity and assignment
   - Constructor: `__init__(self, repo: str, metadata_service: MetadataService)`
   - Instance methods: `find_available_reviewer()`

3. **PRService** - PR and branch naming utilities
   - Constructor: `__init__(self, repo: str)`
   - Instance methods: `get_project_prs()`
   - Static methods: `format_branch_name()`, `parse_branch_name()`

4. **ProjectService** - Project detection from PRs and paths
   - Constructor: `__init__(self, repo: str)`
   - Instance methods: `detect_project_from_pr()`
   - Static methods: `detect_project_paths()`

**Composite Services** (`src/claudestep/services/composite/`):

5. **StatisticsService** - Statistics collection and aggregation
   - Constructor: `__init__(self, repo: str, metadata_service: MetadataService, base_branch: str = "main")`
   - Instance methods: `collect_team_member_stats()`, `collect_project_stats()`, `collect_all_statistics()`
   - Static methods: `extract_cost_from_comment()`, `count_tasks()`

6. **ArtifactService** - Artifact operations
   - Module-level functions: `find_project_artifacts()`, `get_artifact_metadata()`, `find_in_progress_tasks()`, `get_reviewer_assignments()`

7. **AutoStartService** - Auto-start project detection and decision logic
   - Constructor: `__init__(self, repo: str, pr_service: PRService, auto_start_enabled: bool = True)`
   - Instance methods: `detect_changed_projects()`, `determine_new_projects()`, `should_auto_trigger()`
   - Dependency: Uses `PRService` (core) to check for existing PRs
   - Orchestrates: Git operations (infrastructure) for file change detection

8. **WorkflowService** - GitHub workflow triggering
   - Constructor: `__init__(self, repo: str)`
   - Instance methods: `trigger_claudestep_workflow()`, `batch_trigger_claudestep_workflows()`
   - Uses infrastructure layer for `gh` command execution

**Infrastructure Services** (`src/claudestep/infrastructure/`):

7. **MetadataService** - Project and artifact metadata management
   - Constructor: `__init__(self, metadata_store: GitHubMetadataStore)`
   - Instance methods: `get_project()`, `save_project()`, `update_project()`, `get_artifact()`, `save_artifact()`

### Service Instantiation in CLI Commands

Services are instantiated **once** at the beginning of each command execution:

```python
def cmd_prepare(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    # === Get common dependencies ===
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    # === Initialize infrastructure ===
    metadata_store = GitHubMetadataStore(repo)
    metadata_service = MetadataService(metadata_store)

    # === Initialize services ===
    project_service = ProjectService(repo)
    task_service = TaskService(repo, metadata_service)
    reviewer_service = ReviewerService(repo, metadata_service)
    pr_service = PRService(repo)

    # === Use services throughout command ===
    project = project_service.detect_project_from_pr(pr_number)
    task = task_service.find_next_available_task(spec_content)
    reviewer = reviewer_service.find_available_reviewer(reviewers, label, project)
    branch = pr_service.format_branch_name(project, task_index)

    # ... rest of command logic
```

### Service Instantiation Pattern

All CLI commands follow this three-section pattern:

1. **Get common dependencies** - Extract `repo` and other config from environment
2. **Initialize infrastructure** - Create `GitHubMetadataStore` and `MetadataService`
3. **Initialize services** - Instantiate all needed services with their dependencies

This pattern:
- Eliminates redundant service creation
- Makes dependencies explicit and testable
- Provides consistent structure across all commands
- Enables easy addition of new services

### Static vs Instance Methods

**Use instance methods when:**
- The method needs access to `self.repo` or `self.metadata_service`
- The method performs I/O or makes API calls
- The method needs to share state with other methods

**Use static methods when:**
- The method is a pure function with no state dependency
- The method performs pure computation or string manipulation
- The method can be called without instantiating the service

**Example**:
```python
class PRService:
    def __init__(self, repo: str):
        self.repo = repo

    def get_project_prs(self, project: str) -> List[dict]:
        """Instance method - needs self.repo"""
        return fetch_prs_from_github(self.repo, project)

    @staticmethod
    def parse_branch_name(branch: str) -> tuple[str, int]:
        """Static method - pure function, no state needed"""
        match = re.match(r"^([^/]+)/task-(\d+)", branch)
        return match.groups() if match else (None, None)
```

### Testing Services

**Unit Test Pattern**:
```python
class TestTaskService:
    """Test suite for TaskService"""

    def test_find_next_available_task_returns_first_unchecked(self):
        """Should return the first unchecked task from spec content"""
        # Arrange
        mock_metadata_service = Mock()
        service = TaskService(
            repo="owner/repo",
            metadata_service=mock_metadata_service
        )
        spec_content = """
        - [x] Completed task
        - [ ] Next task
        - [ ] Future task
        """

        # Act
        result = service.find_next_available_task(spec_content)

        # Assert
        assert result.description == "Next task"
        assert result.index == 2
```

**Integration Test Pattern**:
```python
def test_prepare_command_with_services(mock_subprocess):
    """Should use services to orchestrate preparation workflow"""
    with patch('claudestep.cli.commands.prepare.ProjectService') as MockProject:
        with patch('claudestep.cli.commands.prepare.TaskService') as MockTask:
            # Mock service instances
            mock_project_service = MockProject.return_value
            mock_task_service = MockTask.return_value

            # Set up mock behavior
            mock_project_service.detect_project_from_pr.return_value = "test-project"
            mock_task_service.find_next_available_task.return_value = task_metadata

            # Act
            result = cmd_prepare(args, gh)

            # Assert
            assert result == 0
            MockProject.assert_called_once_with(repo="owner/repo")
            mock_project_service.detect_project_from_pr.assert_called_once()
```

## Future: Metadata Synchronization

### Convention: Metadata as Source of Truth with Future Sync Capability

ClaudeStep follows a **metadata-first architecture** where:

- **Metadata configuration is the single source of truth** for statistics and reporting
- **Metadata is kept up-to-date** by merge triggers and workflow runs
- **GitHub API queries are available but not used** in normal operations
- **Future synchronize command** will enable metadata validation and drift detection

### Why Metadata as Source of Truth?

**Benefits**:
1. **Consistency** - All statistics come from the same source (metadata), not mixed sources
2. **Performance** - No GitHub API rate limit concerns for statistics queries
3. **Cross-project aggregation** - Easy to aggregate stats across multiple projects
4. **Offline capability** - Statistics work without GitHub API access (using cached metadata)
5. **Type safety** - Metadata uses well-defined domain models, not raw JSON

**Comparison**:

❌ **Direct GitHub API approach** (what we avoid for statistics):
```python
# BAD: Querying GitHub API for statistics
prs = run_gh_command("pr list --json number,title,assignees")
data = json.loads(prs)
for pr in data:
    reviewer = pr["assignees"][0]["login"]  # String keys, no type safety
    # Complex JSON navigation, easy to break
```

✅ **Metadata-based approach** (what we use):
```python
# GOOD: Using metadata configuration
projects = metadata_service.list_project_names()
for project in projects:
    metadata = metadata_service.get_project(project)
    for pr in metadata.pull_requests:
        reviewer = pr.reviewer  # Type-safe property access
        pr_title = pr.title or pr.task_description  # Graceful fallback
```

### GitHub PR Operations: Built for Future Use

The infrastructure layer includes GitHub PR query functions in `infrastructure/github/operations.py` that provide type-safe access to GitHub's actual PR state:

```python
def list_pull_requests(
    repo: str,
    state: str = "all",
    label: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[GitHubPullRequest]:
    """Fetch PRs with filtering, returns domain models"""
    # GitHub CLI command construction
    # JSON parsing via domain model factories
    # Returns type-safe GitHubPullRequest objects
```

**These functions enable a future "synchronize" command** that can:

- **Detect PRs closed outside normal workflow** - Find PRs that were merged/closed manually
- **Backfill metadata from existing PRs** - Import historical ClaudeStep PRs into metadata
- **Audit metadata accuracy** - Verify metadata matches GitHub reality
- **Correct drift** - Update metadata when it diverges from actual PR state
- **Validate consistency** - Check that all expected PRs exist and have correct status

### Current Data Flow: Merge Triggers → Metadata → Statistics

```
┌────────────────────────┐
│   Workflow Run         │
│   (finalize command)   │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   Update Metadata      │
│   - PR number          │
│   - PR title           │
│   - Reviewer           │
│   - Task info          │
│   - Timestamp          │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   Metadata Storage     │
│   (Single source of    │
│    truth)              │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│   Statistics Service   │
│   - Queries metadata   │
│   - No GitHub API      │
│   - Type-safe models   │
└────────────────────────┘
```

### Future Data Flow: Synchronize Command

```
┌────────────────────────┐
│   Synchronize Command  │
│   (future feature)     │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────────────────┐
│   Query GitHub API                 │
│   - list_pull_requests()           │
│   - Filter by ClaudeStep label     │
│   - Returns GitHubPullRequest      │
│     domain models                  │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│   Compare with Metadata            │
│   - Check for missing PRs          │
│   - Verify PR status matches       │
│   - Detect manual changes          │
└──────────┬─────────────────────────┘
           │
           ▼
┌────────────────────────────────────┐
│   Update Metadata                  │
│   - Backfill missing PRs           │
│   - Correct incorrect status       │
│   - Report drift                   │
└────────────────────────────────────┘
```

### Why Keep GitHub Infrastructure Layer?

Although statistics don't currently use GitHub PR queries, we maintain the infrastructure for:

1. **Future synchronize command** - Validate and correct metadata against GitHub
2. **Backfill historical data** - Import existing PRs from before ClaudeStep adoption
3. **Audit and compliance** - Verify metadata accuracy for reporting
4. **Disaster recovery** - Rebuild metadata from GitHub if storage corrupted
5. **Migration tools** - Support future metadata format changes

The infrastructure is **ready but dormant** - tested, documented, and available when needed.

### Design Principles

1. **Parse once into well-formed models** - GitHub JSON → `GitHubPullRequest` domain models
2. **Infrastructure layer owns external integrations** - All GitHub CLI calls in `operations.py`
3. **Single source of truth** - Metadata configuration for all current operations
4. **Type safety** - Services work with typed domain objects, not JSON dictionaries
5. **Future-ready** - Infrastructure exists for synchronization without blocking current features

### StatisticsService: Example of Metadata-First Architecture

The `StatisticsService` exemplifies the metadata-first approach:

**Before refactoring** (Phases 1-7 of refactor-statistics-service-architecture.md):
```python
# BAD: Direct GitHub API calls with JSON parsing in service layer
def collect_team_member_stats(self, days_back: int, label: str):
    # Raw GitHub CLI commands
    merged_prs_json = run_gh_command(f"pr list --state merged --json ...")
    open_prs_json = run_gh_command(f"pr list --state open --json ...")

    # JSON parsing in service layer
    merged_prs = json.loads(merged_prs_json)
    for pr in merged_prs:
        reviewer = pr["assignees"][0]["login"]  # String keys, no type safety
```

**After refactoring** (Current implementation):
```python
# GOOD: Metadata-based with type-safe domain models
def collect_team_member_stats(self, days_back: int) -> Dict[str, TeamMemberStats]:
    """Collect statistics from metadata configuration"""
    stats_by_reviewer: Dict[str, TeamMemberStats] = {}

    # Query metadata service (single source of truth)
    projects = self.metadata_service.list_project_names()

    for project in projects:
        metadata = self.metadata_service.get_project(project)

        # Type-safe access to pull requests
        for pr in metadata.pull_requests:
            reviewer = pr.reviewer  # Type-safe property
            pr_ref = PRReference.from_metadata_pr(pr, project)  # Domain model

            if pr.merged_at:
                stats_by_reviewer[reviewer].add_merged_pr(pr_ref)
            else:
                stats_by_reviewer[reviewer].add_open_pr(pr_ref)

    return stats_by_reviewer
```

**Key improvements:**
- ✅ No `run_gh_command()` calls - uses metadata service
- ✅ No `json.loads()` or dictionary navigation - uses domain models
- ✅ Type-safe `pr.reviewer`, `pr.merged_at` properties
- ✅ `PRReference` domain model encapsulates PR information
- ✅ Single source of truth: metadata updated by merge triggers
- ✅ Cross-project aggregation automatic (all projects in metadata)
- ✅ No GitHub API rate limits for statistics queries

For the complete refactoring process, see `docs/proposed/refactor-statistics-service-architecture.md`.

### Related Documentation

- **GitHub domain models**: `src/claudestep/domain/github_models.py` - `GitHubUser`, `GitHubPullRequest`, `GitHubPullRequestList`
- **GitHub operations**: `src/claudestep/infrastructure/github/operations.py` - `list_pull_requests()`, `list_merged_pull_requests()`, `list_open_pull_requests()`
- **Metadata models**: `src/claudestep/domain/models.py` - `PullRequest`, `PRReference`, `HybridProjectMetadata`
- **Statistics service**: `src/claudestep/services/composite/statistics_service.py` - Uses metadata only, no GitHub API
- **Refactoring documentation**: `docs/proposed/refactor-statistics-service-architecture.md` - Complete refactoring process (Phases 1-9)

---

## Summary

**ClaudeStep Architecture** follows these key principles:

✅ **Service Layer Pattern**: Follows Martin Fowler's pattern with a lightweight, pragmatic approach
✅ **Layered Architecture**: Clear separation between CLI, Service, Domain, and Infrastructure layers
✅ **Python-First**: Business logic in Python, YAML as thin wrapper
✅ **Command Dispatcher**: Single entry point with subcommands
✅ **Multiple Actions**: Organized in subdirectories (`statistics/`, `discovery/`)
✅ **Shared Codebase**: All actions use the same Python package
✅ **Class-Based Services**: Dependency injection, consistent patterns, better testability
✅ **Testable**: Unit tests for Python code, not YAML
✅ **Modular**: Clear separation between commands, models, and utilities

This architecture enables rapid development, easy testing, and maintainable code as the project grows.
