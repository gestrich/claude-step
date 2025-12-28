# E2E Tests: Remote Execution via GitHub Workflows

## Background

Currently, when running `./tests/e2e/run_test.sh` locally, the script executes pytest on the developer's machine, which performs git operations (commits, pushes, branch creation) that mutate the local git state. This creates several problems:

1. **Local git pollution** - Test execution modifies the developer's working directory and branches
2. **Environment inconsistency** - Tests run in different environments (local vs CI)
3. **Setup complexity** - Developers need proper git configuration and Python environment locally

The goal is to refactor the local test runner script to:
- **Trigger** the e2e-test.yml workflow on GitHub via `gh workflow run`
- **Monitor** the workflow execution remotely
- **Report** results back to the developer
- **Zero local git mutations** - all test execution happens on GitHub's runners

This approach provides clean separation: the local script becomes a simple trigger/monitor, while all actual test execution (pytest orchestration, git operations, workflow triggering) happens on GitHub's infrastructure.

## Phases

- [ ] Phase 1: Update run_test.sh to trigger remote workflow

Modify `tests/e2e/run_test.sh` to:
- Keep existing prerequisite checks (gh CLI, authentication)
- Remove Python/pytest checks (not needed locally anymore)
- Remove the local `pytest tests/e2e/` execution
- Add `gh workflow run e2e-test.yml` to trigger the workflow on GitHub
- Capture the workflow run ID from the trigger
- Add clear messaging that tests are running remotely on GitHub

Files to modify:
- `tests/e2e/run_test.sh`

Technical considerations:
- Use `gh workflow run` with `--ref` parameter to specify which branch to run from
- The workflow will run from the current branch the user is on
- Need to capture the run ID for monitoring in Phase 2

Expected outcome:
- Running the script triggers the GitHub workflow instead of running pytest locally
- Script provides feedback that the workflow was triggered successfully

- [ ] Phase 2: Add workflow monitoring and result reporting

Extend `tests/e2e/run_test.sh` to:
- Wait for the workflow run to complete using `gh run watch <run-id>`
- Stream logs to the console so developers can see progress
- Check the final workflow conclusion (success/failure/cancelled)
- Exit with appropriate exit code (0 for success, 1 for failure)
- Provide helpful messages about viewing logs via GitHub UI

Files to modify:
- `tests/e2e/run_test.sh`

Technical considerations:
- `gh run watch` provides live log streaming
- May need to handle cases where workflow is queued for a long time
- Should handle Ctrl+C gracefully (workflow continues, but local monitoring stops)
- Provide link to GitHub Actions UI for detailed inspection

Expected outcome:
- Developers see live progress of tests running on GitHub
- Clear success/failure indication when complete
- Easy access to detailed logs if needed

- [ ] Phase 3: Update documentation

Update documentation to reflect the new remote execution model:
- Update `docs/architecture/e2e-testing.md`:
  - Explain that `run_test.sh` now triggers remote execution
  - Remove references to local pytest execution polluting git state
  - Update prerequisites (no longer need pytest/Python locally)
  - Add section on monitoring remote test execution
  - Clarify that tests still run via pytest, just on GitHub's runners
- Update any inline comments in `run_test.sh` about what it does

Files to modify:
- `docs/architecture/e2e-testing.md`
- `tests/e2e/run_test.sh` (comments)

Expected outcome:
- Documentation accurately reflects new execution model
- Developers understand the benefits and how to use it

- [ ] Phase 4: Optional - Add support for passing branch/ref

Consider adding optional parameter to `run_test.sh`:
- Allow developers to specify which branch/ref to run tests from
- Default to current branch if not specified
- Pass through to `gh workflow run --ref <branch>`

Files to modify:
- `tests/e2e/run_test.sh`

Technical considerations:
- This allows testing feature branches without checking them out locally
- Syntax: `./tests/e2e/run_test.sh [branch-name]`
- Validate that the branch exists on remote before triggering

Expected outcome:
- Developers can test any remote branch without switching locally
- More flexible testing workflow

- [ ] Phase 5: Validation

Test the new remote execution flow:

**Manual testing:**
1. From main branch, run `./tests/e2e/run_test.sh`
2. Verify it triggers e2e-test.yml workflow on GitHub
3. Verify logs stream to console
4. Verify success/failure is reported correctly
5. Verify local git state is unchanged (no commits, no branch switches)
6. Test from a feature branch to ensure tests run with feature branch code

**Success criteria:**
- No local git mutations when running tests
- Clear feedback about remote execution
- Tests pass on GitHub (same as before)
- Documentation is accurate and clear
- Exit codes work correctly for CI integration
