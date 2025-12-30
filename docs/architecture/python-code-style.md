# Python Code Style Guide

## Service Layer Organization

This document describes the organizational principles and patterns used for Python code in the ClaudeStep project, particularly for service classes.

## Method Organization Principles

All service classes follow a consistent organization pattern to improve readability and maintainability:

### 1. Public Before Private

Public methods (part of the API) appear before private/internal methods (prefixed with `_`). This allows developers to understand the public API of each service at a glance without scrolling through implementation details.

### 2. High-Level Before Low-Level

More abstract, higher-level operations come before detailed implementation helpers. This creates a natural reading flow from "what the service does" to "how it does it."

### 3. Logical Grouping

Related methods are grouped together with clear section comments. This helps developers quickly navigate to the functionality they need.

### 4. Standard Order

Methods follow this ordering:
1. Special methods (`__init__`, `__str__`, etc.)
2. Class methods (`@classmethod`)
3. Static methods (`@staticmethod`)
4. Instance methods (public, then private)

## Section Headers

Use clear section comments to separate different types of methods:

```python
class MyService:
    def __init__(self):
        """Constructor always comes first."""
        pass

    # Public API methods
    def high_level_operation(self):
        """Main public methods in order of abstraction level."""
        pass

    def mid_level_operation(self):
        """Supporting public methods."""
        pass

    # Static utility methods
    @staticmethod
    def utility_function():
        """Static utilities at the end."""
        pass

    # Private helper methods
    def _internal_helper(self):
        """Private implementation details last."""
        pass
```

For services with many methods, use more descriptive section headers with separators:

```python
class ComplexService:
    def __init__(self):
        pass

    # ============================================================
    # Core CRUD Operations
    # ============================================================

    def create_resource(self):
        pass

    def get_resource(self):
        pass

    # ============================================================
    # Query Operations
    # ============================================================

    def find_resources(self):
        pass

    # ============================================================
    # Utility Operations
    # ============================================================

    @staticmethod
    def parse_identifier(text: str):
        pass
```

## Environment Variables and Configuration

### Principle: Services Should Not Read Environment Variables

Service classes and their methods should **never** read environment variables directly using `os.environ.get()`. All environment variable access should happen at the **entry point layer** (CLI commands, web handlers, etc.) and be passed explicitly as constructor or method parameters.

### Anti-Pattern (❌ Avoid)

```python
# BAD: Service reads environment variables directly
class StatisticsService:
    def __init__(self, repo: str, metadata_service: MetadataService):
        self.repo = repo
        self.metadata_service = metadata_service

    def collect_all_statistics(self, config_path: Optional[str] = None):
        # ❌ Hidden dependency on environment
        base_branch = os.environ.get("BASE_BRANCH", "main")
        label = "claudestep"
        # ... rest of implementation
```

**Problems with this approach:**
- **Hidden dependencies**: Not obvious from the API what environment variables are needed
- **Poor testability**: Tests must mock environment variables
- **Tight coupling**: Service is coupled to the deployment environment
- **Hard to reuse**: Can't easily use the service in different contexts
- **Inconsistent**: Mixes explicit parameters with implicit environment access

### Recommended Pattern (✅ Use This)

```python
# GOOD: Service receives all configuration explicitly
class StatisticsService:
    def __init__(
        self,
        repo: str,
        metadata_service: MetadataService,
        base_branch: str = "main"
    ):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            metadata_service: MetadataService instance for accessing metadata
            base_branch: Base branch to fetch specs from (default: "main")
        """
        self.repo = repo
        self.metadata_service = metadata_service
        self.base_branch = base_branch  # ✅ Stored as instance variable

    def collect_all_statistics(
        self,
        config_path: Optional[str] = None,
        label: str = "claudestep"
    ):
        """Collect statistics for all projects

        Args:
            config_path: Optional path to specific config
            label: GitHub label for filtering (default: "claudestep")
        """
        # ✅ Uses instance variables, no environment access
        base_branch = self.base_branch
        # ... rest of implementation
```

**Adapter layer in `__main__.py` handles ALL environment variable reading:**

```python
# In __main__.py - Adapter layer reads environment variables and CLI args
elif args.command == "statistics":
    return cmd_statistics(
        gh=gh,
        repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        base_branch=args.base_branch or os.environ.get("BASE_BRANCH", "main"),
        config_path=args.config_path or os.environ.get("CONFIG_PATH"),
        days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30")),
        format_type=args.format or os.environ.get("STATS_FORMAT", "slack"),
        slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", "")
    )

# In cli/commands/statistics.py - Command receives explicit parameters
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str = "main",
    config_path: Optional[str] = None,
    days_back: int = 30,
    format_type: str = "slack",
    slack_webhook_url: str = ""
) -> int:
    """Orchestrate statistics workflow."""
    # ✅ Passes everything explicitly to service
    metadata_store = GitHubMetadataStore(repo)
    metadata_service = MetadataService(metadata_store)
    statistics_service = StatisticsService(repo, metadata_service, base_branch)

    # ✅ Uses parameters directly - no environment access
    report = statistics_service.collect_all_statistics(
        config_path=config_path if config_path else None
    )
```

### Benefits

