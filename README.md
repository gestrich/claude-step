# ClaudeStep

## Overview

An automated system for performing ongoing code refactoring using AI (Claude Code) and GitHub Actions. The system continuously generates pull requests for incremental refactoring work, reducing the manual burden and maintaining momentum on large-scale codebase improvements.

## Features

- 🤖 **AI-Powered Refactoring** - Uses Claude Code to perform refactoring tasks
- 📋 **Checklist-Driven** - Works through tasks in your spec.md file systematically
- 👥 **Multi-Reviewer Support** - Distributes PRs across team members
- 🔄 **Multiple Trigger Modes** - Scheduled, manual, or automatic on PR merge
- 📊 **Progress Tracking** - Track completed vs remaining tasks
- 💬 **Slack Integration** - Post statistics and progress reports to Slack channels
- ⚡ **Incremental PRs** - One small PR at a time for easier review

## Use as a GitHub Action

Add the action to your workflow:

```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'your-project-name'
```

**Quick Start:**
1. See [Quick Start](#quick-start) below for a 5-minute setup guide
2. Check [examples/basic/workflow.yml](examples/basic/workflow.yml) for a simple example
3. See [examples/advanced/workflow.yml](examples/advanced/workflow.yml) for all features

## Quick Start

Get up and running with ClaudeStep in 5 minutes.

### Prerequisites

- GitHub repository with code to refactor
- Anthropic API key ([get one here](https://console.anthropic.com))

### Step 1: Create Refactor Project (2 min)

Create this directory structure in your repo:

```bash
mkdir -p refactor/my-refactor
```

Create `refactor/my-refactor/configuration.json`:

```json
{
  "branchPrefix": "refactor/ai-refactor",
  "reviewers": [
    {
      "username": "YOUR_GITHUB_USERNAME",
      "maxOpenPRs": 1
    }
  ]
}
```

Create `refactor/my-refactor/spec.md`:

```markdown
# My Refactoring Project

Describe what you want to refactor and how to do it.

Include:
- Specific patterns to follow
- Before/after code examples
- Any edge cases or special handling

## Checklist

- [ ] First task to refactor
- [ ] Second task to refactor
- [ ] Third task to refactor
```

### Step 2: Configure GitHub (1 min)

#### Add API Key

1. Go to Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Name: `ANTHROPIC_API_KEY`
4. Value: (paste your Anthropic API key)
5. Click "Add secret"

#### Enable PR Creation

1. Go to Settings > Actions > General
2. Scroll to "Workflow permissions"
3. Check "Allow GitHub Actions to create and approve pull requests"
4. Click "Save"

#### Create Label

```bash
gh label create "ai-refactor" --color "0E8A16"
```

### Step 3: Add Workflow (1 min)

Create `.github/workflows/ai-refactor.yml`:

```yaml
name: ClaudeStep

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
  workflow_dispatch:     # Allow manual trigger

permissions:
  contents: write
  pull-requests: write
  actions: read

jobs:
  refactor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: gestrich/claude-step@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: 'my-refactor'
```

### Step 4: Run & Test (1 min)

#### Manual Test

1. Go to Actions tab in GitHub
2. Click "ClaudeStep" workflow
3. Click "Run workflow"
4. Wait ~2-5 minutes
5. Check for new PR!

#### What to Expect

- ✅ Workflow runs successfully
- ✅ New branch created: `2025-01-my-refactor-1`
- ✅ PR created with label "ai-refactor"
- ✅ PR assigned to you
- ✅ First task from spec.md is completed

### Step 5: Review & Iterate

#### Review the PR

1. Check the code changes
2. Verify it follows your spec
3. Make any needed fixes
4. **Important**: If you fix issues, update spec.md in the same PR to improve future PRs

#### Merge

1. When satisfied, merge the PR
2. Next run (tomorrow or manual) will create PR for next task

#### Improve

As you review PRs, update spec.md with:
- More specific instructions
- Edge cases you discover
- Examples of good/bad patterns

The instructions will improve over time!

### Next Steps

#### Scale Up

Once comfortable:

```json
{
  "reviewers": [
    {
      "username": "alice",
      "maxOpenPRs": 2  // ← Increase capacity
    },
    {
      "username": "bob",   // ← Add more reviewers
      "maxOpenPRs": 1
    }
  ]
}
```

#### Add PR Merge Trigger

For faster iteration:

```yaml
on:
  schedule:
    - cron: '0 9 * * *'
  workflow_dispatch:
  pull_request:  # ← Add this
    types: [closed]

jobs:
  refactor:
    # Only run on merged PRs
    if: github.event_name != 'pull_request' || github.event.pull_request.merged == true
    # ... rest of job
```

Now when you merge a PR, it immediately creates the next one!

#### Multiple Projects

Create additional refactor projects:

```
refactor/
├── swift-migration/
│   ├── configuration.json
│   └── spec.md
├── typescript-conversion/
│   ├── configuration.json
│   └── spec.md
└── api-refactor/
    ├── configuration.json
    └── spec.md
```

Run different projects on different schedules or manually.

### Troubleshooting

#### No PR Created

**Check workflow summary** - it shows:
- Reviewer capacity (are all reviewers at max?)
- Available tasks (are all tasks complete or in progress?)

**Common causes:**
1. All reviewers are at capacity (check open PRs with your label)
2. All tasks in spec.md are completed or in progress
3. Label doesn't exist or doesn't match config

**Common fixes:**
- Increase `maxOpenPRs` if at capacity
- Add more unchecked tasks to spec.md
- Verify label exists: `gh label list`

#### PR Creation Fails

**Common causes:**
- Missing `ANTHROPIC_API_KEY` secret
- Workflow doesn't have PR creation permissions
- Branch already exists (shouldn't happen with date prefix)

**Verify:**
- Secret exists in Settings > Secrets and variables > Actions
- "Allow GitHub Actions to create and approve pull requests" is enabled
- You have write access to the repo

#### Bad PR Quality

**Claude makes mistakes** - This is normal initially!

**Solutions:**
1. Add more detailed instructions to spec.md
2. Include specific before/after examples
3. Document common mistakes to avoid
4. Consider starting with one manual PR to set the pattern
5. **Update instructions in the same PR** when you fix issues

The more context you provide, the better Claude performs. Instructions improve over time.

#### Reviewer Assignment Not Working

The action uses artifacts to track PR assignments. If assignment seems wrong:
1. Check that artifact uploads are succeeding in workflow logs
2. Verify label matches between config and actual PRs
3. Wait for one full workflow run to establish state

### Tips for Success

1. **Start with clear, simple tasks**
   ```markdown
   - [ ] Convert UserService.js to TypeScript
   ```
   Not: `- [ ] Fix the auth stuff`

2. **Provide examples in spec.md**
   - Show before/after code
   - Document patterns to follow
   - Explain edge cases

3. **Review thoroughly at first**
   - First few PRs may need guidance
   - Update spec.md when you fix issues
   - Quality improves quickly with good instructions

4. **One PR at a time initially**
   - Set `maxOpenPRs: 1`
   - Increase after you're confident
   - Easier to iterate on instructions

5. **Merge regularly**
   - Don't let PRs pile up
   - Keep momentum going
   - Batch review if needed

## Action Inputs & Outputs

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `anthropic_api_key` | ✅ | - | Anthropic API key for Claude Code |
| `github_token` | ✅ | `${{ github.token }}` | GitHub token for PR operations |
| `project_name` | ✅ | - | Project folder name under `/refactor` |
| `config_path` | ❌ | `refactor/{project}/configuration.json` | Custom config path |
| `spec_path` | ❌ | `refactor/{project}/spec.md` | Custom spec file path |
| `pr_template_path` | ❌ | `refactor/{project}/pr-template.md` | Custom PR template path |
| `claude_model` | ❌ | `claude-sonnet-4-5` | Claude model to use (sonnet-4-5 or opus-4-5) |
| `claude_allowed_tools` | ❌ | `Write,Read,Bash,Edit` | Comma-separated list of tools Claude can use |
| `base_branch` | ❌ | `main` | Base branch for PRs |
| `working_directory` | ❌ | `.` | Working directory |

### Outputs

| Output | Description |
|--------|-------------|
| `pr_number` | Number of created PR (empty if none) |
| `pr_url` | URL of created PR (empty if none) |
| `reviewer` | Assigned reviewer username |
| `task_completed` | Task description completed |
| `has_capacity` | Whether reviewer had capacity |
| `all_tasks_done` | Whether all tasks are complete |

### Input Details

**claude_model:**
- `claude-sonnet-4-5` (recommended) - Balanced performance and cost
- `claude-opus-4-5` - Highest capability, higher cost

**claude_allowed_tools:**
Available tools: `Write`, `Read`, `Bash`, `Edit`, `Glob`, `Grep`

Default: `Write,Read,Bash,Edit`

Example with all tools:
```yaml
claude_allowed_tools: 'Write,Read,Bash,Edit,Glob,Grep'
```

**Security note:** Only add tools that are safe for your use case. More tools = more power but also more potential for unintended changes.

**anthropic_api_key:**
Get your API key from [console.anthropic.com](https://console.anthropic.com), then:
1. Go to Settings > Secrets and variables > Actions
2. Create secret named `ANTHROPIC_API_KEY`
3. Reference it: `${{ secrets.ANTHROPIC_API_KEY }}`

## Configuration Reference

### configuration.json

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | ✅ | GitHub label for PRs |
| `branchPrefix` | string | ✅ | Prefix for branch names |
| `reviewers` | array | ✅ | List of reviewers with capacity |

**Reviewers** array items:
- `username` (string): GitHub username
- `maxOpenPRs` (number): Max open PRs per reviewer

**Example:**
```json
{
  "branchPrefix": "refactor/swift-migration",
  "reviewers": [
    { "username": "alice", "maxOpenPRs": 1 },
    { "username": "bob", "maxOpenPRs": 2 }
  ]
}
```

All PRs are automatically labeled with `claudestep` for tracking purposes.

### spec.md Format

The `spec.md` file combines instructions and checklist in a single document.

**Requirements:**
- Must be valid Markdown
- Must contain at least one `- [ ]` or `- [x]` checklist item
- Checklist items can appear anywhere in the file
- The entire file content is provided to Claude as context

**Example:**
```markdown
# Migration Instructions

[Your detailed instructions here - can be multiple sections]

## Guidelines
- Rule 1
- Rule 2

## Checklist
- [ ] First task
  - Additional details for this task can go here
- [ ] Second task
- [x] Completed task

## More Information
[Additional context...]

- [ ] Another task (checklist items can appear anywhere!)
```

**Task Lifecycle:**
1. **Unchecked (`- [ ]`)**: Task is pending
2. **Action picks task**: Creates PR for it
3. **PR merged**: Action automatically marks as `- [x]`
4. **Checked (`- [x]`)**: Task is skipped in future runs

**Writing Effective Instructions:**

Be specific with task descriptions:
```markdown
# Bad
- [ ] Update the user service

# Good
- [ ] Convert UserService.getUserById() to use async/await instead of callbacks
```

The entire spec.md is provided to Claude, so include context:
- **Before/After Examples** - Show exactly what code should look like
- **Coding Patterns** - Document conventions to follow
- **Edge Cases** - Explain special handling needed

**Iterative Improvement:**

Start with basic instructions and refine based on PR reviews:

1. Initial:
   ```markdown
   Convert to TypeScript
   - [ ] Convert user.js
   ```

2. After first PR, update:
   ```markdown
   Convert to TypeScript
   - Use strict mode (`strict: true`)
   - Add explicit return types
   - Don't use `any` type
   - [ ] Convert auth.js
   ```

3. Continue refining as you learn what works.

**Common Patterns for Organizing Tasks:**

Group related tasks:
```markdown
## Database Layer
- [ ] Convert UserRepository
- [ ] Convert ProductRepository

## API Layer
- [ ] Convert UserController
- [ ] Convert ProductController
```

Progressive complexity:
```markdown
## Phase 1: Simple Components
- [ ] Convert Button component
- [ ] Convert Input component

## Phase 2: Complex Components
- [ ] Convert UserProfile (uses context)
- [ ] Convert DataTable (uses custom hooks)
```

### pr-template.md (Optional)

Template for PR descriptions with `{{TASK_DESCRIPTION}}` placeholder.

**Template Variables:**
- `{{TASK_DESCRIPTION}}` - The task description from spec.md

**Example:**
```markdown
## Task
{{TASK_DESCRIPTION}}

## Changes
This PR was automatically created by ClaudeStep.

## Review Checklist
- [ ] Code follows project conventions
- [ ] Tests pass
- [ ] No unintended changes
- [ ] Documentation updated if needed

## Instructions for Reviewer
If you find issues:
1. Fix them directly in this PR
2. Update spec.md with improved instructions
3. Merge when ready

---
_Auto-generated by ClaudeStep_
```

**Default template** (if no pr-template.md exists):
```markdown
## Task
{task description}
```

## Trigger Modes

### Scheduled (Recommended for Getting Started)

```yaml
on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
```

- Predictable, steady pace
- One PR per day per reviewer
- Easy to manage initially

### Manual Dispatch

```yaml
on:
  workflow_dispatch:
    inputs:
      project:
        description: 'Project name'
        required: true
```

- On-demand PR creation
- Useful for testing and demos
- Allows project selection

### Automatic (PR Merge)

```yaml
on:
  pull_request:
    types: [closed]

jobs:
  refactor:
    if: github.event.pull_request.merged == true
    # ...
```

- Creates next PR immediately when one merges
- Fastest iteration speed
- Best for active refactoring periods

## Setup

Before using ClaudeStep, you need to configure a few things:

### 1. Install the Claude Code GitHub App

Run this command in Claude Code to install the GitHub app and set up authentication:

```
/install-github-app
```

This grants the necessary permissions for Claude to interact with your repository.

### 2. Add Anthropic API Key

Add your Anthropic API key as a repository secret:

1. Go to **Settings > Secrets and variables > Actions**
2. Add a secret named `ANTHROPIC_API_KEY` with your key from [console.anthropic.com](https://console.anthropic.com)

### 3. Enable PR Creation

Allow GitHub Actions to create pull requests:

1. Go to **Settings > Actions > General**
2. Scroll to **Workflow permissions**
3. Check **"Allow GitHub Actions to create and approve pull requests"**
4. Save

### 4. Create Your Refactor Label

Create a label for tracking refactor PRs:

```bash
gh label create "your-refactor-label" --description "Automated refactor PRs" --color "0E8A16"
```

All PRs are automatically labeled with `claudestep` for tracking purposes.

### 5. Setup Slack Notifications (Optional)

To receive statistics and progress reports in Slack, you'll need a webhook URL.

#### Get Slack Webhook URL

1. Go to [https://api.slack.com/apps](https://api.slack.com/apps)
2. Click **"Create New App"** → **"From scratch"**
3. Name your app (e.g., "ClaudeStep Bot") and select your workspace
4. In the app settings, go to **"Incoming Webhooks"**
5. Toggle **"Activate Incoming Webhooks"** to **On**
6. Click **"Add New Webhook to Workspace"**
7. Select the channel where you want notifications (e.g., `#refactoring-updates`)
8. Click **"Allow"**
9. Copy the webhook URL (looks like `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX`)

#### Add Webhook to GitHub

1. Go to your repository **Settings > Secrets and variables > Actions**
2. Click **"New repository secret"**
3. Name: `SLACK_WEBHOOK_URL`
4. Value: (paste your Slack webhook URL)
5. Click **"Add secret"**

#### Use in Workflows

The Statistics action outputs formatted messages ready for Slack:

```yaml
- name: Generate Statistics
  id: stats
  uses: gestrich/claude-step/statistics@v1
  with:
    github_token: ${{ secrets.GITHUB_TOKEN }}

- name: Post to Slack
  uses: slackapi/slack-github-action@v2
  with:
    payload: |
      {
        "text": "ClaudeStep Report",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": ${{ toJson(steps.stats.outputs.slack_message) }}
            }
          }
        ]
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK_URL }}
```

See [.github/workflows/claudestep-statistics.yml](.github/workflows/claudestep-statistics.yml) for a complete example.

---

See [Configuration Reference](#configuration-reference) for details on `configuration.json` and `spec.md` format.

## Background

### Problems Being Solved

1. **Motivation & Inertia** - Large refactors require creating many PRs over time. Having an automated system breaks the inertia and keeps progress moving.

2. **Burden of Review** - By delivering one PR at a time, the review burden becomes manageable.

3. **Tracking Progress** - The system provides visibility into what's done vs. what remains.

4. **Hands-off Operation** - Runs automatically, sending notifications when work is ready for review.

### Per-User PR Assignment

Instead of a global `maxConcurrentPRs`, PRs are assigned per reviewer. This:
- Distributes review load across team members
- Allows parallel progress (2 reviewers = 2 simultaneous PRs)
- Each reviewer only sees PRs assigned to them
- When a reviewer merges their PR, a new one is created for them

See [Trigger Modes](#trigger-modes) for details on scheduled, manual, and automatic triggers.

## Best Practices

### How It Works

#### 1. Create the Specification

Create `spec.md` combining instructions and checklist:
```markdown
# Swift Migration

Convert Objective-C files to Swift following these guidelines:

- Use Swift naming conventions (camelCase for methods, PascalCase for types)
- Replace `NSString` with `String`, `NSArray` with `[Type]`
- Use guard statements instead of nested if-let
- Add appropriate access control (public/private/internal)

## Before/After Example
[... detailed examples ...]

## Checklist

- [ ] Convert UserManager.m
- [ ] Convert NetworkClient.m
- [x] Convert Logger.m (completed)
```

The `- [ ]` items can appear anywhere in the file—they don't need to be in a specific section. This allows you to include detailed instructions under each item if needed.

#### 2. ClaudeStep (GitHub Action)

Runs on schedule or merge trigger:
1. Check for open PRs with the label
2. If under max, create a new PR for the next item
3. Claude reads the entire `spec.md` file to understand both what to do and how to do it
4. Apply the label and use the PR template

#### 3. Human Review & Refinement

When notified:
- Review and merge if good
- If issues: fix and **update the instructions in the same PR**
- Goal: incrementally improve toward 90%+ accuracy

### Improving Instructions

- **Add fixes to the same PR** - When you see instruction gaps, add improvements alongside the refactor code. Keeps the process clean.
- **Expect frequent edits early** - This is normal. Instructions will stabilize over time.
- **Start with one PR at a time** - Easier to iterate when you're not fixing multiple PRs with outdated instructions.

### Quality & Review Responsibility

**You are responsible for this code.** AI-generated refactors are no different than using IDE refactor tools—the responsibility stays with you.

#### Team Considerations

- **Agree on review levels per refactor type** - Mechanical renames may need less scrutiny than logic changes.
- **Define QA involvement** - Does QA need to test every PR, or can some be batched weekly?
- **CI vs. manual testing** - Is your test coverage sufficient, or do engineers need to build and run locally?

#### Make It Part of Your Pipeline

- If QA reviews weekly, batch these PRs for that review
- Don't let refactor PRs become noise—integrate them into your existing process

#### PR Template Tips

Include a "Things to Check" section in your PR template with a checklist based on the refactor type.

### Getting Started Tips

Once you have the system set up, here are tips for rolling it out:

- **Lead with a manual PR** - Stage your first PR manually with several example refactors. This kicks off the chain and sets the pattern for Claude to follow.

- **One at a time initially** - Start with one concurrent PR. You'll be editing instructions frequently early on—don't want multiple PRs doing it wrong.

- **Use immediate trigger first** - Start with merge-triggered runs for faster iteration. Switch to scheduled (daily) once the process is stable.

- **Scale up gradually** - As confidence grows, add more reviewers and increase concurrent PRs per reviewer.

## Development

### Running Integration Tests

The project includes end-to-end integration tests that validate the complete ClaudeStep workflow.

**Prerequisites:**
- GitHub CLI (`gh`) installed and authenticated
- Write access to the demo repository
- Python 3.11+ and pytest

**Quick start:**
```bash
# Run integration tests
./tests/integration/run_test.sh

# Or use pytest directly
pytest tests/integration/test_workflow_e2e.py -v -s -m integration
```

**What the tests validate:**
- Manual workflow trigger and PR creation
- Reviewer capacity management (max 2 PRs per reviewer)
- Merge trigger functionality
- Resource cleanup

See [tests/integration/README.md](tests/integration/README.md) for detailed documentation.

## Validation

The action validates your configuration at runtime:

**configuration.json:**
- ✅ File exists and is valid JSON
- ✅ Required fields present (`branchPrefix`, `reviewers`)
- ✅ Reviewers array has at least one entry
- ✅ Each reviewer has `username` and `maxOpenPRs`
- ✅ `maxOpenPRs` is between 1 and 10

**spec.md:**
- ✅ File exists
- ✅ Contains at least one checklist item (`- [ ]` or `- [x]`)

If validation fails, the workflow will error with a descriptive message.

## How It Works

The ClaudeStep action follows this workflow:

1. **Check Capacity** - Finds first reviewer under their `maxOpenPRs` limit
2. **Find Task** - Scans spec.md for first unchecked `- [ ]` item
3. **Create Branch** - Names branch with format `YYYY-MM-{project}-{index}`
4. **Run Claude** - Provides entire spec.md as context for the task
5. **Create PR** - Assigns to reviewer, applies label, uses template
6. **Track Progress** - Uploads artifact with task metadata

When you merge a PR, the next run will pick up the next unchecked task and repeat the process.

## Security

- API keys stored as GitHub secrets (never in logs)
- Uses repository GITHUB_TOKEN with minimal permissions
- No external services beyond Anthropic API
- All code runs in GitHub Actions sandbox

## Limitations

- Requires Anthropic API key (costs apply based on usage)
- Claude Code action requires specific Claude models
- Maximum 90-day artifact retention for tracking
- GitHub API rate limits apply (rarely hit in practice)

## Examples

- [Basic Example](examples/basic/workflow.yml) - Single project, scheduled trigger
- [Advanced Example](examples/advanced/workflow.yml) - Multi-project with all triggers

## Contributing

Contributions welcome! Please:
1. Open an issue to discuss changes
2. Follow existing code style
3. Add tests for new features
4. Update documentation

## License

MIT License - see LICENSE file

## Support

- 📚 [Configuration Reference](#configuration-reference)
- 🐛 [Report Issues](https://github.com/gestrich/claude-step/issues)
- 💬 [Discussions](https://github.com/gestrich/claude-step/discussions)

## Credits

Created by [gestrich](https://github.com/gestrich)

Built with [Claude Code](https://github.com/anthropics/claude-code-action) by Anthropic

## Configuration Best Practices

1. **Start simple** - Basic instructions, one reviewer, low capacity (`maxOpenPRs: 1`)
2. **Test manually** - Use `workflow_dispatch` to test before scheduling
3. **Iterate on instructions** - Update spec.md based on review feedback
4. **Monitor capacity** - Check workflow summaries to see reviewer load
5. **Version control everything** - Commit config changes with code changes
6. **Document gotchas** - Add special cases to spec.md as you discover them
7. **Group related tasks** - Organize checklist items by layer, component, or complexity
8. **Be specific** - Clear task descriptions lead to better results

## TODO

- [x] **Slack Action and metrics**

✅ Implemented! The Statistics action generates reports with project progress and team activity. See [Setup Slack Notifications](#5-setup-slack-notifications-optional) and [.github/workflows/claudestep-statistics.yml](.github/workflows/claudestep-statistics.yml) for setup instructions.

Metrics tracked:
- Project completion progress (with visual progress bars)
- Tasks completed, in progress, and pending per project
- Team member activity (merged PRs, open PRs)
- Configurable time periods (days back)

- [x] **Leaderboard & Stats**

✅ Implemented! The Statistics action now includes a leaderboard that tracks and ranks team members by merged PRs.

Features:
- 🥇🥈🥉 Medal awards for top 3 contributors
- Visual activity bars showing relative contribution
- Ranks all active team members
- Shows both merged and open PR counts
- Integrated into both Slack messages and GitHub Actions summaries
- Automatically sorted by activity level

The leaderboard appears prominently at the top of statistics reports, making it easy to recognize top reviewers and encourage friendly competition. See [Setup Slack Notifications](#5-setup-slack-notifications-optional) for configuration.

- [ ] **Cost in PR Summary**

Show Claude Code cost in PR summary

- [ ] **Claude Code generated Summary**

A section in the PR summary should show summarized output from Claude code on what was done.

- [ ] **Implement PR rejection handling**

Options for handling bad PRs:
- Check out the branch, mark item as skipped in `spec.md`
- (Future/Bonus) Use Claude Code mentions to close or update the PR automatically

- [ ] **Random Code Smell Example**

The idea is to support random refactors based on the most egregious code smells in the codebase.

- [ ] **Local Build Script**

Fetch open PRs and build locally on a schedule. Ready to run when you sit down to review.

- [ ] **UI Automation Screenshots**

Capture screenshots showing the result. Visual verification without manual testing.

- [ ] **Resolve open questions**

- Best approach for Claude token/credential management in Actions?
- Can Claude Code mentions be used to update/close PRs?

- [ ] **Test creation logic**

Test label detection, max PRs per user, and per-user assignment logic.

- [ ] **Record video walkthrough**

Create "ClaudeStep" tutorial video.

- [ ] **Write blog post**

Written guide explaining the approach.

- [ ] **Open source the repo**

Complete setup that others can use.
