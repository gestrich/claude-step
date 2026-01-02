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
4. **Same directory allowed** - User can set both inputs to the same directory if desired
5. **Any `.md` file is a spec** - No more `spec.md` naming requirement

This simplifies setup and gives users full control over their directory structure.

## Phases

- [ ] Phase 1: Update workflow inputs and action.yml

**Goal**: Add new inputs for spec and config directories.

**Files to modify**:
- `action.yml` - Add inputs, update environment variable passing

**Changes**:
- Add `spec_directory` input (required, no default)
- Add `config_directory` input (optional, default empty)
- Remove `project_name` input (will be derived from spec filename)
- Pass new inputs as environment variables to Python commands

**New inputs**:
```yaml
inputs:
  spec_directory:
    description: 'Directory containing spec files (*.md). Each file is a project.'
    required: true
  config_directory:
    description: 'Directory containing config files (*.yml). Optional. Configs match specs by filename.'
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
- Add class method `find_all(spec_directory: str) -> List[Project]` that:
  - Lists all `*.md` files in spec_directory
  - Creates Project for each, deriving name from filename

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
  - Create Project instances with appropriate directories

**Tests to update**:
- `tests/unit/infrastructure/repositories/test_project_repository.py`

---

- [ ] Phase 5: Update CLI commands for new inputs

**Goal**: Commands receive and use new directory parameters.

**Files to modify**:
- `src/claudestep/__main__.py` - Update argument parsing and environment reading
- `src/claudestep/cli/commands/prepare.py` - Use new project discovery
- `src/claudestep/cli/commands/finalize.py` - Use new paths
- `src/claudestep/cli/commands/discover_ready.py` - Use new discovery

**Changes**:
- Add `--spec-directory` and `--config-directory` CLI arguments
- Read from `SPEC_DIRECTORY` and `CONFIG_DIRECTORY` environment variables
- Update project discovery to use new `ProjectRepository.discover_projects()`
- Remove logic that assumes `claude-step/{project}/` structure

**Environment variable mapping**:
```python
spec_directory = args.spec_directory or os.environ.get("SPEC_DIRECTORY", "")
config_directory = args.config_directory or os.environ.get("CONFIG_DIRECTORY", "")
```

**Tests to update**:
- `tests/integration/cli/commands/test_prepare.py`
- `tests/integration/cli/commands/test_discover.py`

---

- [ ] Phase 6: Update statistics command

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

- [ ] Phase 7: Update branch naming and PR service

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

- [ ] Phase 8: Update documentation

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

**Example documentation**:
```markdown
## Quick Start

1. Create a specs directory with your project files:

```
specs/
├── auth-migration.md
└── api-cleanup.md
```

2. Configure the workflow:

```yaml
- uses: gestrich/claude-step@v2
  with:
    spec_directory: 'specs'
    # config_directory: 'configs'  # Optional
```
```

---

- [ ] Phase 9: Validation

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
- Configs loaded from config_directory when present
- Default configs used when no config file exists
- Branch names use project name derived from filename
