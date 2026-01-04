# ClaudeChain Metadata Branch

This branch stores metadata for pull requests created by ClaudeChain.

## Purpose

ClaudeChain is a GitHub Action that automates code refactoring by creating incremental pull requests. This branch contains:

- **Task metadata**: Information about each PR created by ClaudeChain
- **Project tracking**: Progress and statistics for each ClaudeChain project
- **Cost tracking**: AI model usage costs for each PR

## Structure

```
claudechain-metadata/
├── projects/
│   ├── project-1.json
│   ├── project-2.json
│   └── project-3.json
└── README.md
```

### Files

- **`projects/{project-name}.json`**: Metadata for all PRs in a project
- **`README.md`**: This file

## What's Stored

Each project JSON file contains:

- Task definitions from `spec.md` (with status tracking)
- Pull request details (PR numbers, branch names, states)
- Assigned reviewers
- Creation timestamps
- Workflow run IDs for each AI operation
- AI cost tracking with detailed breakdowns (USD)

## Example

```json
{
  "schema_version": "2.0",
  "project": "my-refactor",
  "last_updated": "2025-01-15T10:30:00Z",
  "tasks": [
    {
      "index": 1,
      "description": "Refactor authentication",
      "status": "completed"
    },
    {
      "index": 2,
      "description": "Add input validation",
      "status": "pending"
    }
  ],
  "pull_requests": [
    {
      "task_index": 1,
      "pr_number": 42,
      "branch_name": "claude-chain-my-refactor-1",
      "reviewer": "alice",
      "pr_state": "merged",
      "created_at": "2025-01-10T14:22:00Z",
      "ai_operations": [
        {
          "type": "PRCreation",
          "model": "claude-sonnet-4",
          "cost_usd": 0.15,
          "created_at": "2025-01-10T14:22:00Z",
          "workflow_run_id": 123456
        },
        {
          "type": "PRSummary",
          "model": "claude-sonnet-4",
          "cost_usd": 0.02,
          "created_at": "2025-01-10T14:23:00Z",
          "workflow_run_id": 123456
        }
      ]
    }
  ]
}
```

## How It's Used

ClaudeChain reads this metadata to:

1. **Check reviewer capacity**: Ensure reviewers aren't over their `maxOpenPRs` limit
2. **Generate statistics**: Weekly team reports showing progress and contributions
3. **Track costs**: Monitor AI model usage costs per PR and project
4. **Show progress**: Display completion percentages in statistics

## Manual Inspection

You can view this metadata using:

```bash
# List all projects
git ls-tree -r --name-only claudechain-metadata projects/

# View a specific project
git show claudechain-metadata:projects/my-project.json

# Clone just the metadata branch
git clone --branch claudechain-metadata --single-branch <repo-url>
```

Or browse directly on GitHub: Switch to the `claudechain-metadata` branch in the GitHub UI.

## Schema Documentation

For complete schema documentation, see:
- Main repo: `docs/metadata-schema.md`
- GitHub: https://github.com/anthropics/claude-chain/blob/main/docs/metadata-schema.md

## Maintenance

- **Automatic updates**: ClaudeChain updates this branch automatically after each PR
- **Manual edits**: Not recommended (changes may be overwritten)
- **Branch protection**: This branch typically has no protection rules
- **Deletion**: Deleting this branch will cause ClaudeChain to recreate it with empty state

## Privacy Note

This metadata is stored in the same repository as your code. If your repository is:
- **Public**: This metadata is also public
- **Private**: This metadata is private to repository collaborators

The metadata contains:
- ✅ Task descriptions (from your spec.md files)
- ✅ GitHub usernames (reviewers)
- ✅ PR numbers and timestamps
- ❌ No code or sensitive data
- ❌ No API keys or credentials

## Questions?

For more information:
- ClaudeChain Documentation: https://github.com/anthropics/claude-chain
- Report Issues: https://github.com/anthropics/claude-chain/issues
