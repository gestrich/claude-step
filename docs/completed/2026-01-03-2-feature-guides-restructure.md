# Feature Guides Restructure

## Background

The current documentation structure has the README.md as the primary source of truth, with feature guides as supplementary material. This creates maintenance challenges and inconsistencies.

**New paradigm:** Feature guides are the source of truth. README.md is a condensed derivative that contains no details not found in the detailed guides. This ensures:
- Single source of truth for each feature
- README stays accurate by validating against guides
- Easier maintenance (update one place, derive the rest)

**Agreed structure (5 guides):**

```
docs/feature-guides/
├── how-it-works.md            # Core mental model: PR chain, task lifecycle, automatic continuation
├── setup.md                   # Workflow file, secrets, permissions, Claude Code app
├── projects.md                # spec.md + configuration.yml + modifying tasks
├── notifications.md           # Slack, PR summaries, statistics reports
└── troubleshooting.md
```

**Files to delete:** `getting-started.md`, `modifying-tasks.md` (content absorbed into new structure)

## Phases

- [x] Phase 1: Create `how-it-works.md`

Core mental model guide covering:
- What ClaudeStep does (high-level overview)
- The PR chain: Task → PR → Merge → Next Task
- Hash-based task identification (why reordering is safe)
- Branch naming conventions (`claude-step-{project}-{hash}`)
- What Claude Code does vs what the GitHub Action does
- Automatic continuation flow (claudestep label + merge triggers next)
- Orphaned PR detection (when task descriptions change)

This is the conceptual foundation that helps users understand everything else.

- [x] Phase 2: Create `setup.md`

One-time setup guide covering:
- Prerequisites (Anthropic API key)
- Creating the workflow file (`.github/workflows/claude-step.yml`)
  - Simplified workflow format
  - Required inputs (`anthropic_api_key`, `github_token`, etc.)
  - Triggers (`workflow_dispatch`, `pull_request: types: [closed]`)
  - Full workflow inputs/outputs reference
- GitHub repository settings:
  - Adding `ANTHROPIC_API_KEY` secret
  - Enabling "Allow GitHub Actions to create and approve pull requests"
  - Installing Claude Code GitHub App (`/install-github-app`)
- Starting ClaudeStep for the first time (manual trigger or labeled PR)

- [x] Phase 3: Create `projects.md`

Project authoring guide covering:
- Project structure (`claude-step/{project-name}/`)
- `spec.md` format:
  - Combining instructions and steps
  - Checkbox syntax (`- [ ]`, `- [x]`)
  - Task lifecycle (unchecked → PR → merged → auto-marked complete)
- `configuration.yml` format:
  - Reviewers array with `username` and `maxOpenPRs`
  - Optional `baseBranch` override
  - Full schema reference
- Modifying tasks safely:
  - Reordering (safe - hash-based)
  - Inserting new tasks (safe)
  - Deleting completed tasks (safe)
  - Deleting tasks with open PRs (creates orphaned PR)
  - Changing task descriptions (creates orphaned PR)
  - Resolving orphaned PRs
- Optional: PR template customization (`pr-template.md`)

- [x] Phase 4: Create `notifications.md`

Notifications and visibility guide covering:
- Slack notifications:
  - Getting a webhook URL
  - Adding `SLACK_WEBHOOK_URL` secret
  - Passing to action via `slack_webhook_url` input
  - What PR creation notifications include
- PR summaries:
  - `add_pr_summary` input (default: true)
  - What summaries contain
  - Cost (~$0.002-0.005 per summary)
- Statistics reports:
  - Setting up the statistics workflow (`.github/workflows/claudestep-statistics.yml`)
  - Statistics action inputs (`days_back`, `base_branch`, `slack_webhook_url`)
  - What reports include (leaderboard, project progress, cost tracking)
  - Scheduling (cron for weekly reports)

- [x] Phase 5: Create `troubleshooting.md`

Common issues guide covering:
- First task not starting (manual trigger required, or use labeled PR)
- PR merge doesn't trigger next task (check label, verify merged not just closed)
- Spec file not found (must be in base branch)
- Workflow permissions issues
- Claude Code GitHub App not installed
- API rate limits
- Orphaned PR warnings (link to projects.md for resolution)

- [x] Phase 6: Update `docs/feature-guides/README.md`

Update the index to reflect new structure:
- Remove references to deleted guides
- Add entries for all 5 new guides with descriptions
- Organize as a clear catalog

- [x] Phase 7: Delete obsolete guides

Remove:
- `docs/feature-guides/getting-started.md`
- `docs/feature-guides/modifying-tasks.md`

Content from these has been absorbed into `setup.md` and `projects.md`.

- [x] Phase 8: Rewrite `README.md` as derivative

Restructure README.md to mirror the feature guides:

```markdown
# ClaudeStep

## Overview
[Brief intro - what it does, why it exists, key features]

## How It Works
[Condensed mental model]
→ Link to docs/feature-guides/how-it-works.md

## Setup
[Essential steps only]
→ Link to docs/feature-guides/setup.md

## Projects
[Brief spec.md/configuration.yml overview]
→ Link to docs/feature-guides/projects.md

## Notifications
[Brief Slack, summaries, statistics overview]
→ Link to docs/feature-guides/notifications.md

## Troubleshooting
[Top 2-3 common issues only]
→ Link to docs/feature-guides/troubleshooting.md

## Development
[Testing, contributing - stays in README only, not a user feature]

## Support & Credits
[Links, license]
```

Each section:
- Contains condensed info (not full details)
- Links to the detailed guide for more
- No information that doesn't exist in the corresponding guide

- [x] Phase 9: Create validation command

Create `.claude/commands/validate-readme.md`:
- Instructions for Claude Code to:
  1. Read all feature guides in `docs/feature-guides/`
  2. Read `README.md`
  3. Verify README content is accurate and derived from guides
  4. Check for information in README that's missing from guides
  5. Check for outdated information
  6. Report discrepancies

- [x] Phase 10: Validation

Run validation:
- Execute the new `/validate-readme` command to verify README matches guides
- Manual review of each guide for completeness and accuracy
- Verify all links work
- Check that deleted files are removed
- Ensure README is a proper derivative (no orphaned details)
