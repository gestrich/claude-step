# Setup Guide

This guide walks you through the one-time setup to get ClaudeChain running in your repository. Once configured, ClaudeChain will automatically create a chain of PRs from your task list—one task at a time, each building on the last.

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

**Important:** Commit this workflow file to your default branch (usually `main`). GitHub Actions requires workflow files to exist on the default branch for manual triggers (`workflow_dispatch`) to appear in the Actions UI.

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
      base_branch:
        description: 'Base branch where spec file lives'
        required: true
        type: string
        default: 'main'
  pull_request:
    types: [closed]
    paths:
      - 'claude-chain/**'

permissions:
  contents: write
  pull-requests: write
  actions: read

jobs:
  run-claudechain:
    runs-on: ubuntu-latest
    steps:
      - uses: gestrich/claude-chain@main
        with:
          anthropic_api_key: ${{ secrets.CLAUDE_CHAIN_ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: ${{ github.event.inputs.project_name || '' }}
          default_base_branch: ${{ github.event.inputs.base_branch || 'main' }}
          claude_allowed_tools: 'Read,Write,Edit,Bash(git add:*),Bash(git commit:*)'  # Configure as needed
          # slack_webhook_url: ${{ secrets.CLAUDE_CHAIN_SLACK_WEBHOOK_URL }}
```

**What this does:**
- `workflow_dispatch` - Allows manual triggering with project name and base branch inputs
- `pull_request: types: [closed]` - Triggers when PRs are merged (for auto-continuation)
- `paths: ['claude-chain/**']` - Only triggers when files under claude-chain/ change
- `project_name` - Used for manual triggers; auto-detected for PR events from changed spec.md files
- `default_base_branch` - The branch PRs will target; validated against project config if set
- `claude_allowed_tools` - Controls which tools Claude can use (see [Tool Permissions](#tool-permissions))

### Standard Workflow (Alternative)

For more explicit control, specify the project name directly:

```yaml
name: ClaudeChain

on:
  pull_request:
    types: [closed]
    paths:
      - 'claude-chain/**'
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
      - uses: gestrich/claude-chain@main
        with:
          anthropic_api_key: ${{ secrets.CLAUDE_CHAIN_ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: 'my-refactor'
          # slack_webhook_url: ${{ secrets.CLAUDE_CHAIN_SLACK_WEBHOOK_URL }}
```

**Use this when:**
- You have a single project
- You want explicit control over which project runs
- You're not using the simplified event-based detection

### Triggers Explained

| Trigger | Purpose |
|---------|---------|
| `workflow_dispatch` | Manual trigger with project name and base branch |
| `pull_request: types: [closed]` | Auto-trigger when PRs changing spec.md are merged |

**Note:** ClaudeChain automatically detects projects from changed spec.md files. When you merge a PR that adds or modifies a spec.md file, ClaudeChain triggers automatically. No labels are required for initial triggering—just merge your spec PR and the first task starts.

**Base branch validation:** ClaudeChain validates that the merge target matches the project's configured `baseBranch` (in configuration.yml). If your project uses a non-main base branch, set it in configuration.yml to ensure PRs only process when merged to the correct branch.

---

## Configure GitHub Settings

### Add the Anthropic API Key Secret

1. Go to **Settings** → **Secrets and variables** → **Actions** → **Repository secrets**
2. Click **New repository secret**
3. Name: `CLAUDE_CHAIN_ANTHROPIC_API_KEY`
4. Value: Your API key from [console.anthropic.com](https://console.anthropic.com)
5. Click **Add secret**

### Enable PR Creation Permission

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Check **"Allow GitHub Actions to create and approve pull requests"**
4. Click **Save**

### Install Claude Code GitHub App (Optional)

This step is optional but enables using `@claude` mentions on PRs for interactive code review.

In your local repository, run Claude Code and execute:

```
/install-github-app
```

Follow the prompts to install the app on your repository.

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

### Option 1: Merge a Spec PR (Recommended)

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
3. Merge the PR

ClaudeChain detects the spec.md change and automatically creates the first task PR. No labels required!

### Option 2: Manual Trigger

1. Push your project files directly to main
2. Go to **Actions** → **ClaudeChain** → **Run workflow**
3. Enter your project name (e.g., `my-project`)
4. Enter the base branch (e.g., `main`)
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
| `project_name` | No | - | Project folder name. Auto-detected from changed spec.md files or workflow_dispatch input |
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
- uses: gestrich/claude-chain@main
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
