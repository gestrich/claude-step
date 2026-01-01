## Background

Currently, the ClaudeStep workflows (`claudestep-auto-start.yml` and `claudestep.yml`) use hardcoded or explicitly configured base branches. This creates coupling between the workflow configuration and the branch being worked on, requiring different configurations for production (`main`) vs E2E testing (`main-e2e`).

**The Problem:**
- Auto-start workflow needs to know which base branch to use (`main` vs `main-e2e`)
- ClaudeStep workflow needs to know which base branch PRs should target
- This creates duplication and requires branch-specific logic

**The Insight:**
The base branch is implicitly defined by **where the spec was merged**. If a spec is merged to `main`, then:
1. Auto-start creates PRs targeting `main`
2. When those PRs merge, the next PR also targets `main`

The branch context flows through the workflow naturally:
- **Spec merge**: The branch where the spec lives IS the base branch
- **Auto-start PR**: Targets the branch where the spec was pushed
- **Subsequent PRs**: Target the same branch as the previous PR (from `github.base_ref`)

This makes workflows completely generic - they work on ANY branch without configuration.

**Architectural Constraint (from [docs/general-architecture/github-actions.md](../general-architecture/github-actions.md)):**
ClaudeStep follows a **base branch source of truth** pattern where spec files (`spec.md`, `configuration.yml`) are **always fetched from the base branch via GitHub API**, never from the filesystem. This means:
- The base branch determines where specs are read from
- All ClaudeStep operations fetch specs using `get_file_from_branch(repo, base_branch, file_path)`
- PRs **do** modify spec files (they mark tasks as complete in `spec.md`)
- When PRs merge, the updated spec is now in the base branch for the next workflow run
- The base branch must be correctly determined for workflows to function

This architectural principle makes the base branch detection even more critical - it's not just about PR targeting, it's about knowing **which branch to fetch spec files from** and **where updated specs will be merged to**.

## User Requirements

1. **Generic workflows**: Auto-start and ClaudeStep workflows should work on ANY branch (main, main-e2e, feature branches, etc.)
2. **No hardcoded branches**: Remove all hardcoded `main` or `main-e2e` references from workflow logic
3. **Infer base from context**: Derive the base branch from the GitHub event context (push, PR merge)
4. **Maintain compatibility**: Existing production usage on `main` should work unchanged
5. **Enable E2E testing**: E2E tests on `main-e2e` should work without workflow changes

## Phases

- [ ] Phase 1: Analyze current base branch usage

**Goal**: Understand where and how base branches are currently used in workflows.

**Tasks**:
1. Review [claudestep-auto-start.yml](../.github/workflows/claudestep-auto-start.yml) for base branch usage:
   - Trigger conditions (`on.push.branches`)
   - Environment variables (`BASE_BRANCH`)
   - How base branch is passed to the auto-start command

2. Review [claudestep.yml](../.github/workflows/claudestep.yml) for base branch usage:
   - Workflow inputs (`base_branch`, `checkout_ref`)
   - How base branch is determined for PR merge events
   - How base branch is passed to ClaudeStep commands

3. Review [src/claudestep/cli/commands/auto_start.py](../../src/claudestep/cli/commands/) to understand how auto-start uses `BASE_BRANCH`

4. Review [src/claudestep/cli/commands/prepare.py](../../src/claudestep/cli/commands/) to understand how prepare command uses base branch

5. Document current flow:
   - How base branch flows from workflow → CLI → services
   - What happens if base branch is wrong or missing
   - Where base branch affects PR creation, spec reading, etc.

**Expected outcome**: Clear understanding of all base branch touchpoints and dependencies.

---

- [ ] Phase 2: Design generic base branch inference

**Goal**: Design how workflows will infer base branch from GitHub event context.

**Tasks**:
1. Define inference rules for different trigger types:

   **Auto-Start Workflow (triggered by push):**
   - Triggered when: Spec file pushed to a branch
   - Base branch = `${{ github.ref_name }}` (the branch that was pushed to)
   - Example: Push to `main-e2e` → base branch is `main-e2e`

   **ClaudeStep Workflow (triggered by workflow_dispatch):**
   - Triggered when: Manually invoked or called by auto-start
   - Base branch = `${{ inputs.base_branch }}` OR `${{ github.ref_name }}`
   - Fallback: If not provided, use the branch being checked out

   **ClaudeStep Workflow (triggered by PR merge):**
   - Triggered when: PR with "claudestep" label is merged
   - Base branch = `${{ github.base_ref }}` (the branch the PR was merged INTO)
   - Example: PR merges into `main-e2e` → base branch is `main-e2e`

