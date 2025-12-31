# Project Name Refactor Implementation Plan

## Problem

Current implementation uses `project_name` as a required input parameter. This doesn't work well with PR merge/close triggers because when a PR is merged or closed, the workflow is triggered automatically but there's no way to pass the project name as an input parameter.

## Solution Design

The solution requires deriving the project name from the PR that triggered the workflow, falling back to manual input for workflow_dispatch triggers.

## Implementation Phases

### Phase 1: Update Action Trigger Logic

**Objective:** Enable automatic project name derivation when workflow is triggered by PR close/merge events.

**Implementation:**
- Detect when action is triggered via PR that was closed or merged
- Extract PR number from the triggering event
- Derive associated project name from PR artifacts or metadata
- Investigate existing artifact-checking code for project name derivation logic
- Use derived project name to run the action

**Technical Considerations:**
- Check workflow event payload for PR information (`github.event.pull_request.number`)
- May need to read project name from PR labels, branch name pattern, or stored artifacts
- Ensure backwards compatibility during this phase

**Success Criteria:**
- Workflow can automatically determine project name from merged/closed PRs
- No manual intervention needed for PR-triggered workflow runs

### Phase 2: Manual Workflow Runs

**Objective:** Support manual workflow_dispatch triggers with user-provided project name.

**Implementation:**
- Add conditional logic to check trigger type
- For `workflow_dispatch` events:
  - Require user to enter project name as input via GitHub UI
  - Validate that project name input is provided
  - Throw clear error if project name is missing
- Ensure project name always comes from one of two sources:
  1. Derived from closed PR (Phase 1)
  2. Manually entered during workflow dispatch

**Technical Considerations:**
- Update workflow YAML to include `project_name` as input for workflow_dispatch
- Add input validation in action entry point
- Consider making project_name optional in YAML but required in code logic

**Success Criteria:**
- Manual workflow runs work correctly with user-provided project name
- Clear UI for entering project name in GitHub Actions interface

### Phase 3: Error Handling

**Objective:** Provide robust validation and helpful error messages.

**Implementation:**
- Add validation that project name is always available before action proceeds
- Implement error handling for scenarios where:
  - Neither PR-derived nor manually-provided project name exists
  - Project name derivation from PR fails
  - Invalid or empty project name provided
- Create clear, actionable error messages for debugging
- Log project name source (PR-derived vs manual) for troubleshooting

**Technical Considerations:**
- Log workflow trigger type and project name source
- Include PR number in error messages when relevant
- Provide troubleshooting hints in error messages

**Success Criteria:**
- All edge cases handled gracefully
- Error messages clearly explain what went wrong and how to fix it
- No silent failures or unclear error states

### Phase 4: Update README

**Objective:** Document the new project name handling for users.

**Implementation:**
- Update README to explain both trigger methods:
  1. Automatic (PR-based): Project name derived automatically
  2. Manual (workflow_dispatch): User enters project name
- Document project name derivation mechanism
- Add troubleshooting section for project name issues
- Update workflow YAML examples to show project_name input for manual runs
- Remove or update any sections that assume project_name is always manually provided

**Technical Considerations:**
- Keep documentation concise and clear
- Include examples of both trigger types
- Explain when each trigger type is appropriate

**Success Criteria:**
- Users understand how project name is determined
- Documentation covers both automatic and manual workflows
- Clear guidance on when to use workflow_dispatch with project_name input

## Implementation Order

1. **Phase 1** - Enables automatic PR-triggered workflows (primary use case)
2. **Phase 2** - Maintains support for manual workflow runs
3. **Phase 3** - Ensures robustness and debuggability
4. **Phase 4** - Communicates changes to users

## Testing Strategy

After each phase:
- Test PR merge trigger with project name derivation
- Test PR close (without merge) trigger
- Test manual workflow_dispatch with project name
- Test manual workflow_dispatch without project name (should error)
- Verify error messages are clear and actionable
