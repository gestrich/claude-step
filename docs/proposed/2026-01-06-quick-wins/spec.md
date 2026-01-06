# ClaudeChain Quick Wins

Small improvements that can be completed in under 2 hours each. These are low-risk, high-value enhancements to improve ClaudeChain's usability and user feedback.

## Background

The TODO list contains many small improvements that have accumulated. This spec extracts the quick wins - tasks that require minimal architectural changes and can be completed independently. Each phase is self-contained and provides immediate value.

---

- [ ] **Add project name to PR titles**

Currently PR titles are generated without indicating which project they belong to. When multiple ClaudeChain projects exist in a repository, it's unclear which project a PR is associated with from the title alone.

**Current behavior:**
```
Task a3f2b891: Add user authentication
```

**Target behavior:**
```
[auth-migration] Task a3f2b891: Add user authentication
```

**Files to modify:**
- `src/claudechain/cli/commands/prepare.py` - Update PR title generation to prepend project name

**Implementation:**
1. In `prepare.py`, locate where the PR title is constructed
2. Prepend the project name in brackets: `f"[{project_name}] {existing_title}"`
3. Update any tests that assert on PR title format

---

- [ ] **Add repository name to Slack notifications**

When ClaudeChain is used across multiple repositories, Slack notifications don't indicate which repository the statistics are for. This makes it hard to identify the source at a glance.

**Current behavior:**
```
ClaudeChain Statistics
Project Progress
...
```

**Target behavior:**
```
ClaudeChain Statistics (owner/repo-name)
Project Progress
...
```

**Files to modify:**
- `src/claudechain/domain/models.py` - Add `repo` field to `StatisticsReport` and include in header
- `src/claudechain/services/composite/statistics_service.py` - Pass repo to report
- `src/claudechain/cli/commands/statistics.py` - Ensure repo is passed through

**Implementation:**
1. Add `repo: Optional[str] = None` to `StatisticsReport.__init__`
2. Update `to_header_section()` to include repo name if present
3. Pass `self.repo` when creating the report in `StatisticsService`

---

- [ ] **Add orphaned PRs disclaimer to GH Summary**

The GitHub Action step summary shows detailed task views but doesn't explain what orphaned PRs mean. Users may be confused when they see "Orphaned PRs" listed without context.

**Target behavior:**
Add a note above the orphaned PRs section explaining:
```
> **Note:** Orphaned PRs are pull requests whose associated tasks have been removed from the spec file.
> These may need manual review to determine if they should be closed or if the task should be restored.
```

**Files to modify:**
- `src/claudechain/domain/models.py` - Update `format_project_details()` or `to_project_details_section()` to include disclaimer

**Implementation:**
1. In `to_project_details_section()`, add a TextBlock with the disclaimer before listing orphaned PRs
2. Only show the disclaimer if there are orphaned PRs in any project

---

- [ ] **Show PR links in Statistics summary**

The warnings section mentions PRs by number (e.g., "#42") but these are not clickable in the GitHub step summary. Adding full URLs would make it easier to navigate to problematic PRs.

**Files to modify:**
- `src/claudechain/domain/models.py` - Update `to_warnings_section()` to include full PR URLs as markdown links

**Implementation:**
1. In `to_warnings_section()`, construct the full PR URL using the repo and PR number
2. Format as markdown link: `[#42](https://github.com/owner/repo/pull/42)`
3. Requires repo to be available on the report (see "Add repository name" task above)

---

- [ ] **Add trigger instructions when no PRs are open**

When statistics show no open PRs for a project that has remaining tasks, users may not know how to trigger the next PR creation. The Slack message should include helpful guidance.

**Current behavior:**
```
No open PRs (3 tasks remaining)
```

**Target behavior:**
```
No open PRs (3 tasks remaining)
Trigger: Run the "ClaudeChain" workflow manually or push to the spec branch
```

**Files to modify:**
- `src/claudechain/domain/models.py` - Update `to_warnings_section()` to add trigger hint for projects with `has_remaining_tasks`

**Implementation:**
1. When a project has `has_remaining_tasks == True`, append a hint about triggering
2. Keep the hint generic since trigger methods vary by setup

---

- [ ] **Support Slack webhook override in project config**

Different teams in the same repository may want ClaudeChain notifications sent to different Slack channels. Allow the project config to override the default webhook URL.

**Current behavior:**
Single `SLACK_WEBHOOK_URL` environment variable for all projects.

**Target behavior:**
Project config can specify `slack_webhook_url` to override:
```yaml
project: auth-migration
assignee: alice
slack_webhook_url: https://hooks.slack.com/services/TEAM/CHANNEL
```

**Files to modify:**
- `src/claudechain/domain/project_configuration.py` - Add `slack_webhook_url` field
- `src/claudechain/cli/commands/statistics.py` - Use project-specific webhook if available
- Update config schema documentation

**Implementation:**
1. Add optional `slack_webhook_url: Optional[str] = None` field to `ProjectConfiguration`
2. Update `from_yaml_string()` to parse the new field
3. In statistics command, check each project's config for override before using default

---

- [ ] **Add workflow file change triggers**

ClaudeChain workflows should re-run when their workflow files are modified. This ensures changes to the workflow are tested.

**Files to modify:**
- `.github/workflows/claudechain.yml` (or equivalent) - Add path triggers

**Target configuration:**
```yaml
on:
  push:
    paths:
      - '.github/workflows/claudechain*.yml'
      - '.claude-chain/**'
  workflow_dispatch:
  # ... existing triggers
```

**Implementation:**
1. Add `paths` filter to push trigger
2. Include both workflow files and ClaudeChain config directories
3. Document the behavior in workflow comments

---

- [ ] **Standardize Phase vs Step terminology in docs**

Documentation inconsistently uses "Phase" and "Step" to describe stages of work. Pick one term and use it consistently.

**Decision:** Use "Phase" for spec.md task groupings (already established pattern).

**Files to review and update:**
- `docs/feature-guides/*.md`
- `docs/feature-architecture/*.md`
- `README.md`

**Implementation:**
1. Search for "step" (case-insensitive) in documentation
2. Replace with "phase" where it refers to spec.md task stages
3. Keep "step" for GitHub Action steps (different context)

---

## Validation

After completing all phases, run the test suite:

```bash
export PYTHONPATH=src:scripts
pytest tests/unit/ tests/integration/ -v
```

Each phase should include its own test updates where applicable.