2. Design validation logic:
   - Ensure base branch is always set before running ClaudeStep commands
   - Log the derived base branch for debugging
   - Fail fast if base branch cannot be determined

3. Update workflow parameter strategy:
   - Remove default values for `base_branch` (let it be inferred)
   - Keep `base_branch` as optional override for manual testing
   - Document when manual override is appropriate

**Expected outcome**: Clear rules for inferring base branch from any GitHub event.

---

- [ ] Phase 3: Update auto-start workflow

**Goal**: Make auto-start workflow derive base branch from push event.

**Tasks**:
1. Update [claudestep-auto-start.yml](../.github/workflows/claudestep-auto-start.yml):

   ```yaml
   on:
     push:
       branches:
         - main
         - main-e2e
         # Could even be '**' to support any branch
       paths:
         - 'claude-step/*/spec.md'
   ```

2. Update environment variable to use event context:

   ```yaml
   env:
     # Derive base branch from the branch that was pushed to
     BASE_BRANCH: ${{ github.ref_name }}
   ```

3. Add logging to workflow for debugging:

   ```yaml
   - name: Log derived base branch
     run: echo "Base branch derived from push event: ${{ github.ref_name }}"
   ```

4. Remove any hardcoded branch references in the workflow

5. Test scenarios:
   - Push spec to `main` → derives `main`
   - Push spec to `main-e2e` → derives `main-e2e`
   - Push spec to `feature/test` → derives `feature/test`

**Expected outcome**: Auto-start workflow works on any branch without configuration changes.

---

- [ ] Phase 4: Update main ClaudeStep workflow

**Goal**: Make ClaudeStep workflow derive base branch from event context.

**Tasks**:
1. Update [claudestep.yml](../.github/workflows/claudestep.yml) workflow_dispatch inputs:

   ```yaml
   on:
     workflow_dispatch:
       inputs:
         project_name:
           required: true
         base_branch:
           description: 'Base branch (optional - will be inferred if not provided)'
           required: false
           # No default - will be inferred from checkout_ref
         checkout_ref:
           description: 'Branch to checkout'
           required: false
           default: 'main'
   ```

2. Update the "Determine project and checkout ref" step to infer base branch:

   ```yaml
   - name: Determine project and base branch
     id: project
     run: |
       if [ "${{ github.event_name }}" = "workflow_dispatch" ]; then
         PROJECT="${{ github.event.inputs.project_name }}"

         # Infer base branch: use input if provided, else use checkout_ref
         if [ -n "${{ github.event.inputs.base_branch }}" ]; then
           BASE_BRANCH="${{ github.event.inputs.base_branch }}"
         else
           BASE_BRANCH="${{ github.event.inputs.checkout_ref || 'main' }}"
         fi

         CHECKOUT_REF="${{ github.event.inputs.checkout_ref || 'main' }}"

       elif [ "${{ github.event_name }}" = "pull_request" ]; then
         # Extract project from branch name
         BRANCH="${{ github.head_ref }}"
         PROJECT=$(echo "$BRANCH" | sed -E 's/^claude-step-([^-]+)-[0-9]+$/\1/')

         # Base branch is where the PR was merged INTO
         BASE_BRANCH="${{ github.base_ref }}"
         CHECKOUT_REF="${{ github.base_ref }}"
       fi

       echo "name=$PROJECT" >> $GITHUB_OUTPUT
       echo "base_branch=$BASE_BRANCH" >> $GITHUB_OUTPUT
       echo "checkout_ref=$CHECKOUT_REF" >> $GITHUB_OUTPUT
       echo "Determined: project=$PROJECT, base=$BASE_BRANCH, checkout=$CHECKOUT_REF"
   ```

3. Add validation to ensure base branch is set:

   ```yaml
   - name: Validate base branch
     run: |
       if [ -z "${{ steps.project.outputs.base_branch }}" ]; then
         echo "ERROR: Base branch could not be determined"
         exit 1
       fi
       echo "✓ Base branch: ${{ steps.project.outputs.base_branch }}"
   ```

4. Update ClaudeStep action call to use derived base branch:

   ```yaml
   - name: Run ClaudeStep action
     uses: ./
     with:
       base_branch: ${{ steps.project.outputs.base_branch }}
   ```

