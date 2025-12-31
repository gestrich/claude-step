# Refactor Auto-Start Workflow to Python

## Background

The ClaudeStep auto-start workflow (`.github/workflows/claudestep-auto-start.yml`) currently contains significant business logic implemented in bash scripts within the YAML file. This violates ClaudeStep's **Python-first architecture** principle, which states that GitHub Actions YAML files should be lightweight wrappers that invoke Python commands.

According to the architecture documentation (docs/architecture/architecture.md):

> **Convention: Minimal YAML, Maximal Python**
>
> ClaudeStep follows a **Python-first architecture** where:
> - **GitHub Actions YAML files** are lightweight wrappers
> - **Python code** contains all business logic
> - **Actions invoke Python** via `python3 -m claudestep <command>`

Currently, the auto-start workflow includes ~130 lines of bash logic for:
1. Detecting changed spec files (`git diff` parsing)
2. Extracting project names from file paths
3. Querying GitHub API to check if projects are new
4. Triggering workflows for new projects
5. Generating summaries

This logic should live in Python service layers, with the YAML workflow acting only as a thin orchestration layer.

## Phases

- [x] Phase 1: Create domain models for auto-start detection ✅

Create domain models in `src/claudestep/domain/` to represent:
- `AutoStartProject` - Represents a project detected for potential auto-start
- `ProjectChangeType` enum - Added, Modified, Deleted
- `AutoStartDecision` - Whether to trigger, with reason

Files to create:
- `src/claudestep/domain/auto_start.py`

Follow patterns from existing domain models like `domain/project.py` and `domain/spec_content.py`.

**Technical Notes:**
- Created `src/claudestep/domain/auto_start.py` with three models:
  - `ProjectChangeType`: Enum with ADDED, MODIFIED, DELETED values
  - `AutoStartProject`: Dataclass with name, change_type, and spec_path attributes
  - `AutoStartDecision`: Dataclass with project, should_trigger, and reason attributes
- Followed existing patterns from `domain/project.py` and `domain/spec_content.py`
- Used dataclasses for simplicity and immutability
- All models include `__repr__` methods for debugging
- Build passes successfully and module imports correctly

- [x] Phase 2: Add git diff operations to infrastructure layer ✅

Extend existing `src/claudestep/infrastructure/git/operations.py` with new functions:
- `detect_changed_files(ref_before: str, ref_after: str, pattern: str) -> List[str]` - Wrapper around `git diff --name-only --diff-filter=AM`
- `detect_deleted_files(ref_before: str, ref_after: str, pattern: str) -> List[str]` - Wrapper around `git diff --name-only --diff-filter=D`
- `parse_spec_path_to_project(path: str) -> Optional[str]` - Extract project name from `claude-step/*/spec.md` paths

Use existing `run_git_command()` helper for consistent error handling. Follow patterns from the existing functions in this module.

**Technical Notes:**
- Added three new functions to `src/claudestep/infrastructure/git/operations.py`:
  - `detect_changed_files()`: Detects added or modified files using `git diff --name-only --diff-filter=AM`
  - `detect_deleted_files()`: Detects deleted files using `git diff --name-only --diff-filter=D`
  - `parse_spec_path_to_project()`: Parses `claude-step/{project}/spec.md` paths to extract project names
- All functions use the existing `run_git_command()` helper for consistent error handling
- Added `Optional` type import for the parse function return type
- Included comprehensive docstrings with Args, Returns, Raises, and Examples sections
- Functions handle empty git output gracefully by returning empty lists
- Parse function validates path format strictly (must be exactly 3 parts: claude-step/project/spec.md)
- Build passes successfully and all functions import and execute correctly

- [ ] Phase 3: Create composite service for auto-start orchestration

Create composite service in `src/claudestep/services/composite/auto_start_service.py`:
- `AutoStartService` class with dependency injection
- `detect_changed_projects()` - Identify projects with spec.md changes
- `determine_new_projects()` - Check which projects have no existing PRs
- `should_auto_trigger()` - Business logic for auto-start decision

**Why composite service?** Auto-start orchestrates multiple operations across layers:
- Calls core service: `PRService.count_project_prs()` to check for existing PRs
- Calls infrastructure: git diff operations for file change detection
- Aggregates data from multiple sources to make auto-trigger decisions
- This follows the pattern: Composite → Core → Infrastructure

Service should use:
- `PRService` (core service) to check for existing PRs
- Git operations from `infrastructure.git.operations` for file change detection
- Domain models for type-safe returns

Constructor pattern:
```python
class AutoStartService:
    def __init__(self, repo: str, pr_service: PRService):
        self.repo = repo
        self.pr_service = pr_service
```

- [ ] Phase 4: Create CLI command for auto-start detection

Create CLI command in `src/claudestep/cli/commands/auto_start.py`:
- `cmd_auto_start(gh, repo, base_branch, ref_before, ref_after)` function
- Instantiate services with dependencies
- Call service methods to detect projects
- Write GitHub Actions outputs for projects to trigger
- Return exit code

