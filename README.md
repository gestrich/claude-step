# ClaudeChain

> **Warning:** This project is in beta (pre-release). APIs and behavior will change.

## Overview

ClaudeChain is a **GitHub Action** that automates staging pull requests and running Claude Code as a chain. Define your tasks in a spec file, and ClaudeChain creates PRs one at a time—when you merge one, it automatically stages the next.

Built for the tedious work that never gets prioritized—migrations, refactoring, code cleanup, documentation—broken into small, reviewable PRs that you merge at your own pace.

```
┌──────────────┐    ┌─────────────────┐    ┌────────────┐    ┌───────────────┐
│ You write    │───▶│ ClaudeChain     │───▶│ PR created │───▶│ You review    │
│ tasks        │    │ runs Claude Code│    │            │    │ and merge     │
└──────────────┘    └────────▲────────┘    └────────────┘    └───────┬───────┘
                             │                                       │
                             │         ┌────────────────┐            │
                             └─────────│ Merge triggers │◀───────────┘
                                       │ next task      │
                                       └────────────────┘

spec.md tasks          PRs                        Result
─────────────          ───                        ──────
- [ ] Task 1    →    PR #1    → merge →    - [x] Task 1
- [ ] Task 2    →    PR #2    → merge →    - [x] Task 2
- [ ] Task 3    →    PR #3    → merge →    - [x] Task 3
```

**Key features:**
- 🔗 **Chained automation** - Each merged PR triggers the next task automatically
- 🤖 **Claude Code integration** - AI implements each task from your spec
- ⚡ **One PR at a time** - Small, focused changes that are easy to review
- 💬 **Slack notifications** - Get alerted when PRs are created and ready for review
- 📊 **Scheduled statistics** - Add a cron trigger to post progress across all projects

<p align="center">
  <img src="docs/images/slack-pr-notification.png" alt="Slack PR Notification" height="200">
  <img src="docs/images/slack-statistics-report.png" alt="Slack Statistics Report" height="200">
</p>

## Project Setup

Minimal convention required. Create a folder per project under `claude-chain/` with a `spec.md` file:

```
┌─────────────────────────────────────────────────────────────────┐
│  claude-chain/                                                  │
│  └── my-refactor/                                               │
│      ├── spec.md              ← Required                        │
│      ├── pr-template.md       ← Optional                        │
│      └── configuration.yml    ← Optional                        │
└─────────────────────────────────────────────────────────────────┘
```

| File | Purpose |
|------|---------|
| `spec.md` | Tasks and instructions for Claude |
| `pr-template.md` | Custom PR description template |
| `configuration.yml` | Assignee, base branch, tool permissions |

→ **[Full guide: Projects](docs/feature-guides/projects.md)**

## Workflow Setup

**Prerequisites:**
- [Anthropic API key](https://console.anthropic.com) (required)
- [Slack webhook URL](https://api.slack.com/messaging/webhooks) (optional, for notifications)

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
      base_branch:
        description: 'Base branch for PR'
        required: true
        type: string
        default: 'main'  # Default branch PRs target
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
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          github_event: ${{ toJson(github.event) }}
          event_name: ${{ github.event_name }}
          project_name: ${{ github.event.inputs.project_name || '' }}
          # Default branch PRs target - shoudl be same as 
          # base_branch.default above
          default_base_branch: ${{ github.event.inputs.base_branch || 'main' }}  # Per-project override in configuration.yml
          # Configure cladue tools as needed
          claude_allowed_tools: 'Read,Write,Edit,Bash(git add:*),Bash(git commit:*)'
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

**Statistics workflow** (`.github/workflows/claudechain-statistics.yml`) - optional, for weekly progress reports:

```yaml
name: ClaudeChain Statistics

on:
  schedule:
    - cron: '0 9 * * *'  # Daily at 9 AM UTC
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
      - uses: gestrich/claude-chain/statistics@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### 2. Configure GitHub

1. **Add secret:** Settings → Secrets & Variables → Actions → Repository Secrets → `ANTHROPIC_API_KEY`
2. **Add secret (optional):** Same path → `SLACK_WEBHOOK_URL` (for notifications)
3. **Enable PRs:** Settings → Actions → General → "Allow GitHub Actions to create and approve pull requests"
4. **Install app:** Run `/install-github-app` in Claude Code. (Optional: To use @claude on PRs)

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
- Create a PR that adds/modifies your spec.md and merge it (triggers automatically), or
- Manual trigger: Actions → ClaudeChain → Run workflow (requires project name and base branch)

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

**Example pr-template.md:**

```markdown
## Task

{{TASK_DESCRIPTION}}

## Review Checklist

- [ ] Code follows project conventions
- [ ] Tests pass
- [ ] No unintended changes

---
*Auto-generated by ClaudeChain*
```

Use `{{TASK_DESCRIPTION}}` as a placeholder—it gets replaced with the task text from spec.md (e.g., "Add input validation to login endpoint").

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

**First task not starting?** Either merge a PR that changes spec.md (triggers automatically) or use manual trigger from Actions tab.

**PR merge doesn't trigger next task?** Check that the PR was merged (not just closed) and that it changed files under `claude-chain/`.

**Spec file not found?** Ensure `spec.md` is committed and pushed to your base branch.

**Base branch mismatch?** If your project uses a non-main base branch, set `baseBranch` in configuration.yml to match.

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