✅ **Explicit dependencies**: Constructor signature shows exactly what the service needs

✅ **Easy testing**: Just pass test values - no environment mocking needed
```python
# Testing is straightforward
service = StatisticsService("owner/repo", mock_metadata, base_branch="develop")
```

✅ **Separation of concerns**: CLI handles environment, service handles business logic

✅ **Reusability**: Service works in any context (CLI, web app, scripts, tests)

✅ **Type safety**: IDEs can autocomplete and type-check parameters

✅ **Self-documenting**: API clearly shows what configuration is needed

### When to Use Constructor vs Method Parameters

**Use constructor parameters for:**
- Configuration that applies to all operations (e.g., `repo`, `base_branch`)
- Dependencies/services that won't change (e.g., `metadata_service`)
- Settings that define the service's behavior globally

**Use method parameters for:**
- Operation-specific values that vary per call (e.g., `config_path`, `days_back`)
- Optional filters or constraints (e.g., `label`)
- Values that might differ between invocations

### Exception: Environment Variables in Infrastructure Layer

The **only** layer that should read environment variables is the **infrastructure layer** - specifically for connecting to external systems:

```python
# OK: Infrastructure layer for GitHub API connections
class GitHubMetadataStore:
    def __init__(self, repo: str, token: Optional[str] = None):
        self.repo = repo
        # ✅ OK here: Infrastructure layer connecting to external system
        self.token = token or os.environ.get("GITHUB_TOKEN")
```

Even here, prefer explicit parameters with environment variables as fallback defaults.

## CLI Command Pattern

### Principle: Commands Use Explicit Parameters, Not Environment Variables

CLI command functions should receive explicit parameters and never read environment variables directly. The adapter layer in `__main__.py` is responsible for translating CLI arguments and environment variables into parameters.

### Architecture Layers

```
GitHub Actions (env vars) → __main__.py (adapter) → commands (params) → services (params)
```

Only `__main__.py` reads environment variables in the CLI layer.

### Anti-Pattern (❌ Avoid)

```python
# BAD: Command reads environment variables
def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")  # Don't do this!
    config_path = args.config_path  # Mixing args and env is confusing
```

**Problems:**
- Hidden dependencies on environment variables
- Awkward local usage (must set env vars)
- Poor type safety with Namespace
- Harder to test

### Recommended Pattern (✅ Use This)

```python
# In cli/parser.py
parser_statistics.add_argument("--repo", help="GitHub repository (owner/name)")
parser_statistics.add_argument("--config-path", help="Path to configuration file")
parser_statistics.add_argument("--days-back", type=int, default=30)

# In cli/commands/statistics.py - Pure function with explicit parameters
def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    config_path: Optional[str] = None,
    days_back: int = 30
) -> int:
    """Orchestrate statistics workflow.

    Args:
        gh: GitHub Actions helper instance
        repo: GitHub repository (owner/name)
        config_path: Optional path to configuration file
        days_back: Days to look back for statistics

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Use parameters directly - no environment access!
    metadata_store = GitHubMetadataStore(repo)
    ...

# In __main__.py - Adapter layer
elif args.command == "statistics":
    return cmd_statistics(
        gh=gh,
        repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        config_path=args.config_path or os.environ.get("CONFIG_PATH"),
        days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30"))
    )
```

**Benefits:**
- ✅ Explicit dependencies: Function signature shows exactly what's needed
- ✅ Type safety: IDEs can autocomplete and type-check
- ✅ Easy testing: Just pass parameters, no environment mocking
- ✅ Works for both GitHub Actions and local development
- ✅ Discoverable: `--help` shows all options

## Module-Level Code

For modules with functions rather than classes (like `artifact_operations_service.py`), use this order:

1. **Dataclasses and models** (public before private)
2. **Public API functions** (high-level to low-level)
3. **Module utilities** (helper functions used by the public API)
4. **Private helper functions** (prefixed with `_`)

Example:

```python
# Public models
@dataclass
class ProjectArtifact:
    """Public dataclass."""
    pass

# Public API functions
def find_artifacts():
    """Highest-level public function."""
    pass

def get_artifact_details():
    """Mid-level public function."""
    pass

# Module utilities
def parse_artifact_name(name: str):
    """Utility function."""
    pass

# Private helper functions
def _fetch_from_api():
    """Private implementation detail."""
    pass
```

## Benefits

This organizational approach provides:

- **Easier onboarding**: New developers can quickly understand what a service does by reading public methods first
- **Better maintainability**: Clear separation between public contracts and implementation details
- **Intuitive navigation**: Developers can find methods more quickly with consistent structure
- **Clearer API boundaries**: Public vs. private methods are visually distinct

## Examples

See the following services for reference implementations:

- [task_management_service.py](../../src/claudestep/application/services/task_management_service.py) - Simple service with public API and static utilities
- [metadata_service.py](../../src/claudestep/application/services/metadata_service.py) - Complex service with multiple logical sections
- [artifact_operations_service.py](../../src/claudestep/application/services/artifact_operations_service.py) - Module-level functions and dataclasses

## Related Documentation

- See [docs/completed/reorganize-service-methods.md](../completed/reorganize-service-methods.md) for the history of applying these principles to the codebase
