# Flat Spec Directory Structure

## Background

The current ClaudeStep project structure requires specs to be organized as:
```
claude-step/
├── project-a/
│   ├── spec.md
│   └── configuration.yml  (optional)
├── project-b/
│   ├── spec.md
│   └── configuration.yml  (optional)
```

This nested structure has limitations:
- Forces a specific directory name (`claude-step/`)
- Requires one subdirectory per project
- Requires the spec file to be named `spec.md`

The new approach allows users to specify **flat directories** for specs and configs:

```
# User chooses any directory names
my-specs/
├── auth-migration.md      → project name: "auth-migration"
├── api-cleanup.md         → project name: "api-cleanup"
└── refactor-tests.md      → project name: "refactor-tests"

my-configs/                 (optional)
├── auth-migration.yml     → config for "auth-migration"
└── api-cleanup.yml        → config for "api-cleanup"
```

**Key changes:**
1. **Workflow inputs define directories** - `spec_directory` (required) and `config_directory` (optional)
2. **Project name from filename** - `my-project.md` → project name `my-project`
3. **Config matched by name** - `my-project.yml` in config directory matches `my-project.md` spec
4. **PR template matched by name** - `my-project-pr-template.md` in config directory (optional)
5. **Same directory allowed** - User can set both inputs to the same directory if desired
6. **All `.md` files are specs** - Must contain valid task checkboxes or error is thrown
7. **Manual trigger by project name** - `workflow_dispatch` still accepts `project_name` for single-project runs

This simplifies setup and gives users full control over their directory structure.

**Breaking change**: This is a v3 breaking change. Existing `claude-step/{project}/` structures will not work without migration.

## Phases

- [ ] Phase 1: Update workflow inputs and action.yml

**Goal**: Add new inputs for spec and config directories.

**Files to modify**:
- `action.yml` - Add inputs, update environment variable passing

**Changes**:
- Add `spec_directory` input (required, no default)
- Add `config_directory` input (optional, default empty)
- Keep `project_name` input for `workflow_dispatch` manual triggers (optional, runs single project if provided)
- Pass new inputs as environment variables to Python commands

**New inputs**:
```yaml
inputs:
  spec_directory:
    description: 'Directory containing spec files (*.md). Each file is a project.'
    required: true
  config_directory:
    description: 'Directory containing config files (*.yml, *-pr-template.md). Optional. Matched by project name.'
    required: false
    default: ''
  project_name:
    description: 'Optional: Run only this project (for manual workflow_dispatch triggers)'
    required: false
    default: ''
```

---

- [ ] Phase 2: Update Project domain model

**Goal**: Change how projects are identified and how paths are computed.

**Files to modify**:
- `src/claudestep/domain/project.py`

**Changes**:
- Update `Project` dataclass to store:
  - `name: str` - Project name (derived from filename without extension)
  - `spec_directory: str` - Directory containing spec files
  - `config_directory: Optional[str]` - Directory containing config files (may be None)
- Update path properties:
  - `spec_path` → `{spec_directory}/{name}.md`
  - `config_path` → `{config_directory}/{name}.yml` if config_directory set, else `None`
  - `pr_template_path` → `{config_directory}/{name}-pr-template.md` if config_directory set, else `None`
- Add factory method for cleaner construction:
  ```python
  @classmethod
  def from_spec_file(cls, spec_path: str, config_directory: Optional[str]) -> "Project":
      """Create Project from a spec file path."""
      name = Path(spec_path).stem
      spec_directory = str(Path(spec_path).parent)
      return cls(name=name, spec_directory=spec_directory, config_directory=config_directory)
  ```

**Tests to update**:
- `tests/unit/domain/test_project.py` - Update for new structure

---

- [ ] Phase 3: Update ProjectConfiguration for new paths

**Goal**: Configuration loading works with new path structure.

**Files to modify**:
- `src/claudestep/domain/project_configuration.py`

**Changes**:
- `from_yaml_string()` remains unchanged (parses content)
- Ensure it handles being called with `None` content gracefully (returns default)

**Tests to update**:
- `tests/unit/domain/test_project_configuration.py`

---

- [ ] Phase 4: Update ProjectRepository for new discovery

