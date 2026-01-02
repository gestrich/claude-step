# Optional Configuration File

## Background

Currently, ClaudeStep requires a `configuration.yml` file for every project. This file serves two purposes:
1. **Project discovery** - Projects are identified by the presence of `configuration.yml`
2. **Reviewer configuration** - Defines who reviews PRs and their capacity limits

This requirement creates friction for simple use cases where users just want to automate tasks without managing reviewer assignments. We want to:

1. **Make configuration optional** - Projects should work with sensible defaults
2. **Discover projects by spec.md** - The spec file is the true definition of a project, not the config
3. **Provide default configuration** - When no config exists, use defaults:
   - No reviewer assigned (PRs created without assignee)
   - Global per-project limit of 1 open PR at a time

This simplifies onboarding: users can create just a `spec.md` file and start using ClaudeStep immediately.

## Phases

- [ ] Phase 1: Change project discovery to use spec.md

**Goal**: Projects are discovered by the presence of `spec.md`, not `configuration.yml`.

**Files to modify**:
- `src/claudestep/domain/project.py` - Update `Project.find_all()` to look for `spec.md`
- `src/claudestep/cli/commands/discover.py` - Update discovery logic if it has separate implementation

**Changes**:
- Scan `claude-step/*/` directories for `spec.md` instead of `configuration.yml`
- A project exists if it has a `spec.md` file (config becomes optional)
- Update any path properties that assume config existence

**Tests to update**:
- `tests/unit/domain/test_project.py` - Update discovery tests

---

- [ ] Phase 2: Create default configuration model

**Goal**: Define a default `ProjectConfiguration` that's used when no config file exists.

**Files to modify**:
- `src/claudestep/domain/project_configuration.py` - Add `ProjectConfiguration.default()` class method

**Default values**:
```python
@classmethod
def default(cls, project: Project) -> "ProjectConfiguration":
    """Return default configuration when no config file exists."""
    return cls(
        project=project,
        reviewers=[],  # No reviewers - PRs created without assignee
        base_branch=None  # Use workflow context branch
    )
```

**Tests to add**:
- Test `ProjectConfiguration.default()` returns expected values
- Test that default config has empty reviewers list

---

- [ ] Phase 3: Update ProjectRepository to return defaults when config missing

**Goal**: `load_configuration()` returns default config instead of `None` when file doesn't exist.

**Files to modify**:
- `src/claudestep/infrastructure/repositories/project_repository.py`

**Changes**:
- When `get_file_from_branch()` returns `None` for config, return `ProjectConfiguration.default(project)`
- Add optional parameter `require_config: bool = False` to allow callers to get `None` if they need to distinguish

**Tests to update**:
- Update repository tests to expect default config instead of `None`

---

- [ ] Phase 4: Implement global per-project PR limit

**Goal**: When no reviewers configured, enforce max 1 open PR per project globally.

**Files to modify**:
- `src/claudestep/services/core/reviewer_service.py` - Add logic for no-reviewer case
- `src/claudestep/services/core/pr_service.py` - May need method to count open PRs for project

**Changes**:
- In `find_available_reviewer()`:
  - If `config.reviewers` is empty, check global project PR count
  - If project has < 1 open PR, return `None` (no reviewer) but allow PR creation
  - If project has >= 1 open PR, return indication that capacity is exhausted
- Update return type or add new method to handle "no reviewer but has capacity" case

**New behavior**:
```python
def find_available_reviewer(self, config, project, label):
    if not config.reviewers:
        # No reviewers configured - use global project limit
        open_pr_count = self.pr_service.get_open_pr_count_for_project(project, label)
        if open_pr_count >= 1:  # Default limit
            return None, False  # No capacity
        return None, True  # No reviewer, but has capacity
    # ... existing reviewer logic
```

**Tests to add**:
- Test no-reviewer case with 0 open PRs returns capacity available
- Test no-reviewer case with 1+ open PRs returns no capacity

---

- [ ] Phase 5: Update prepare command to handle no-reviewer case

**Goal**: PRs can be created without an assignee when no reviewer is configured.

**Files to modify**:
- `src/claudestep/cli/commands/prepare.py`

**Changes**:
- Remove/update the check that fails when `config.reviewers` is empty (lines 126-127)
- When `reviewer_service.find_available_reviewer()` returns no reviewer but has capacity:
  - Set `reviewer` output to empty string
  - Continue with PR creation (finalize will create PR without assignee)
- Update capacity exhaustion message for no-reviewer case

**Current code to change**:
```python
# REMOVE or UPDATE this check:
if not config.reviewers:
    raise ConfigurationError("Missing required field: reviewers")
```

**Tests to update**:
- Test prepare succeeds with empty reviewers list
- Test prepare respects global PR limit when no reviewers

---

- [ ] Phase 6: Update finalize command to create PR without assignee

**Goal**: PRs are created without `--assignee` flag when reviewer is empty.

**Files to modify**:
- `src/claudestep/cli/commands/finalize.py`
- `src/claudestep/infrastructure/github/operations.py` - If PR creation is there

**Changes**:
- When `reviewer` is empty/None, omit `--assignee` from `gh pr create` command
- Ensure PR is still created with correct labels and base branch

**Tests to update**:
- Test PR creation without assignee
- Verify `gh pr create` command doesn't include `--assignee` when reviewer is empty

---

- [ ] Phase 7: Update statistics and other commands for optional config

**Goal**: Commands that use configuration handle the default case gracefully.

**Files to modify**:
- `src/claudestep/services/composite/statistics_service.py`
- `src/claudestep/cli/commands/discover_ready.py`
- Any other commands that load configuration

**Changes**:
- Statistics: Handle projects with no reviewers (show "No reviewers configured" or skip reviewer stats)
- discover_ready: Projects with default config should be discoverable
- Ensure no command crashes when config has empty reviewers

**Tests to update**:
- Test statistics with default-config projects
- Test discover_ready finds projects without config files

---

- [ ] Phase 8: Update documentation

**Goal**: Documentation reflects that configuration is optional.

**Files to modify**:
- `README.md` - Update setup instructions to show config is optional
- `docs/feature-guides/getting-started.md` - Simplify quick start
- `docs/feature-architecture/github-integration.md` - Update if needed

**Documentation changes**:
- Show minimal setup with just `spec.md`
- Explain when/why to add `configuration.yml` (multiple reviewers, custom limits)
- Document default behavior (no assignee, 1 PR limit)

---

- [ ] Phase 9: Validation

**Automated tests**:
```bash
# Run all unit and integration tests
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v

# Specifically run config-related tests
PYTHONPATH=src:scripts pytest tests/unit/domain/test_project.py -v
PYTHONPATH=src:scripts pytest tests/unit/domain/test_project_configuration.py -v
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_prepare.py -v
```

**Manual verification** (if E2E needed):
- Create a test project with only `spec.md` (no config)
- Trigger workflow manually
- Verify PR is created without assignee
- Verify second task is blocked until first PR is merged

**Success criteria**:
- All existing tests pass
- New tests for default configuration pass
- Projects discovered by `spec.md` presence
- PRs created without assignee when no config
- Global 1-PR limit enforced for no-config projects
