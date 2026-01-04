# Generate CLAUDE.md

Generate CLAUDE.md by synthesizing information from the architecture and user documentation.

## Instructions

1. Read the following documentation sources:

   **User Documentation:**
   - `README.md` - Project overview and quick start
   - `docs/feature-guides/how-it-works.md` - Core concepts
   - `docs/feature-guides/setup.md` - Setup guide
   - `docs/feature-guides/projects.md` - Project configuration
   - `docs/feature-guides/notifications.md` - Notifications
   - `docs/feature-guides/troubleshooting.md` - Troubleshooting

   **Architecture Documentation:**
   - `docs/general-architecture/testing-philosophy.md` - Testing requirements
   - `docs/general-architecture/service-layer-pattern.md` - Service patterns
   - `docs/general-architecture/domain-model-design.md` - Domain model patterns
   - `docs/general-architecture/python-style.md` - Python coding style
   - `docs/general-architecture/command-dispatcher.md` - Command architecture
   - `docs/general-architecture/github-actions.md` - GitHub Actions conventions

   **Feature Architecture:**
   - `docs/feature-architecture/README.md` - Feature architecture overview
   - Read any other feature architecture docs as needed for context

2. Generate a CLAUDE.md file with the following structure:

   ```markdown
   # Guide for Claude Code

   ## Before Starting Any Tasks

   [Instruct Claude to read key documents before making changes]

   ## Project Overview

   [Brief description of what ClaudeChain is and how users interact with it]

   ## Code Architecture

   [Key architectural patterns - service layer, domain models, etc.]

   ## Testing Requirements

   [Testing philosophy and requirements from testing-philosophy.md]

   ## Code Style

   [Key Python style guidelines]

   ## Common Patterns

   [Frequently used patterns in the codebase]
   ```

3. Guidelines for generation:

   **Do:**
   - Keep it concise - CLAUDE.md should be a quick reference, not duplicate all docs
   - Focus on what Claude needs to know to make good changes
   - Reference the source docs so Claude can read details when needed
   - Include the most important rules and patterns
   - Emphasize backward compatibility and user experience

   **Don't:**
   - Copy entire documents - summarize and reference instead
   - Include implementation details that are in feature-architecture docs
   - Duplicate content that's already in README.md
   - Add information not derived from the documentation

4. Present the generated CLAUDE.md content to the user for review.

5. After user approval, write the file to `CLAUDE.md` in the project root.

## When to Run

Run this command:
- After significant changes to architecture documentation
- After adding new general patterns or conventions
- When CLAUDE.md feels out of sync with the documentation
- As part of major documentation updates
