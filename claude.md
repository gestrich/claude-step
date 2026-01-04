# Guide for Claude Code

## Before Starting Any Tasks

**Important:** Before working on tasks in this project, please read the following documents once to understand the project structure, workflows, and conventions:

1. **README.md** - Understand what ClaudeChain is, how it works, and how users interact with it
2. **docs/README.md** - Navigate the documentation structure
3. **docs/feature-guides/** - User-facing guides for ClaudeChain features
4. **docs/feature-architecture/** - Technical documentation for specific features
5. **docs/general-architecture/** - General design patterns and coding conventions:
   - Testing philosophy and requirements
   - Service layer pattern
   - Domain model design
   - Python style guide

This context is crucial for making changes that align with the project's design and user expectations.

## Project Overview

ClaudeChain is a GitHub Action that automates code refactoring using AI. It:
- Reads task lists from spec.md files
- Creates incremental PRs for each task
- Manages reviewer assignments and capacity
- Tracks progress automatically

Understanding how users interact with this system will help ensure any changes maintain backward compatibility and improve the user experience.

## Code Architecture

ClaudeChain follows Martin Fowler's **Service Layer pattern** with a layered architecture:

```
┌─────────────────────────────────────────┐
│          CLI Layer                      │  ← Orchestration only
│  (commands: prepare, finalize, etc.)    │
├─────────────────────────────────────────┤
│       Service Layer                     │  ← Business logic
│  Core: PRService, TaskService, etc.     │
│  Composite: StatisticsService, etc.     │
├─────────────────────────────────────────┤
│     Infrastructure Layer                │  ← External integrations
│  (git, github, filesystem)              │
├─────────────────────────────────────────┤
│         Domain Layer                    │  ← Models, exceptions
│  (dataclasses, config, parsing)         │
└─────────────────────────────────────────┘
```

**Key principles:**
- **CLI commands** orchestrate services but contain no business logic
- **Services** encapsulate business operations with constructor-based dependency injection
- **Domain models** parse data once and provide type-safe APIs
- **Infrastructure** wraps external systems (git, GitHub API, filesystem)

## Testing Requirements

**Philosophy:** Test behavior, not implementation. Mock at boundaries, not internals.

**Running tests:**
```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v

# With coverage
pytest tests/unit/ tests/integration/ --cov=src/claudechain --cov-report=term-missing
```

**Requirements:**
- 85%+ overall coverage (CI enforces 70% minimum)
- All new features require tests
- Bug fixes should include regression tests
- Follow Arrange-Act-Assert pattern
- One concept per test (exception: E2E tests)

**What to mock:** External systems only (subprocess, HTTP, file I/O)
**What NOT to mock:** Internal logic, domain models, helper functions

## Code Style

**Method organization:** Public before private, high-level before low-level.

**Dependency injection:** Required dependencies via constructor, no optional dependencies with default factories.

**Configuration:** Flows from entry point (`__main__.py`), never read environment variables in services.

**Fail fast:** Raise exceptions for abnormal cases, don't return empty/default values silently.

**Datetimes:** Always timezone-aware using `datetime.now(timezone.utc)`.

## Common Patterns

**Service instantiation in commands:**
```python
def cmd_prepare(args, gh):
    # 1. Get dependencies
    repo = os.environ.get("GITHUB_REPOSITORY", "")

    # 2. Initialize infrastructure
    metadata_store = GitHubMetadataStore(repo)
    metadata_service = MetadataService(metadata_store)

    # 3. Initialize services
    task_service = TaskService(repo, metadata_service)

    # 4. Use services
    task = task_service.find_next_available_task(spec_content)
```

**Domain models with parsing:**
```python
@dataclass
class ProjectConfiguration:
    @classmethod
    def from_yaml_string(cls, content: str) -> 'ProjectConfiguration':
        # Parse once, validate, return type-safe model
```

**Static vs instance methods:**
- Instance methods: need `self.repo` or perform I/O
- Static methods: pure functions with no state dependency
