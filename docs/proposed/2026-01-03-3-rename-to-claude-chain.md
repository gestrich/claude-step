## Background

The project is being renamed from "Claude Chain" to "Claude Chain". This is a mechanical refactor involving string replacements across the codebase, plus updates to external dependencies and references.

The rename affects:
- This repository (claude-chain)
- A dependent repository (swift-lambda-sample)
- The project directory name
- The GitHub repository name and remote URL
- A Slack app that references the old name

## Phases

- [ ] Phase 1: String replacements in this repository

Perform case-sensitive string replacements throughout the codebase:
- "Claude Chain" → "Claude Chain"
- "Claude-Chain" → "Claude-Chain"
- "claude-chain" → "claude-chain"
- "claude_chain" → "claude_chain"
- "ClaudeChain" → "ClaudeChain"
- "claudechain" → "claudechain"
- "CLAUDE_CHAIN" → "CLAUDE_CHAIN"
- "CLAUDECHAIN" → "CLAUDECHAIN"

Use grep/ripgrep to find all occurrences, then perform replacements systematically. Verify no occurrences remain after replacement.

- [ ] Phase 2: Update dependent repository (swift-lambda-sample)

Update `/Users/bill/Developer/personal/swift-lambda-sample` to use the new name:
- Apply the same string replacement patterns as Phase 1
- Update any GitHub Action references that point to this repository
- Update any configuration that references the old name

- [ ] Phase 3: User action - Rename project directory

**User action required:** Rename the project directory from `claude-chain` to `claude-chain`:
```bash
mv /Users/bill/Developer/personal/claude-chain /Users/bill/Developer/personal/claude-chain
```

- [ ] Phase 4: User action - Rename GitHub repository

**User action required:** Rename the repository on GitHub:
1. Go to repository Settings on GitHub
2. Change repository name from `claude-chain` to `claude-chain`
3. GitHub will automatically set up redirects for the old name

- [ ] Phase 5: Update git remote URL

After the GitHub repository is renamed, update the remote URL:
```bash
git remote set-url origin git@github.com:<username>/claude-chain.git
```

Also update the remote URL in the swift-lambda-sample repository if it references this repo.

- [ ] Phase 6: User action - Update Slack app name

**User action required:** Update the Slack app configuration:
1. Go to api.slack.com/apps
2. Find the app with "Claude Chain" in the name
3. Update the app name to use "Claude Chain"
4. Update any display names or descriptions that reference the old name

- [ ] Phase 7: Validation

Verify the rename was successful:
- Run `grep -ri "claude.step" . --include="*.py" --include="*.md" --include="*.yaml" --include="*.yml"` to confirm no old references remain (excluding git history)
- Run the test suite: `pytest tests/unit/ tests/integration/ -v`
- Verify git remote is correctly configured: `git remote -v`
- Test that the GitHub Action still works (may require a test PR)
