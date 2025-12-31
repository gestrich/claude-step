# Feature Architecture

Technical documentation for specific ClaudeStep features and components. These documents explain how individual features are designed and implemented.

## What Belongs Here

Documentation about specific features:
- Feature-specific architecture and design decisions
- API reference and contracts
- Integration points with external systems
- Data structures and algorithms for specific features
- Trade-offs and technical considerations
- Feature-specific testing approaches

## What Doesn't Belong Here

- User-facing how-to guides (see [feature-guides](../feature-guides/))
- General patterns used across features (see [general-architecture](../general-architecture/))
- Implementation checklists and ephemeral specs (see [specs](../specs/))

## Available Documentation

Currently being organized. Documentation will be moved here from:
- `docs/architecture/` (feature-specific docs like e2e-testing.md)
- `docs/completed/` (extracted durable knowledge from implementation specs)
- `docs/api.md` (API reference)

## Writing Feature Architecture Documentation

When documenting feature architecture:
- Focus on **why** design decisions were made and **how** features work internally
- Include architecture diagrams where helpful
- Document integration points and dependencies
- Explain trade-offs and alternatives considered
- Keep it durable - extract implementation details from ephemeral specs
- Update when the feature architecture changes

For general patterns that apply across features, create documentation in [general-architecture](../general-architecture/) instead.
