# Implementation Specs

Ephemeral documentation for planning and tracking implementation work. Unlike durable architecture documentation, specs are temporary artifacts of the development process.

## What Belongs Here

Temporary implementation documentation:
- Detailed implementation plans and checklists
- Step-by-step task breakdowns
- Verification logs and testing notes
- File change lists and code snippets
- Implementation progress tracking
- Temporary design explorations

## What Doesn't Belong Here

- Durable architecture knowledge (extract to [feature-architecture](../feature-architecture/) or [general-architecture](../general-architecture/))
- User-facing guides (see [feature-guides](../feature-guides/))
- Stable API documentation (see [feature-architecture](../feature-architecture/))

## Directory Structure

### [active/](active/)
Implementation specs currently being worked on. These are living documents that track active development work.

**Lifecycle:**
1. Create spec in `active/` when starting significant implementation work
2. Update as work progresses
3. When complete, extract durable knowledge to architecture docs
4. Move to `archive/` with date prefix

### [archive/](archive/)
Completed implementation specs for historical reference. These provide a record of how features were built but are not the primary source of architectural knowledge.

**Naming convention:** `YYYY-MM-description.md`
- Example: `2024-12-formalize-service-layer.md`
- Date reflects when work was completed (from git history)

## When to Create a Spec

Create an implementation spec when:
- Planning a significant new feature
- Breaking down complex refactoring work
- Coordinating work across multiple files/components
- You need detailed task tracking beyond what git commits provide

Skip creating a spec for:
- Small bug fixes
- Simple one-file changes
- Routine maintenance

## Extracting Knowledge from Specs

Before archiving a completed spec, ask:
- **Architecture decisions:** Should this go in feature-architecture or general-architecture?
- **Design patterns:** Is this a reusable pattern worth documenting?
- **Technical trade-offs:** Would this help future developers understand why things work this way?

Extract durable knowledge to architecture docs, then archive the spec for historical reference.

## Why This Structure?

Implementation specs are valuable during development but become outdated quickly. By treating them as ephemeral and extracting durable knowledge to architecture docs, we:
- Keep architecture docs focused and maintainable
- Preserve implementation history for reference
- Avoid confusion between current architecture and historical implementation notes
- Make it clear which docs should be updated when code changes