**Goal**: Repository loads specs and configs from flat directories.

**Files to modify**:
- `src/claudestep/infrastructure/repositories/project_repository.py`

**Changes**:
- Update `load_spec()` to use `project.spec_path` (which now uses spec_directory)
- Update `load_configuration()` to:
  - Return default config if `project.config_path` is `None`
  - Return default config if file doesn't exist
  - Parse file if it exists
- Add `discover_projects(spec_directory: str, config_directory: Optional[str]) -> List[Project]`:
  - List `*.md` files in spec_directory via GitHub API
  - Handle pagination for directories with many files
  - Create Project instances with appropriate directories
- Add `load_pr_template()` to load PR template from `{config_directory}/{name}-pr-template.md`
  - Return default template if file doesn't exist
  - Return default template if `config_directory` is None

**Tests to update**:
- `tests/unit/infrastructure/repositories/test_project_repository.py`

---

- [ ] Phase 5: Add spec file validation

**Goal**: Ensure all `.md` files in spec_directory are valid specs with task checkboxes.

**Files to modify**:
- `src/claudestep/domain/spec_content.py` - Add validation method

**Changes**:
- Add `validate()` method to `SpecContent` that raises `InvalidSpecError` if:
  - No task checkboxes found (`- [ ]` or `- [x]`)
  - File is empty
- Call validation during project discovery
- Raise clear error message: `"Invalid spec file '{filename}': No task checkboxes found. Spec files must contain at least one task in format '- [ ] Task description'"`

**New exception**:
```python
class InvalidSpecError(ClaudeStepError):
    """Raised when a spec file is invalid (no tasks, malformed, etc.)."""
    pass
```

**Tests to add**:
- `tests/unit/domain/test_spec_content.py` - Test validation logic
- Test empty file raises error
- Test file without checkboxes raises error
- Test valid file with checkboxes passes

---

- [ ] Phase 6: Update CLI commands for new inputs

**Goal**: Commands receive and use new directory parameters.

**Files to modify**:
- `src/claudestep/__main__.py` - Update argument parsing and environment reading
- `src/claudestep/cli/commands/prepare.py` - Use new project discovery
- `src/claudestep/cli/commands/finalize.py` - Use new paths
- `src/claudestep/cli/commands/discover_ready.py` - Use new discovery

**Changes**:
- Add `--spec-directory` and `--config-directory` CLI arguments
- Add `--project-name` optional argument for single-project runs
- Read from `SPEC_DIRECTORY`, `CONFIG_DIRECTORY`, and `PROJECT_NAME` environment variables
- Update project discovery to use new `ProjectRepository.discover_projects()`
- If `project_name` provided, filter to only that project
- Remove logic that assumes `claude-step/{project}/` structure

**Environment variable mapping**:
```python
spec_directory = args.spec_directory or os.environ.get("SPEC_DIRECTORY", "")
config_directory = args.config_directory or os.environ.get("CONFIG_DIRECTORY", "")
project_name = args.project_name or os.environ.get("PROJECT_NAME", "")
```

**Tests to update**:
- `tests/integration/cli/commands/test_prepare.py`
- `tests/integration/cli/commands/test_discover.py`

---

- [ ] Phase 7: Update statistics command

**Goal**: Statistics collection works with new structure.

**Files to modify**:
- `src/claudestep/cli/commands/statistics.py`
- `src/claudestep/services/composite/statistics_service.py`

**Changes**:
- Accept spec_directory and config_directory parameters
- Discover projects from spec_directory
- Load configs from config_directory (or use defaults)
- Remove references to old `claude-step/{project}/` paths

**Tests to update**:
- `tests/integration/cli/commands/test_statistics.py`

---

- [ ] Phase 8: Update branch naming and PR service

**Goal**: Branch names and PR detection work with new project names.

**Files to modify**:
- `src/claudestep/services/core/pr_service.py`

**Changes**:
- Branch naming format unchanged: `claude-step-{project}-{task_hash}`
- Project detection from branch unchanged (extracts project name)
- Verify no assumptions about directory structure in PR service

**Tests to verify**:
- Existing PR service tests should pass without changes

---

