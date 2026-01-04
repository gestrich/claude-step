# General Architecture

General architectural patterns, conventions, and principles used across the ClaudeChain codebase. These documents explain how we build software in this project.

## What Belongs Here

Documentation about general patterns and conventions:
- Code style guides (Python, TypeScript, etc.)
- Design patterns used across the codebase
- Service layer patterns
- Command dispatcher architecture
- Domain model design principles
- Testing philosophy and approaches
- GitHub Actions conventions
- General integration patterns

## What Doesn't Belong Here

- Feature-specific implementation details (see [feature-architecture](../feature-architecture/))
- User-facing guides (see [feature-guides](../feature-guides/))
- Temporary implementation plans (see [specs](../specs/))

## Writing General Architecture Documentation

When documenting general architecture:
- Focus on **patterns** that apply across multiple features
- Explain the **principles** behind the patterns
- Provide examples from the actual codebase
- Document **when** to use each pattern
- Keep it pragmatic - explain trade-offs and exceptions
- Update when patterns evolve or new patterns emerge

For feature-specific architecture, create documentation in [feature-architecture](../feature-architecture/) instead.

## Relationship to Feature Architecture

Think of general architecture as the "vocabulary" and "grammar" of the codebase:
- **General architecture** defines how we structure services, models, and tests in general
- **Feature architecture** explains how specific features implement those patterns

Example:
- General: "Service layer pattern" - explains the general approach
- Feature: "PR summarization service" - explains how PR summary implements that pattern
