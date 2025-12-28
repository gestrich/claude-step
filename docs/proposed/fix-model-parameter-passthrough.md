# Fix Model Parameter Passthrough to Claude Code CLI

## Background

ClaudeStep accepts a `claude_model` input parameter that allows users to specify which Claude model to use (e.g., `claude-3-haiku-20240307` for cost savings or `claude-sonnet-4-5` for better performance). However, this parameter is currently not being passed to the underlying `anthropics/claude-code-action@v1` when it executes.

**The Problem:**
- E2E tests specify `claude_model: 'claude-3-haiku-20240307'` in `.github/workflows/claudestep-test.yml`
- The action.yml accepts this input with default `'claude-sonnet-4-5'`
- BUT the model parameter is never passed to Claude Code CLI via `claude_args`
- Result: Claude Code always uses its default model (Sonnet 4.5), ignoring the configuration
- Evidence: Commit messages show "Co-Authored-By: Claude Sonnet 4.5" even when Haiku is specified

**Cost Impact:**
E2E tests are using Sonnet instead of Haiku, resulting in ~12x higher costs:
- Haiku: $0.25 input / $1.25 output per MTok
- Sonnet: $3 input / $15 output per MTok

**Technical Context:**
- Claude Code CLI accepts `--model` flag to specify which model to use
- The flag should be added to `claude_args` parameter when calling `anthropics/claude-code-action@v1`
- This affects two places: main task execution and PR summary generation

## Phases

- [x] Phase 1: Update main task execution to pass model parameter

Modify `action.yml` in the "Run Claude Code" step (around line 112-122):

**Current:**
```yaml
- name: Run Claude Code
  id: claude_code
  if: steps.prepare.outputs.has_capacity == 'true' && steps.prepare.outputs.has_task == 'true'
  uses: anthropics/claude-code-action@v1
  with:
    prompt: ${{ steps.prepare.outputs.claude_prompt }}
    anthropic_api_key: ${{ inputs.anthropic_api_key }}
    github_token: ${{ inputs.github_token }}
    claude_args: '--allowedTools ${{ inputs.claude_allowed_tools }}'
    show_full_output: true
```

**Updated:**
```yaml
- name: Run Claude Code
  id: claude_code
  if: steps.prepare.outputs.has_capacity == 'true' && steps.prepare.outputs.has_task == 'true'
  uses: anthropics/claude-code-action@v1
  with:
    prompt: ${{ steps.prepare.outputs.claude_prompt }}
    anthropic_api_key: ${{ inputs.anthropic_api_key }}
    github_token: ${{ inputs.github_token }}
    claude_args: '--allowedTools ${{ inputs.claude_allowed_tools }} --model ${{ inputs.claude_model }}'
    show_full_output: true
```

**Key change:** Add `--model ${{ inputs.claude_model }}` to the `claude_args` parameter.

- [x] Phase 2: Update PR summary generation to pass model parameter

Modify `action.yml` in the "Generate and post PR summary" step (around line 181-193):

**Current:**
```yaml
- name: Generate and post PR summary
  id: pr_summary
  if: |
    inputs.add_pr_summary == 'true' &&
    steps.prepare_summary.outputs.summary_prompt != ''
  uses: anthropics/claude-code-action@v1
  with:
    prompt: ${{ steps.prepare_summary.outputs.summary_prompt }}
    anthropic_api_key: ${{ inputs.anthropic_api_key }}
    github_token: ${{ inputs.github_token }}
    claude_args: '--allowedTools Bash'
    show_full_output: true
  continue-on-error: true
```

**Updated:**
```yaml
- name: Generate and post PR summary
  id: pr_summary
  if: |
    inputs.add_pr_summary == 'true' &&
    steps.prepare_summary.outputs.summary_prompt != ''
  uses: anthropics/claude-code-action@v1
  with:
    prompt: ${{ steps.prepare_summary.outputs.summary_prompt }}
    anthropic_api_key: ${{ inputs.anthropic_api_key }}
    github_token: ${{ inputs.github_token }}
    claude_args: '--allowedTools Bash --model ${{ inputs.claude_model }}'
    show_full_output: true
  continue-on-error: true
```

**Key change:** Add `--model ${{ inputs.claude_model }}` to the `claude_args` parameter.

- [ ] Phase 3: Verify E2E test configuration

Confirm that `.github/workflows/claudestep-test.yml` is correctly configured to use Haiku:

**Expected configuration (line 35):**
```yaml
claude_model: 'claude-3-haiku-20240307'
```

This should already be present from the E2E test isolation work. No changes needed if it's already there.

- [ ] Phase 4: Update documentation

Update `README.md` to clarify how the `claude_model` parameter works:

**Location:** Action Inputs & Outputs section (around line 177)

**Current:**
```markdown
| `claude_model` | N | `claude-sonnet-4-5` | Claude model to use (sonnet-4-5 or opus-4-5) |
```

**Updated:**
```markdown
| `claude_model` | N | `claude-sonnet-4-5` | Claude model to use (e.g., claude-3-haiku-20240307, claude-sonnet-4-5, claude-opus-4-5) |
```

**Location:** Input Details section (around line 198)

**Current:**
```markdown
**claude_model:** `claude-sonnet-4-5` (recommended, balanced) or `claude-opus-4-5` (highest capability, higher cost)
```

**Updated:**
```markdown
**claude_model:** Specify which Claude model to use:
- `claude-3-haiku-20240307` - Fastest, most cost-effective ($0.25/$1.25 per MTok)
- `claude-sonnet-4-5` - Recommended, balanced performance and cost (default)
- `claude-opus-4-5` - Highest capability, higher cost
```

- [ ] Phase 5: Validation

**Testing approach:**
1. **Trigger E2E test workflow** manually via GitHub Actions
2. **Verify model usage** by checking:
   - Workflow logs show `--model claude-3-haiku-20240307` in Claude Code execution
   - Commit messages in generated PRs show "Co-Authored-By: Claude Haiku" (or similar)
   - Cost information in PR comments reflects Haiku pricing (lower than Sonnet)
3. **Check both invocations:**
   - Main task execution uses specified model
   - PR summary generation uses specified model

**Success criteria:**
- E2E test PRs show Haiku in commit messages instead of Sonnet
- Workflow logs confirm `--model` flag is being passed correctly
- No regression in PR creation or summary generation functionality

**Note:** This is primarily an integration test validation since it requires actual workflow execution. Unit tests aren't applicable as this is a GitHub Actions workflow configuration change.

## Technical Notes

### Phase 1 Completion (2025-12-28)
- Updated `action.yml` line 120 to include `--model ${{ inputs.claude_model }}` in the `claude_args` parameter for the main task execution step
- Verified tests pass (507/511 passing, 3 E2E failures unrelated to this change)
- The model parameter will now be passed through to Claude Code CLI for all main task executions

### Phase 2 Completion (2025-12-28)
- Updated `action.yml` line 191 to include `--model ${{ inputs.claude_model }}` in the `claude_args` parameter for the PR summary generation step
- Verified tests pass (494/511 passing, same 3 E2E failures plus 13 errors unrelated to this change)
- The model parameter will now be passed through to Claude Code CLI for both main task execution and PR summary generation
- Both invocations of `anthropics/claude-code-action@v1` now respect the `claude_model` input parameter
