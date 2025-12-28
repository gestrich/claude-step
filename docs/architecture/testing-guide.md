# ClaudeStep Testing Guide

This guide documents the testing practices, conventions, and workflows for the ClaudeStep project.

## Quick Start

### Running Tests Locally

```bash
# Run all unit tests
PYTHONPATH=src:scripts pytest tests/unit/ -v

# Run all integration tests
PYTHONPATH=src:scripts pytest tests/integration/ -v

# Run both unit and integration tests
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v

# Run with coverage report
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing --cov-report=html

# Run tests for a specific module
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_prepare.py -v

# Run a specific test
PYTHONPATH=src:scripts pytest tests/integration/cli/commands/test_prepare.py::TestCmdPrepare::test_successful_preparation -v
```

### Understanding Test Results

```bash
# View coverage in terminal
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing

# View detailed HTML coverage report (opens in browser)
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Test Architecture

### Directory Structure

Tests mirror the `src/` directory structure:

```
tests/
├── conftest.py                           # Shared fixtures
├── unit/
│   ├── domain/                           # Domain layer tests
│   │   ├── test_config.py
│   │   ├── test_models.py
│   │   └── test_exceptions.py
│   ├── infrastructure/                   # Infrastructure layer tests
│   │   ├── git/
│   │   │   └── test_operations.py
│   │   ├── github/
│   │   │   ├── test_operations.py
│   │   │   └── test_actions.py
│   │   └── filesystem/
│   │       └── test_operations.py
│   └── application/                      # Application layer tests
│       ├── collectors/
│       │   └── test_statistics.py
│       ├── formatters/
│       │   └── test_table_formatter.py
│       └── services/
│           ├── test_pr_operations.py
│           ├── test_task_management.py
│           ├── test_reviewer_management.py
│           ├── test_project_detection.py
│           └── test_artifact_operations.py
├── integration/                          # Integration tests
│   └── cli/                              # CLI command integration tests
│       └── commands/
│           ├── test_prepare.py
│           ├── test_prepare_summary.py
│           ├── test_finalize.py
│           ├── test_discover.py
│           ├── test_discover_ready.py
│           ├── test_statistics.py
│           ├── test_add_cost_comment.py
│           ├── test_extract_cost.py
│           └── test_notify_pr.py
├── e2e/                                  # End-to-end tests
└── builders/                             # Test helpers/factories
```

### Test Layers

1. **Domain Tests** (`tests/unit/domain/`) - Test models, configuration, exceptions
2. **Infrastructure Tests** (`tests/unit/infrastructure/`) - Test external integrations (git, GitHub, filesystem)
3. **Application Tests** (`tests/unit/application/`) - Test business logic and services
4. **CLI Integration Tests** (`tests/integration/cli/`) - Test command orchestration across multiple components
5. **E2E Tests** (`tests/e2e/`) - Test complete workflows with real GitHub API

## Test Style Guide

**IMPORTANT**: All tests in this project MUST follow these conventions. Consistency is critical for maintainability.

### Required Test Structure

```python
class TestFeatureName:
    """Test suite for FeatureName functionality"""

    @pytest.fixture
    def fixture_name(self):
        """Fixture providing test data - clear docstring explaining purpose"""
        return setup_test_data()

    def test_feature_does_something_when_condition(self, fixture_name):
        """Test description explaining what this verifies

        Should read like: "Test that feature does X when Y condition exists"
        """
        # Arrange - Set up test data and mocks
        expected_value = "expected"
        mock_dependency = Mock()

        # Act - Execute the code under test
        result = function_under_test(fixture_name, mock_dependency)

        # Assert - Verify the outcome
        assert result == expected_value
        mock_dependency.method.assert_called_once()
