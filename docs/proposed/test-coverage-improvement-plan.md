# Test Coverage Improvement Plan

## Overview

This document outlines a comprehensive plan to improve test coverage in the ClaudeStep project by implementing Python testing best practices. The goal is to achieve robust, maintainable test coverage that enables confident refactoring and prevents regressions.

## Recent Updates (December 2025)

Following the completion of the branch naming simplification refactoring (see `docs/completed/simplify-branch-naming.md`), this test plan has been updated to reflect:

1. **New `pr_operations.py` module** - Centralized PR utilities with comprehensive tests (21 test cases) already implemented
2. **Simplified branch naming** - All tests should use the standard format `claude-step-{project}-{index}`
3. **Removed `branchPrefix` configuration** - Tests should verify this field is rejected with a helpful error message
4. **Simplified `project_detection.py`** - Uses centralized `parse_branch_name()` utility instead of multiple format parsing
5. **Centralized PR fetching** - Multiple modules now use shared `get_project_prs()` utility

These changes reduce code duplication and simplify the testing surface area.

## Current State

### Existing Tests
- `tests/test_statistics.py` - Statistics models and collectors
- `tests/test_table_formatter.py` - Table formatting utilities
- `tests/test_prepare_summary.py` - PR summary command
- `tests/test_task_management.py` - Task finding and marking
- `tests/test_pr_operations.py` - PR operations utilities (branch naming, parsing, PR fetching)
- `tests/integration/test_workflow_e2e.py` - End-to-end workflow

### Coverage Gaps
The following modules lack unit tests:
- Core commands (prepare, finalize, discover, etc.)
- GitHub and Git operations wrappers
- Configuration loading and validation
- Reviewer capacity management
- Project detection (simplified after branch naming refactoring)
- Custom exception hierarchy

## Testing Principles to Follow

Based on Python testing best practices:

1. **Test Isolation** - Each test is independent with clean state
2. **Fast Execution** - Mock external dependencies (GitHub API, git commands, file system where appropriate)
3. **One Concept Per Test** - Each test validates one specific behavior
4. **Descriptive Names** - Test names explain the scenario being tested
5. **Arrange-Act-Assert** - Clear test structure
6. **Parametrization** - Use pytest.mark.parametrize for similar test cases
7. **Proper Mocking** - Mock external services, not internal logic
8. **Edge Case Coverage** - Test boundary conditions, empty inputs, errors

## Implementation Plan

### Phase 1: Infrastructure & Core Utilities

- [ ] **Set up test infrastructure**
  - [ ] Add `pytest.ini` configuration file
  - [ ] Add `conftest.py` with common fixtures
  - [ ] Set up code coverage reporting with `pytest-cov`
  - [ ] Configure coverage thresholds in CI/CD
  - [ ] Document how to run tests in development

- [ ] **Create common test fixtures** (`tests/conftest.py`)
  - [ ] Fixture for temporary git repository
  - [ ] Fixture for mock GitHub API responses
  - [ ] Fixture for sample project configurations
  - [ ] Fixture for spec.md files with various states
  - [ ] Fixture for mocked GitHubActionsHelper

- [ ] **Test exception hierarchy** (`tests/test_exceptions.py`)
  - [ ] Test custom exception classes exist
  - [ ] Test exception inheritance structure
  - [ ] Test exception message formatting

### Phase 2: Operations Layer

- [x] **Test pr_operations.py** (`tests/test_pr_operations.py`) - ✅ COMPLETED
  - [x] Test `format_branch_name()` - branch name generation
  - [x] Test `parse_branch_name()` - extract project and index from branch
  - [x] Test `get_project_prs()` - fetch PRs by project using branch prefix
  - [x] Test branch name format validation (`claude-step-{project}-{index}`)
  - [x] Test complex project names with hyphens
  - [x] Test invalid input handling
  - [x] Test PR fetching with various states (open, merged, all)
  - [x] Test error handling for API failures
  - [x] Test roundtrip (format → parse → verify)
  - **Note**: 21 comprehensive tests already implemented during branch naming refactoring

- [ ] **Test git_operations.py** (`tests/test_git_operations.py`)
  - [ ] Mock subprocess calls to git commands
  - [ ] Test `create_branch()` - success and failure cases
  - [ ] Test `commit_changes()` - with and without files
  - [ ] Test `push_branch()` - success, failure, force push scenarios
  - [ ] Test `get_current_branch()` - various git states
  - [ ] Test error handling for git command failures
  - [ ] Test proper command construction (quoting, arguments)