- [ ] Phase 9: Update auto-start workflow and project detection

**Goal**: Auto-start detection works with new flat directory structure.

**Files to modify**:
- `src/claudestep/services/composite/auto_start_service.py`
- `.github/workflows/claudestep.yml` (path filters)

**Changes**:
- Update `detect_changed_projects()` to:
  - Accept `spec_directory` parameter
  - Detect changes to `{spec_directory}/*.md` files
  - Extract project name from changed filename
- Update workflow path filters:
  - Old: `claude-step/**/spec.md`
  - New: User-configured via workflow inputs (document how to set up)

**Note**: Auto-start path filters require user configuration since `spec_directory` is user-defined. Document in README that users should update their workflow triggers:

```yaml
on:
  push:
    paths:
      - 'my-specs/*.md'  # User configures to match their spec_directory
```

**Tests to update**:
- `tests/unit/services/composite/test_auto_start_service.py`

---

- [ ] Phase 10: Update documentation

**Goal**: Documentation reflects new directory structure.

**Files to modify**:
- `README.md` - Update setup instructions
- `docs/feature-guides/getting-started.md` - New quick start with flat structure
- `action.yml` description updates (done in Phase 1)

**Documentation changes**:
- Remove `claude-step/{project}/` examples
- Show new flat directory structure
- Explain spec_directory (required) and config_directory (optional)
- Show examples of same-directory and separate-directory configurations
- Document PR template location: `{config_directory}/{project}-pr-template.md`
- Document auto-start path filter configuration
- Add migration guide for v2 → v3

**Example documentation**:
```markdown
## Quick Start

1. Create a specs directory with your project files:

```
specs/
├── auth-migration.md
└── api-cleanup.md
```

2. (Optional) Create configs directory:

```
configs/
├── auth-migration.yml           # Config for auth-migration
├── auth-migration-pr-template.md  # PR template for auth-migration
└── api-cleanup.yml              # Config for api-cleanup
```

3. Configure the workflow:

```yaml
- uses: gestrich/claude-step@v3
  with:
    spec_directory: 'specs'
    config_directory: 'configs'  # Optional
```
```

**Migration guide** (add to README):
```markdown
## Migrating from v2

v3 changes from nested to flat directory structure:

**Before (v2)**:
```
claude-step/
├── my-project/
│   ├── spec.md
│   ├── configuration.yml
│   └── pr-template.md
```

**After (v3)**:
```
specs/
└── my-project.md

configs/  # Optional
├── my-project.yml
└── my-project-pr-template.md
```

**Workflow changes**:
```yaml
# Before (v2)
- uses: gestrich/claude-step@v2
  with:
    project_name: 'my-project'

# After (v3)
- uses: gestrich/claude-step@v3
  with:
    spec_directory: 'specs'
    config_directory: 'configs'
    project_name: 'my-project'  # Optional: for manual single-project runs
```
```

---

- [ ] Phase 11: Validation

**Automated tests**:
```bash
# Run all unit and integration tests
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v

# Specifically run updated tests
PYTHONPATH=src:scripts pytest tests/unit/domain/test_project.py -v
PYTHONPATH=src:scripts pytest tests/unit/infrastructure/repositories/test_project_repository.py -v
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_prepare.py -v
```

**Manual verification** (if E2E needed):
- Create test spec directory with 2 `.md` files
- Create test config directory with 1 `.yml` file (matching one spec)
- Trigger workflow with new inputs
- Verify:
  - Both projects discovered
  - Project with config uses config settings
  - Project without config uses defaults
  - PRs created with correct project names

**Success criteria**:
- All existing tests pass (updated for new structure)
- New tests for flat directory discovery pass
- Projects discovered from `*.md` files in spec_directory
- Invalid spec files (no checkboxes) throw clear error
- Configs loaded from config_directory when present
- Default configs used when no config file exists
- PR templates loaded from `{config_directory}/{project}-pr-template.md` when present
- Default PR template used when no template file exists
- Branch names use project name derived from filename
- Manual `workflow_dispatch` with `project_name` runs only that project
- Auto-start detects changes to `{spec_directory}/*.md` files
- Metadata branch storage unchanged (still `projects/{project-name}.json`)
