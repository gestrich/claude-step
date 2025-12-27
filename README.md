# ClaudeStep

## Overview

ClaudeStep runs Claude Code on individual steps that you define for your project, creating pull requests for each step one at a time. When you merge a PR, it automatically stages the next PR, creating a chain of incremental improvements.

Built on Claude Code and GitHub Actions, it automates the tedious refactoring work that never gets prioritized -- migrations, code cleanup, and documentation that would otherwise sit on the backlog forever.

## Features

- 📋 **Incremental automation** - Write your refactor spec, get automated PRs for each step
- ⚡ **Manageable review burden** - One small PR at a time, distributed across team
- 🔄 **Continuous flow** - Merge PRs when you have time, next PR stages automatically
- 💬 **Context for reviewers** - AI-generated summaries explain each change
- 📊 **Visibility** - Track progress, team stats, and completion rates

## Getting Started

### Prerequisites

- GitHub repository with code to refactor
- Anthropic API key ([get one here](https://console.anthropic.com))

### Step 1: Create a Project

ClaudeStep relies on projects in the `claude-step` folder to source where to find its projects and configuration.

Create this directory structure in your repo:

```bash
mkdir -p claude-step/my-refactor
```

Create `claude-step/my-refactor/configuration.yml`:

```yaml
branchPrefix: refactor/ai-refactor
reviewers:
  - username: YOUR_GITHUB_USERNAME
    maxOpenPRs: 1
```

Create `claude-step/my-refactor/spec.md`:

```markdown
# My Refactoring Project

Describe what you want to refactor and how to do it.

Include:
- Specific patterns to follow
- Before/after code examples
- Any edge cases or special handling

## Checklist

Checklist items are formatted with a dash followed by open brackets (e.g., `- [ ]`). You can have any content between the brackets. ClaudeStep will process these checklist items in order as it finds them throughout the markdown document, so plan on every single item being processed.

- [ ] First step to refactor
- [ ] Second step to refactor
- [ ] Third step to refactor
```

### Step 2: Add Workflow

Create `.github/workflows/claude-step.yml`:

```yaml
name: ClaudeStep

on:
  pull_request:
    types: [closed]      # Triggers when you merge or close PRs
  workflow_dispatch:     # Allow manual trigger

# Note: The workflow triggers on both merged and closed-without-merging PRs.
# If you close a PR without merging and don't want it to re-open, first update
# spec.md to mark that step as complete (or remove it), merge that change, then close the PR.

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

### Step 3: Setup Slack Notifications (Optional)

To receive statistics and progress reports in Slack:

1. Create a Slack webhook at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
2. Add the webhook URL as a GitHub secret named `SLACK_WEBHOOK_URL`
3. Pass it to the action:

```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'my-refactor'
    slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Step 4: Configure GitHub

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

#### Install Claude Code GitHub App

The Claude Code GitHub App allows the action to interact with your repository. This is a remote GitHub configuration, not a local installation.

In your local repository directory, run this command in Claude Code:

```
/install-github-app
```

This installs the app at the GitHub repository level and grants the necessary permissions for Claude to read your spec and create pull requests.

### Step 5: Run & Test

#### Push Changes to Main

Before the workflow can run, your project configuration and spec need to be on the main branch:

1. Commit your changes (configuration.yml, spec.md, workflow file)
2. Push to your main branch
3. Ensure all changes are merged

#### Trigger Initial Workflow

The workflow will run automatically when you merge PRs (assuming you set up the merge/close trigger above). However, for the first PR, you need to trigger it manually to get the workflow going:

1. Go to Actions tab in GitHub
2. Click "ClaudeStep" workflow
3. Click "Run workflow"
4. Wait ~2-5 minutes
5. Check for new PR!

Once the first PR is created, future PRs will be staged automatically when you merge.

#### What to Expect

- ✅ Workflow runs successfully
- ✅ New branch created: `2025-01-my-refactor-1`
- ✅ PR created with label "claude-step"
- ✅ PR assigned to you
- ✅ First step from spec.md is completed
- ✅ AI-generated summary comment posted on PR (explains changes)

### Step 6: Review & Iterate

#### Review the PR

1. Check the code changes
2. Verify it follows your spec
3. Make any needed fixes

#### Merge

1. When satisfied, merge the PR
2. After merge, workflow will create PR for next step

### Scaling Up

Once comfortable, you can:

1. **Increase capacity per reviewer:**
   ```yaml
   reviewers:
     - username: alice
       maxOpenPRs: 2  # ← Increase from 1
   ```

2. **Add more reviewers:**
   ```yaml
   reviewers:
     - username: alice
       maxOpenPRs: 1
     - username: bob  # ← Add team members
       maxOpenPRs: 1
   ```

3. **Create multiple projects:**
   ```
   claude-step/
   ├── swift-migration/
   │   ├── configuration.yml
   │   └── spec.md
   ├── typescript-conversion/
   │   ├── configuration.yml
   │   └── spec.md
   └── api-refactor/
       ├── configuration.yml
       └── spec.md
   ```

## Action Inputs & Outputs

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `anthropic_api_key` | Y | - | Anthropic API key for Claude Code |
| `github_token` | Y | `${{ github.token }}` | GitHub token for PR operations |
| `project_name` | Y | - | Project folder name under `/claude-step` |
| `claude_model` | N | `claude-sonnet-4-5` | Claude model to use (sonnet-4-5 or opus-4-5) |
| `claude_allowed_tools` | N | `Write,Read,Bash,Edit` | Comma-separated list of tools Claude can use |
| `base_branch` | N | `main` | Base branch for PRs |
| `working_directory` | N | `.` | Working directory |
| `add_pr_summary` | N | `true` | Add AI-generated summary comment to PR |
| `slack_webhook_url` | N | - | Slack webhook URL for PR notifications |
| `pr_label` | N | `claude-step` | Label to apply to ClaudeStep PRs |

### Outputs

| Output | Description |
|--------|-------------|
| `pr_number` | Number of created PR (empty if none) |
| `pr_url` | URL of created PR (empty if none) |
| `reviewer` | Assigned reviewer username |
| `step_completed` | Step description completed |
| `has_capacity` | Whether reviewer had capacity |
| `all_steps_done` | Whether all steps are complete |

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

**add_pr_summary:**
Controls whether an AI-generated summary comment is posted on each PR. The summary analyzes the PR diff and explains what was changed and why in under 200 words.

- `true` (default) - Automatically post summary comments
- `false` - Skip summary generation

The summary provides context for reviewers and helps document the changes made. Each summary costs approximately $0.002-0.005 in API credits (based on diff size).

Example to disable:
```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'my-refactor'
    add_pr_summary: false
```

**slack_webhook_url:**
Optional Slack webhook URL for PR notifications. When provided, ClaudeStep posts a message to Slack whenever a new PR is created.

To set up:
1. Create a Slack webhook at [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
2. Add the webhook URL as a GitHub secret (e.g., `SLACK_WEBHOOK_URL`)
3. Pass it to the action:

```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'my-refactor'
    slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**pr_label:**
Label to apply to all ClaudeStep PRs. Defaults to `claude-step` if not specified.

This label is used to:
- Identify PRs created by ClaudeStep
- Track reviewer workload and capacity
- Auto-detect projects when a PR is merged

Example to use a custom label:
```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'my-refactor'
    pr_label: 'refactoring'
```

**anthropic_api_key:**
Get your API key from [console.anthropic.com](https://console.anthropic.com), then:
1. Go to Settings > Secrets and variables > Actions
2. Create secret named `ANTHROPIC_API_KEY`
3. Reference it: `${{ secrets.ANTHROPIC_API_KEY }}`

## Configuration Reference

### configuration.yml

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | ✅ | GitHub label for PRs |
| `branchPrefix` | string | ❌ | Prefix for branch names (see Branch Naming below) |
| `reviewers` | array | ✅ | List of reviewers with capacity |

**Branch Naming:**
- **With `branchPrefix`**: Branches are named `{branchPrefix}-{task_index}` (e.g., `refactor/swift-migration-1`, `refactor/swift-migration-2`)
- **Without `branchPrefix`**: Branches use the default YYYY-MM date format: `{YYYY-MM}-{project_name}-{task_index}` (e.g., `2025-01-my-refactor-1`)

**Reviewers** array items:
- `username` (string): GitHub username
- `maxOpenPRs` (number): Max open PRs per reviewer

**Example:**
```yaml
branchPrefix: refactor/swift-migration
reviewers:
  - username: alice
    maxOpenPRs: 1
  - username: bob
    maxOpenPRs: 2
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
- [ ] First step
  - Additional details for this step can go here
- [ ] Second step
- [x] Completed step

## More Information
[Additional context...]

- [ ] Another step (checklist items can appear anywhere!)
```

**Step Lifecycle:**
1. **Unchecked (`- [ ]`)**: Step is pending
2. **Action picks step**: Creates PR for it
3. **PR merged**: Action automatically marks as `- [x]`
4. **Checked (`- [x]`)**: Step is skipped in future runs

**Writing Effective Instructions:**

Be specific with step descriptions:
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

**Common Patterns for Organizing Steps:**

Group related steps:
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
- `{{TASK_DESCRIPTION}}` - The step description from spec.md

**Example:**
```markdown
## Step
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
## Step
{step description}
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
    # ...
```

- Creates next PR immediately when one closes (merged or not)
- Fastest iteration speed
- Best for active refactoring periods
- **Important:** If closing without merging, update `spec.md` first to avoid the PR re-opening

## Per-User PR Assignment

Instead of a global `maxConcurrentPRs`, PRs are assigned per reviewer. This:
- Distributes review load across team members
- Allows parallel progress (2 reviewers = 2 simultaneous PRs)
- Each reviewer only sees PRs assigned to them
- When a reviewer merges their PR, a new one is created for them

See [Configuration Reference](#configuration-reference) for details on `configuration.yml` and `spec.md` format.

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

**configuration.yml:**
- ✅ File exists and is valid YAML
- ✅ Required field present (`reviewers`)
- ✅ Reviewers array has at least one entry
- ✅ Each reviewer has `username` and `maxOpenPRs`
- ✅ `maxOpenPRs` is between 1 and 10
- ✅ Optional `branchPrefix` field (if omitted, uses YYYY-MM date format)

**spec.md:**
- ✅ File exists
- ✅ Contains at least one checklist item (`- [ ]` or `- [x]`)

If validation fails, the workflow will error with a descriptive message.

## How It Works

The ClaudeStep action follows this workflow:

1. **Check Capacity** - Finds first reviewer under their `maxOpenPRs` limit
2. **Find Step** - Scans spec.md for first unchecked `- [ ]` item
3. **Create Branch** - Names branch with format `YYYY-MM-{project}-{index}`
4. **Run Claude** - Provides entire spec.md as context for the step
5. **Create PR** - Assigns to reviewer, applies label, uses template
6. **Track Progress** - Uploads artifact with step metadata

When you merge a PR, the next run will pick up the next unchecked step and repeat the process.

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

## TODO

See [docs/TODO.md](docs/TODO.md) for planned features and improvements.