- [ ] **Test github_operations.py** (`tests/test_github_operations.py`)
  - [ ] Mock GitHub CLI (`gh`) commands
  - [ ] Test `create_pull_request()` - various PR configurations
  - [ ] Test `get_open_prs()` - empty, single, multiple PRs
  - [ ] Test `close_pull_request()` - success and error cases
  - [ ] Test `add_pr_comment()` - comment posting
  - [ ] Test `get_pr_diff()` - diff retrieval
  - [ ] Test error handling for GitHub API failures
  - [ ] Test rate limiting scenarios
  - [ ] Test authentication errors

- [ ] **Test github_actions.py** (`tests/test_github_actions.py`)
  - [ ] Mock environment variables (GITHUB_OUTPUT, GITHUB_STEP_SUMMARY)
  - [ ] Test `write_output()` - output file writing
  - [ ] Test `write_summary()` - markdown summary formatting
  - [ ] Test `set_failed()` - error state handling
  - [ ] Test output sanitization (special characters, multiline)

### Phase 3: Business Logic Layer

- [ ] **Test config.py** (`tests/test_config.py`)
  - [ ] Test loading valid configuration.yml files
  - [ ] Test missing required fields (should fail gracefully)
  - [ ] Test invalid YAML syntax handling
  - [ ] Test default value application
  - [ ] Test reviewer configuration parsing
  - [ ] Test branchPrefix rejection (should fail with helpful error message)
  - [ ] Test configuration validation rules
  - [ ] Test edge cases (empty files, malformed data)

- [ ] **Test reviewer_management.py** (`tests/test_reviewer_management.py`)
  - [ ] Test `check_reviewer_capacity()` - at capacity, under capacity, over capacity
  - [ ] Test `find_available_reviewer()` - single reviewer, multiple reviewers
  - [ ] Test reviewer rotation logic
  - [ ] Test capacity calculation with various PR states
  - [ ] Test handling of zero maxOpenPRs
  - [ ] Test filtering by PR labels
  - [ ] Test edge cases (no reviewers configured, all at capacity)

- [ ] **Test project_detection.py** (`tests/test_project_detection.py`)
  - [ ] Test detecting project from environment variable
  - [ ] Test detecting project from PR branch name using `parse_branch_name()` utility
  - [ ] Test project path resolution
  - [ ] Test spec.md file discovery
  - [ ] Test configuration.yml file discovery
  - [ ] Test error cases (project not found, missing files, invalid branch names)
  - [ ] Test multiple projects in claude-step/ directory
  - [ ] Test simplified branch format parsing (`claude-step-{project}-{index}`)

### Phase 4: Command Layer

- [ ] **Test commands/prepare.py** (`tests/test_commands/test_prepare.py`)
  - [ ] Mock all external dependencies (git, GitHub, file system)
  - [ ] Test successful preparation workflow
  - [ ] Test reviewer capacity check integration
  - [ ] Test task discovery integration
  - [ ] Test branch creation using `format_branch_name()` utility
  - [ ] Test branch name format (`claude-step-{project}-{index}`)
  - [ ] Test prompt generation
  - [ ] Test output variable setting
  - [ ] Test failure scenarios (no capacity, no tasks, missing files)
  - [ ] Test skip_indices handling for in-progress tasks

- [ ] **Test commands/finalize.py** (`tests/test_commands/test_finalize.py`)
  - [ ] Mock git and GitHub operations
  - [ ] Test commit creation with changes
  - [ ] Test spec.md task marking
  - [ ] Test PR creation
  - [ ] Test PR template substitution
  - [ ] Test metadata artifact creation
  - [ ] Test handling no changes scenario
  - [ ] Test error recovery (commit succeeds but PR fails)

- [ ] **Test commands/discover.py** (`tests/test_commands/test_discover.py`)
  - [ ] Mock file system operations
  - [ ] Test finding all projects in claude-step/
  - [ ] Test filtering valid projects (must have spec.md)
  - [ ] Test output formatting (JSON)
  - [ ] Test empty directory handling
  - [ ] Test invalid project structure handling

- [ ] **Test commands/discover_ready.py** (`tests/test_commands/test_discover_ready.py`)
  - [ ] Mock GitHub API for PR queries
  - [ ] Test finding projects with available capacity
  - [ ] Test filtering by reviewer capacity
  - [ ] Test output formatting
  - [ ] Test all reviewers at capacity scenario
  - [ ] Test projects with no reviewers

- [ ] **Test commands/statistics.py** (`tests/test_commands/test_statistics.py`)
  - [ ] Mock statistics collector
  - [ ] Test report generation workflow
  - [ ] Test output formatting (JSON, Slack)
  - [ ] Test GitHub Actions output writing
  - [ ] Test handling projects with no tasks
  - [ ] Test date range filtering

