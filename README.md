# ClaudeStep

## Overview

An automated system for performing ongoing code refactoring using AI (Claude Code) and GitHub Actions. The system continuously generates pull requests for incremental refactoring work, reducing the manual burden and maintaining momentum on large-scale codebase improvements.

## Use as a GitHub Action

Add the action to your workflow:

```yaml
- uses: gestrich/claude-step@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    github_token: ${{ secrets.GITHUB_TOKEN }}
    project_name: 'your-project-name'
```

**Benefits:**
- ✅ No workflow files to maintain
- ✅ Automatic updates with `@v1` tag
- ✅ Simpler setup
- ✅ Works with any repository

**Quick Start:**
1. See [ACTION_README.md](ACTION_README.md) for complete documentation
2. Check [examples/basic/workflow.yml](examples/basic/workflow.yml) for a simple example
3. See [examples/advanced/workflow.yml](examples/advanced/workflow.yml) for all features

## TODO

- [ ] **Create Labels**

The action should create the new label when it does not exist.

- [ ] **Slack Action and metrics**

Post progress updates and metrics to Slack when PRs are merged.

Success metrics to track:
- Time from PR creation to merge (review efficiency)
- Percentage of PRs merged without modification
- Total items completed over time
- Specification refinement iterations needed

- [ ] **Progress Celebration**

Post to Slack on merge: "✅ 47/300 files converted to Swift". Keeps momentum visible. You can even include a summary celebrating the number of PRs reviewed by each user.

- [ ] **Leaderboard & Stats**

Create a GitHub Pages site or Slack integration that tracks merges per developer over time. Query merged PRs with your refactor label using the GitHub API, aggregate by assignee, and display a leaderboard. Great for friendly competition and recognizing top reviewers.

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

Create a label for tracking refactor PRs (must match `label` in your `config.json`):

```bash
gh label create "your-refactor-label" --description "Automated refactor PRs" --color "0E8A16"
```

### 5. Configuration

A `configuration.json` file per refactor project:

```json
{
  "label": "swift-migration",
  "branchPrefix": "refactor/swift-migration",
  "reviewers": [
    { "username": "alice", "maxOpenPRs": 1 },
    { "username": "bob", "maxOpenPRs": 1 }
  ]
}
```

- **label** - GitHub tag used to identify PRs for this refactor
- **branchPrefix** - Prefix for branch names (actual format: YYYY-MM-{project}-{index})
- **reviewers** - List of GitHub usernames and how many PRs each can have open at once

### 6. spec.md Format

The `spec.md` file combines instructions and checklist in a single document. Format requirements:

**Checklist Items:**
- Use `- [ ]` for unchecked items (tasks to do)
- Use `- [x]` for checked items (completed tasks)
- Items can appear anywhere in the file (not limited to a specific section)
- At least one checklist item must be present

**Example Structure:**

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

**Validation:**
The GitHub Action validates that `spec.md` contains at least one checklist item (`- [ ]` or `- [x]`). If none are found, the workflow will fail with a clear error message.

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

### Trigger Modes

| Mode | How It Works | Best For |
|------|--------------|----------|
| **Scheduled** | Runs daily via cron | Predictable workload, steady pace |
| **Immediate** | Triggers on PR merge (if label matches) | Fast iteration, rapid progress |

Recommendation: Start with immediate trigger for faster feedback, switch to scheduled once the process is stable.

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
