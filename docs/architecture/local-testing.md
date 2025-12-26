# Local Testing Setup

## Testing Repository

This application uses `/Users/bill/Developer/personal/claude-refactor-chain` as a dedicated testing repository.

### Purpose

The repository serves as a local testing environment for:
- Creating test projects and artifacts
- Validating application functionality
- Testing GitHub integrations

### GitHub Integration Testing

The app interacts with GitHub using the `gh` CLI APIs to:
- Monitor workflow runs
- Check CI/CD status
- Verify GitHub Actions execution
- Test pull request workflows

### Usage

This testing setup allows safe experimentation and validation of features without affecting production repositories. All GitHub API interactions are performed through the official `gh` CLI tool, ensuring consistent and reliable communication with GitHub services.
