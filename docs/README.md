# ClaudeChain Documentation

This directory contains all documentation for the ClaudeChain project, organized by audience and purpose.

## Documentation Structure

### [Feature Guides](feature-guides/) - For Users
User-facing documentation explaining how to use ClaudeChain features:
- Getting started guides
- How-to guides for specific features
- User workflows and best practices

**Start here if you're** using ClaudeChain in your project.

### [Feature Architecture](feature-architecture/) - For Developers
Technical documentation for specific features and components:
- Feature-specific design and implementation details
- API reference documentation
- Integration guides
- Testing strategies for specific features

**Start here if you're** working on a specific feature or need to understand how a particular component works.

### [General Architecture](general-architecture/) - For Contributors
General patterns, conventions, and architectural principles:
- Code style guides
- Design patterns used across the codebase
- Testing philosophy
- Service layer patterns
- Command dispatcher architecture

**Start here if you're** contributing to ClaudeChain and need to understand the overall architecture and coding conventions.

### Implementation Specs
Ephemeral documentation for planning and tracking implementation work:
- **[proposed/](proposed/)** - Current implementation specs being worked on
- **[completed/](completed/)** - Completed implementation specs for historical reference

**Start here if you're** looking for detailed implementation history or need to reference how something was built.

## Quick Links

- [Getting Started Guide](feature-guides/getting-started.md) - New to ClaudeChain? Start here
- [Architecture Overview](general-architecture/) - Understanding the system design
- [API Reference](feature-architecture/api-reference.md) - Detailed API documentation

## Contributing to Documentation

When adding new documentation:
1. **User guides** go in `feature-guides/` - focus on how to use features
2. **Feature technical docs** go in `feature-architecture/` - focus on how features are implemented
3. **General patterns** go in `general-architecture/` - focus on reusable patterns across the codebase
4. **Implementation specs** go in `proposed/` - temporary planning docs that get archived to `completed/` when done

See the README in each directory for more specific guidance.