- [ ] **Test commands/add_cost_comment.py** (`tests/test_commands/test_add_cost_comment.py`)
  - [ ] Mock GitHub API for comment posting
  - [ ] Test cost extraction and formatting
  - [ ] Test comment creation on PR
  - [ ] Test handling missing cost data
  - [ ] Test handling invalid PR numbers

- [ ] **Test commands/extract_cost.py** (`tests/test_commands/test_extract_cost.py`)
  - [ ] Mock artifact reading
  - [ ] Test cost data extraction from metadata
  - [ ] Test parsing various cost formats
  - [ ] Test handling missing artifacts
  - [ ] Test output formatting

- [ ] **Test commands/notify_pr.py** (`tests/test_commands/test_notify_pr.py`)
  - [ ] Mock Slack webhook calls
  - [ ] Test notification message formatting
  - [ ] Test webhook request construction
  - [ ] Test error handling (webhook failures)
  - [ ] Test optional notification (when webhook not configured)

### Phase 5: Integration & Quality

- [ ] **Improve existing tests**
  - [ ] Review test_statistics.py for additional edge cases
  - [ ] Review test_table_formatter.py for formatting edge cases
  - [ ] Review test_prepare_summary.py for template variations (currently has 5 pre-existing failures to investigate)
  - [ ] Review test_task_management.py for additional scenarios
  - [ ] Review test_pr_operations.py for additional PR fetching scenarios
  - [ ] Add parametrized tests where multiple similar cases exist

- [ ] **Add integration test coverage**
  - [ ] Test full prepare → finalize workflow (mocked)
  - [ ] Test error propagation through command chain
  - [ ] Test state management across commands
  - [ ] Test concurrent PR handling scenarios

- [ ] **Set up coverage reporting**
  - [ ] Configure pytest-cov to track coverage
  - [ ] Add coverage report to CI/CD pipeline
  - [ ] Set minimum coverage threshold (start at 70%, target 80%+)
  - [ ] Generate HTML coverage reports for local development
  - [ ] Identify and document intentionally untested code

- [ ] **Add property-based testing** (optional, for critical paths)
  - [ ] Install `hypothesis` library
  - [ ] Add property tests for task ID generation
  - [ ] Add property tests for spec.md parsing
  - [ ] Add property tests for configuration validation

### Phase 6: Documentation & CI/CD

- [ ] **Document testing practices**
  - [ ] Create `docs/testing-guide.md`
  - [ ] Document how to run tests locally
  - [ ] Document how to write new tests
  - [ ] Document mocking strategies
  - [ ] Document common fixtures and their usage
  - [ ] Add examples of well-written tests

- [ ] **Set up CI/CD testing**
  - [ ] Add GitHub Actions workflow for running tests on PR
  - [ ] Run tests on multiple Python versions (3.11, 3.12, 3.13)
  - [ ] Add test status badge to README.md
  - [ ] Configure PR merge requirements (tests must pass)
  - [ ] Add coverage reporting to PR comments

- [ ] **Performance testing** (optional)
  - [ ] Ensure test suite runs in under 10 seconds
  - [ ] Identify and optimize slow tests
  - [ ] Consider splitting unit vs integration test runs
  - [ ] Add `pytest-benchmark` for performance-critical code

## Success Criteria

- [ ] **Coverage Goals**
  - [ ] Overall coverage > 80%
  - [ ] All business logic modules > 90% coverage
  - [ ] All command modules tested
  - [ ] All operations modules tested

- [ ] **Quality Goals**
  - [ ] All tests are isolated and independent
  - [ ] Test suite runs in < 10 seconds
  - [ ] No flaky tests
  - [ ] Clear test names and documentation
  - [ ] Proper use of fixtures and parametrization

- [ ] **Process Goals**
  - [ ] Tests run automatically on every PR
  - [ ] Coverage reports visible in PR reviews
  - [ ] Testing guide documented and accessible
  - [ ] New code requires tests (enforced in PR reviews)

## Testing Tools & Dependencies

```bash
# Core testing framework
pytest>=7.0.0

# Coverage reporting
pytest-cov>=4.0.0

# Mocking (built-in to Python 3.3+)
# unittest.mock

# Property-based testing (optional)
hypothesis>=6.0.0

# Performance benchmarking (optional)
pytest-benchmark>=4.0.0
```

## Example Test Structure