**Expected outcome**: ClaudeStep workflow infers base branch from PR merge events or uses checkout_ref as fallback.

---

- [ ] Phase 5: Update workflow documentation

**Goal**: Document the new generic workflow behavior.

**Tasks**:
1. Add comments to [claudestep-auto-start.yml](../.github/workflows/claudestep-auto-start.yml):
   ```yaml
   # This workflow is generic and works on ANY branch.
   # The base branch is automatically derived from the push event (github.ref_name).
   # When a spec is pushed to 'main', PRs target 'main'.
   # When a spec is pushed to 'main-e2e', PRs target 'main-e2e'.
   ```

2. Add comments to [claudestep.yml](../.github/workflows/claudestep.yml):
   ```yaml
   # This workflow is generic and works on ANY branch.
   # Base branch inference:
   # - PR merge: Uses github.base_ref (branch PR was merged into)
   # - Manual trigger: Uses base_branch input if provided, else checkout_ref
   # - Auto-start: Called by auto-start workflow with explicit base_branch
   ```

3. Update [docs/feature-guides/](../../docs/feature-guides/) if there's documentation about workflows

4. Update README or workflow documentation to explain:
   - Workflows now work on any branch automatically
   - No need to configure base branches for different environments
   - How to override base branch for testing (use `base_branch` input)

**Expected outcome**: Clear documentation explaining generic workflow behavior.

---

- [ ] Phase 6: Update E2E test plan

**Goal**: Simplify the E2E test redesign plan by removing workflow-specific phases.

**Tasks**:
1. Update [docs/proposed/2026-01-01-redesign-e2e-tests.md](2026-01-01-redesign-e2e-tests.md):
   - Remove Phase 8 (Update auto-start workflow) - no longer needed
   - Remove Phase 9 (Update main claudestep workflow) - no longer needed
   - Update remaining phases to reflect that workflows are already generic

2. Update test expectations:
   - Tests don't need to configure workflow base branches
   - Tests just push specs to `main-e2e` and workflows automatically adapt
   - Simplifies test setup and reduces coupling

**Expected outcome**: E2E test plan is simpler without workflow-specific configuration phases.

---

- [ ] Phase 7: Handle edge cases and validation

**Goal**: Ensure generic workflows handle edge cases correctly.

**Tasks**:
1. Handle missing base branch gracefully:
   - Add validation that fails fast with clear error message
   - Log all derived values for debugging
   - Provide guidance on how to fix (e.g., "Provide base_branch input")

2. Test branch name edge cases:
   - Branch names with slashes (`feature/new-thing`)
   - Branch names with special characters
   - Very long branch names

3. Consider security implications:
   - Can workflows be triggered on untrusted branches?
   - Should there be allowlist for which branches can trigger?
   - Document security considerations

4. Handle workflow_dispatch from GitHub UI:
   - User manually triggers on a branch
   - Ensure base_branch is correctly inferred or required
   - Test manual triggering from different branches

**Expected outcome**: Workflows handle edge cases and fail with clear error messages.

---

- [ ] Phase 8: Validation

**Goal**: Ensure generic workflows work correctly on all supported branches.

**Tasks**:
1. Test auto-start workflow:
   - Push spec to `main` → verify PR created targeting `main`
   - Push spec to `main-e2e` → verify PR created targeting `main-e2e`
   - Push spec to `feature/test` → verify PR created targeting `feature/test`

2. Test ClaudeStep workflow (PR merge):
   - Merge PR into `main` → verify next PR targets `main`
   - Merge PR into `main-e2e` → verify next PR targets `main-e2e`

3. Test ClaudeStep workflow (manual dispatch):
   - Trigger on `main` without base_branch input → verify uses `main`
   - Trigger with explicit base_branch → verify uses provided value
   - Trigger with invalid base_branch → verify fails with clear error

4. Verify E2E tests work with generic workflows:
   - Run E2E test suite
   - Verify tests don't need workflow-specific configuration
   - Verify `main-e2e` workflow executions work correctly

5. Verify production usage unchanged:
   - Specs pushed to `main` still create PRs correctly
   - PRs merged on `main` still trigger next PR correctly

**Success criteria**:
- All workflows work on any branch without configuration
- Base branch correctly inferred from event context
- E2E tests simplified (no workflow configuration needed)
- Production workflows continue working unchanged
- Clear error messages when base branch cannot be determined
