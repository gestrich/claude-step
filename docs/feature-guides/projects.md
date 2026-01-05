# Projects Guide

This guide explains how to create and configure ClaudeChain projects, including writing task specs and managing tasks safely. Each project defines a chain of tasks that ClaudeChain works through one PR at a time.

## Table of Contents

- [Project Structure](#project-structure)
- [spec.md Format](#specmd-format)
- [configuration.yml Format](#configurationyml-format)
  - [Tool Permissions](#tool-permissions)
- [Modifying Tasks](#modifying-tasks)
- [PR Templates](#pr-templates)

---

## Project Structure

ClaudeChain discovers projects by looking for `spec.md` files in the `claude-chain/` directory:

```
your-repo/
├── claude-chain/
│   ├── auth-refactor/
│   │   ├── spec.md              # Required: task list and instructions
│   │   ├── configuration.yml    # Optional: reviewers and settings
│   │   └── pr-template.md       # Optional: custom PR description
│   ├── api-cleanup/
│   │   └── spec.md
│   └── docs-update/
│       ├── spec.md
│       └── configuration.yml
└── ...
```

**Key points:**
- Each subdirectory under `claude-chain/` is a project
- The directory name becomes the project name (e.g., `auth-refactor`)
- Only `spec.md` is required; other files are optional
- You can have multiple projects running in parallel

---

## spec.md Format

The `spec.md` file combines instructions for Claude and a task checklist.

### Basic Structure

```markdown
# Project Title

Describe what you want to refactor and how to do it.

Include:
- Patterns to follow
- Code examples
- Edge cases to handle
- Files or directories to focus on

## Tasks

- [ ] First task to complete
- [ ] Second task to complete
- [ ] Third task to complete
```

### Task Syntax

Tasks use Markdown checkbox syntax:

| Syntax | Meaning |
|--------|---------|
| `- [ ] Task description` | Unchecked (pending) |
| `- [x] Task description` | Checked (complete) |

**Rules:**
- Tasks can appear anywhere in the file (not just at the end)
- Only lines matching `- [ ]` or `- [x]` are treated as tasks
- The description text is used to generate the task hash
- When a PR merges, ClaudeChain automatically marks the task `- [x]`

**Flexible organization:** Tasks can be organized however you like—grouped under headings, separated by blank lines, or interspersed with other text. Just ensure each task starts with `- [ ]` so ClaudeChain can find it.

### Task Lifecycle

```
1. You write:     - [ ] Add input validation
                        ↓
2. PR created:    PR #42 "ClaudeChain: Add input validation"
                        ↓
3. You merge:     PR #42 merged
                        ↓
4. Auto-marked:   - [x] Add input validation
                        ↓
5. Skipped:       Task ignored in future runs
```

### Writing Good Tasks

**Be specific:**
```markdown
# ❌ Too vague
- [ ] Fix the authentication

# ✅ Specific and actionable
- [ ] Add rate limiting to /api/auth/login endpoint (max 5 attempts per minute)
```

**One change per task:**
```markdown
# ❌ Too broad
- [ ] Refactor authentication and add logging

# ✅ Focused
- [ ] Extract authentication logic into AuthService class
- [ ] Add structured logging to authentication flow
```

**Include context in the spec, not the task:**
```markdown
# Auth Refactoring

We're moving from session-based to JWT authentication.
Follow the patterns in `src/auth/jwt-example.ts`.

## Tasks

- [ ] Add JWT token generation to login endpoint
- [ ] Add JWT verification middleware
- [ ] Update protected routes to use new middleware
```

### Adding Details to Tasks

You can add details below a task without affecting its hash:

```markdown
- [ ] Add user authentication

  Implementation notes:
  - Use OAuth 2.0 with Google and GitHub providers
  - Store tokens in httpOnly cookies
  - Add CSRF protection

  Reference: See `docs/auth-spec.md` for full requirements
```

Only the checkbox line (`- [ ] Add user authentication`) is hashed. The indented content below can be changed freely without creating orphaned PRs.

---

## configuration.yml Format

The configuration file is **optional**. Without it, ClaudeChain uses these defaults:
- PRs created without an assignee
- Maximum 1 open PR per project

### Basic Structure

```yaml
assignee: alice
```

### Full Schema

```yaml
# Optional: GitHub username to assign PRs to
assignee: alice

# Optional: Override base branch for this project
baseBranch: develop

# Optional: Override allowed tools for this project
allowedTools: Read,Write,Edit,Bash

# Optional: Days before a PR is considered stale (for statistics)
stalePRDays: 7
```

### Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `assignee` | string | No | GitHub username to assign PRs to |
| `baseBranch` | string | No | Override base branch (defaults to workflow context) |
| `allowedTools` | string | No | Override allowed tools (defaults to workflow input) |
| `stalePRDays` | number | No | Days before a PR is considered stale (default: 7) |

### Stale PR Tracking

The `stalePRDays` setting controls when PRs are flagged as stale in statistics reports:

```yaml
# Flag PRs as stale after 14 days (default is 7)
stalePRDays: 14
assignee: alice
```

Stale PRs appear in statistics reports with warnings:
- The project's **Status** column shows `⚠️ N stale`
- The **Projects Needing Attention** section lists specific stale PRs with assignee info

This helps identify PRs that may be stuck or need attention.

### Capacity Management

ClaudeChain enforces a simple rule: **one open PR per project at a time**. This ensures:
- Focus on completing one task before starting the next
- Clean merge history without conflicts
- Clear ownership of what's currently in progress

When the open PR is merged (or closed), ClaudeChain automatically creates a PR for the next task.

### Base Branch Override

Use `baseBranch` when a project targets a different branch:

```yaml
# This project targets 'develop' instead of 'main'
baseBranch: develop
assignee: alice
```

### Tool Permissions

Use `allowedTools` to customize which tools Claude can use for a specific project. This overrides the workflow-level `claude_allowed_tools` input.

**Default tools** (minimal for security):
- `Read` - Read spec.md and codebase files
- `Write` - Create new files
- `Edit` - Modify existing files
- `Bash(git add:*)` - Stage changes
- `Bash(git commit:*)` - Commit changes

**When to expand permissions:**

If your tasks require running tests, builds, or other shell commands, add them to the project's configuration:

```yaml
# Full Bash access for this project
allowedTools: Read,Write,Edit,Bash
assignee: alice
```

**Granular Bash permissions:**

Use `Bash(command:*)` syntax to allow specific commands only:

```yaml
# Allow only specific commands
allowedTools: Read,Write,Edit,Bash(git add:*),Bash(git commit:*),Bash(npm test:*),Bash(npm run build:*)
```

**Examples by project type:**

| Project Type | Recommended `allowedTools` |
|--------------|----------------------------|
| Documentation updates | `Read,Write,Edit,Bash(git add:*),Bash(git commit:*)` (default) |
| Code refactoring with tests | `Read,Write,Edit,Bash` |
| Build-dependent changes | `Read,Write,Edit,Bash(git add:*),Bash(git commit:*),Bash(npm run build:*)` |
| Security-sensitive projects | `Read,Edit,Bash(git add:*),Bash(git commit:*)` (no `Write`) |

**Configuration hierarchy:**
1. Workflow-level `claude_allowed_tools` input (default for all projects)
2. Project-level `allowedTools` in `configuration.yml` (overrides workflow default)

---

## Modifying Tasks

ClaudeChain uses hash-based task identification, making most modifications safe.

### Safe Operations

#### ✅ Reordering Tasks

Move tasks freely—the hash stays the same:

```markdown
# Before
- [ ] Task A
- [ ] Task B
- [ ] Task C

# After (safe!)
- [ ] Task C
- [ ] Task A
- [ ] Task B
```

#### ✅ Inserting New Tasks

Add tasks anywhere:

```markdown
# Before
- [ ] Task A
- [ ] Task C

# After (safe!)
- [ ] Task A
- [ ] Task B    ← New task
- [ ] Task C
```

#### ✅ Deleting Completed Tasks

Remove tasks that are already done:

```markdown
# Before
- [x] Task A    ← Completed
- [ ] Task B

# After (safe!)
- [ ] Task B
```

### Operations That Create Orphaned PRs

#### ⚠️ Changing Task Descriptions

Editing the checkbox text creates a new hash:

```markdown
# Before (PR #123 open for this task)
- [ ] Add user authentication

# After (creates orphaned PR!)
- [ ] Add OAuth authentication
```

**Result:** PR #123 becomes orphaned. ClaudeChain warns you; close the old PR and a new one will be created.

#### ⚠️ Deleting Tasks With Open PRs

Removing an uncompleted task orphans its PR:

```markdown
# Before (PR #123 open for Task A)
- [ ] Task A
- [ ] Task B

# After (creates orphaned PR!)
- [ ] Task B
```

### Resolving Orphaned PRs

When ClaudeChain detects orphaned PRs, it shows a warning:

```
⚠️  Warning: Found 1 orphaned PR(s):
  - PR #123 (claude-chain-auth-39b1209d) - task hash no longer matches any task

To resolve:
  1. Review the PR and verify if it should be closed
  2. Close the orphaned PR
  3. ClaudeChain will automatically create a new PR for the current task
```

**Steps:**
1. Click the PR link in the warning
2. Review whether the work is still relevant
3. Close the PR (add a comment explaining why)
4. The next workflow run creates a new PR for the updated task

### Best Practices

| Scenario | Recommendation |
|----------|----------------|
| Reordering tasks | ✅ Do it anytime |
| Adding new tasks | ✅ Do it anytime |
| Removing completed tasks | ✅ Do it anytime |
| Changing task text | ⏳ Wait until PR is merged |
| Removing uncompleted tasks | ⚠️ Close the orphaned PR after |

---

## PR Templates

Customize PR descriptions with a template file.

### Creating a Template

Create `claude-chain/{project}/pr-template.md`:

```markdown
## Task

{{TASK_DESCRIPTION}}

## Review Checklist

- [ ] Code follows project conventions
- [ ] Tests pass
- [ ] No unintended changes
- [ ] Documentation updated if needed

---
*Auto-generated by ClaudeChain*
```

### Template Variables

| Variable | Replaced With |
|----------|---------------|
| `{{TASK_DESCRIPTION}}` | The task text from spec.md |

For example, if your spec.md contains:
```markdown
- [ ] Add input validation to login endpoint
```

Then `{{TASK_DESCRIPTION}}` becomes `Add input validation to login endpoint` in the PR body.

### Default Template

If no template exists, ClaudeChain uses a simple default with just the task description.

---

## Examples

### Minimal Project

Just a `spec.md`:

```
claude-chain/quick-fix/
└── spec.md
```

```markdown
# Quick Fix

Fix the typos in error messages.

- [ ] Fix typo in login error message
- [ ] Fix typo in signup error message
```

### Full Project

All optional files:

```
claude-chain/auth-migration/
├── spec.md
├── configuration.yml
└── pr-template.md
```

**spec.md:**
```markdown
# Auth Migration

Migrate from session-based to JWT authentication.

## Background

We're switching to JWTs for better scalability.
See `docs/auth-rfc.md` for the full design.

## Tasks

- [ ] Add JWT utility functions to `src/auth/jwt.ts`
- [ ] Update login endpoint to return JWT
- [ ] Add JWT verification middleware
- [ ] Update protected routes to use new middleware
- [ ] Remove session-related code
- [ ] Update tests
```

**configuration.yml:**
```yaml
assignee: alice
```

**pr-template.md:**
```markdown
## Auth Migration Task

{{TASK_DESCRIPTION}}

## Testing

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

## Security Review

- [ ] No secrets exposed
- [ ] Auth flow is secure
```

---

## Next Steps

- [How It Works](./how-it-works.md) - Understand the PR chain and task identification
- [Notifications Guide](./notifications.md) - Set up Slack notifications
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