```python
# tests/test_reviewer_management.py
import pytest
from unittest.mock import Mock, patch

from claudestep.reviewer_management import check_reviewer_capacity
from claudestep.models import ReviewerConfig


class TestCheckReviewerCapacity:
    """Tests for reviewer capacity checking"""

    @pytest.fixture
    def reviewer_config(self):
        """Fixture providing a sample reviewer configuration"""
        return ReviewerConfig(username="alice", maxOpenPRs=2)

    @pytest.fixture
    def mock_github_api(self):
        """Fixture providing mocked GitHub API"""
        with patch('claudestep.github_operations.get_open_prs') as mock:
            yield mock

    def test_reviewer_under_capacity(self, reviewer_config, mock_github_api):
        """Should return True when reviewer has capacity"""
        # Arrange
        mock_github_api.return_value = [{"number": 1}]  # 1 open PR

        # Act
        result = check_reviewer_capacity(reviewer_config)

        # Assert
        assert result is True
        mock_github_api.assert_called_once_with("alice", label="claude-step")

    def test_reviewer_at_capacity(self, reviewer_config, mock_github_api):
        """Should return False when reviewer is at capacity"""
        # Arrange
        mock_github_api.return_value = [{"number": 1}, {"number": 2}]  # 2 open PRs

        # Act
        result = check_reviewer_capacity(reviewer_config)

        # Assert
        assert result is False

    @pytest.mark.parametrize("open_pr_count,expected", [
        (0, True),   # Under capacity
        (1, True),   # Under capacity
        (2, False),  # At capacity
        (3, False),  # Over capacity
    ])
    def test_capacity_boundaries(self, reviewer_config, mock_github_api, open_pr_count, expected):
        """Should correctly handle various capacity levels"""
        # Arrange
        mock_github_api.return_value = [{"number": i} for i in range(open_pr_count)]

        # Act
        result = check_reviewer_capacity(reviewer_config)

        # Assert
        assert result == expected
```

## Migration Strategy

### Approach: Incremental Implementation

1. **Start with infrastructure** (Phase 1) to establish testing patterns
2. **Test operations layer** (Phase 2) to enable mocking in higher layers
3. **Test business logic** (Phase 3) with operations mocked
4. **Test commands** (Phase 4) with full dependency mocking
5. **Improve quality** (Phase 5) through iteration
6. **Document and automate** (Phase 6) for long-term sustainability

### Prioritization

**High Priority** (implement first):
- Test infrastructure and fixtures
- git_operations.py and github_operations.py (foundational)
- config.py (core functionality, including branchPrefix rejection validation)
- reviewer_management.py (business logic)
- commands/prepare.py and commands/finalize.py (main workflows)
- **Note**: pr_operations.py already has comprehensive tests ✅

**Medium Priority** (implement second):
- task_management.py (already has tests, but enhance)
- commands/discover.py and commands/discover_ready.py
- project_detection.py (simplified after branch naming refactoring - now uses parse_branch_name())
- statistics_collector.py (already has tests, but enhance)

**Low Priority** (implement as time allows):
- commands/notify_pr.py (nice-to-have feature)
- commands/add_cost_comment.py (optional feature)
- commands/extract_cost.py (utility)
- Property-based testing
- Performance benchmarking

## Risks & Mitigation

| Risk | Mitigation |
|------|------------|
| Tests become slow due to excessive mocking | Use fixtures efficiently, minimize I/O operations |
| Mocking makes tests brittle | Mock at system boundaries only, not internal functions |
| Coverage metrics without quality | Require code review of tests, enforce best practices |
| Tests don't catch real bugs | Combine unit tests with integration tests, use E2E tests for critical paths |
| Tests become outdated | Run tests in CI/CD, require tests for new features |

## Timeline Estimate

- **Phase 1**: 1-2 days (infrastructure setup)
- **Phase 2**: 1-2 days (operations layer - 2 modules remaining; pr_operations.py already complete ✅)
- **Phase 3**: 2-3 days (business logic - 3 modules, including updated config validation)
- **Phase 4**: 5-7 days (commands - 8 modules)
- **Phase 5**: 2-3 days (integration and quality improvements)
- **Phase 6**: 1-2 days (documentation and CI/CD)

**Total: 12-19 days** (can be parallelized or spread over multiple contributors)

**Note**: Recent branch naming refactoring has already delivered comprehensive tests for pr_operations.py, reducing overall timeline by 1 day.

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/)
- [Testing Best Practices (Python Guide)](https://docs.python-guide.org/writing/tests/)

## Next Steps

1. Review and approve this proposal
2. Set up initial testing infrastructure (Phase 1)
3. Begin implementing tests following the prioritization order
4. Review and iterate based on learnings
5. Update this document with progress and adjustments

**Progress Made**: The branch naming simplification refactoring (December 2025) has already delivered:
- ✅ Comprehensive tests for `pr_operations.py` (21 test cases)
- ✅ Centralized PR fetching utilities that reduce testing surface area
- ✅ Simplified branch naming logic that makes future tests easier to write
