# Getting Started with ClaudeStep

This guide walks you through setting up your first ClaudeStep project and understanding the automatic workflow.

## Table of Contents

- [Quick Start](#quick-start)
- [What Happens Automatically](#what-happens-automatically)
- [Troubleshooting](#troubleshooting)
- [Next Steps](#next-steps)

---

## Quick Start

### 1. Create Your Project Structure

```bash
mkdir -p claude-step/my-refactor
```

### 2. Create `claude-step/my-refactor/configuration.yml`

```yaml
reviewers:
  - username: YOUR_GITHUB_USERNAME
    maxOpenPRs: 1
```

### 3. Create `claude-step/my-refactor/spec.md`

```markdown
# My Refactoring Project

Describe what you want to refactor and how to do it.

Include patterns to follow, code examples, and edge cases.

## Steps

- [ ] First step to refactor
- [ ] Second step to refactor
- [ ] Third step to refactor
```

### 4. Push to Your Base Branch

```bash
git add claude-step/my-refactor/
git commit -m "Add ClaudeStep project: my-refactor"
git push origin main
```

> **Note:** ClaudeStep workflows work on **any branch**. Push your spec to whichever branch you want PRs to target (typically `main` for production, or a test branch like `main-e2e` for testing). The workflows automatically adapt to the branch.

### 5. Start ClaudeStep

You have two options to start ClaudeStep for a new project:

**Option 1: Add spec via PR with `claudestep` label (Recommended)**

Instead of pushing directly to main, create a PR that adds your spec files:

```bash
git checkout -b add-my-refactor-spec
git add claude-step/my-refactor/
git commit -m "Add ClaudeStep project: my-refactor"
git push origin add-my-refactor-spec
```

Then:
1. Create a PR from your branch
2. Add the `claudestep` label to the PR
3. Merge the PR

This will automatically trigger ClaudeStep to create the first task PR, starting the chain of automated PRs.

**Option 2: Manual trigger**

If you pushed directly to main:

1. Go to **Actions** > **ClaudeStep** > **Run workflow**
2. Enter your project name (e.g., `my-refactor`)
3. Click **Run workflow**
4. Wait ~2-5 minutes for the first PR to be created

---

## What Happens Automatically

### After the First PR

Once the first PR is created:

1. **You review and merge** the PR when ready (ensure it has the `claudestep` label)
2. **ClaudeStep detects the merge** automatically
3. **Creates the next PR** for the second task
4. **Process continues** until all tasks are complete

**Note:** PRs must have the `claudestep` label and be merged (not just closed) to trigger the next task.

### Example Timeline

```
0:00 - You manually trigger ClaudeStep for your project
0:02 - ClaudeStep workflow starts
0:05 - PR #1 created for first task
...
You merge PR #1
...
0:10 - ClaudeStep detects merge (PR had claudestep label)
0:12 - PR #2 created for second task
...
(continues for all tasks)
```

---

## Troubleshooting

### First Task Not Starting

If the first task doesn't start after adding your spec:

**If you added spec via PR:** Make sure the PR had the `claudestep` label before merging. If not, use manual trigger.

**Manual trigger fallback:**
1. Go to **Actions** > **ClaudeStep** > **Run workflow**
2. Select your branch (usually `main`)
3. Enter your project name (e.g., `my-refactor`)
4. Click **Run workflow**

Subsequent tasks will auto-trigger when you merge PRs with the `claudestep` label.

### PR Merge Doesn't Trigger Next Task

If merging a PR doesn't trigger the next task:

#### 1. Check the Label

Ensure the PR has the `claudestep` label. PRs created by ClaudeStep automatically get this label.

#### 2. Verify It Was Merged

The PR must be **merged**, not just closed. Closing without merging won't trigger the next task.

#### 3. Check Workflow Logs

1. Go to **Actions** > **ClaudeStep** > latest run
2. Look for error messages or skip reasons
3. Common issues:
   - Missing `claudestep` label
   - PR was closed without merging
   - API failures or permission issues

### Spec Files Not Found

**Error Message:**
```
Error: Spec files not found in branch 'main'
Required files:
  - claude-step/my-refactor/spec.md
  - claude-step/my-refactor/configuration.yml

Please merge your spec files to the 'main' branch before running ClaudeStep.
```

**Solution:**
1. Verify files exist in your repository: `ls claude-step/my-refactor/`
2. Ensure files are committed: `git status`
3. Push to your base branch: `git push origin main` (or whatever branch you're using)
4. Wait for auto-start workflow to run again

> **Note:** The error message shows the branch ClaudeStep is looking in. Ensure your spec files are in that branch.

### Workflow Permissions Issues

**Error Message:**
```
Error: GitHub Actions is not permitted to create pull requests
```

**Solution:**
1. Go to **Settings** > **Actions** > **General**
2. Scroll to **Workflow permissions**
3. Check **"Allow GitHub Actions to create and approve pull requests"**
4. Save and retry

### Claude Code GitHub App Not Installed

**Error Message:**
```
Error: Claude Code GitHub App is not installed
```

**Solution:**
1. Run in your local repository:
   ```bash
   claude-code
   /install-github-app
   ```
2. Follow the installation prompts
3. Retry the workflow

### API Rate Limits

**Error Message:**
```
Error: GitHub API rate limit exceeded
```

**Solution:**
- Wait for rate limit to reset (typically 1 hour)
- For high-volume projects, consider:
  - Reducing the number of concurrent projects
  - Spacing out spec merges
  - Using GitHub Enterprise (higher rate limits)

---

## Next Steps

### Customize Your Workflow

**PR Template:**
Create `claude-step/my-refactor/pr-template.md` to customize PR descriptions:

```markdown
## Step
{{TASK_DESCRIPTION}}

## Review Checklist
- [ ] Code follows conventions
- [ ] Tests pass
- [ ] No unintended changes

---
_Auto-generated by ClaudeStep_
```

**Slack Notifications:**
Add Slack webhook URL to get notified when PRs are created:

```yaml
# .github/workflows/claude-step.yml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'my-refactor'
    slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

### Scale Up

**Multiple Reviewers:**
```yaml
# claude-step/my-refactor/configuration.yml
reviewers:
  - username: alice
    maxOpenPRs: 1
  - username: bob
    maxOpenPRs: 2
```

**Multiple Projects:**
```bash
mkdir -p claude-step/auth-migration
mkdir -p claude-step/api-cleanup
# Create spec.md and configuration.yml in each
```

### Monitor Progress

**Weekly Statistics:**
Set up automatic weekly reports:

```yaml
# .github/workflows/claudestep-statistics.yml
name: ClaudeStep Statistics

on:
  schedule:
    - cron: '0 9 * * 1'  # Monday at 9 AM UTC
  workflow_dispatch:

jobs:
  statistics:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: gestrich/claude-step/statistics@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          days_back: 7
          slack_webhook_url: ${{ secrets.SLACK_WEBHOOK_URL }}
```

---

## Learn More

- **[Modifying Tasks](./modifying-tasks.md)** - How to safely reorder, insert, and delete tasks
- **[Architecture Documentation](../architecture/architecture.md)** - Deep dive into how ClaudeStep works
- **[README](../../README.md)** - Full configuration reference and examples

---

## Questions?

- 🐛 [Report Issues](https://github.com/gestrich/claude-step/issues)
- 💬 [Discussions](https://github.com/gestrich/claude-step/discussions)
- 📚 [Documentation](../architecture/architecture.md)