```

### Naming Conventions

**Class Names**: `TestModuleName` or `TestFunctionName`
- ✅ `TestReviewerManagement`
- ✅ `TestCheckReviewerCapacity`
- ❌ `ReviewerTests` (wrong suffix)
- ❌ `TestReviewers` (too vague)

**Test Method Names**: `test_<what>_<when>_<condition>`
- ✅ `test_find_reviewer_returns_none_when_all_at_capacity`
- ✅ `test_create_branch_raises_error_when_branch_exists`
- ✅ `test_parse_branch_extracts_project_and_index`
- ❌ `test_reviewer` (not descriptive)
- ❌ `test_find_reviewer_works` (vague)

**Fixture Names**: `<resource>_<state>` or `mock_<service>`
- ✅ `reviewer_config`, `sample_spec_file`, `mock_github_api`
- ❌ `data`, `setup`, `fixture1`

## Testing Principles

### 1. Test Behavior, Not Implementation

**✅ GOOD - Tests the behavior/outcome:**
```python
def test_find_available_reviewer_returns_reviewer_under_capacity(mock_github_api):
    """Should return first reviewer with available capacity"""
    # Arrange
    reviewers = [
        ReviewerConfig(username="alice", maxOpenPRs=2),
        ReviewerConfig(username="bob", maxOpenPRs=2)
    ]
    mock_github_api.get_open_prs.side_effect = [
        [{"number": 1}, {"number": 2}],  # alice at capacity
        [{"number": 3}]  # bob under capacity
    ]

    # Act
    result = find_available_reviewer(reviewers, mock_github_api)

    # Assert
    assert result.username == "bob"
```

**❌ BAD - Tests implementation details:**
```python
def test_find_available_reviewer_calls_check_capacity_for_each(mock_check):
    """Don't test that internal functions are called - test outcomes"""
    reviewers = [ReviewerConfig(username="alice", maxOpenPRs=2)]

    with patch('module.check_reviewer_capacity') as mock_check:
        find_available_reviewer(reviewers)
        assert mock_check.call_count == 1  # Brittle - breaks if refactored
```

### 2. Mock at System Boundaries

**✅ GOOD - Mock external services:**
```python
def test_create_pull_request_success(mock_subprocess):
    """Should execute gh CLI command with correct arguments"""
    mock_subprocess.run.return_value = Mock(returncode=0, stdout="PR #123")

    result = create_pull_request(
        title="Test PR",
        body="Description",
        base="main"
    )

    assert result == "123"
    mock_subprocess.run.assert_called_once()
```

**❌ BAD - Over-mocking internal logic:**
```python
def test_prepare_command():
    with patch('module.os') as mock_os:
        with patch('module.Path') as mock_path:
            with patch('module.yaml') as mock_yaml:
                with patch('module.find_task') as mock_find:
                    with patch('module.create_branch') as mock_branch:
                        # 5+ mocks = you're testing mocks, not code
                        cmd_prepare(args)
```

### 3. Test Edge Cases and Boundaries

Use parametrization for testing multiple boundary conditions:

```python
@pytest.mark.parametrize("open_pr_count,max_prs,expected", [
    (0, 2, True),   # Well under capacity
    (1, 2, True),   # Just under capacity
    (2, 2, False),  # Exactly at capacity
    (3, 2, False),  # Over capacity
    (0, 0, False),  # Edge case: zero max
])
def test_check_reviewer_capacity_boundary_conditions(
    open_pr_count, max_prs, expected, mock_github_api
):
    """Should correctly handle all capacity boundary conditions"""
    reviewer = ReviewerConfig(username="alice", maxOpenPRs=max_prs)
    mock_github_api.get_open_prs.return_value = [
        {"number": i} for i in range(open_pr_count)
    ]

    result = check_reviewer_capacity(reviewer, mock_github_api)

    assert result == expected
```

### 4. One Concept Per Test

**✅ GOOD - Focused tests:**
```python
def test_prepare_creates_branch():
    """Should create a new branch for the task"""
    # Test only branch creation

def test_prepare_finds_next_task():
    """Should find the next uncompleted task from spec.md"""
    # Test only task finding

def test_prepare_assigns_reviewer():
    """Should assign a reviewer with available capacity"""
    # Test only reviewer assignment
