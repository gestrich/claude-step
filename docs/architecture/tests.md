# Testing Architecture

This document describes the testing architecture and philosophy for the ClaudeStep project. It explains **why** we test the way we do and provides guidance on how to approach testing new features.

## Table of Contents

- [Testing Philosophy](#testing-philosophy)
- [Testing Principles](#testing-principles)
- [Test Architecture Overview](#test-architecture-overview)
- [Testing by Layer](#testing-by-layer)
- [What to Test vs What Not to Test](#what-to-test-vs-what-not-to-test)
- [Common Patterns](#common-patterns)
- [References](#references)

## Testing Philosophy

ClaudeStep's testing strategy is built on three core beliefs:

1. **Test behavior, not implementation** - Tests should verify what the code does, not how it does it
2. **Mock at boundaries, not internals** - Mock external systems (APIs, subprocess, filesystem), not internal logic
3. **Value over coverage** - We prioritize meaningful tests over arbitrary coverage metrics

Our goal is **85% code coverage** with **493 tests** that provide confidence in refactoring and catch real regressions, not tests that break when internal implementations change.

### Why This Matters

ClaudeStep is a GitHub Action that orchestrates complex workflows involving:
- Git operations (branching, commits, merges)
- GitHub API interactions (PRs, comments, labels)
- File I/O (reading specs, writing artifacts)
- Subprocess execution (gh CLI, git commands)

Poor test architecture would lead to:
- ❌ Tests that break on refactoring (testing implementation details)
- ❌ Over-mocked tests that don't catch real bugs (mocking too much)
- ❌ Slow, flaky tests (relying on timing or external services)
- ❌ Unmaintainable test code (duplicating production logic in tests)

Good test architecture gives us:
- ✅ Confidence in refactoring (tests verify behavior, not structure)
- ✅ Fast, reliable test suite (493 tests run in ~5 seconds)
- ✅ Clear test failures (when a test breaks, you know what's wrong)
- ✅ Easy to write new tests (clear patterns and fixtures)

## Testing Principles

### 1. Test Isolation and Independence

**Every test should be completely independent.** Tests must not:
- Rely on execution order
- Share mutable state
- Depend on previous test results
- Affect other tests when run in parallel

**Example:**
```python
# ✅ GOOD - Each test is self-contained
class TestTaskManagement:
    def test_find_first_task(self, tmp_path):
        """Should find the first unchecked task"""
        # Arrange - Create fresh test data for this test only
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
        - [ ] Task 1
        - [ ] Task 2
        """)

        # Act
        result = find_next_available_task(str(spec_file))

        # Assert
        assert result == (1, "Task 1")

    def test_find_task_after_completed(self, tmp_path):
        """Should skip completed tasks"""
        # Arrange - Fresh data, doesn't depend on previous test
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""
        - [x] Task 1
        - [ ] Task 2
        """)

        # Act
        result = find_next_available_task(str(spec_file))

        # Assert
        assert result == (2, "Task 2")

# ❌ BAD - Tests depend on shared state
shared_state = {"count": 0}

def test_increment():
    shared_state["count"] += 1
    assert shared_state["count"] == 1  # Breaks if tests run out of order

def test_increment_again():
    shared_state["count"] += 1
    assert shared_state["count"] == 2  # Depends on previous test
```

### 2. Mock at System Boundaries, Not Internal Logic

**Mock external systems, not your own code.** The boundary is where your code interacts with the outside world.

**System boundaries to mock:**
- Subprocess execution (`subprocess.run`)
- HTTP requests (GitHub API)
- File I/O (reading/writing files in production paths)
- Time (`datetime.now()`)
- Environment variables

**Internal logic NOT to mock:**
- Helper functions within your module
- Domain models
- Business logic
- Data transformations

**Example:**
```python
# ✅ GOOD - Mock at the boundary (subprocess)
def test_create_pull_request_success(mock_subprocess):
    """Should create PR via gh CLI"""
    # Arrange - Mock the external system
    mock_subprocess.run.return_value = Mock(
        returncode=0,
        stdout="https://github.com/owner/repo/pull/123"
    )

    # Act - Test the real business logic
    pr_url = create_pull_request(
        title="Test PR",
        body="Description",
        base="main"
    )

    # Assert - Verify behavior
    assert pr_url == "https://github.com/owner/repo/pull/123"
    mock_subprocess.run.assert_called_once()

# ❌ BAD - Over-mocking internal logic
def test_prepare_command(mock_find_task, mock_create_branch, mock_assign_reviewer):
    """Too many mocks - testing mocks, not real code"""
    with patch('module.find_next_task') as mock_find:
        with patch('module.create_branch') as mock_branch:
            with patch('module.assign_reviewer') as mock_assign:
                # You're just testing that mocks return what you told them to
                cmd_prepare(args)
```

### 3. Arrange-Act-Assert Pattern

**Every test should follow AAA structure:**

1. **Arrange** - Set up test data and mocks
2. **Act** - Execute the code under test
3. **Assert** - Verify the outcome

This makes tests easy to read and understand.

**Example:**
```python
def test_find_available_reviewer_returns_first_under_capacity(mock_github_api):
    """Should return the first reviewer with available capacity"""
    # Arrange - Set up test data
    reviewers = [
        ReviewerConfig(username="alice", maxOpenPRs=2),
        ReviewerConfig(username="bob", maxOpenPRs=2)
    ]
    mock_github_api.get_open_prs.side_effect = [
        [{"number": 1}, {"number": 2}],  # alice at capacity
        [{"number": 3}]  # bob under capacity
    ]

    # Act - Execute the function
    result = find_available_reviewer(reviewers, mock_github_api)

    # Assert - Verify behavior
    assert result.username == "bob"
    assert mock_github_api.get_open_prs.call_count == 2
```

### 4. One Concept Per Test

**Each test should verify ONE specific behavior.** If a test has multiple unrelated assertions, split it into separate tests.

**Why?** When a test fails, you should immediately know what broke. Multi-concept tests make debugging harder.

**Example:**
```python
# ✅ GOOD - Focused tests
class TestReviewerManagement:
    def test_find_reviewer_returns_first_available(self, mock_github_api):
        """Should return first reviewer with capacity"""
        # Test only the "find available reviewer" behavior
        ...

    def test_find_reviewer_returns_none_when_all_at_capacity(self, mock_github_api):
        """Should return None when all reviewers are at capacity"""
        # Test only the "no available reviewers" behavior
        ...

    def test_find_reviewer_skips_reviewers_at_capacity(self, mock_github_api):
        """Should skip reviewers who are at max PR capacity"""
        # Test only the "skip at-capacity reviewers" behavior
        ...

# ❌ BAD - Testing too many concepts
def test_reviewer_workflow(self, mock_github_api):
    """Tests everything - too broad"""
    # Find reviewer
    reviewer = find_available_reviewer(...)
    assert reviewer is not None

    # Assign PR
    assign_reviewer(pr, reviewer)
    assert pr.assigned == reviewer

    # Check capacity
    assert check_capacity(reviewer) == True

    # Update config
    update_config(reviewer)
    assert config_updated == True
    # If any assertion fails, which behavior broke?
```

## Test Architecture Overview

### Directory Structure

Tests mirror the `src/` directory structure, making it easy to find tests for any module:

```
tests/
├── conftest.py                           # Shared fixtures (imported automatically)
├── unit/
│   ├── domain/                           # Domain layer tests
│   │   ├── test_config.py               # Configuration parsing
│   │   ├── test_models.py               # Domain models
│   │   └── test_exceptions.py           # Custom exceptions
│   ├── infrastructure/                   # Infrastructure layer tests
│   │   ├── git/
│   │   │   └── test_operations.py       # Git operations (branch, commit)
│   │   ├── github/
│   │   │   ├── test_operations.py       # GitHub API (PRs, comments)
│   │   │   └── test_actions.py          # GitHub Actions helpers
│   │   └── filesystem/
│   │       └── test_operations.py       # File I/O operations
│   └── application/                      # Application layer tests
│       ├── collectors/
│       │   └── test_statistics.py       # Statistics collection
│       ├── formatters/
│       │   └── test_table_formatter.py  # Table formatting
│       └── services/
│           ├── test_pr_operations.py           # PR management
│           ├── test_task_management.py         # Task finding/completion
│           ├── test_reviewer_management.py     # Reviewer assignment
│           ├── test_project_detection.py       # Project detection
│           └── test_artifact_operations.py     # Artifact management
├── integration/                          # Integration tests
│   └── cli/                              # CLI command integration tests
│       └── commands/
│           ├── test_prepare.py           # prepare command
│           ├── test_finalize.py          # finalize command
│           ├── test_discover.py          # discover command
│           └── ...                       # Other CLI commands
├── e2e/                                  # End-to-end tests
└── builders/                             # Test helpers/factories
```

### Layer-Based Testing Strategy

ClaudeStep follows a **layered architecture**, and we test each layer differently:

```
┌─────────────────────────────────────────┐
│          CLI Layer                      │  ← Test command orchestration
│  (commands: prepare, finalize, etc.)    │     Mock everything below
├─────────────────────────────────────────┤
│       Application Layer                 │  ← Test business logic
│  (services: task mgmt, reviewer mgmt)   │     Mock infrastructure
├─────────────────────────────────────────┤
│     Infrastructure Layer                │  ← Test external integrations
│  (git, github, filesystem)              │     Mock external systems
├─────────────────────────────────────────┤
│         Domain Layer                    │  ← Test directly
│  (models, config, exceptions)           │     Minimal/no mocking
└─────────────────────────────────────────┘
```

**Key insight:** The **lower** the layer, the **less** you mock. Domain models are pure logic and need minimal mocking. CLI commands orchestrate everything and need maximum mocking.

### Fixture Organization and Reuse

**All shared fixtures live in `tests/conftest.py`**, organized by category:

- **File System Fixtures** - `tmp_path`, spec files, config files
- **Git Fixtures** - Mock git repos, subprocess mocks
- **GitHub Fixtures** - Mock GitHub API, PR data
- **Configuration Fixtures** - Sample configs, reviewer configs
- **Domain Model Fixtures** - Pre-built models for common scenarios

**Why conftest.py?** Pytest automatically discovers and imports fixtures from `conftest.py`, making them available to all tests without manual imports.

**Example fixture usage:**
```python
class TestPrepareCommand:
    def test_successful_preparation(
        self,
        tmp_path,                    # Built-in pytest fixture
        mock_subprocess,             # From conftest.py
        sample_config_dict,          # From conftest.py
        sample_spec_file,            # From conftest.py
        mock_github_actions_helper   # From conftest.py
    ):
        """Should execute complete preparation workflow"""
        # All fixtures are ready to use - no setup code needed
        ...
```

### Test Type Boundaries

**Unit tests** (`tests/unit/`) test a single function or class in isolation:
```python
def test_parse_task_index_from_branch():
    """Unit test - tests one function"""
    result = parse_branch_name("claude-step-my-project-5")
    assert result == ("my-project", 5)
```

**Integration tests** (`tests/integration/`) test how multiple components work together:
```python
def test_prepare_workflow_creates_pr_with_task_from_spec(
    mock_subprocess, tmp_path, mock_github_api
):
    """Integration test - tests prepare command end-to-end"""
    # Tests: find task → create branch → assign reviewer → create PR
    result = cmd_prepare(args)
    assert result == 0
```

**E2E tests** (`tests/e2e/`) test complete workflows with real GitHub API:
- Located in `tests/e2e/` with comprehensive README
- Test actual workflow runs using ClaudeStep on itself
- Create real PRs, branches, and workflow runs
- Slower and more expensive, run manually

## Testing by Layer

### Domain Layer (99% average coverage)

**Files:** `src/claudestep/domain/`
- `models.py` - Domain models (TaskMetadata, ReviewerConfig, etc.)
- `config.py` - Configuration parsing
- `exceptions.py` - Custom exceptions

**Testing approach:**
- ✅ **Direct testing** - Minimal mocking
- ✅ **Test business rules** - Validation logic, data transformations
- ✅ **Test edge cases** - Invalid inputs, boundary conditions

**What to mock:** Almost nothing. Domain models are pure logic.

**Example:**
```python
class TestMarkdownFormatter:
    """Test suite for MarkdownFormatter functionality"""

    def test_bold_formatting_for_github(self):
        """Should format text as bold using GitHub markdown syntax"""
        # Arrange - No mocking needed
        formatter = MarkdownFormatter(for_slack=False)

        # Act
        result = formatter.bold("important")

        # Assert
        assert result == "**important**"

    def test_bold_formatting_for_slack(self):
        """Should format text as bold using Slack mrkdwn syntax"""
        # Arrange
        formatter = MarkdownFormatter(for_slack=True)

        # Act
        result = formatter.bold("important")

        # Assert
        assert result == "*important*"
```

**Key principle:** Domain tests verify business logic without external dependencies.

### Infrastructure Layer (97% average coverage)

**Files:** `src/claudestep/infrastructure/`
- `git/operations.py` - Git operations (create branch, commit, checkout)
- `github/operations.py` - GitHub API (create PR, add comment, close PR)
- `github/actions.py` - GitHub Actions helpers (write output, set summary)
- `filesystem/operations.py` - File I/O (read files, write artifacts)

**Testing approach:**
- ✅ **Mock external systems** - subprocess, HTTP, file I/O
- ✅ **Test success and error paths** - What happens on success? On failure?
- ✅ **Verify system calls** - Check correct commands are executed

**What to mock:** Everything external to Python (subprocess, network, filesystem)

**Example:**
```python
class TestGitOperations:
    """Tests for git operations"""

    def test_create_branch_executes_git_checkout(self, mock_subprocess):
        """Should execute git checkout -b with branch name"""
        # Arrange - Mock the subprocess call
        mock_subprocess.run.return_value = Mock(returncode=0)

        # Act - Test our code that calls subprocess
        create_branch("feature-branch", base="main")

        # Assert - Verify correct command was executed
        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args[0][0]
        assert "git" in call_args
        assert "checkout" in call_args
        assert "-b" in call_args
        assert "feature-branch" in call_args

    def test_create_branch_raises_error_on_failure(self, mock_subprocess):
        """Should raise error when git command fails"""
        # Arrange - Mock a failed subprocess call
        mock_subprocess.run.return_value = Mock(
            returncode=1,
            stderr="fatal: branch already exists"
        )

        # Act & Assert - Verify error handling
        with pytest.raises(GitOperationError):
            create_branch("existing-branch")
```

**Key principle:** Infrastructure tests verify we call external systems correctly and handle their responses/errors.

### Application Layer (95% average coverage)

**Files:** `src/claudestep/application/services/`
- `task_management.py` - Find tasks, mark complete, generate task IDs
- `reviewer_management.py` - Find available reviewers, check capacity
- `pr_operations.py` - Create PRs, manage PR lifecycle
- `artifact_operations.py` - Write/read task artifacts
- `project_detection.py` - Detect project from PR branch

**Testing approach:**
- ✅ **Mock infrastructure** - Mock git, GitHub API, filesystem
- ✅ **Test business logic** - Reviewer selection, task finding algorithms
- ✅ **Test edge cases** - No reviewers available, all tasks complete, etc.

**What to mock:** Infrastructure layer (subprocess, GitHub API, file I/O)

**Example:**
```python
class TestFindAvailableReviewer:
    """Tests for find_available_reviewer function"""

    def test_returns_first_reviewer_under_capacity(self, mock_github_api):
        """Should return first reviewer with available PR capacity"""
        # Arrange - Mock infrastructure
        reviewers = [
            ReviewerConfig(username="alice", maxOpenPRs=2),
            ReviewerConfig(username="bob", maxOpenPRs=2)
        ]
        mock_github_api.get_open_prs.side_effect = [
            [{"number": 1}, {"number": 2}],  # alice at capacity (2/2)
            [{"number": 3}]  # bob under capacity (1/2)
        ]

        # Act - Test business logic
        result = find_available_reviewer(reviewers, mock_github_api)

        # Assert - Verify correct reviewer selected
        assert result.username == "bob"

    def test_returns_none_when_all_at_capacity(self, mock_github_api):
        """Should return None when no reviewers have capacity"""
        # Arrange
        reviewers = [
            ReviewerConfig(username="alice", maxOpenPRs=1),
            ReviewerConfig(username="bob", maxOpenPRs=1)
        ]
        mock_github_api.get_open_prs.side_effect = [
            [{"number": 1}],  # alice at capacity
            [{"number": 2}]   # bob at capacity
        ]

        # Act
        result = find_available_reviewer(reviewers, mock_github_api)

        # Assert
        assert result is None
```

**Key principle:** Application tests verify business logic while treating infrastructure as a black box.

### CLI Integration Tests (98% average coverage)

**Location:** `tests/integration/cli/commands/`

**Files under test:** `src/claudestep/cli/commands/`
- `prepare.py` - Prepare next task (find task, create branch, assign reviewer)
- `finalize.py` - Finalize completed task (mark complete, create PR)
- `discover.py` - Discover next task without creating PR
- `statistics.py` - Generate project statistics

**Testing approach:**
- ✅ **Mock everything below** - Mock application services, infrastructure
- ✅ **Test command orchestration** - Verify correct sequence of operations
- ✅ **Test output** - Verify GitHub Actions outputs are written correctly

**What to mock:** Everything except the command logic itself

**Note:** These tests are in `tests/integration/` (not `tests/unit/`) because they test how multiple components work together, even though external dependencies are mocked.

**Example:**
```python
# tests/integration/cli/commands/test_prepare.py
class TestCmdPrepare:
    """Tests for the prepare command"""

    def test_successful_preparation(
        self,
        tmp_path,
        mock_subprocess,
        sample_config_dict,
        sample_spec_file,
        mock_github_actions_helper
    ):
        """Should execute complete preparation workflow successfully"""
        # Arrange - Mock all dependencies
        with patch('claudestep.cli.commands.prepare.detect_project_from_pr') as mock_detect:
            with patch('claudestep.cli.commands.prepare.load_config') as mock_config:
                with patch('claudestep.cli.commands.prepare.find_next_available_task') as mock_find:
                    mock_detect.return_value = "test-project"
                    mock_config.return_value = sample_config_dict
                    mock_find.return_value = (2, "Implement feature X")

                    # Act - Execute the command
                    result = cmd_prepare(mock_github_actions_helper)

                    # Assert - Verify command succeeded and wrote outputs
                    assert result == 0
                    mock_github_actions_helper.write_output.assert_any_call('task_id', '2')
                    mock_github_actions_helper.write_output.assert_any_call(
                        'task_description', 'Implement feature X'
                    )

    def test_exits_when_no_tasks_available(
        self,
        mock_github_actions_helper
    ):
        """Should exit gracefully when all tasks are complete"""
        # Arrange
        with patch('claudestep.cli.commands.prepare.find_next_available_task') as mock_find:
            mock_find.return_value = None

            # Act
            result = cmd_prepare(mock_github_actions_helper)

            # Assert
            assert result == 0
            mock_github_actions_helper.set_notice.assert_called_with(
                "All tasks complete!"
            )
```

**Key principle:** CLI integration tests verify commands orchestrate lower layers correctly without re-testing those layers' logic.

## What to Test vs What Not to Test

### What to Test ✅

1. **Business logic**
   - Task finding algorithms
   - Reviewer selection logic
   - Task completion marking
   - Project detection from branch names

2. **Edge cases and boundaries**
   - Empty inputs (no tasks, no reviewers)
   - Boundary conditions (exactly at capacity)
   - Invalid inputs (malformed configs, missing files)

3. **Error handling**
   - File not found
   - API failures
   - Invalid configuration
   - Git operation failures

4. **Integration points**
   - Correct subprocess commands
   - Correct API calls
   - Correct file operations

5. **Data transformations**
   - Parsing spec files
   - Formatting output
   - Generating task IDs

### What NOT to Test ❌

1. **Language/framework features**
   ```python
   # ❌ Don't test Python itself
   def test_list_append():
       my_list = []
       my_list.append(1)
       assert len(my_list) == 1  # Python works, don't test it
   ```

2. **Third-party libraries**
   ```python
   # ❌ Don't test pytest
   def test_pytest_fixtures_work():
       assert True  # pytest works, don't test it

   # ❌ Don't test PyYAML
   def test_yaml_loads_correctly():
       result = yaml.safe_load("key: value")
       assert result == {"key": "value"}  # PyYAML works, don't test it
   ```

3. **Trivial getters/setters**
   ```python
   # ❌ Don't test simple properties
   def test_reviewer_username_getter():
       reviewer = ReviewerConfig(username="alice", maxOpenPRs=2)
       assert reviewer.username == "alice"  # No logic to test
   ```

4. **Implementation details**
   ```python
   # ❌ Don't test internal helper calls
   def test_prepare_calls_internal_helper():
       with patch('module._internal_helper') as mock:
           cmd_prepare()
           assert mock.called  # Breaks if refactored
   ```

5. **External service behavior**
   ```python
   # ❌ Don't test GitHub API behavior
   def test_github_returns_prs():
       # We mock GitHub API, we don't test how it works
       pass
   ```

## Common Patterns

### Using Fixtures from conftest.py

Fixtures in `conftest.py` are automatically available to all tests:

```python
# tests/conftest.py defines:
@pytest.fixture
def sample_spec_file(tmp_path):
    """Fixture providing a sample spec.md file"""
    spec_content = """# Project

    - [x] Task 1
    - [ ] Task 2
    """
    spec_file = tmp_path / "spec.md"
    spec_file.write_text(spec_content)
    return spec_file

# Your test can use it:
def test_find_task(sample_spec_file):
    """No import needed - pytest finds it automatically"""
    result = find_next_available_task(str(sample_spec_file))
    assert result == (2, "Task 2")
```

**Common fixtures:**
- `tmp_path` - Built-in pytest fixture for temporary directories
- `sample_spec_file` - Pre-built spec.md with tasks
- `sample_config_dict` - Pre-built configuration
- `mock_subprocess` - Mocked subprocess module
- `mock_github_api` - Mocked GitHub API client

### Using Test Data Builders

The `tests/builders/` directory provides **builder pattern helpers** for creating complex test data with fluent interfaces and sensible defaults. Builders make tests more readable and reduce duplication.

**Available Builders:**

- **`ConfigBuilder`** - Build configuration dictionaries
- **`SpecFileBuilder`** - Build spec.md file content
- **`PRDataBuilder`** - Build GitHub PR response data
- **`ArtifactBuilder`** - Build ProjectArtifact and TaskMetadata objects

**Example: ConfigBuilder**

```python
from tests.builders import ConfigBuilder

def test_reviewer_assignment():
    """Builder makes config creation clean and readable"""
    # ✅ GOOD - Using builder
    config = (ConfigBuilder()
              .with_reviewer("alice", max_prs=2)
              .with_reviewer("bob", max_prs=3)
              .with_project("my-project")
              .build())

    # vs ❌ Manual dictionary construction (harder to read)
    config = {
        "reviewers": [
            {"username": "alice", "maxOpenPRs": 2},
            {"username": "bob", "maxOpenPRs": 3}
        ],
        "project": "my-project"
    }
```

**Example: SpecFileBuilder**

```python
from tests.builders import SpecFileBuilder

def test_task_counting(tmp_path):
    """Builder makes spec file creation declarative"""
    # ✅ GOOD - Using builder
    spec_path = (SpecFileBuilder()
                 .with_title("My Project")
                 .add_completed_task("Task 1")
                 .add_completed_task("Task 2")
                 .add_task("Task 3")
                 .add_task("Task 4")
                 .write_to(tmp_path))

    result = count_tasks(str(spec_path))
    assert result == (4, 2)  # 4 total, 2 completed
```

**Example: PRDataBuilder**

```python
from tests.builders import PRDataBuilder

def test_pr_processing():
    """Builder handles GitHub API response structure"""
    # ✅ GOOD - Using builder
    pr = (PRDataBuilder()
          .with_number(123)
          .with_task(3, "Implement feature", "my-project")
          .with_user("alice")
          .as_merged()
          .build())

    assert pr["state"] == "closed"
    assert pr["merged"] == True
```

**When to Use Builders:**

- ✅ When creating the same type of test data repeatedly
- ✅ When test data structure is complex (nested dicts, multiple fields)
- ✅ When you want to emphasize *what* the test data represents, not *how* it's structured
- ✅ When you need sensible defaults with occasional overrides

**When NOT to Use Builders:**

- ❌ For simple, one-off test data (use inline dicts/strings)
- ❌ When testing edge cases of data structure itself
- ❌ When the builder would be more complex than the data

**Quick Helper Methods:**

Builders provide static methods for common cases:

```python
# Default configuration (alice, bob, charlie)
config = ConfigBuilder.default()

# Single reviewer
config = ConfigBuilder.single_reviewer("alice", max_prs=2)

# Spec with all tasks completed
spec_content = SpecFileBuilder.all_completed(num_tasks=5)

# Spec with mixed progress
spec_content = SpecFileBuilder.mixed_progress(completed=2, pending=3)

# Open PR
pr = PRDataBuilder.open_pr(number=123, task_index=3)

# Merged PR
pr = PRDataBuilder.merged_pr(number=456, task_index=1)
```

For more details, see the builder implementations in `tests/builders/`.

### Parametrized Tests for Boundary Conditions

Use `@pytest.mark.parametrize` to test multiple cases with the same logic:

```python
@pytest.mark.parametrize("open_prs,max_prs,expected", [
    (0, 2, True),   # Well under capacity
    (1, 2, True),   # Just under capacity
    (2, 2, False),  # Exactly at capacity
    (3, 2, False),  # Over capacity
    (0, 0, False),  # Edge case: zero max
])
def test_check_capacity_boundaries(open_prs, max_prs, expected, mock_github_api):
    """Should correctly handle all capacity boundary conditions"""
    # Arrange
    reviewer = ReviewerConfig(username="alice", maxOpenPRs=max_prs)
    mock_github_api.get_open_prs.return_value = [
        {"number": i} for i in range(open_prs)
    ]

    # Act
    result = check_reviewer_capacity(reviewer, mock_github_api)

    # Assert
    assert result == expected
```

**Benefits:**
- Tests all boundary conditions
- Easy to add new cases
- Clear failure messages (shows which parameters failed)

### Error Handling and Edge Cases

Always test both success and failure paths:

```python
class TestLoadConfig:
    def test_load_valid_config(self, sample_config_file):
        """Should load and parse valid configuration"""
        # Test success path
        config = load_config(str(sample_config_file))
        assert len(config.reviewers) == 3

    def test_load_missing_file(self):
        """Should raise FileNotFoundError when config missing"""
        # Test error path
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.yml")

    def test_load_invalid_yaml(self, tmp_path):
        """Should raise ValidationError for invalid YAML"""
        # Test validation error path
        bad_config = tmp_path / "bad.yml"
        bad_config.write_text("invalid: yaml: content:")

        with pytest.raises(ValidationError):
            load_config(str(bad_config))
```

### Testing Async Code (If Applicable)

ClaudeStep is currently synchronous, but if async code is added:

```python
import pytest

class TestAsyncOperations:
    @pytest.mark.asyncio
    async def test_async_function(self):
        """Should execute async operation correctly"""
        # Arrange
        mock_client = AsyncMock()

        # Act
        result = await async_fetch_data(mock_client)

        # Assert
        assert result is not None
```

## References

### Related Documentation

- **[Testing Guide](../testing-guide.md)** - Detailed style guide for writing tests (naming conventions, code smells, examples)
- **[Test Coverage Notes](../testing-coverage-notes.md)** - Coverage analysis and rationale for intentionally untested code
- **[Test Coverage Improvement Plan](../completed/test-coverage-improvement-plan.md)** - Historical implementation notes from building the test suite

### Code Examples

Real examples from the codebase:
- **Domain tests:** `tests/unit/domain/test_models.py` - Testing domain models
- **Infrastructure tests:** `tests/unit/infrastructure/git/test_operations.py` - Testing git operations
- **Application tests:** `tests/unit/application/services/test_task_management.py` - Testing business logic
- **CLI integration tests:** `tests/integration/cli/commands/test_prepare.py` - Testing command orchestration

### External Resources

- [pytest documentation](https://docs.pytest.org/) - Official pytest docs
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/) - Coverage plugin docs
- [unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html) - Python mocking guide
- [Testing Best Practices](https://docs.python-guide.org/writing/tests/) - Python testing guide

## Quick Reference

### Test Checklist

Before committing a test:

- [ ] Test name describes what's being tested
- [ ] Test has docstring explaining purpose
- [ ] Test follows Arrange-Act-Assert structure
- [ ] Test has meaningful assertions
- [ ] Test mocks at boundaries, not internals
- [ ] Test is focused (one concept)
- [ ] Test will fail if code is broken
- [ ] Test won't break on refactoring

### When to Mock

| Component | Mock? | Why |
|-----------|-------|-----|
| subprocess.run | ✅ Yes | External system |
| GitHub API calls | ✅ Yes | External system |
| File I/O (production paths) | ✅ Yes | External system |
| Your business logic | ❌ No | Internal logic |
| Domain models | ❌ No | Pure logic |
| Helper functions | ❌ No | Internal logic |

### Coverage Guidelines

| Priority | Target Coverage | Examples |
|----------|----------------|----------|
| High | 90%+ | Business logic, commands |
| Medium | 70%+ | Utilities, formatters |
| Low | Skip | Getters, entry points (E2E tested) |

**Current overall coverage: 85.03%** (exceeding 70% minimum)
