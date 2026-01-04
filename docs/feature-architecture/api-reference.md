# ClaudeChain CLI API Reference

This document provides quick reference commands for running ClaudeChain CLI operations locally.

## Prerequisites

Before running any commands, ensure you have:

1. Activated the Python virtual environment:
   ```bash
   source .venv/bin/activate
   ```

2. GitHub CLI (`gh`) authenticated:
   ```bash
   gh auth status
   ```

## Statistics Command

Generate statistics and reports for ClaudeChain projects.

### Quick Start

For the `gestrich/claude-chain` repository:

```bash
# Statistics for a specific project
source .venv/bin/activate && python -m claudechain statistics \
  --repo "gestrich/claude-chain" \
  --config-path claude-chain/e2e-test-project/configuration.yml

# Statistics for all projects (scans entire repository)
source .venv/bin/activate && python -m claudechain statistics \
  --repo "gestrich/claude-chain"
```

### All Options

```bash
python -m claudechain statistics \
  --repo "gestrich/claude-chain" \           # GitHub repository (owner/name)
  --base-branch main \                       # Base branch to fetch specs from (default: main)
  --config-path <path> \                     # Optional: path to specific project config
  --days-back 30 \                           # Days to look back for statistics (default: 30)
  --format slack \                           # Output format: slack or json (default: slack)
  --show-reviewer-stats                      # Include reviewer leaderboard (default: off)
```

### Parameters

- `--repo`: **Required** - GitHub repository in `owner/name` format
  - For this repository, use: `gestrich/claude-chain`
  - The repository must exist on GitHub and be accessible via your `gh` CLI authentication

- `--base-branch`: Branch to fetch project specs from (default: `main`)

- `--config-path`: Optional path to a specific project configuration file
  - If provided, only that project will be analyzed
  - Example: `claude-chain/e2e-test-project/configuration.yml`
  - If omitted, all projects in the repository will be scanned

- `--days-back`: Number of days to look back for PR statistics (default: 30)

- `--format`: Output format (default: `slack`)
  - `slack`: Human-readable format with tables and progress bars
  - `json`: Machine-readable JSON format

- `--show-reviewer-stats`: Include reviewer leaderboard in output (default: off)
  - When enabled, shows a table ranking reviewers by merged PR count

### Output

The command generates:

1. **Slack-formatted report** (if format is `slack`):
   - Project progress with task counts, completion percentages, and status warnings
   - Projects needing attention section (if any issues exist)
   - Reviewer leaderboard (if `--show-reviewer-stats` is enabled)
   - Visual progress bars and tables

2. **JSON statistics** (always generated):
   - Project statistics (total tasks, completed, in-progress, pending, stale PR count)
   - Team member statistics (merged PRs, open PRs)
   - Timestamps and metadata

3. **GitHub Step Summary** (Markdown):
   - Written to `GITHUB_STEP_SUMMARY` if running in GitHub Actions
   - Contains detailed breakdown of all statistics

### Example Output

```
=== ClaudeChain Statistics Collection ===
Days back: 30
Config path: claude-chain/e2e-test-project/configuration.yml

Single project mode: claude-chain/e2e-test-project/configuration.yml

Processing 1 project(s)...
Tracking 1 unique reviewer(s)
Collecting statistics for project: e2e-test-project
  Tasks: 1/310 completed
  In-progress: 2
  Pending: 307

=== Collection Complete ===
Projects found: 1
Team members tracked: 1

*📊 Project Progress*
┌──────────────────┬──────┬────────┬───────┬─────────────────┬──────┬────────┐
│ Project          │ Open │ Merged │ Total │ Progress        │ Cost │ Status │
├──────────────────┼──────┼────────┼───────┼─────────────────┼──────┼────────┤
│ e2e-test-project │    2 │      1 │   310 │ ░░░░░░░░░░   0% │    - │        │
└──────────────────┴──────┴────────┴───────┴─────────────────┴──────┴────────┘
```

With `--show-reviewer-stats`, the leaderboard appears before project progress:

```
*🏆 Leaderboard*
┌──────┬──────────┬──────┬────────┐
│ Rank │ Username │ Open │ Merged │
├──────┼──────────┼──────┼────────┤
│ 🥇   │ gestrich │    1 │      2 │
└──────┴──────────┴──────┴────────┘
```

## Other Commands

See `python -m claudechain --help` for a full list of available commands:

```bash
python -m claudechain --help
```

Available commands:
- `prepare` - Prepare everything for Claude Code execution
- `finalize` - Finalize after Claude Code execution (commit, PR, summary)
- `prepare-summary` - Prepare prompt for PR summary generation
- `post-pr-comment` - Post unified PR comment with summary and cost breakdown
- `format-slack-notification` - Format Slack notification message for created PR
- `statistics` - Generate statistics and reports

## Notes

- All commands that interact with GitHub require the `gh` CLI to be authenticated
- The `--repo` parameter should always use `gestrich/claude-chain` for this repository
- Statistics are fetched from the GitHub API, not from local files
- Files must be committed and pushed to the specified branch (default: `main`) to be included in statistics