```

**❌ BAD - Testing too many things:**
```python
def test_prepare_workflow():
    """Too broad - should be split into multiple tests"""
    result = cmd_prepare(args)
    assert result.exit_code == 0
    assert result.branch_created
    assert result.task_found
    assert result.reviewer_assigned
    assert result.prompt_generated
    # If any assertion fails, you don't know which part broke
```

## Common Fixtures

The `tests/conftest.py` file provides reusable fixtures organized by category:

### File System Fixtures
- `tmp_project_dir` - Temporary directory with sample project structure
- `sample_spec_file` - spec.md with various task states
- `empty_spec_file` - Empty spec.md file
- `all_completed_spec_file` - spec.md with all tasks completed

### Git Fixtures
- `mock_git_repo` - Creates a real temporary git repository

### GitHub Fixtures
- `mock_github_api` - Mock GitHub API responses
- `sample_pr_data` - Sample PR object
- `sample_pr_list` - List of sample PRs
- `github_env_vars` - GitHub Actions environment variables

### Configuration Fixtures
- `sample_config_file` - YAML configuration file
- `sample_config_dict` - Configuration as a dictionary
- `single_reviewer_config` - Single reviewer configuration
- `no_reviewers_config` - Configuration with no reviewers
- `config_with_deprecated_field` - Config with deprecated branchPrefix

### Domain Model Fixtures
- `sample_reviewer_config` - ReviewerConfig instance
- `sample_task_metadata` - TaskMetadata instance
- `sample_prompt_template` - Prompt template content

### Mocking Fixtures
- `mock_subprocess` - Mocked subprocess module
- `mock_github_actions_helper` - Mocked GitHubActionsHelper

## Writing Good Tests

### Do's ✅

1. **Write descriptive test names** that explain what's being tested
2. **Add docstrings** explaining the test's purpose
3. **Follow Arrange-Act-Assert** structure
4. **Test edge cases** (empty inputs, boundary conditions, errors)
5. **Use parametrization** for similar test cases with different inputs
6. **Mock external dependencies** (git, GitHub API, filesystem I/O)
7. **Test error handling** (exceptions, invalid inputs)
8. **Keep tests focused** - one behavior per test
9. **Use fixtures** for common test data
10. **Verify meaningful behavior** - not just "doesn't crash"

### Don'ts ❌

1. **Don't test implementation details** - test behavior and outcomes
2. **Don't over-mock** - mock at system boundaries only
3. **Don't write tests without assertions**
4. **Don't test third-party libraries** - they have their own tests
5. **Don't test language features** - Python works
6. **Don't write getter/setter tests** - no business logic
7. **Don't create tests that duplicate the code** they're testing
8. **Don't make tests depend on each other** - each test is isolated
9. **Don't use sleep or timing** - use mocks instead
10. **Don't test multiple concepts** in one test

## Test Code Smells

Warning signs that a test needs improvement:

- **No Assertions** - Test executes code but doesn't verify anything
- **Magic Numbers** - Unexplained values (use constants with names)
- **Sleep/Wait** - Tests shouldn't depend on timing (use mocks)
- **Shared State** - Tests modify global state or depend on test order
- **Too Many Mocks** - More than 3-4 mocks suggests poor boundaries
- **Long Tests** - Over 20 lines suggests testing too much at once
- **Duplicate Logic** - Test reimplements the code it's testing
- **Vague Names** - Can't tell what's being tested from the name
- **No Docstrings** - Purpose of test isn't clear
- **Fixture Bloat** - Fixtures setting up data not used by the test

## Coverage Guidelines

### Current Coverage Status

As of December 2025:
- **Overall coverage: 85.03%** (exceeding 70% minimum threshold)
- **493 tests passing** (0 failures)
- **CI enforces minimum 70% coverage**

### What to Test

**High Priority (90%+ coverage):**
- Business logic (task management, reviewer assignment)
- Command orchestration (prepare, finalize, discover)
- Configuration validation
- Error handling paths

**Medium Priority (70%+ coverage):**
- Utilities and formatters
- GitHub API integrations
- Artifact operations

**Low Priority (may skip):**
- Simple getters/setters
- Third-party library wrappers
- CLI argument parsing (tested via E2E)
- Entry points (`__main__.py` - tested via E2E)

### Viewing Coverage Reports

```bash
# Generate HTML coverage report
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=html

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux

