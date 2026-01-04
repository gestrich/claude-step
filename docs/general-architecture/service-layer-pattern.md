# Service Layer Pattern

## Overview

ClaudeChain follows Martin Fowler's **Service Layer pattern** from "Patterns of Enterprise Application Architecture" (2002). This architectural pattern defines the application's boundary with a layer of services that establishes available operations and coordinates responses.

**Reference**: [Service Layer - Martin Fowler's PoEAA Catalog](https://martinfowler.com/eaaCatalog/serviceLayer.html)

## What is Service Layer?

From Fowler's catalog:

> "Defines an application's boundary with a layer of services that establishes a set of available operations and coordinates the application's response in each operation."

The Service Layer pattern:
- **Encapsulates business logic** in service classes
- **Coordinates operations** across domain and infrastructure layers
- **Provides a unified API** for different client types (CLI, API, etc.)
- **Manages transactions** and orchestrates responses

## ClaudeChain's Implementation

ClaudeChain implements Service Layer with a **lightweight, pragmatic approach**:

✅ **We follow the spirit, not the letter** - Rough alignment with Fowler's principles, not dogmatic adherence
✅ **Service classes encapsulate business logic** - All operations coordinated through services
✅ **Layered architecture** - Clear separation between CLI, Service, Domain, and Infrastructure
✅ **Dependency injection** - Services receive dependencies via constructors
✅ **Python-first** - No framework overhead, just well-organized Python classes

❌ **We don't enforce strict boundaries** - Services can call infrastructure directly when practical
❌ **No transaction management** - Operations are simple enough not to require transaction coordination
❌ **No complex service contracts** - Services use simple Python methods, not formal interfaces

## Layer Responsibilities

ClaudeChain's architecture consists of four layers:

### 1. CLI Layer (`cli/`)
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

### 2. Service Layer (`services/`)
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

### 3. Domain Layer (`domain/`)
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

### 4. Infrastructure Layer (`infrastructure/`)
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

## Service Class Conventions

All services in ClaudeChain follow consistent patterns:

### Constructor-Based Dependency Injection
```python
class ServiceName:
    def __init__(self, repo: str, metadata_service: MetadataService):
        """Initialize service with required dependencies."""
        self.repo = repo
        self.metadata_service = metadata_service
```

### Services Encapsulate Related Operations
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

### Services Can Depend on Other Services and Infrastructure
```python
class StatisticsService:
    def __init__(self, repo: str, metadata_service: MetadataService, base_branch: str = "main"):
        self.repo = repo
        self.metadata_service = metadata_service  # Service dependency
        self.base_branch = base_branch  # Configuration

    def collect_project_stats(self, project: str) -> ProjectStats:
        # Uses infrastructure directly with instance config
        spec_content = get_file_from_branch(self.repo, self.base_branch, f"claude-chain/{project}/spec.md")

        # Uses other services
        metadata = self.metadata_service.get_project(project)

        # Business logic
        return self._aggregate_statistics(spec_content, metadata)
```

### Commands Orchestrate Services, Don't Implement Business Logic
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

## Benefits of Service Layer Approach

1. **Clear Separation of Concerns** - Each layer has distinct responsibilities
2. **Testability** - Services can be tested independently with mocked dependencies
3. **Reusability** - Multiple commands can use the same services
4. **Maintainability** - Business logic consolidated in service classes, not scattered across commands
5. **Consistency** - All services follow the same architectural pattern
6. **Flexibility** - Easy to add new operations or refactor without changing CLI interface

## Example: Full Stack for Task Preparation

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

## Service Layer Organization

### Convention: Two-Level Service Architecture

ClaudeChain organizes services into **two architectural levels**:

**Core Services** (`services/core/`) provide foundational operations for specific domain areas (PRs, tasks, reviewers, projects). These are building blocks with minimal dependencies that can be used independently or composed together. Examples include `PRService`, `TaskService`, `ReviewerService`, and `ProjectService`.

**Composite Services** (`services/composite/`) orchestrate complex multi-step operations by coordinating multiple core services. They aggregate data from various sources and implement higher-level business logic. Examples include `StatisticsService` and `ArtifactService`.

This organization provides clear dependency direction (Composite → Core → Infrastructure), makes the architecture visible in the filesystem, and enables independent testing of each layer. For implementation details, see the service source code in [`src/claudechain/services/`](../../src/claudechain/services/).

## Available Services

### Core Services (`src/claudechain/services/core/`)

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

### Composite Services (`src/claudechain/services/composite/`)

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
   - Instance methods: `trigger_claudechain_workflow()`, `batch_trigger_claudechain_workflows()`
   - Uses infrastructure layer for `gh` command execution

### Infrastructure Services (`src/claudechain/infrastructure/`)

9. **MetadataService** - Project and artifact metadata management
   - Constructor: `__init__(self, metadata_store: GitHubMetadataStore)`
   - Instance methods: `get_project()`, `save_project()`, `update_project()`, `get_artifact()`, `save_artifact()`

## Service Instantiation in CLI Commands

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

## Static vs Instance Methods

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

## Testing Services

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
    with patch('claudechain.cli.commands.prepare.ProjectService') as MockProject:
        with patch('claudechain.cli.commands.prepare.TaskService') as MockTask:
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
