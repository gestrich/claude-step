# Scheduled PR Creation

## Background

Currently, ClaudeChain relies on two triggers to create PRs:
1. **Manual trigger** - User runs workflow via `workflow_dispatch`
2. **Merge trigger** - PR merge with `claudechain` label triggers next task

This works well for continuous chains, but has gaps:
- First PR requires manual trigger (no previous PR to merge)
- If a merge trigger fails, the chain breaks silently
- Projects can stall without anyone noticing

This plan adds a new capability: **scheduled PR creation** that ensures all projects with available capacity have open PRs. Users can run this on a schedule (e.g., daily) to catch any projects that have fallen behind.

**Key principles from architecture docs:**
- Python-first: Minimal YAML, all business logic in Python
- Service layer pattern: CLI orchestrates services, services contain business logic
- Domain models: Parse once into well-formed models
- Fail fast: Raise exceptions for abnormal cases
- **Maximize code reuse**: Avoid duplicate implementations by reusing/extending existing services

## Phases

- [ ] Phase 1: Research existing code for reuse

Before implementing, identify existing code that can be reused or extended. The goal is to avoid duplicate implementations and leverage the existing service layer.

**Areas to investigate:**

1. **Project discovery**
   - Check `StatisticsService.collect_all_statistics()` - already discovers projects
   - Check `ProjectRepository` for existing discovery methods
   - Look for GitHub API calls that list `claude-chain/` directory contents

2. **Capacity checking**
   - Check `ReviewerService` for existing capacity logic
   - Look at how the main workflow determines if a reviewer has capacity
   - Find where `maxOpenPRs` is evaluated against current open PRs

3. **PR creation**
   - Identify the existing PR creation flow in `WorkflowService` or similar
   - Understand how `prepare` and `finalize` commands work together
   - Determine if we can call existing methods or need to create new ones

4. **Task identification**
   - Check `TaskService` for finding the next uncompleted task
   - Look at how spec.md is parsed to find pending tasks

**Files to examine:**
- [src/claudechain/services/composite/statistics_service.py](src/claudechain/services/composite/statistics_service.py) - Project discovery in multi-project mode
- [src/claudechain/services/core/reviewer_service.py](src/claudechain/services/core/reviewer_service.py) - Capacity checking
- [src/claudechain/services/core/task_service.py](src/claudechain/services/core/task_service.py) - Task identification
- [src/claudechain/services/core/pr_service.py](src/claudechain/services/core/pr_service.py) - PR operations
- [src/claudechain/infrastructure/repositories/project_repository.py](src/claudechain/infrastructure/repositories/project_repository.py) - Project loading
- [src/claudechain/cli/commands/prepare.py](src/claudechain/cli/commands/prepare.py) - Existing PR preparation flow

**Output of this phase:**
- Document which existing methods can be reused directly
- Document which methods need minor modifications
- Document what new code is actually needed
- Update subsequent phases based on findings

- [ ] Phase 2: Add `open-prs` CLI command

Create a new CLI command that loops through all projects and opens PRs for those with available capacity.

**Files to create/modify:**
- [src/claudechain/cli/commands/open_prs.py](src/claudechain/cli/commands/open_prs.py) - New command file
- [src/claudechain/cli/main.py](src/claudechain/cli/main.py) - Register new command

**Command signature:**
```bash
python -m claudechain open-prs \
  --repo "owner/repo" \
  --base-branch main \
  --dry-run  # Optional: show what would be created without creating
```

**CLI command implementation:**
```python
def cmd_open_prs(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str = "main",
    anthropic_api_key: str = "",
    claude_model: str = "claude-sonnet-4-5",
    allowed_tools: str = "",
    dry_run: bool = False,
    slack_webhook_url: str = "",
) -> int:
    """Open PRs for all projects with available capacity."""
```