# View in terminal with missing lines
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing
```

Coverage reports are also available in GitHub Actions artifacts for every CI run.

## CI/CD Integration

### Automated Testing

Tests run automatically on:
- Every push to main branch
- Every pull request
- Via `.github/workflows/test.yml`

### Test Workflow

```yaml
# .github/workflows/test.yml
- name: Run unit and integration tests with coverage
  run: |
    PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ \
      --cov=src/claudestep \
      --cov-report=term-missing \
      --cov-report=html \
      --cov-fail-under=70
```

### PR Requirements

- All tests must pass
- Coverage must meet 70% minimum threshold
- New features require tests
- Bug fixes should include regression tests

## Example Tests

### Testing a Command

```python
# tests/integration/cli/commands/test_prepare.py
class TestCmdPrepare:
    """Tests for the prepare command"""

    def test_successful_preparation(
        self,
        mock_subprocess,
        sample_config_dict,
        sample_spec_file,
        mock_github_actions_helper
    ):
        """Should execute complete preparation workflow successfully"""
        # Arrange
        with patch('claudestep.cli.commands.prepare.detect_project_from_pr') as mock_detect:
            mock_detect.return_value = "test-project"
            # ... more setup ...

            # Act
            result = cmd_prepare(args)

            # Assert
            assert result == 0
            mock_github_actions_helper.write_output.assert_any_call(
                'task_id', '2'
            )
```

### Testing a Service

```python
# tests/unit/application/services/test_task_management.py
class TestFindNextAvailableTask:
    """Tests for find_next_available_task function"""

    def test_returns_first_unchecked_task(self, tmp_path):
        """Should return the first unchecked task from spec file"""
        # Arrange
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
        - [x] Completed task
        - [ ] Next task to do
        - [ ] Future task
        """)

        # Act
        result = find_next_available_task(str(spec_file))

        # Assert
        assert result.description == "Next task to do"
        assert result.index == 2
```

### Testing Error Handling

```python
def test_load_config_raises_error_when_file_missing(self):
    """Should raise FileNotFoundError when config file doesn't exist"""
    # Arrange
    nonexistent_path = "/path/to/missing/config.yml"

    # Act & Assert
    with pytest.raises(FileNotFoundError):
        load_config(nonexistent_path)
```

## Best Practices Summary

### Quick Checklist

Before committing a test, verify:

- [ ] Test name clearly describes what's being tested
- [ ] Test has a docstring explaining its purpose
- [ ] Test follows Arrange-Act-Assert structure
- [ ] Test has meaningful assertions (not just "doesn't crash")
- [ ] Test mocks external dependencies, not internal logic
- [ ] Test is focused (one concept/behavior)
- [ ] Test will fail if the code is broken
- [ ] Test won't break if internal implementation changes
- [ ] Test doesn't duplicate existing test coverage
- [ ] Test adds value (not testing language/framework/library)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [Test Coverage Improvement Plan](proposed/test-coverage-improvement-plan.md)
- [Testing Best Practices (Python Guide)](https://docs.python-guide.org/writing/tests/)

## Getting Help

If you have questions about testing:
1. Review existing tests in `tests/unit/` and `tests/integration/` for examples
2. Check the [Test Coverage Improvement Plan](proposed/test-coverage-improvement-plan.md) for detailed patterns
3. Ask in code review for guidance on testing approach
4. Run tests locally before pushing to catch issues early

## Running Different Test Types

```bash
# Run only unit tests (fast, isolated functions)
PYTHONPATH=src:scripts pytest tests/unit/ -v

# Run only integration tests (CLI commands, component orchestration)
PYTHONPATH=src:scripts pytest tests/integration/ -v

# Run both unit and integration tests (standard for CI)
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v

# Run e2e tests (slow, real GitHub API - manual only)
pytest tests/e2e/ -v -s
```