Follow pattern from `cli/commands/prepare.py` and `cli/commands/discover.py`.

Environment variables to read in `__main__.py` adapter layer:
- `GITHUB_REPOSITORY`
- `BASE_BRANCH`
- `GITHUB_SHA` (after commit)
- `GITHUB_SHA_BEFORE` (before commit, from `github.event.before`)

- [ ] Phase 5: Wire up command in __main__.py dispatcher

Add command registration in `src/claudestep/__main__.py`:
- Add `auto-start` subparser
- Add arguments: `--repo`, `--base-branch`, `--ref-before`, `--ref-after`
- Map to `cmd_auto_start()` in dispatcher
- Read environment variables in adapter layer, pass as explicit parameters

Follow pattern from existing commands like `statistics` and `discover`.

- [ ] Phase 6: Create workflow trigger service for GitHub workflow dispatch

Create composite service in `src/claudestep/services/composite/workflow_service.py`:
- `WorkflowService` class
- `trigger_claudestep_workflow()` - Wrapper around `gh workflow run`
- Error handling for workflow trigger failures
- Batch triggering for multiple projects

Use infrastructure layer for `gh` command execution.

- [ ] Phase 7: Add workflow triggering to auto-start command

Extend `cmd_auto_start()` to:
- Use `WorkflowService` to trigger workflows for new projects
- Pass `project_name`, `base_branch`, `checkout_ref` parameters
- Collect failed triggers
- Write summary outputs (success count, failure count, failed projects)

Update GitHub Actions outputs to include:
- `triggered_projects` - Space-separated list
- `failed_projects` - Space-separated list
- `trigger_count` - Number of successful triggers

- [ ] Phase 8: Refactor YAML workflow to use Python command

Simplify `.github/workflows/claudestep-auto-start.yml`:

**Before** (current):
```yaml
steps:
  - name: Detect changed spec files
    id: detect
    run: |
      # 60+ lines of bash logic

  - name: Check if projects are new
    id: check_new
    run: |
      # 40+ lines of bash logic

  - name: Trigger ClaudeStep
    run: |
      # 20+ lines of bash logic
```

**After** (refactored):
```yaml
steps:
  - name: Setup Python
    uses: actions/setup-python@v5
    with:
      python-version: '3.11'

  - name: Detect and trigger auto-start
    id: auto_start
    run: python3 -m claudestep auto-start
    env:
      GITHUB_REPOSITORY: ${{ github.repository }}
      BASE_BRANCH: main
      REF_BEFORE: ${{ github.event.before }}
      REF_AFTER: ${{ github.sha }}
      GH_TOKEN: ${{ github.token }}

  - name: Generate summary
    if: always()
    run: python3 -m claudestep auto-start-summary
    env:
      TRIGGERED_PROJECTS: ${{ steps.auto_start.outputs.triggered_projects }}
      FAILED_PROJECTS: ${{ steps.auto_start.outputs.failed_projects }}
```

Move all bash logic to Python. YAML only:
- Sets up environment
- Invokes Python commands
- Passes parameters via environment variables

- [ ] Phase 9: Add auto-start summary command

Create `cmd_auto_start_summary()` in `src/claudestep/cli/commands/auto_start.py`:
- Read outputs from auto-start step
- Generate GitHub Actions step summary
- Format markdown summary showing:
  - Projects detected
  - Projects auto-triggered
  - Projects skipped (with reasons)
  - Any failures

Keep summary generation in Python, not bash.

- [ ] Phase 10: Add configuration option to disable auto-start

Add check in `AutoStartService.should_auto_trigger()`:
- Read repository variable `CLAUDESTEP_AUTO_START_ENABLED`
- Default to `true` if not set
- Return early with reason if disabled

Update workflow to pass environment variable:
```yaml
env:
  AUTO_START_ENABLED: ${{ vars.CLAUDESTEP_AUTO_START_ENABLED != 'false' }}
```

Document in README.md how to disable via repository variables.

- [ ] Phase 11: Add unit tests for auto-start service

Create test file `tests/unit/services/composite/test_auto_start_service.py`:
- Test `detect_changed_projects()` with various git diff outputs
- Test `determine_new_projects()` with existing/no existing PRs
- Test `should_auto_trigger()` decision logic
- Test disabled auto-start configuration
- Mock `PRService` (core service dependency) and git operations (infrastructure)

Follow patterns from `tests/unit/services/composite/test_statistics_service.py` for mocking service dependencies.

- [ ] Phase 12: Add integration tests for auto-start command

Create test file `tests/integration/cli/test_auto_start.py`:
- Test `cmd_auto_start()` with mocked services
- Test GitHub Actions output writing
- Test error handling for failed workflow triggers
- Verify correct service instantiation

Follow patterns from `tests/integration/cli/test_prepare.py`.

- [ ] Phase 13: Update architecture documentation