**Output format:**
```
📋 Opening PRs for projects with capacity...

auth-migration:
  Current: 1 open, 2 max capacity
  Action: Opening 1 PR for task "Add JWT verification"

api-cleanup:
  Current: 2 open, 2 max capacity
  Action: No capacity available (skipping)

docs-update:
  Current: 0 open, 1 max capacity
  Action: Opening 1 PR for task "Update API docs"

Summary: Opened 2 PRs, skipped 1 project (at capacity)
```

- [ ] Phase 3: Create `OpenPRsService` composite service

Create a service that orchestrates project discovery and PR creation.

**Files to create:**
- [src/claudechain/services/composite/open_prs_service.py](src/claudechain/services/composite/open_prs_service.py)

**Service design:**
```python
class OpenPRsService:
    """Service for opening PRs across all projects with capacity."""

    def __init__(
        self,
        repo: str,
        project_repository: ProjectRepository,
        pr_service: PRService,
        reviewer_service: ReviewerService,
        task_service: TaskService,
        base_branch: str = "main"
    ):
        pass

    def discover_projects(self) -> List[ProjectConfiguration]:
        """Find all projects in the repository."""
        pass

    def check_project_capacity(
        self, config: ProjectConfiguration
    ) -> ProjectCapacityResult:
        """Check if project has capacity for new PRs."""
        pass

    def open_prs_for_all_projects(
        self, dry_run: bool = False
    ) -> OpenPRsResult:
        """Open PRs for all projects with capacity."""
        pass
```

**Domain models to add:**
```python
@dataclass
class ProjectCapacityResult:
    """Result of checking a project's PR capacity."""
    project_name: str
    current_open_prs: int
    max_capacity: int  # Sum of all reviewers' maxOpenPRs, or global default
    available_slots: int
    has_capacity: bool
    next_task: Optional[str]  # Task description if capacity available

@dataclass
class OpenPRsResult:
    """Result of open-prs operation."""
    projects_checked: int
    prs_opened: int
    projects_skipped: int  # At capacity
    projects_complete: int  # No remaining tasks
    errors: List[str]
    details: List[ProjectCapacityResult]
```

- [ ] Phase 4: Implement project discovery

Use existing infrastructure to discover all projects.

**Implementation approach:**
- Use `ProjectRepository.discover_projects()` if it exists, or create it
- Alternative: Scan for `claude-chain/*/spec.md` files via GitHub API
- Return list of `ProjectConfiguration` objects

**Files to modify:**
- [src/claudechain/infrastructure/repositories/project_repository.py](src/claudechain/infrastructure/repositories/project_repository.py) - Add `discover_projects()` method if needed

**Discovery logic:**
1. List contents of `claude-chain/` directory via GitHub API
2. For each subdirectory, check if `spec.md` exists
3. Load configuration for each discovered project
4. Return list of project configurations

- [ ] Phase 5: Implement capacity checking

Calculate available capacity for each project.

**Capacity calculation:**
1. Load project configuration to get reviewer list
2. For each reviewer, get their `maxOpenPRs` setting
3. Count current open PRs assigned to each reviewer
4. Calculate total capacity: `sum(maxOpenPRs) - current_open_prs`
5. If no reviewers configured, use global default (1 PR max)

**Files to use:**
- `ReviewerService.check_capacity()` - May already have this logic
- `PRService.get_open_prs_for_project()` - Get current open PRs

- [ ] Phase 6: Implement PR creation loop

Create PRs for each project with available capacity.

**Implementation:**
```python
def open_prs_for_all_projects(self, dry_run: bool = False) -> OpenPRsResult:
    result = OpenPRsResult(...)

    projects = self.discover_projects()

    for config in projects:
        capacity = self.check_project_capacity(config)
        result.details.append(capacity)

        if not capacity.has_capacity:
            result.projects_skipped += 1
            continue

        if capacity.next_task is None:
            result.projects_complete += 1
            continue

        if dry_run:
            print(f"  Would open PR for: {capacity.next_task}")
            continue

        # Create PR using existing workflow
        # This is the tricky part - need to trigger actual PR creation
        try:
            self._create_pr_for_project(config, capacity)
            result.prs_opened += 1
        except Exception as e:
            result.errors.append(f"{config.project.name}: {e}")

    return result
```

