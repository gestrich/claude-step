## Background

ClaudeStep previously had AI-generated PR summary functionality that would analyze the diff and post a summary comment to each PR. This feature was added in commit e680d1f and later enhanced with cost tracking in commit ab68ce6.

Currently, the summary infrastructure is still in place:
- The `add_pr_summary` input exists in action.yml (line 39-42) and defaults to `true`
- The `prepare-summary` command generates a prompt successfully (logs show "✅ Summary prompt prepared for PR #114")
- The summary prompt template exists at `src/claudestep/resources/prompts/summary_prompt.md`
- The `Generate and post PR summary` step is defined in action.yml (lines 182-193)

However, PR summaries are no longer being posted to PRs. Recent PRs (e.g., #114) only show cost breakdown comments but lack the AI-generated summary that should explain what changes were made and why.

Investigation reveals that while the prompt is being prepared, the actual Claude Code execution to generate and post the summary may not be running or may be failing silently due to the `continue-on-error: true` flag.

## Phases

- [ ] Phase 1: Investigate why summary posting stopped working

Examine recent workflow runs to understand exactly where the summary generation process is failing:
- Check if the "Generate and post PR summary" step is being skipped or failing
- **CRITICAL**: Investigate the conditional logic in action.yml lines 167-168 and 184-186:
  - `inputs.add_pr_summary == 'true'` - Verify if this input is actually being passed as `'true'` (string) vs `true` (boolean)
  - `steps.finalize.outputs.pr_number != ''` - Confirm PR number is being output correctly
  - `steps.prepare_summary.outputs.summary_prompt != ''` - Verify the prompt is being generated and output
  - Check if GitHub Actions is interpreting boolean inputs correctly (may need to use `inputs.add_pr_summary != 'false'` instead)
- Look for any error messages in workflow logs related to the Claude Code action for summary generation
- Check if the step is being skipped due to condition evaluation
- Examine the "Prepare summary prompt" step (lines 164-180) to see if it's running and setting outputs
- Check if there are any issues with the anthropics/claude-code-action@v1 integration

**Specific investigation tasks**:
1. Check workflow run 20625002452 logs for "Prepare summary prompt" step status
2. Check if "Generate and post PR summary" step appears in the logs at all
3. Look for GitHub Actions step condition evaluation messages
4. Verify the value of `add_pr_summary` input in workflow dispatch (may be defaulting incorrectly)

Files to review:
- `.github/workflows/claudestep.yml` (or wherever ClaudeStep is invoked)
- Recent workflow run logs (especially 20625002452)
- `action.yml` lines 164-194
- Check how the action is being called to see if `add_pr_summary` input is explicitly set

Expected outcome: Clear understanding of the root cause why summaries stopped being posted, particularly whether it's a conditional logic issue with the `add_pr_summary` input

- [ ] Phase 2: Fix the summary generation step

Based on Phase 1 findings, implement the fix:
- If the step is being skipped, fix the conditional logic (likely boolean vs string comparison issue)
- If Claude Code is failing, investigate and fix the error (may need to check anthropics/claude-code-action compatibility)
- **IMPORTANT**: Remove `continue-on-error: true` from the summary generation step (line 194 in action.yml)
  - This is a code smell that masks failures and makes debugging impossible
  - If the step fails, we need to see the error, not silently continue
  - The workflow should fail loudly if summary generation fails, not hide the issue
- Ensure the summary comment is being posted to the PR correctly

Key considerations:
- The summary prompt expects Claude to run `gh pr diff` and `gh pr comment`
- The claude_args specify `--allowedTools Bash,Write` which should be sufficient
- The show_full_output flag is set to true for debugging
- Removing `continue-on-error` will expose any hidden failures

Files to modify:
- `action.yml` (lines 182-194) - Remove `continue-on-error: true` from line 194
- `action.yml` (lines 164-180) - May need to fix boolean comparison in conditional
- Potentially `src/claudestep/cli/commands/prepare_summary.py` if output format needs adjustment
- Potentially `src/claudestep/resources/prompts/summary_prompt.md` if prompt needs refinement

Expected outcome: Summary generation step executes successfully and posts comments, or fails loudly with clear error messages

- [ ] Phase 3: Verify summary format and content quality

Ensure the posted summaries meet quality standards:
- Verify the summary comment format matches the template (includes "## AI-Generated Summary" header)
- Check that summaries are concise (<200 words as specified in prompt)
- Ensure summaries explain both what changed and why
- Confirm the footer with workflow URL is included

Files to check:
- `src/claudestep/resources/prompts/summary_prompt.md` - may need prompt refinement
- Example PR comments to assess quality

Expected outcome: Posted summaries are well-formatted and provide useful information

- [ ] Phase 4: Update E2E tests to properly validate summaries

The E2E test `test_basic_workflow_end_to_end` currently checks for summary comments but uses a broad pattern that doesn't match the actual format:
- Test looks for "Summary" or "Changes" in comment body (line 113)
- Actual format uses "## AI-Generated Summary" header
- Need to update test to match the actual comment format

Files to modify:
- `tests/e2e/test_workflow_e2e.py` lines 111-116
- Update the pattern to look for "AI-Generated Summary" instead of generic "Summary"
- Consider also checking for the ClaudeStep footer

Expected outcome: E2E test accurately validates that summary comments are being posted

- [ ] Phase 5: Validation

Run end-to-end tests and manual verification:

**IMPORTANT**: Always run E2E tests using the provided script:
```bash
tests/e2e/run_test.sh
```
- Do NOT run pytest directly for E2E tests
- The script triggers the actual GitHub Actions workflow and monitors results
- Watch the script output for test results and workflow URLs

Validation steps:
1. Run `tests/e2e/run_test.sh` to execute the E2E test suite
2. Monitor the script output to ensure `test_basic_workflow_end_to_end` passes
3. Check the workflow run URLs provided in the output
4. Verify that the test PR receives both:
   - Cost breakdown comment (existing functionality)
   - AI-generated summary comment (restored functionality)
5. Check that the summary comment has the expected format with "## AI-Generated Summary" header
6. Verify summary content is relevant and useful
7. If tests fail, check the uploaded artifacts for detailed logs

Success criteria:
- E2E test script completes successfully
- `test_basic_workflow_end_to_end` passes
- Test PRs receive both cost and summary comments
- Summary comments follow the expected format (includes "## AI-Generated Summary")
- Summary content accurately describes the changes made
- No workflow failures or hidden errors
