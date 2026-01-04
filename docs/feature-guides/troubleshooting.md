# Troubleshooting

This guide covers common issues and solutions when using ClaudeChain.

## Table of Contents

- [First Task Not Starting](#first-task-not-starting)
- [PR Merge Doesn't Trigger Next Task](#pr-merge-doesnt-trigger-next-task)
- [Spec File Not Found](#spec-file-not-found)
- [Workflow Permissions Issues](#workflow-permissions-issues)
- [Claude Code GitHub App Not Installed](#claude-code-github-app-not-installed)
- [API Rate Limits](#api-rate-limits)
- [Orphaned PR Warnings](#orphaned-pr-warnings)
- [PR Already Open for Project](#pr-already-open-for-project)
- [Workflow Runs But No PR Created](#workflow-runs-but-no-pr-created)

---

## First Task Not Starting

**Symptom:** You added a project but no PR was created.

**Cause:** The first task for a new project cannot auto-trigger—there's no previous PR to merge.

### Solution

**Option 1: Use a labeled PR (Recommended)**

1. Create a PR that adds your spec files
2. Add the `claudechain` label to the PR
3. Merge the PR

ClaudeChain detects the merge and creates the first task PR.

**Option 2: Manual trigger**

1. Go to **Actions** → **ClaudeChain** → **Run workflow**
2. Select your branch (usually `main`)
3. Enter your project name (e.g., `my-refactor`)
4. Click **Run workflow**

Subsequent tasks will auto-trigger when you merge PRs.

---

## PR Merge Doesn't Trigger Next Task

**Symptom:** You merged a ClaudeChain PR but no new PR was created.

### Check 1: Verify the Label

The PR must have the `claudechain` label. PRs created by ClaudeChain get this automatically, but if someone removed it:

1. Check the merged PR for the `claudechain` label
2. If missing, use manual trigger for the next task

### Check 2: Verify It Was Merged

The PR must be **merged**, not just closed:

- ✅ "Merged" status triggers next task
- ❌ "Closed" without merge does not trigger

Check the PR page—it should say "merged" with a purple icon, not "closed" with a red icon.

### Check 3: Check Workflow Logs

1. Go to **Actions** → **ClaudeChain**
2. Find the run triggered by your merge
3. Look for skip reasons or errors:
   - "PR does not have claudechain label"
   - "PR was closed without merging"
   - "No tasks remaining"

### Check 4: Verify Tasks Remain

If all tasks are complete (`- [x]`), there's nothing left to do:

```markdown
- [x] Task 1  ← All complete
- [x] Task 2
- [x] Task 3
```

Add more tasks or start a new project.

---

## Spec File Not Found

**Error:**
```
Error: spec.md not found in branch 'main'
Required file:
  - claude-chain/my-project/spec.md

Please merge your spec.md file to the 'main' branch before running ClaudeChain.
```

### Solution

ClaudeChain fetches spec files from your base branch via the GitHub API. They must be committed and pushed:

1. Verify the file exists locally:
   ```bash
   ls claude-chain/my-project/spec.md
   ```

2. Check if it's committed:
   ```bash
   git status
   ```

3. Push to your base branch:
   ```bash
   git add claude-chain/my-project/spec.md
   git commit -m "Add spec.md"
   git push origin main
   ```

4. Re-run the workflow

**Note:** The `configuration.yml` file is optional—only `spec.md` is required.

---

## Workflow Permissions Issues

**Error:**
```
Error: GitHub Actions is not permitted to create pull requests
```

### Solution

1. Go to **Settings** → **Actions** → **General**
2. Scroll to **Workflow permissions**
3. Check **"Allow GitHub Actions to create and approve pull requests"**
4. Click **Save**
5. Re-run the workflow

---

## Claude Code GitHub App Not Installed

**Error:**
```
Error: Claude Code GitHub App is not installed
```

### Solution

1. Open a terminal in your repository
2. Run Claude Code:
   ```bash
   claude-code
   ```
3. Execute the install command:
   ```
   /install-github-app
   ```
4. Follow the prompts to install the app
5. Re-run the workflow

---

## API Rate Limits

**Error:**
```
Error: GitHub API rate limit exceeded
```

### Solution

GitHub has rate limits on API calls. If exceeded:

1. **Wait** - Rate limits reset hourly
2. **Reduce concurrency** - Run fewer projects simultaneously
3. **Space out merges** - Don't merge many PRs at once

For high-volume usage, consider GitHub Enterprise (higher rate limits).

---

## Orphaned PR Warnings

**Warning:**
```
⚠️  Warning: Found 2 orphaned PR(s):
  - PR #123 (claude-chain-auth-39b1209d) - task hash no longer matches any task
  - PR #125 (claude-chain-auth-a8f3c2d1) - task hash no longer matches any task
```

### Cause

Orphaned PRs occur when:
- You changed a task description while a PR was open
- You deleted a task that had an open PR

The PR references a task hash that no longer exists in `spec.md`.

### Solution

1. **Review each orphaned PR** - Click the link to see what it contains
2. **Close the PR** - The work is for an outdated task
3. **Wait for new PR** - ClaudeChain creates a new PR for the current task

See [Projects Guide - Modifying Tasks](./projects.md#modifying-tasks) for how to avoid orphaned PRs.

---

## PR Already Open for Project

**Message:**
```
Project already has an open PR. Skipping PR creation.
```

### Cause

ClaudeChain enforces one open PR per project at a time. A PR for this project is already open and awaiting review.

### Solution

**Option 1: Merge or close the existing PR**

Review and merge the open PR to allow the next task to proceed.

**Option 2: Check for the open PR**

1. Go to **Pull requests** in your repository
2. Search for PRs with the `claudechain` label
3. Find the PR for this project and review it

This is working as designed—one PR at a time keeps changes focused and avoids merge conflicts.

---

## Workflow Runs But No PR Created

**Symptom:** Workflow completes successfully but no PR appears.

### Check 1: Review Workflow Output

1. Go to **Actions** → find the workflow run
2. Expand the ClaudeChain step
3. Look for outputs:
   - `skipped: true` - Check `skip_reason`
   - `all_steps_done: true` - All tasks complete
   - `has_capacity: false` - No reviewer available

### Check 2: Verify Unchecked Tasks Exist

Ensure `spec.md` has at least one unchecked task:

```markdown
- [x] Completed task
- [ ] This task should get a PR  ← Unchecked
```

### Check 3: Check for Errors

Look for error messages in the workflow logs. Common issues:
- API failures
- Permission denied
- File not found

### Check 4: Verify Branch Exists

ClaudeChain creates a branch before the PR. Check if the branch was created:

```bash
git fetch origin
git branch -r | grep claude-chain
```

If the branch exists but no PR, there may have been an error during PR creation.

---

## Getting More Help

If you can't resolve an issue:

1. **Check workflow logs** - Detailed error messages are in Actions
2. **Search existing issues** - [github.com/gestrich/claude-chain/issues](https://github.com/gestrich/claude-chain/issues)
3. **Open a new issue** - Include:
   - Error message
   - Workflow file (sanitize secrets)
   - Steps to reproduce
   - Relevant workflow run logs

---

## Quick Reference

| Symptom | Likely Cause | Quick Fix |
|---------|--------------|-----------|
| First task not starting | Manual trigger needed | Actions → Run workflow |
| Merge doesn't trigger | Missing label or closed without merge | Check label, verify merged |
| Spec not found | Not pushed to base branch | `git push origin main` |
| Can't create PRs | Permissions not enabled | Settings → Actions → Allow PRs |
| App not installed | Claude Code GitHub App missing | `/install-github-app` |
| Rate limit | Too many API calls | Wait 1 hour |
| Orphaned PRs | Task description changed | Close old PR |
| PR already open | One PR per project limit | Merge existing PR |

---

## Next Steps

- [How It Works](./how-it-works.md) - Understand the core concepts
- [Setup Guide](./setup.md) - Initial configuration
- [Projects Guide](./projects.md) - Project configuration details
