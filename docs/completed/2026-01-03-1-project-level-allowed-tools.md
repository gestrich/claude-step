## Background

ClaudeChain currently supports `claude_allowed_tools` as an action input (workflow-level configuration), allowing users to specify which tools Claude Code can use during task execution. The current default is `Write,Read,Bash,Edit`.

The user wants to extend this to support **per-project configuration overrides** via `configuration.yml`, following the same pattern used for `baseBranch` (workflow default → project override). This follows the established hierarchy:

1. **Action input** (workflow-level default, applies to all projects)
2. **Project configuration** (per-project override in `configuration.yml`)

This mirrors the existing pattern for `baseBranch` where:
- Workflow provides a default via `base_branch` input
- Project's `configuration.yml` can override with `baseBranch` field

**Research findings** (from [Claude Code Action](https://github.com/anthropics/claude-code-action)):
- The Claude Code Action v1 uses `claude_args` to pass `--allowedTools` to Claude CLI
- Available tools include: `Write`, `Read`, `Bash`, `Edit`, `Glob`, `Grep`, and potentially MCP tools
- Tools are passed as comma-separated values: `--allowedTools Write,Read,Bash,Edit`
- **Granular Bash permissions**: Syntax `Bash(command:*)` restricts to specific commands (e.g., `Bash(gh pr diff:*)`)

**Important: Two Claude Code invocations exist in action.yml:**
1. **Main task execution** (line 190) - User-configurable via `claude_allowed_tools` input and project config
2. **PR summary generation** (line 259) - Internal step, NOT user-configurable, should use minimal permissions

The summary step currently uses `Bash,Write` which is overly permissive. It only needs:
- `Bash(gh pr diff:*)` - Fetch PR diff
- `Bash(cat:*)` - Verify file was written
- `Write` - Save summary to file

**Main task execution minimum requirements:**

The standard ClaudeChain prompt (in `prepare.py`) instructs Claude to:
> "When you're done, use git add and git commit to commit your changes."

This means the **minimum required tools** for main task execution are:

| Tool | Required For |
|------|-------------|
| `Read` | Reading spec.md and codebase files |
| `Write` or `Edit` | Making code changes |
| `Bash(git add:*)` | Staging changes (explicit in prompt) |
| `Bash(git commit:*)` | Committing changes (explicit in prompt) |

**Claude Code Action default behavior:**

Per [Claude Code Action documentation](https://github.com/anthropics/claude-code-action/blob/main/docs/configuration.md), Claude does **NOT** have Bash access by default. The default includes only:
- File operations (reading, editing, committing)
- Comment management
- Basic GitHub operations

ClaudeChain's current default `Write,Read,Bash,Edit` is more permissive than Claude Code Action's baseline. This was chosen because many refactoring tasks require running tests/builds, but it's worth reconsidering.

**Decision:** Match Claude Code Action's minimal default, plus only the specific Bash commands ClaudeChain requires:
```
Read,Write,Edit,Bash(git add:*),Bash(git commit:*)
```

This aligns with Claude Code Action's security-first philosophy while adding only what's necessary for the core ClaudeChain workflow (staging and committing changes). Users who need additional Bash access (for tests, builds, etc.) can explicitly add it via `allowedTools` config.

**Breaking change:** The current default `Write,Read,Bash,Edit` will be replaced. Existing users relying on full Bash access will need to add `Bash` to their workflow input or project config.

## Phases

- [x] Phase 1: Extend ProjectConfiguration domain model

Add `allowed_tools` field to the `ProjectConfiguration` dataclass in `src/claudechain/domain/project_configuration.py`:

```python
@dataclass
class ProjectConfiguration:
    project: Project
    reviewers: List[Reviewer]
    base_branch: Optional[str] = None
    allowed_tools: Optional[str] = None  # New field
```

Add factory method updates:
- `from_yaml_string()`: Parse `allowedTools` from YAML (use camelCase to match existing `baseBranch` convention)
- `default()`: Keep `allowed_tools=None` (meaning "use workflow default")
- Add `get_allowed_tools(default: str) -> str` method following the same pattern as `get_base_branch()`
- Update `to_dict()` to include `allowedTools` when set

**Files to modify:**
- `src/claudechain/domain/project_configuration.py`

- [x] Phase 2: Pass allowed_tools through prepare command

Per architecture principles (see `docs/general-architecture/python-style.md`), environment variables should only be read in `__main__.py`, not in CLI commands. The adapter layer in `__main__.py` handles all env var reading and passes explicit parameters to commands.

Update the following files:

**Files to modify:**

1. `src/claudechain/__main__.py`
   - Read env var and pass to command:
     ```python
     elif args.command == "prepare":
         return cmd_prepare(
             gh=gh,
             # ... existing params ...
             default_allowed_tools=os.environ.get("CLAUDE_ALLOWED_TOOLS", "Read,Write,Edit,Bash(git add:*),Bash(git commit:*)")
         )
     ```

2. `src/claudechain/cli/commands/prepare.py`
   - Add `default_allowed_tools: str` parameter to `cmd_prepare()` function signature
   - Resolve with config: `allowed_tools = config.get_allowed_tools(default_allowed_tools)`
   - Add output: `gh.write_output("allowed_tools", allowed_tools)`

- [x] Phase 3: Update action.yml to use resolved allowed_tools

Modify `action.yml` to:
1. Update input default from `Write,Read,Bash,Edit` to `Read,Write,Edit,Bash(git add:*),Bash(git commit:*)`
2. Pass `CLAUDE_ALLOWED_TOOLS` environment variable to prepare step
3. Use `${{ steps.prepare.outputs.allowed_tools }}` in Claude Code step instead of `${{ inputs.claude_allowed_tools }}`

**Files to modify:**
- `action.yml`
  - Change input default (line 44):
    ```yaml
    # Before
    default: 'Write,Read,Bash,Edit'
    # After
    default: 'Read,Write,Edit,Bash(git add:*),Bash(git commit:*)'
    ```
  - Add `CLAUDE_ALLOWED_TOOLS: ${{ inputs.claude_allowed_tools }}` to prepare step's env
  - Change line 190 from:
    ```yaml
    claude_args: '--allowedTools ${{ inputs.claude_allowed_tools }} --model ${{ inputs.claude_model }}'
    ```
    to:
    ```yaml
    claude_args: '--allowedTools "${{ steps.prepare.outputs.allowed_tools || inputs.claude_allowed_tools }}" --model ${{ inputs.claude_model }}'
    ```
  - Note: Quotes around allowedTools value are required for the `Bash(command:*)` syntax

- [x] Phase 4: Tighten PR summary step permissions

The PR summary generation step (line 259 in action.yml) currently uses `--allowedTools Bash,Write` which grants full Bash access. This should be restricted to only the specific commands needed.

**Current (overly permissive):**
```yaml
claude_args: '--allowedTools Bash,Write --model ${{ inputs.claude_model }}'
```

**New (minimal permissions):**
```yaml
claude_args: '--allowedTools "Bash(gh pr diff:*),Bash(cat:*),Write" --model ${{ inputs.claude_model }}'
```

**Why these specific permissions:**
- `Bash(gh pr diff:*)` - Required to fetch PR diff via `gh pr diff {PR_NUMBER} --patch`
- `Bash(cat:*)` - Required to verify summary file was written via `cat {SUMMARY_FILE_PATH}`
- `Write` - Required to save summary to the temp file

**Important:** This is NOT user-configurable. The summary step is an internal ClaudeChain operation that should always use minimal, fixed permissions regardless of project configuration.

**Files to modify:**
- `action.yml` (line 259)

- [x] Phase 5: Add unit tests

Add tests for the new functionality:

1. **Domain model tests** (`tests/unit/domain/test_project_configuration.py`):
   - Test `from_yaml_string()` parses `allowedTools` correctly
   - Test `get_allowed_tools()` returns project value when set
   - Test `get_allowed_tools()` returns default when not set
   - Test `to_dict()` includes `allowedTools` when present

2. **Prepare command tests** (`tests/unit/cli/commands/test_prepare.py`):
   - Test allowed_tools output uses project config when present
   - Test allowed_tools output uses workflow default when not in config

**Files to modify:**
- `tests/unit/domain/test_project_configuration.py`
- `tests/unit/cli/commands/test_prepare.py`

- [x] Phase 6: Update documentation

Update documentation to explain the new configuration option:

1. **README.md**:
   - Add `allowedTools` to configuration.yml reference table
   - Add example showing per-project tool restriction
   - Clarify hierarchy: action input → project config override
   - Document minimum required permissions vs. default
   - Document that PR summary step uses fixed minimal permissions (not user-configurable)

2. **Feature guide** (`docs/feature-guides/getting-started.md`):
   - Add note about tool customization in "Customize Your Workflow" section

**Configuration.yml example to add:**
```yaml
reviewers:
  - username: alice
    maxOpenPRs: 1
baseBranch: develop
allowedTools: Write,Read,Edit  # Restrict to safe tools (no Bash)
```

**Documentation for tool permissions (add to README.md):**

```markdown
### Tool Permissions

ClaudeChain uses two Claude Code invocations with different permission scopes:

**Main Task Execution** (user-configurable):
- Default: `Read,Write,Edit,Bash(git add:*),Bash(git commit:*)`
- Configure via `claude_allowed_tools` input or project's `allowedTools` config

| Tool | Purpose |
|------|---------|
| `Read` | Read spec.md and codebase files |
| `Write` / `Edit` | Make code changes |
| `Bash(git add:*)` | Stage changes (required by ClaudeChain prompt) |
| `Bash(git commit:*)` | Commit changes (required by ClaudeChain prompt) |

To enable additional Bash commands (e.g., for running tests or builds), add them to your configuration:
```yaml
# configuration.yml - enable full Bash access
allowedTools: Read,Write,Edit,Bash

# Or specific commands only
allowedTools: Read,Write,Edit,Bash(git add:*),Bash(git commit:*),Bash(npm test:*),Bash(npm run build:*)
```

**PR Summary Generation** (fixed, not user-configurable):
- Permissions: `Bash(gh pr diff:*),Bash(cat:*),Write`
- This internal step always uses minimal permissions regardless of project settings
```

**Documentation note about summary step:**
> **Note:** The PR summary generation step uses fixed, minimal permissions (`Bash(gh pr diff:*)`, `Bash(cat:*)`, `Write`) and is not affected by the `allowedTools` configuration. This ensures the summary step operates securely regardless of project settings.

**Files to modify:**
- `README.md` (Configuration Reference section)
- `docs/feature-guides/getting-started.md`

- [x] Phase 7: Validation

Run the test suite to verify changes:

```bash
# Run unit tests for affected modules
PYTHONPATH=src:scripts pytest tests/unit/domain/test_project_configuration.py -v
PYTHONPATH=src:scripts pytest tests/unit/cli/commands/test_prepare.py -v

# Run full unit test suite
PYTHONPATH=src:scripts pytest tests/unit/ -v

# Run integration tests
PYTHONPATH=src:scripts pytest tests/integration/ -v

# Verify coverage is maintained
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudechain --cov-fail-under=70
```

**Success criteria:**
- All existing tests pass
- New tests for `allowedTools` functionality pass
- Coverage remains above 70%
- Documentation accurately reflects the new feature
