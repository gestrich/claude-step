# ClaudeChain

## Overview

ClaudeChain runs Claude Code on individual tasks that you define for your project, creating pull requests for each task one at a time. When you merge a PR, it automatically stages the next PR, creating a chain of incremental improvements.

Built on Claude Code and GitHub Actions, it automates the tedious refactoring work that never gets prioritized—migrations, refactoring, code cleanup, and documentation that would otherwise sit on the backlog forever.

**Key features:**
- 📋 **Incremental automation** - Write your refactor spec, get automated PRs for each task
- ⚡ **Manageable review burden** - One PR at a time, small focused changes
- 🔄 **Continuous flow** - Merge PRs when you have time, next PR stages automatically
- 💬 **Context for reviewers** - AI-generated summaries explain each change
- 📊 **Visibility** - Track progress, team stats, cost, and completion rates

## How It Works

ClaudeChain creates a chain of PRs, one task at a time:

```
spec.md tasks          PRs                        Result
─────────────          ───                        ──────
- [ ] Task 1    →    PR #1    → merge →    - [x] Task 1
- [ ] Task 2    →    PR #2    → merge →    - [x] Task 2
- [ ] Task 3    →    PR #3    → merge →    - [x] Task 3
```

Each task is identified by a hash of its description, so you can freely reorder, insert, and delete tasks without breaking PR tracking.

→ **[Full guide: How It Works](docs/feature-guides/how-it-works.md)**

## Quick Start

**Prerequisite:** [Anthropic API key](https://console.anthropic.com)

### 1. Add the Workflows

Create these workflow files and **commit them to your default branch** (required for manual triggers to appear in the Actions UI).

**Main workflow** (`.github/workflows/claudechain.yml`):

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
      - main # Branch your PRs merge into

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
          claude_allowed_tools: 'Read,Write,Edit,Bash(git add:*),Bash(git commit:*)'  # Configure as needed
          base_branch: 'main'  # Branch your PRs merge into
```

**Statistics workflow** (`.github/workflows/claudechain-statistics.yml`) - optional, for weekly progress reports:

```yaml
name: ClaudeChain Statistics

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM UTC
  workflow_dispatch:

permissions:
  contents: read
  actions: read
  pull-requests: read

jobs:
  statistics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gestrich/claude-chain/statistics@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 2. Configure GitHub

1. **Add secret:** Settings → Secrets & Variables → Actions → Repository Secrets → `ANTHROPIC_API_KEY`
2. **Enable PRs:** Settings → Actions → General → "Allow GitHub Actions to create and approve pull requests"
3. **Install app:** Run `/install-github-app` in Claude Code. (Optional: To use @claude on PRs)

### 3. Create a Project

```bash
mkdir -p claude-chain/my-refactor
```

Create `claude-chain/my-refactor/spec.md`:

```markdown
# My Refactoring Project

Describe what you want to refactor and how to do it.

## Tasks

- [ ] First task to complete
- [ ] Second task to complete
- [ ] Third task to complete
```

Tasks can be organized however you like—grouped under headings, separated by blank lines, or interspersed with other text. Just ensure each task starts with `- [ ]` so ClaudeChain can find it.

### 4. Start ClaudeChain

Push your project to main, then either:
- Create a PR with the `claudechain` label and merge it, or
- Manual trigger: Actions → ClaudeChain → Run workflow

→ **[Full guide: Setup](docs/feature-guides/setup.md)**

## Projects

Each project lives in `claude-chain/{project-name}/` with:

| File | Required | Purpose |
|------|----------|---------|
| `spec.md` | Yes | Task list and instructions for Claude |
| `configuration.yml` | No | Reviewer assignment, base branch, and tool overrides |
| `pr-template.md` | No | Custom PR description template |

**Example configuration.yml:**

```yaml
assignee: alice                     # Optional: GitHub username for PR assignment
baseBranch: develop                 # Optional: override base branch
allowedTools: Read,Write,Edit,Bash  # Optional: override tool permissions
```

→ **[Full guide: Projects](docs/feature-guides/projects.md)**

## Notifications

| Feature | Purpose | Default |
|---------|---------|---------|
| Slack notifications | Alert team when PRs are created | Disabled |
| PR summaries | AI-generated explanation on each PR | Enabled |
| Statistics reports | Weekly team progress and activity | Optional (see Quick Start) |

Enable Slack by adding `slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}` to your workflow.

→ **[Full guide: Notifications](docs/feature-guides/notifications.md)**

## Troubleshooting

**First task not starting?** The first task requires manual trigger or a labeled PR merge.

**PR merge doesn't trigger next task?** Check that the PR has the `claudechain` label and was merged (not just closed).

**Spec file not found?** Ensure `spec.md` is committed and pushed to your base branch.

→ **[Full guide: Troubleshooting](docs/feature-guides/troubleshooting.md)**

## Documentation

| Guide | Description |
|-------|-------------|
| [How It Works](docs/feature-guides/how-it-works.md) | Core concepts: PR chain, task identification, automatic continuation |
| [Setup](docs/feature-guides/setup.md) | Workflow file, secrets, permissions, action reference |
| [Projects](docs/feature-guides/projects.md) | spec.md, configuration.yml, modifying tasks |
| [Notifications](docs/feature-guides/notifications.md) | Slack, PR summaries, statistics reports |
| [Troubleshooting](docs/feature-guides/troubleshooting.md) | Common issues and solutions |

## Development

```bash
# Run tests
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v

# Run E2E tests
./tests/e2e/run_test.sh
```

See [tests/e2e/README.md](tests/e2e/README.md) for E2E testing documentation.

## Contributing

Contributions welcome! Open an issue to discuss changes. Add tests and update docs.

## Support & Credits

- 🐛 [Report Issues](https://github.com/gestrich/claude-chain/issues)
- 💬 [Discussions](https://github.com/gestrich/claude-chain/discussions)

Created by [gestrich](https://github.com/gestrich). Built with [Claude Code](https://github.com/anthropics/claude-code-action).

MIT License - see LICENSE file
