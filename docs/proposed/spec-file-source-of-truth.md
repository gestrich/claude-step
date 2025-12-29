# Spec File Source of Truth

## Background

Currently, ClaudeStep has an inconsistency in how spec files are accessed. The statistics workflow is failing because it's trying to read spec files from the filesystem (e.g., `claude-step/test-project-0d044eb4/configuration.yml`), but these files don't exist in the main branch - they were only created during E2E test runs and never merged.

**The Problem:**
- Spec files (`spec.md`, `configuration.yml`) are created in test branches but not merged to main
- Statistics and other operations try to read these files from the filesystem
- This causes "File not found" errors
- Metadata storage contains project data, but no corresponding spec files exist

**The Solution:**
The spec files must always exist in the **main branch** (or whatever the project's default branch is) as the source of truth. This means:
1. Users must merge their spec before running ClaudeStep workflows
2. All operations must fetch spec files from GitHub via API (not filesystem)
3. The main branch name should be configurable (default: "main")

**User Requirements:**
- When ClaudeStep workflow runs, return clear error if spec doesn't exist in main branch
- Projects should be able to define their main branch name (some use "master")
- Main branch input should be configurable in actions (defaults to "main")
- Statistics action should also accept main branch input
- All spec references must download via GitHub API
- Clean start: Delete existing project JSON files in metadata storage

## Phases

- [ ] Phase 1: Add Base Branch Configuration Support

Add support for configurable base branch across all actions and workflows.

**Tasks:**
- Update `action.yml` to add `base_branch` input (default: "main")
- Update `discovery/action.yml` to add `base_branch` input (default: "main")
- Update `.github/workflows/claudestep.yml` to accept and pass `base_branch` input
- Update `.github/workflows/claudestep-statistics.yml` to accept and pass `base_branch` input
- Store base branch in environment variable for Python code to access

**Files to Modify:**
- `action.yml` - Add base_branch input
- `discovery/action.yml` - Add base_branch input
- `.github/workflows/claudestep.yml` - Add base_branch input/output
- `.github/workflows/claudestep-statistics.yml` - Add base_branch input

**Expected Outcome:**
All workflows can accept a configurable base branch name (defaults to "main")

- [ ] Phase 2: Create GitHub API Helper for Spec File Retrieval

Add infrastructure support for fetching files from specific branches via GitHub API.

**Tasks:**
- Add function to `src/claudestep/infrastructure/github/operations.py`:
  - `get_file_from_branch(repo: str, branch: str, file_path: str) -> Optional[str]`
  - Uses GitHub Contents API to fetch file content
  - Returns file content as string, or None if not found
  - Handles Base64 decoding (GitHub API returns Base64 encoded)
- Add function to check if file exists:
  - `file_exists_in_branch(repo: str, branch: str, file_path: str) -> bool`

**Files to Create/Modify:**
- `src/claudestep/infrastructure/github/operations.py` - Add new functions

**Expected Outcome:**
Python code can fetch any file from any branch via GitHub API without filesystem access

- [ ] Phase 3: Update Prepare Command to Validate Spec Existence

Modify the prepare command to check that spec files exist in base branch before proceeding.

**Tasks:**
- Update `src/claudestep/cli/commands/prepare.py`:
  - Get base branch from environment (default: "main")
  - Before loading spec, check if `claude-step/{project}/spec.md` exists in base branch
  - Check if `claude-step/{project}/configuration.yml` exists in base branch
  - If either doesn't exist, return error with clear message:
    ```
    Error: Spec files not found in branch '{base_branch}'
    Required files:
      - claude-step/{project}/spec.md
      - claude-step/{project}/configuration.yml

    Please merge your spec files to the '{base_branch}' branch before running ClaudeStep.
    ```
  - Exit with code 1 (error)

**Files to Modify:**
- `src/claudestep/cli/commands/prepare.py`

**Expected Outcome:**
Users get clear error message if they try to run ClaudeStep without spec in base branch

- [ ] Phase 4: Update All Spec File Access to Use GitHub API

Replace all filesystem reads of spec files with GitHub API fetches from base branch.

**Tasks:**
- Update `src/claudestep/cli/commands/prepare.py`:
  - Replace `open(spec_path, "r")` with `get_file_from_branch(repo, base_branch, f"claude-step/{project}/spec.md")`
  - Use API to read spec content instead of filesystem
- Update `src/claudestep/application/collectors/statistics_collector.py`:
  - Replace filesystem access in `count_tasks(spec_path)` with API access
  - Update `collect_project_stats()` to fetch spec via API
  - Remove dependency on spec_path being a filesystem path
- Update `src/claudestep/domain/config.py`:
  - Update `load_config()` to optionally load from string content (for API usage)
  - Or create `load_config_from_api()` variant
- Update `src/claudestep/application/services/task_management.py`:
  - Update `find_next_available_task()` to accept spec content string or use API
  - Update `mark_task_complete()` - this is trickier as it writes to spec

**Special Consideration for `mark_task_complete()`:**
This function writes to spec.md to mark tasks complete. Since we can't write to the checked-out branch's spec (it's not in main), we have two options:
1. Don't mark tasks complete in spec during workflow (rely on PR merge to update spec)
2. Update the spec on the PR branch only (not main)

**Recommendation:** Option 1 - Remove spec marking during workflow, let PR merge update the spec

**Files to Modify:**
- `src/claudestep/cli/commands/prepare.py`
- `src/claudestep/application/collectors/statistics_collector.py`
- `src/claudestep/domain/config.py`
- `src/claudestep/application/services/task_management.py`
- `src/claudestep/cli/commands/finalize.py` - Remove spec marking call

**Expected Outcome:**
All spec file access goes through GitHub API from base branch, no filesystem dependencies

- [ ] Phase 5: Update Statistics Collection to Use API

Ensure statistics collection fetches all data via API from base branch.

**Tasks:**
- Update `src/claudestep/application/collectors/statistics_collector.py`:
  - Get base_branch from environment (default: "main")
  - When loading project configs, fetch from base branch via API
  - Update `count_tasks()` to accept spec content string instead of file path
  - Fetch spec.md content via `get_file_from_branch()`
  - If spec files don't exist in base branch for a metadata project, log warning but continue
  - This allows statistics to work even if some projects were deleted

**Files to Modify:**
- `src/claudestep/application/collectors/statistics_collector.py`

**Expected Outcome:**
Statistics can run successfully, fetching specs from base branch via API

- [ ] Phase 6: Clean Up Existing Metadata

Delete existing project JSON files to start fresh with the new approach.

**Tasks:**
- Delete all files in `claudestep-metadata` branch under `projects/` directory:
  - `projects/test-project-0d044eb4.json`
  - `projects/test-project-8dce0510.json`
  - `projects/test-project-b1ce74de.json`
- Can do this via GitHub API or manually via git commands
- Document that this is a one-time cleanup for the refactor

**Expected Outcome:**
Clean slate - no orphaned project metadata without corresponding specs

- [ ] Phase 7: Update Documentation

Update user-facing documentation to reflect the new requirement.

**Tasks:**
- Update `README.md`:
  - Add section explaining that spec files must be merged to base branch first
  - Document the `base_branch` input parameter (defaults to "main")
  - Explain workflow: Create spec → Merge to main → Run ClaudeStep
- Update `action.yml` description for base_branch input
- Update `docs/architecture/architecture.md` if needed

**Files to Modify:**
- `README.md`
- `action.yml`
- Potentially `docs/architecture/architecture.md`

**Expected Outcome:**
Users understand they must merge specs before running workflows

- [ ] Phase 8: Update E2E Tests to Use Real Project

Update E2E tests to use a permanent test project with many steps instead of creating temporary fake projects.

**Background:**
The new design requires specs to exist in the main branch. This means E2E tests can no longer create temporary "fake" projects on the fly (since those specs won't be in main). Instead, we need a permanent test project with many steps (300+) committed to the main branch that E2E tests can use.

**Tasks:**
- Create a permanent test project in main branch:
  - Location: `claude-step/e2e-test-project/`
  - Create `spec.md` with 300+ simple tasks (e.g., "Task 1", "Task 2", etc.)
  - Create `configuration.yml` with test reviewer configuration
  - Create `pr-template.md` with standard template
  - Commit to main branch
- Update E2E test files to use this permanent project:
  - `tests/e2e/test_workflow_e2e.py` - Remove temporary project creation logic
  - `tests/e2e/helpers/github_helper.py` - Update to use permanent project name
  - `tests/e2e/helpers/test_branch_manager.py` - Simplify to not create project files
- Update E2E tests to:
  - Use `e2e-test-project` as the project name
  - Skip project creation steps (files already in main)
  - Still create ephemeral test branches for running workflows
  - Clean up PRs and branches after tests (but leave project files in main)
- Benefits:
  - Tests run faster (no project creation overhead)
  - More realistic (uses actual main branch specs like users will)
  - Simpler test code (no mocking project creation)
  - Can test many tasks (300+) to ensure scalability

**Files to Create:**
- `claude-step/e2e-test-project/spec.md` - 300+ tasks
- `claude-step/e2e-test-project/configuration.yml` - Test config
- `claude-step/e2e-test-project/pr-template.md` - Template

**Files to Modify:**
- `tests/e2e/test_workflow_e2e.py` - Use permanent project
- `tests/e2e/test_statistics_e2e.py` - Use permanent project
- `tests/e2e/helpers/github_helper.py` - Remove project creation
- `tests/e2e/helpers/test_branch_manager.py` - Simplify

**Expected Outcome:**
E2E tests use a real project from main branch, validating the actual user workflow

- [ ] Phase 9: Testing & Validation

Comprehensive testing to ensure spec file handling works correctly.

**Test Plan:**

**Unit Tests:**
- Test `get_file_from_branch()` with mocked GitHub API responses
- Test `file_exists_in_branch()` with various scenarios
- Test prepare command spec validation logic
- Test statistics collection with API-fetched specs

**Integration Tests:**
- Test prepare command with missing spec (should error clearly)
- Test prepare command with spec in base branch (should succeed)
- Test statistics collection with projects in metadata but no specs
- Test statistics collection with valid specs in base branch

**E2E Tests:**
- Create test spec in main branch (with `spec.md` and `configuration.yml`)
- Run `tests/e2e/run_test.sh` to trigger the E2E test workflow on GitHub
- Monitor the workflow run to completion
- Verify PR is created successfully
- Trigger the statistics workflow (or wait for it to run automatically)
- Monitor the statistics workflow run
- Verify statistics output shows the correct project data from metadata storage
- Check that statistics only show projects with specs in base branch
- Test with custom base_branch name (e.g., "master") by modifying workflow inputs
- Verify that projects without specs in base branch show appropriate warnings but don't break statistics

**Manual Verification:**
- Delete all project metadata JSON files in `claudestep-metadata` branch
- Create a new spec in main branch (in `claude-step/{project}/` directory)
- Run `tests/e2e/run_test.sh` to trigger full workflow on GitHub
- Monitor workflow execution until PR is created
- Trigger statistics workflow manually or wait for scheduled run
- Verify statistics output:
  - Shows the new project
  - Only includes projects with specs in base branch
  - Displays correct task counts, costs, and progress
- Test error case: Try to run workflow for a project without spec in main branch
- Verify clear error message is shown

**Files to Create/Modify:**
- `tests/unit/infrastructure/github/test_operations.py` - Test new API functions
- `tests/integration/cli/commands/test_prepare.py` - Test spec validation
- `tests/integration/cli/commands/test_statistics.py` - Test API-based spec reading
- Update E2E tests as needed

**Success Criteria:**
- All tests pass (unit, integration, e2e)
- Clear error messages when spec is missing
- Statistics work with API-fetched specs
- Works with custom base branch names
- No filesystem dependencies for spec access

## Migration Notes

**Breaking Changes:**
- Users must merge specs to main branch before running workflows
- Existing projects in metadata without specs will show warnings in statistics

**Migration Steps for Users:**
1. Merge all spec files (`spec.md`, `configuration.yml`) to your main branch
2. Ensure spec files are in `claude-step/{project}/` directory structure
3. Run ClaudeStep workflows as normal (they will now fetch specs from main)

**Internal Migration:**
- Delete orphaned metadata JSON files (Phase 6)
- This is a one-time cleanup, future workflows will create correct metadata
