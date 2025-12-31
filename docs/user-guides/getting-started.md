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

### 4. Push to Main Branch

```bash
git add claude-step/my-refactor/
git commit -m "Add ClaudeStep project: my-refactor"
git push origin main
```

**That's it!** The first task will automatically start within a few minutes.

---

## What Happens Automatically

### Auto-Start Workflow

When you push a new `spec.md` file to your main branch, ClaudeStep automatically:

1. **Detects the new project** (no existing PRs found)
2. **Triggers the ClaudeStep workflow** for your project
3. **Creates a PR for the first task** within 2-5 minutes
4. **Assigns the PR** to an available reviewer

### Subsequent Tasks

After the first task:

1. **You review and merge** the PR when ready
2. **ClaudeStep detects the merge** automatically
3. **Creates the next PR** for the second task
4. **Process continues** until all tasks are complete

### Example Timeline

```
0:00 - You push spec.md to main
0:01 - Auto-start workflow detects new project
0:02 - ClaudeStep workflow starts
0:05 - PR #1 created for first task
...
You merge PR #1
...
0:10 - ClaudeStep detects merge
0:12 - PR #2 created for second task
...
(continues for all tasks)
```

---

## Troubleshooting

### First Task Doesn't Auto-Start

If the first task doesn't automatically start after pushing your spec to main:

#### 1. Check the Auto-Start Workflow Run

- Go to **Actions** > **ClaudeStep Auto-Start**
- Verify the workflow ran after your push
- Check if any errors occurred

#### 2. Review the Workflow Summary

The auto-start workflow provides a summary showing:
- Which projects had spec.md changes
- Whether they were detected as new or existing
- Which projects had auto-trigger initiated

**Example Summary:**
```
Projects with spec.md changes:
- my-refactor

Auto-triggered for new projects:
- ✅ my-refactor (first task will be started)
```

#### 3. Verify It's a New Project

Auto-start only works for **new projects** (no existing ClaudeStep PRs).

**Check for existing PRs:**
1. Go to **Pull Requests**
2. Filter by label: `claudestep`
3. Look for PRs with branches matching `claude-step-my-refactor-*`

**If PRs exist:**
- Your project is not "new" (has existing PRs)
- Auto-start will skip it
- Use PR merge triggers instead (merge a PR to get the next one)

**If no PRs exist:**
- Your project should have been auto-triggered
- Check workflow logs for errors

#### 4. Check Workflow Logs

If auto-start ran but didn't trigger:
1. Go to **Actions** > **ClaudeStep Auto-Start** > latest run
2. Check the "Trigger ClaudeStep for new projects" step
3. Look for error messages (API failures, permissions issues, etc.)

#### 5. Manual Trigger (Fallback)

As a fallback, you can always manually trigger:
1. Go to **Actions** > **ClaudeStep** > **Run workflow**
2. Select your branch (usually `main`)
3. Enter your project name (e.g., `my-refactor`)
4. Click **Run workflow**

This will start the first task manually, and subsequent tasks will auto-trigger on PR merge.

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
3. Push to main branch: `git push origin main`
4. Wait for auto-start workflow to run again

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

## Disabling Auto-Start

If you prefer manual control over when tasks start:

### Option 1: Delete the Auto-Start Workflow

```bash
rm .github/workflows/claudestep-auto-start.yml
git commit -m "Disable auto-start workflow"
git push origin main
```

### Option 2: Disable in GitHub Settings

1. Go to **Actions** > **Workflows**
2. Click **ClaudeStep Auto-Start**
3. Click **⋯** (menu) > **Disable workflow**

**Note:** Disabling auto-start only affects the first task. Subsequent tasks will still auto-trigger when you merge PRs.

### Manual Triggering After Disabling

To start the first task manually:
1. Go to **Actions** > **ClaudeStep** > **Run workflow**
2. Enter your project name
3. Click **Run workflow**

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