Update `docs/architecture/architecture.md`:
- Add `auto-start` to command dispatcher table
- Document `AutoStartService` in composite services section (alongside `StatisticsService` and `ArtifactService`)
- Update auto-start workflow section to reflect Python-first implementation
- Add example showing minimal YAML, maximal Python
- Note dependency direction: `AutoStartService` (composite) → `PRService` (core) → infrastructure

Add to "Available Commands" table:
```markdown
| `auto-start` | Detect new projects and trigger workflows | Auto-Start workflow |
```

- [ ] Phase 14: Validation - E2E testing

Test the refactored auto-start workflow end-to-end:
1. Create test project in `claude-step/test-auto-start-refactor/`
2. Push spec.md to main branch
3. Verify auto-start workflow runs successfully
4. Verify first task PR is created
5. Verify summary shows correct detection and triggering
6. Clean up test project

Run existing E2E tests to ensure no regressions:
```bash
./tests/e2e/run_test.sh
```

## Technical Considerations

### Service Layer Architecture

Following ClaudeStep's layered architecture:

**Infrastructure Layer** (`infrastructure/git/operations.py`):
- Extends existing git operations module with diff detection functions
- Wraps git commands using existing `run_git_command()` helper
- No business logic, just command execution
- Returns raw data (file paths, change types)

**Domain Layer** (`domain/auto_start.py`):
- Models: `AutoStartProject`, `ProjectChangeType`, `AutoStartDecision`
- Pure data structures with validation
- No external dependencies

**Service Layer - Composite** (`services/composite/auto_start_service.py`):
- Orchestrates multi-step auto-start workflow
- Coordinates git operations (infrastructure) and PR queries (core service)
- Depends on `PRService` (core service) for PR existence checks
- Aggregates data from multiple sources (git diff + GitHub API)
- Returns domain models with business decisions

**CLI Layer** (`cli/commands/auto_start.py`):
- Orchestrates service calls
- Reads environment variables (via `__main__.py` adapter)
- Writes GitHub Actions outputs
- No business logic

### Python-First Benefits

Moving logic to Python provides:
1. **Testability** - Unit test business logic independently
2. **Type Safety** - Type hints catch errors at development time
3. **Maintainability** - Easier to read and refactor than bash
4. **Reusability** - Services can be used by other commands
5. **Local Development** - Run and debug without GitHub Actions
6. **Consistency** - Follows same patterns as other ClaudeStep commands

### Backward Compatibility

The refactoring maintains the same workflow triggers and behavior:
- Same `on.push.paths` triggers
- Same detection logic (git diff filtering)
- Same PR query logic (branch name patterns)
- Same workflow triggering mechanism
- Same summary generation

Users should see no functional changes, only improved maintainability.

### Configuration Flow

Following Python code style guide principles:
- Environment variables read only in `__main__.py` adapter layer
- CLI commands receive explicit parameters
- Services receive configuration via constructor or method parameters
- No services read `os.environ.get()` directly

Example:
```python
# __main__.py - Adapter layer
elif args.command == "auto-start":
    return cmd_auto_start(
        gh=gh,
        repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
        base_branch=args.base_branch or os.environ.get("BASE_BRANCH", "main"),
        ref_before=args.ref_before or os.environ.get("REF_BEFORE", ""),
        ref_after=args.ref_after or os.environ.get("REF_AFTER", "")
    )
```

### Error Handling

Services should:
- Raise domain exceptions for business errors
- Let infrastructure exceptions bubble up
- CLI command catches exceptions, logs, and returns error codes

Example:
```python
class AutoStartService:
    def determine_new_projects(self, projects: List[AutoStartProject]) -> List[AutoStartProject]:
        new_projects = []
        for project in projects:
            try:
                pr_count = self.pr_service.count_project_prs(project.name)
                if pr_count == 0:
                    new_projects.append(project)
            except GitHubAPIError as e:
                # Log warning, skip project on API failure
                print(f"⚠️  Error querying GitHub API for {project.name}: {e}")
                continue
        return new_projects
```

### Testing Strategy

**Unit Tests** (services, domain models):
- Mock all dependencies (PRService, git operations)
- Test business logic in isolation
- Fast, no external dependencies

**Integration Tests** (CLI commands):
- Mock subprocess calls to `gh` and `git`
- Test service instantiation and orchestration
- Verify GitHub Actions output format

**E2E Tests** (full workflow):
- Use actual GitHub repository
- Trigger real workflow runs
- Verify PRs created as expected

## Related Documentation

- **Architecture**: `docs/architecture/architecture.md` - Python-first approach, service layer pattern
- **Code Style**: `docs/architecture/python-code-style.md` - Configuration flow, dependency injection
- **Auto-Start**: Current implementation in `.github/workflows/claudestep-auto-start.yml`
- **Similar Refactoring**: `docs/completed/refactor-statistics-service-architecture.md` - Example of YAML→Python migration
