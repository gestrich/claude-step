# ClaudeStep Metadata Branch

This branch stores metadata for pull requests created by ClaudeStep.

## Purpose

ClaudeStep is a GitHub Action that automates code refactoring by creating incremental pull requests. This branch contains:

- **Task metadata**: Information about each PR created by ClaudeStep
- **Project tracking**: Progress and statistics for each ClaudeStep project
- **Cost tracking**: AI model usage costs for each PR

## Structure

```
claudestep-metadata/
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

- Task descriptions from `spec.md`
- PR numbers and branch names
- Assigned reviewers
- Creation timestamps
- Workflow run IDs
- PR states (open, merged, closed)
- AI cost tracking (USD)

## Example

```json
{
  "schema_version": "1.0",
  "project": "my-refactor",
  "last_updated": "2025-01-15T10:30:00Z",
  "tasks": [
    {
      "task_index": 1,
      "task_description": "Refactor authentication",
      "branch_name": "claude-step-my-refactor-1",
      "reviewer": "alice",
      "pr_number": 42,
      "pr_state": "merged",
      "created_at": "2025-01-10T14:22:00Z",
      "workflow_run_id": 123456,
      "main_task_cost_usd": 0.15,
      "pr_summary_cost_usd": 0.02,
      "total_cost_usd": 0.17
    }
  ]
}
```

## How It's Used

ClaudeStep reads this metadata to:

1. **Check reviewer capacity**: Ensure reviewers aren't over their `maxOpenPRs` limit
2. **Generate statistics**: Weekly team reports showing progress and contributions
3. **Track costs**: Monitor AI model usage costs per PR and project
4. **Show progress**: Display completion percentages in statistics

## Manual Inspection

You can view this metadata using:

```bash
# List all projects
git ls-tree -r --name-only claudestep-metadata projects/

# View a specific project
git show claudestep-metadata:projects/my-project.json

# Clone just the metadata branch
git clone --branch claudestep-metadata --single-branch <repo-url>
```

Or browse directly on GitHub: Switch to the `claudestep-metadata` branch in the GitHub UI.

## Schema Documentation

For complete schema documentation, see:
- Main repo: `docs/metadata-schema.md`
- GitHub: https://github.com/anthropics/claude-step/blob/main/docs/metadata-schema.md

## Maintenance

- **Automatic updates**: ClaudeStep updates this branch automatically after each PR
- **Manual edits**: Not recommended (changes may be overwritten)
- **Branch protection**: This branch typically has no protection rules
- **Deletion**: Deleting this branch will cause ClaudeStep to recreate it with empty state

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
- ClaudeStep Documentation: https://github.com/anthropics/claude-step
- Report Issues: https://github.com/anthropics/claude-step/issues
