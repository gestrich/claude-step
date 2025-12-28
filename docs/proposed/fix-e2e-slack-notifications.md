# Fix E2E Test Slack Notifications

## Background

During e2e testing, the ClaudeStep Weekly statistics notifications are successfully posted to Slack, but PR creation notifications are not appearing. This issue occurs because:

1. **Statistics notifications work** because the `claudestep-statistics.yml` workflow sets `SLACK_WEBHOOK_URL` as a job-level environment variable (line 22), and the `slackapi/slack-github-action@v2` automatically picks it up when no explicit `webhook:` parameter is provided.

2. **PR notifications don't work** because:
   - The main `action.yml` requires `slack_webhook_url` to be passed as an action input parameter
   - This input is then passed explicitly to the Slack action via `webhook: ${{ steps.prepare.outputs.slack_webhook_url }}`
   - The `claudestep-test.yml` workflow does NOT pass the `slack_webhook_url` input to the action
   - Therefore, `steps.prepare.outputs.slack_webhook_url` is empty
   - The condition `steps.prepare.outputs.slack_webhook_url != ''` fails
   - The Slack notification step is silently skipped

The fix is straightforward: pass the `slack_webhook_url` input to the ClaudeStep action in the test workflow, just like we pass other secrets (anthropic_api_key, github_token).

## Phases

- [ ] Phase 1: Update claudestep-test.yml workflow

Modify `.github/workflows/claudestep-test.yml` to pass the Slack webhook URL as an input to the ClaudeStep action.

**Changes needed:**
- Add `slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}` to the action inputs in the "Run ClaudeStep action" step (after line 35)
- This passes the GitHub secret to the action, enabling PR notifications

**Files to modify:**
- `.github/workflows/claudestep-test.yml` (line 35, after `claude_model`)

**Expected outcome:**
- The ClaudeStep action will receive the Slack webhook URL
- `steps.prepare.outputs.slack_webhook_url` will be populated
- The condition for posting to Slack will pass
- PR creation notifications will be sent to Slack during e2e tests

- [ ] Phase 2: Document the requirement

Update documentation to clarify that the `slack_webhook_url` input is required for PR notifications.

**Changes needed:**
- Update the main README.md to document that users should pass `slack_webhook_url` as an action input
- Add example workflow snippet showing proper usage
- Clarify the difference between:
  - Statistics notifications (uses job-level env var)
  - PR notifications (requires action input)

**Files to modify:**
- `README.md` (in the usage/configuration section)

**Expected outcome:**
- Users understand they need to pass `slack_webhook_url` to get PR notifications
- Clear example showing both secrets being passed (ANTHROPIC_API_KEY and SLACK_WEBHOOK_URL)

- [ ] Phase 3: Validation

Verify that Slack notifications work correctly in e2e tests.

**Validation approach:**
1. Run the e2e test workflow manually via workflow_dispatch
2. Verify that:
   - The test creates a PR successfully
   - A Slack notification is posted for the PR creation
   - The notification contains correct PR details (number, title, link)
3. Check the workflow logs to confirm:
   - The "Slack webhook URL is configured" message appears
   - The "Post to Slack" step executes (not skipped)
   - No errors in the Slack posting step

**Success criteria:**
- E2E test completes successfully
- Slack notification appears for PR creation
- Notification format matches expected structure (blocks with PR info)
- No errors or warnings in workflow logs related to Slack

**Manual check:**
- Visually inspect the Slack message in the channel to ensure formatting is correct
