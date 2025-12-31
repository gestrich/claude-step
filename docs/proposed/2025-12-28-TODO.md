# TODO

## V1

**Configuration & Workflow Improvements:** See [v1-improvements.md](v1-improvements.md) for detailed tasks related to configuration format, branch naming, action inputs, and PR triggers.

- [ ] **Secure Secrets**

- Confirm secure approach for Claude token Actions
- Confirm secure approach for webhooks (secrets?)

- [ ] **Cost Control**

Explore how to avoid runaway costs from either jobs taking to long or too many PRs opening.

- [ ] **Record video walkthrough**

Create "ClaudeStep" tutorial video.

- [ ] **Write blog post**

Written guide explaining the approach.

## V2

- [ ] AI Retry on Failed Builds

If tests fail on CI after AI generated code, the AI could try to fix it up to N times.

- [ ] **Local Build Script**

Fetch open PRs and build locally on a schedule. Ready to run when you sit down to review.

- [ ] **UI Automation Screenshots**

Capture screenshots showing the result. Visual verification without manual testing.

- [ ] Support additional claude mentions in PR

Use Claude Code mentions to update the PR

- [ ] Explore using GH issues to store tasks

Pros
* Single source of truth for status and things
* Easier to find status
* Can edit outside PRs (completing tasks)
* Maybe config can be eliminated

Cons
* Work defined outside repo
* Strict structure required in unexpected place (GH issue)