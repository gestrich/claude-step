# Setup Guide

This guide walks you through the one-time setup to get ClaudeChain running in your repository.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Create the Workflow File](#create-the-workflow-file)
- [Configure GitHub Settings](#configure-github-settings)
- [Start ClaudeChain](#start-claudechain)
- [Action Reference](#action-reference)

---

## Prerequisites

Before setting up ClaudeChain, you need:

1. **Anthropic API key** - Get one from [console.anthropic.com](https://console.anthropic.com)
2. **GitHub repository** - Where you want to run ClaudeChain
3. **Write access** - You need permission to add workflows and secrets

---

## Create the Workflow File

Create `.github/workflows/claudechain.yml` in your repository.

### Simplified Workflow (Recommended)

This format handles project detection and event routing automatically:

```yaml
name: ClaudeChain

on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name (folder under claude-chain/)'
        required: true
        type: string
  pull_request:
    types: [closed]
    branches:
      - main

permissions:
  contents: write
  pull-requests: write
  actions: read

jobs:
  run-claudechain:
    runs-on: ubuntu-latest
    steps:
      - uses: gestrich/claude-chain@v2
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          github_event: ${{ toJson(github.event) }}
          event_name: ${{ github.event_name }}
          project_name: ${{ github.event.inputs.project_name || '' }}
          # slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**What this does:**
- `workflow_dispatch` - Allows manual triggering with project name input
- `pull_request: types: [closed]` - Triggers when PRs are merged (for auto-continuation)
- `github_event` / `event_name` - Passes event context so the action can detect projects automatically
- `project_name` - Used for manual triggers; auto-detected for PR events

### Standard Workflow (Alternative)

For more explicit control, specify the project name directly:

```yaml
name: ClaudeChain

on:
  pull_request:
    types: [closed]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write
  actions: read

jobs:
  refactor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gestrich/claude-chain@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: 'my-refactor'
          # slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Use this when:**
- You have a single project
- You want explicit control over which project runs
- You're not using the simplified event-based detection

### Triggers Explained

| Trigger | Purpose |
|---------|---------|
| `workflow_dispatch` | Manual trigger for starting new projects |
| `pull_request: types: [closed]` | Auto-continuation when PRs are merged |

**Note:** The first task for a new project requires either a manual trigger or merging a PR with the `claudechain` label. Subsequent tasks auto-trigger on merge.

---

## Configure GitHub Settings

### Add the Anthropic API Key Secret

1. Go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `ANTHROPIC_API_KEY`
4. Value: Your API key from [console.anthropic.com](https://console.anthropic.com)
5. Click **Add secret**

### Enable PR Creation Permission

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Check **"Allow GitHub Actions to create and approve pull requests"**
4. Click **Save**

### Install Claude Code GitHub App

In your local repository, run Claude Code and execute:

```
/install-github-app
```

Follow the prompts to install the app on your repository. This grants Claude Code permission to read your code and create PRs.

### Optional: Add Slack Webhook

For PR creation notifications:

1. Get a webhook URL from [api.slack.com/messaging/webhooks](https://api.slack.com/messaging/webhooks)
2. Add as secret: **Settings** → **Secrets** → **New repository secret**
   - Name: `SLACK_WEBHOOK_URL`
   - Value: Your webhook URL
3. Uncomment the `slack_webhook_url` line in your workflow file

---

## Start ClaudeChain

Before running ClaudeChain, you need at least one project. See the [Projects Guide](./projects.md) for creating `spec.md` and `configuration.yml`.

### Option 1: Labeled PR (Recommended)

1. Create a branch and add your project files:
   ```bash
   git checkout -b add-my-project-spec
   mkdir -p claude-chain/my-project
   # Create spec.md (see Projects Guide)
   git add claude-chain/my-project/
   git commit -m "Add ClaudeChain project: my-project"
   git push origin add-my-project-spec
   ```
2. Create a PR from your branch
3. Add the `claudechain` label to the PR
4. Merge the PR

ClaudeChain detects the merge and automatically creates the first task PR.

### Option 2: Manual Trigger

1. Push your project files directly to main
2. Go to **Actions** → **ClaudeChain** → **Run workflow**
3. Select your branch (usually `main`)
4. Enter your project name (e.g., `my-project`)
5. Click **Run workflow**

The workflow runs and creates a PR for the first task.

### Verify It's Working

After triggering:
1. Go to **Actions** and watch the workflow run (~2-5 minutes)
2. Check **Pull requests** for a new PR
3. The PR title will be "ClaudeChain: {task description}"
4. The PR will have the `claudechain` label

---

## Action Reference

### Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `anthropic_api_key` | Yes | - | Anthropic API key for Claude Code |
| `github_token` | Yes | `${{ github.token }}` | GitHub token for PR operations |
| `project_name` | Conditional | - | Project folder name. Required unless using simplified workflow with `github_event` |
| `github_event` | No | - | GitHub event payload (pass `${{ toJson(github.event) }}`) |
| `event_name` | No | - | GitHub event name (pass `${{ github.event_name }}`) |
| `claude_model` | No | `claude-sonnet-4-5` | Claude model to use |
| `claude_allowed_tools` | No | `Read,Write,Edit,Bash(git add:*),Bash(git commit:*)` | Tools Claude can use (can be overridden per-project) |
| `base_branch` | No | (inferred) | Base branch for PRs |
| `default_base_branch` | No | `main` | Default if not determined from event |
| `working_directory` | No | `.` | Working directory |
| `add_pr_summary` | No | `true` | Add AI-generated summary to PR |
| `slack_webhook_url` | No | - | Slack webhook for notifications |
| `pr_label` | No | `claudechain` | Label for ClaudeChain PRs |

### Outputs

| Output | Description |
|--------|-------------|
| `skipped` | Whether execution was skipped |
| `skip_reason` | Reason for skipping |
| `project_name` | Detected/resolved project name |
| `base_branch` | Resolved base branch |
| `pr_number` | Number of created PR |
| `pr_url` | URL of created PR |
| `reviewer` | Assigned reviewer username |
| `step_completed` | Task description completed |
| `has_capacity` | Whether reviewer had capacity |
| `all_steps_done` | Whether all tasks are complete |

### Model Options

| Model | Description |
|-------|-------------|
| `claude-3-haiku-20240307` | Fastest, most cost-effective |
| `claude-sonnet-4-5` | Balanced performance and cost (default) |
| `claude-opus-4-5` | Highest capability |

### Tool Permissions

ClaudeChain uses minimal permissions by default for security. You can configure tools at the workflow level (`claude_allowed_tools` input) or per-project (`allowedTools` in `configuration.yml`).

**Default tools:**

| Tool | Purpose |
|------|---------|
| `Read` | Read spec.md and codebase files |
| `Write` | Create new files |
| `Edit` | Modify existing files |
| `Bash(git add:*)` | Stage changes (required by ClaudeChain) |
| `Bash(git commit:*)` | Commit changes (required by ClaudeChain) |

**Additional tools available:**

| Tool | Description |
|------|-------------|
| `Bash` | Full shell access (use with caution) |
| `Bash(command:*)` | Restricted to specific command (e.g., `Bash(npm test:*)`) |
| `Glob` | Find files by pattern |
| `Grep` | Search file contents |

**Enabling additional Bash access:**

If your tasks require running tests, builds, or other shell commands, add them explicitly:

```yaml
# Workflow-level: Full Bash access for all projects
- uses: gestrich/claude-chain@v2
  with:
    claude_allowed_tools: 'Read,Write,Edit,Bash'
```

Or configure per-project in `configuration.yml`:

```yaml
# Specific commands only
allowedTools: Read,Write,Edit,Bash(git add:*),Bash(git commit:*),Bash(npm test:*),Bash(npm run build:*)
```

See [Projects Guide](./projects.md#tool-permissions) for per-project configuration details.

**Note:** The PR summary generation step uses fixed, minimal permissions and is not affected by tool configuration

---

## Next Steps

- [Projects Guide](./projects.md) - Create your first project with `spec.md`
- [Notifications Guide](./notifications.md) - Set up Slack notifications and statistics
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
