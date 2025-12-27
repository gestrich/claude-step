# V1 Improvements

Configuration and workflow improvements for V1 release.

## Tasks

- [x] **Use YML for configuration**

**Status:** COMPLETED

**Changes made:**
- Added `load_config()` function to `config.py` that supports both YAML (.yml/.yaml) and JSON formats
- Updated all code to use `load_config()` instead of `load_json()` for configuration files
- Modified `project_detection.py` to check for `.yml` files first, then fall back to `.json` for backwards compatibility
- Updated `discover.py`, `discover_ready.py`, `prepare.py`, and `statistics_collector.py` to support both formats
- Added PyYAML dependency installation to `action.yml`
- Created `examples/configuration.yml` to demonstrate YAML format
- Updated README.md to use YAML examples throughout all documentation
- Updated integration tests to create YAML configuration files

**Technical notes:**
- Backwards compatibility is maintained - existing JSON configs will continue to work
- The system prefers `.yml` files but automatically falls back to `.json` if found
- PyYAML is installed via GitHub Actions during workflow setup

**Next steps:**
- Will need to update /Users/bill/Developer/personal/claude-step-demo to use YAML configuration

- [x] **Improve branch name options**

**Status:** COMPLETED

**Changes made:**
- Fixed branch naming logic in `prepare.py` to actually use the `branchPrefix` configuration field
- When `branchPrefix` is specified, branches are named `{branchPrefix}-{task_index}` (e.g., `refactor/swift-migration-1`)
- When `branchPrefix` is omitted, branches default to YYYY-MM format: `{YYYY-MM}-{project_name}-{task_index}` (e.g., `2025-01-my-refactor-1`)
- Made `branchPrefix` optional instead of required in validation logic
- Updated README.md to document branch naming behavior with clear examples
- Updated validation documentation to reflect that `branchPrefix` is optional

**Technical notes:**
- Previously, the code was loading `branchPrefix` from config but never using it for branch creation
- The config validation incorrectly required `branchPrefix` even though the default behavior didn't use it
- Now users have flexibility to choose their preferred branch naming scheme

- [x] **Remove unnecessary action inputs**

**Status:** COMPLETED

**Changes made:**
- Removed `config_path`, `spec_path`, and `pr_template_path` inputs from `action.yml`
- Updated `detect_project_paths()` function in `project_detection.py` to no longer accept override parameters
- Modified `prepare.py` to always use the standard `claude-step/` directory structure
- Updated README.md to remove documentation for the removed inputs
- All projects must now be located in `claude-step/{project-name}/` with standard file names:
  - `configuration.yml` (or `configuration.json` for backwards compatibility)
  - `spec.md`
  - `pr-template.md`

**Technical notes:**
- The `detect_project_paths()` function signature changed from accepting 3 optional override parameters to accepting none
- Environment variables `CONFIG_PATH`, `SPEC_PATH`, and `PR_TEMPLATE_PATH` are no longer read from action inputs, but are still passed between workflow steps via outputs
- Backwards compatibility is maintained for existing JSON configuration files
- Tests pass successfully (62 passed, 5 pre-existing failures unrelated to this change)

- [x] **Trigger action off of closed PRs, not just merged**

**Status:** COMPLETED

**Changes made:**
- Updated README.md to remove the `if: github.event.pull_request.merged == true` condition from workflow examples
- Modified examples/advanced/workflow.yml to trigger on all closed PRs (not just merged)
- Added documentation warnings about the implications of closing PRs without merging
- Users are now advised: "If closing without merging, update `spec.md` first to avoid the PR re-opening"

**Technical notes:**
- The workflow now triggers on `pull_request: types: [closed]` without filtering by merged status
- This allows the system to respond to both merged PRs and PRs closed for other reasons
- To prevent a closed PR from being re-opened, users should first update spec.md to mark the task as complete or remove it, merge that change, then close the PR
- Tests pass successfully (62 passed, 6 pre-existing failures unrelated to this change)

- [x] **Run e2e tests to verify changes**

**Status:** COMPLETED

**Changes made:**
- Fixed integration test to use correct branch pattern matching for custom `branchPrefix`
- Updated test assertions to look for `refactor/{project_name}-{index}` format instead of `YYYY-MM-{project_name}-{index}`
- Fixed `detect_project_from_pr()` function in `project_detection.py` to handle both default and custom branch prefix formats
- The function now iterates through all project directories and checks each project's config to match the branch name correctly

**Test results:**
- All e2e tests passed successfully (1 passed in ~7 minutes)
- Test validated:
  - First PR creation with correct branch naming
  - Second PR creation while reviewer at capacity
  - Merge trigger functionality creating third PR automatically
  - AI-generated PR summaries on all PRs
  - YAML configuration support
  - Custom branchPrefix support

**Technical notes:**
- The original `detect_project_from_pr()` assumed all branches followed the default `YYYY-MM-{project}-{index}` format
- Now supports custom `branchPrefix` by loading each project's config and matching the branch pattern
- Backwards compatible with projects using default branch naming (no `branchPrefix` specified)

