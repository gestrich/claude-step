## Background

The current Slack notification for ClaudeChain statistics uses Unicode box-drawing characters (┌─┬─┐, │, └─┴─┘) to render tables. While this works, the resulting output is visually unappealing in Slack because:

1. **Monospace dependency**: The table relies on fixed-width fonts, but Slack doesn't guarantee consistent monospace rendering
2. **Code block ugliness**: Tables are wrapped in triple backticks (```), creating a gray code block that looks out of place in a notification
3. **No native styling**: Inside code blocks, we lose all Slack formatting (bold, links, emojis render as text)
4. **Mobile issues**: Wide tables require horizontal scrolling on mobile devices

Based on research into Slack's Incoming Webhook capabilities, the best solution is to use **Slack Block Kit** with **Section Fields** for tabular data. Key findings:

- Slack fully supports Block Kit in incoming webhooks
- Section blocks with `fields` display as a 2-column grid (up to 10 fields)
- Header blocks provide native large bold titles
- Context blocks work well for metadata/timestamps
- mrkdwn formatting (bold, links, emoji) works in all blocks
- The Table Block was officially released in August 2025 (previously beta), but has limitations:
  - Must be placed in `attachments` field, not `blocks`
  - Only one table per message allowed
  - Unclear if it works with incoming webhooks (docs only mention `chat.postMessage`)

**Recommended approach**: Start with an experiment to test whether the Table Block works with incoming webhooks. If it does, use it for clean tabular data. If not, fall back to Section fields approach.

## First Implementation Attempt (Reverted)

An initial implementation was completed through all phases but had to be reverted. During initial experimentation with the Slack Block Kit Builder UI, the blocks rendered correctly with proper formatting (bold text, progress bars, clickable links). However, when integrated into the actual statistics command, the output displayed as raw JSON instead of rendered blocks:

```json
{"text": "ClaudeChain Statistics", "blocks": [{"type": "header", "text": {"type": "plain_text", "text": "ClaudeChain Statistics", "emoji": true}}, {"type": "context", "elements": [{"type": "mrkdwn", "text": "📅 2026-01-07"}]}, {"type": "divider"}, {"type": "section", "text": {"type": "mrkdwn", "text": "cleanup ✅\n██████████ 100%"}}, {"type": "context", "elements": [{"type": "mrkdwn", "text": "9/9 merged  •  💰 $1.66"}]}, {"type": "divider"}, {"type": "section", "text": {"type": "mrkdwn", "text": "*remove-dead-files*\n█████░░░░░ 52%"}}, {"type": "context", "elements": [{"type": "mrkdwn", "text": "11/21 merged  •  💰 $2.56"}]}, {"type": "section", "text": {"type": "mrkdwn", "text": "• #35 [remove-dead-files] Sources/Pages/Examples/LinkExamples.swift (0d)"}}, {"type": "divider"}, {"type": "context", "elements": [{"type": "mrkdwn", "text": "Elapsed time: 30.6s"}]}]}
```

Issues observed:
- Project name "cleanup" was missing asterisks (should be `*cleanup*` for bold)
- PR links were missing URLs (showed `• #35 [title]` instead of `<url|#35 title>`)
- Multiple fix attempts did not resolve the underlying issue

The root cause appears to be something in how the implementation integrated with the statistics command versus the standalone experiments. The commits were reverted to preserve a working state while this is investigated further.

## Phases

- [ ] Phase 1: Experiment with Table Block in webhooks

Before implementing, test whether Slack's Table Block works with incoming webhooks. Create a simple test script that sends a webhook payload with a table block.

Test payload structure:
```json
{
  "text": "Fallback: Project Statistics",
  "attachments": [
    {
      "blocks": [
        {
          "type": "table",
          "rows": [
            [
              {"type": "raw_text", "text": "Project"},
              {"type": "raw_text", "text": "Open"},
              {"type": "raw_text", "text": "Merged"}
            ],
            [
              {"type": "raw_text", "text": "auth-migration"},
              {"type": "raw_text", "text": "1"},
              {"type": "raw_text", "text": "4"}
            ]
          ],
          "column_settings": [
            {"align": "left"},
            {"align": "right"},
            {"align": "right"}
          ]
        }
      ]
    }
  ]
}
```

Test script location: `scripts/test_slack_table_block.py`

This script should:
1. Accept a Slack webhook URL as argument or environment variable
2. Send the test payload
3. Report success/failure
4. If successful, document the working payload structure

**Decision point**: If the Table Block works, proceed with Phase 2a (Table Block implementation). If not, proceed with Phase 2b (Section fields fallback).

- [ ] Phase 2a: Implement Table Block formatter (if experiment succeeds)

If Phase 1 confirms Table Block works with webhooks, create a formatter that uses it:

Files to create/modify:
- Create `src/claudechain/domain/formatters/slack_block_kit_formatter.py`
- Implement table block generation for project progress and leaderboard

Skip to Phase 6 after this.

- [ ] Phase 2b: Create Block Kit message builder (if Table Block doesn't work)

If the Table Block experiment fails, use Section fields approach instead. Create a new `SlackBlockKitFormatter` class that outputs Slack Block Kit JSON structures instead of plain mrkdwn text. This formatter will:

- Generate `blocks` array structure for Slack payloads
- Support Header blocks for titles
- Support Section blocks with text and fields
- Support Context blocks for metadata
- Support Divider blocks

Files to modify:
- Create `src/claudechain/domain/formatters/slack_block_kit_formatter.py`

- [ ] Phase 3: Convert header and metadata to Block Kit (Section fields path only)

Update the statistics report header section to use Block Kit:

Current:
```
*ClaudeChain Statistics Report*
_Generated: 2025-01-03 12:00 UTC_
```

Target Block Kit structure:
```json
{
  "type": "header",
  "text": {"type": "plain_text", "text": "ClaudeChain Statistics Report"}
}
{
  "type": "context",
  "elements": [
    {"type": "mrkdwn", "text": "Generated: 2025-01-03 12:00 UTC | Branch: main"}
  ]
}
```

Files to modify:
- `src/claudechain/domain/models.py` - Add `to_header_blocks()` method to `StatisticsReport`
- `src/claudechain/domain/formatters/slack_block_kit_formatter.py`

- [ ] Phase 4: Convert project progress table to Section fields (Section fields path only)

Replace the ASCII table with Section blocks using fields for a cleaner 2-column layout.

Current ugly format:
```
┌──────────────────┬──────┬────────┬───────┬─────────────────┬───────┐
│ Project          │ Open │ Merged │ Total │ Progress        │ Cost  │
├──────────────────┼──────┼────────┼───────┼─────────────────┼───────┤
│ auth-migration   │    1 │      4 │    10 │ ████░░░░░░  40% │ $0.45 │
└──────────────────┴──────┴────────┴───────┴─────────────────┴───────┘
```

Target Block Kit structure (for each project):
```json
{
  "type": "section",
  "text": {"type": "mrkdwn", "text": "*auth-migration*\n████░░░░░░ 40%"},
  "fields": [
    {"type": "mrkdwn", "text": "*Open:* 1"},
    {"type": "mrkdwn", "text": "*Merged:* 4"},
    {"type": "mrkdwn", "text": "*Total:* 10"},
    {"type": "mrkdwn", "text": "*Cost:* $0.45"}
  ]
}
```

Files to modify:
- `src/claudechain/domain/models.py` - Add `to_project_progress_blocks()` method
- `src/claudechain/domain/formatters/slack_block_kit_formatter.py`

- [ ] Phase 5: Convert leaderboard to Section fields (Section fields path only)

Replace leaderboard ASCII table with cleaner Block Kit sections.

Current:
```
┌──────┬──────────┬──────┬────────┐
│ Rank │ Username │ Open │ Merged │
├──────┼──────────┼──────┼────────┤
│ 🥇   │ alice    │    1 │      5 │
└──────┴──────────┴──────┴────────┘
```

Target:
```json
{
  "type": "section",
  "text": {"type": "mrkdwn", "text": "*Leaderboard*"}
},
{
  "type": "section",
  "fields": [
    {"type": "mrkdwn", "text": "🥇 *alice*\n5 merged, 1 open"},
    {"type": "mrkdwn", "text": "🥈 *bob*\n3 merged, 2 open"}
  ]
}
```

Files to modify:
- `src/claudechain/domain/models.py` - Add `to_leaderboard_blocks()` method
- `src/claudechain/domain/formatters/slack_block_kit_formatter.py`

- [ ] Phase 6: Convert warnings section to Block Kit (both paths)

Update the warnings/attention section to use Block Kit with proper links.

Target:
```json
{
  "type": "section",
  "text": {"type": "mrkdwn", "text": "*⚠️ Needs Attention*"}
},
{
  "type": "section",
  "text": {"type": "mrkdwn", "text": "*auth-migration*\n• <https://github.com/...|#42> (5d, stale)\n• No open PRs (3 tasks remaining)"}
}
```

Files to modify:
- `src/claudechain/domain/models.py` - Add `to_warnings_blocks()` method
- `src/claudechain/domain/formatters/slack_block_kit_formatter.py`

- [ ] Phase 7: Update format_for_slack to output Block Kit JSON (both paths)

Modify `StatisticsReport.format_for_slack()` to return a JSON structure with `blocks` array instead of plain text, and update the statistics command to handle this.

Files to modify:
- `src/claudechain/domain/models.py` - Update `format_for_slack()` to return dict with blocks
- `src/claudechain/cli/commands/statistics.py` - Handle JSON output for Slack webhook

Key change: The webhook payload structure changes from:
```json
{"text": "plain text message"}
```
to:
```json
{
  "text": "Fallback text for notifications",
  "blocks": [...]
}
```

- [ ] Phase 8: Update tests (both paths)

Update existing tests to verify the new Block Kit output structure.

Files to modify:
- `tests/unit/domain/test_models.py` - Update tests for new block methods
- `tests/integration/cli/commands/test_statistics.py` - Verify Block Kit JSON output
- Create `tests/unit/domain/formatters/test_slack_block_kit_formatter.py`

Test requirements:
- Verify blocks array structure is valid
- Verify header blocks use plain_text (required by Slack)
- Verify section fields are limited to 10 per section
- Verify mrkdwn text uses correct syntax
- Verify fallback text is included for notification previews

- [ ] Phase 9: Validation (both paths)

Run full test suite and verify output:

```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v --cov=src/claudechain --cov-report=term-missing
```

Manual verification:
- Run statistics command locally and inspect JSON output
- Validate Block Kit JSON using Slack's Block Kit Builder (https://app.slack.com/block-kit-builder)
- Optionally test with a real Slack webhook to verify rendering