**PR creation options:**
- Option A: Call existing `WorkflowService` methods directly
- Option B: Shell out to the main workflow command
- Option C: Create minimal PR creation flow

Recommend Option A - reuse existing service layer.

- [ ] Phase 7: Create GitHub Action for scheduled runs

Create a composite action that wraps the `open-prs` command.

**Files to create:**
- [open-prs/action.yml](open-prs/action.yml)

**Action definition:**
```yaml
name: 'ClaudeChain Open PRs'
description: 'Open PRs for all projects with available capacity'

inputs:
  anthropic_api_key:
    description: 'Anthropic API key'
    required: true
  github_token:
    description: 'GitHub token'
    required: true
  base_branch:
    description: 'Base branch for PRs'
    required: false
    default: 'main'
  dry_run:
    description: 'Show what would be created without creating'
    required: false
    default: 'false'
  slack_webhook_url:
    description: 'Slack webhook for notifications'
    required: false

runs:
  using: 'composite'
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    - name: Install dependencies
      shell: bash
      run: pip install -e .
    - name: Open PRs
      shell: bash
      env:
        ANTHROPIC_API_KEY: ${{ inputs.anthropic_api_key }}
        GITHUB_TOKEN: ${{ inputs.github_token }}
      run: |
        python -m claudechain open-prs \
          --repo "${{ github.repository }}" \
          --base-branch "${{ inputs.base_branch }}" \
          ${{ inputs.dry_run == 'true' && '--dry-run' || '' }}
```

- [ ] Phase 8: Add documentation

Document the new scheduled PR creation feature.

**Files to create:**
- [docs/feature-guides/scheduled-prs.md](docs/feature-guides/scheduled-prs.md) - New guide

**Content:**
- Why use scheduled PR creation
- Setting up the workflow file
- Configuration options
- Example cron schedules
- Dry-run mode for testing

**Example workflow for users:**
```yaml
name: ClaudeChain Open PRs

on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8 AM UTC
  workflow_dispatch:
    inputs:
      dry_run:
        description: 'Dry run mode'
        type: boolean
        default: false

permissions:
  contents: write
  pull-requests: write

jobs:
  open-prs:
    runs-on: ubuntu-latest
    steps:
      - uses: gestrich/claude-chain/open-prs@v2
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          dry_run: ${{ github.event.inputs.dry_run || 'false' }}
```

**Files to update:**
- [docs/feature-guides/setup.md](docs/feature-guides/setup.md) - Add reference to scheduled PRs
- [README.md](README.md) - Mention scheduled PR creation in features

- [ ] Phase 9: Validation

**Unit tests:**
- Test `ProjectCapacityResult` calculations
- Test `OpenPRsResult` aggregation
- Test `OpenPRsService.discover_projects()`
- Test `OpenPRsService.check_project_capacity()`
- Test `OpenPRsService.open_prs_for_all_projects()` with mocked services
- Test dry-run mode doesn't create PRs

**Integration tests:**
- Test project discovery against test repository structure
- Test capacity calculation with known reviewer configurations
- Test end-to-end with dry-run flag

**Manual verification:**
- Run `open-prs --dry-run` against test repository
- Verify output shows correct capacity calculations
- Verify discovered projects match expected

**Test commands:**
```bash
# Unit tests
python3 -m pytest tests/unit/services/test_open_prs_service.py -v
python3 -m pytest tests/unit/cli/test_open_prs.py -v

# Dry run test
source .venv/bin/activate && python -m claudechain open-prs \
  --repo "gestrich/claude-chain" \
  --dry-run

# Integration test (creates real PRs - use with caution)
source .venv/bin/activate && python -m claudechain open-prs \
  --repo "gestrich/claude-chain"
```
