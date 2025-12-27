# Test Coverage Improvement Plan

## Overview

This document outlines a comprehensive plan to improve test coverage in the ClaudeStep project by implementing Python testing best practices. The goal is to achieve robust, maintainable test coverage that enables confident refactoring and prevents regressions.

**⚠️ IMPORTANT**: All tests written for this project MUST follow the **Test Style Guide and Conventions** section below. Consistency in test style is critical for maintainability, readability, and long-term project health. Code reviews will enforce adherence to these standards.

## Recent Updates (December 2025)

### Architecture Modernization (December 27, 2025)
Following the completion of the architecture modernization (see `docs/completed/architecture-update.md`), this test plan has been updated to reflect:

1. **Layered Architecture** - Code reorganized into domain, infrastructure, application, and CLI layers
2. **Test Structure Reorganized** - Tests now mirror the `src/` structure in `tests/unit/`
3. **All 112 Tests Passing** - Fixed failing `test_prepare_summary.py` tests
4. **CI Workflow Added** - Unit tests run automatically on push and PR
5. **E2E Tests Updated** - Demo repository tests working with new architecture

### Branch Naming Simplification
Following the completion of the branch naming simplification refactoring (see `docs/completed/simplify-branch-naming.md`):

1. **New `pr_operations.py` module** - Centralized PR utilities with comprehensive tests (21 test cases) already implemented
2. **Simplified branch naming** - All tests use the standard format `claude-step-{project}-{index}`
3. **Removed `branchPrefix` configuration** - Tests verify this field is rejected with a helpful error message
4. **Simplified `project_detection.py`** - Uses centralized `parse_branch_name()` utility
5. **Centralized PR fetching** - Multiple modules now use shared `get_project_prs()` utility

These changes reduce code duplication and simplify the testing surface area.

## Current State

### Test Infrastructure ✅
- `pytest.ini` - Pytest configuration
- `.github/workflows/test.yml` - CI workflow for unit tests
- `pyproject.toml` - Package configuration with test dependencies
- Tests run on every push and PR to main branch
- **352 tests passing** with 0 failures (up from 333)

### Existing Tests (Organized by Layer)
**Domain Layer:**
- `tests/unit/domain/test_exceptions.py` - Custom exception classes (17 tests)
- `tests/unit/domain/test_models.py` - Domain models and formatters (37 tests)
- `tests/unit/domain/test_config.py` - Configuration loading and validation (26 tests)

**Infrastructure Layer:**
- `tests/unit/infrastructure/git/test_operations.py` - Git command wrappers (13 tests)
- `tests/unit/infrastructure/github/test_operations.py` - GitHub CLI and API operations (27 tests)
- `tests/unit/infrastructure/github/test_actions.py` - GitHub Actions helpers (17 tests)
- `tests/unit/infrastructure/filesystem/test_operations.py` - Filesystem utilities (27 tests)

**Application Layer:**
- `tests/unit/application/collectors/test_statistics.py` - Statistics models and collectors (44 tests)
- `tests/unit/application/formatters/test_table_formatter.py` - Table formatting utilities (19 tests)
- `tests/unit/application/services/test_pr_operations.py` - PR operations (21 tests)
- `tests/unit/application/services/test_task_management.py` - Task finding and marking (19 tests)
- `tests/unit/application/services/test_reviewer_management.py` - Reviewer capacity and assignment (16 tests)
- `tests/unit/application/services/test_project_detection.py` - Project detection from PRs and path resolution (17 tests)
- `tests/unit/application/services/test_artifact_operations.py` - Artifact operations API (31 tests)

**CLI Layer:**
- `tests/unit/cli/commands/test_prepare_summary.py` - PR summary command (9 tests)
- `tests/unit/cli/commands/test_prepare.py` - Preparation workflow command (19 tests)

**Integration:**
- Demo repository: `claude-step-demo/tests/integration/test_workflow_e2e.py` - End-to-end workflow

### Coverage Gaps
The following modules lack unit tests:

**CLI Layer:**
- `src/claudestep/cli/commands/discover.py` - Project discovery
- `src/claudestep/cli/commands/discover_ready.py` - Ready project discovery
- `src/claudestep/cli/commands/prepare.py` - Task preparation
- `src/claudestep/cli/commands/finalize.py` - Task finalization
- `src/claudestep/cli/commands/statistics.py` - Statistics reporting
- `src/claudestep/cli/commands/extract_cost.py` - Cost extraction
- `src/claudestep/cli/commands/add_cost_comment.py` - Cost comment posting
- `src/claudestep/cli/commands/notify_pr.py` - PR notifications

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

**IMPORTANT**: All tests in this project MUST follow the style guide and conventions documented below. Consistency across the test suite is critical for maintainability.

## Test Style Guide and Conventions

### Required Test Structure

All tests MUST follow this structure:

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
- ❌ `test_1` or `test_case_a` (meaningless)

**Fixture Names**: `<resource>_<state>` or `mock_<service>`
- ✅ `reviewer_config`, `sample_spec_file`, `mock_github_api`
- ❌ `data`, `setup`, `fixture1`

### Good Test Patterns (✅ WRITE THESE)

#### 1. Test Behavior, Not Implementation

```python
# ✅ GOOD - Tests the behavior/outcome
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

# ❌ BAD - Tests implementation details
def test_find_available_reviewer_calls_check_capacity_for_each(mock_check):
    """Don't test that internal functions are called - test outcomes"""
    reviewers = [ReviewerConfig(username="alice", maxOpenPRs=2)]

    with patch('module.check_reviewer_capacity') as mock_check:
        find_available_reviewer(reviewers)
        assert mock_check.call_count == 1  # Brittle - breaks if refactored
```

#### 2. Use Descriptive Assertions

```python
# ✅ GOOD - Clear what's being tested and why
def test_format_branch_name_creates_correct_format():
    """Should create branch name in format: claude-step-{project}-{index}"""
    result = format_branch_name("my-project", 5)

    assert result == "claude-step-my-project-5"
    assert result.startswith("claude-step-")
    assert result.endswith("-5")

# ❌ BAD - Unclear what's being verified
def test_format_branch_name():
    result = format_branch_name("my-project", 5)
    assert result  # What does this even verify?
    assert len(result) > 0  # Too vague
```

#### 3. Test Edge Cases and Boundaries

```python
# ✅ GOOD - Tests multiple boundary conditions
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

#### 4. Mock at System Boundaries

```python
# ✅ GOOD - Mock external services (GitHub, git, filesystem)
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
    args = mock_subprocess.run.call_args[0][0]
    assert "gh pr create" in " ".join(args)

# ❌ BAD - Mocking internal business logic
def test_prepare_command():
    with patch('module.find_next_task') as mock_find:  # Internal function
        with patch('module.check_capacity') as mock_check:  # Internal function
            # Too many mocks of internal logic = testing implementation
            cmd_prepare(args)
```

#### 5. Clear Test Data Setup

```python
# ✅ GOOD - Clear, minimal test data
def test_parse_branch_name_extracts_project_and_index():
    """Should parse standard branch format correctly"""
    # Arrange
    branch_name = "claude-step-my-project-42"

    # Act
    project, index = parse_branch_name(branch_name)

    # Assert
    assert project == "my-project"
    assert index == 42

# ❌ BAD - Overly complex or irrelevant test data
def test_parse_branch_name():
    branch = "claude-step-" + "-".join([
        "my", "project", "with", "lots", "of", "parts"
    ]) + "-" + str(int("42"))  # Why so complex?
    project, index = parse_branch_name(branch)
    assert project  # Assertion doesn't even verify the parsing!
```

### Bad Test Patterns (❌ AVOID THESE)

#### 1. Tests Without Assertions (Test Smoke)

```python
# ❌ BAD - No assertions, just checking it doesn't crash
def test_load_config():
    """This doesn't test anything meaningful"""
    config = load_config("config.yml")
    # No assertions - what are we verifying?

# ✅ GOOD - Actually verify the behavior
def test_load_config_parses_reviewers_correctly():
    """Should parse reviewer configuration from YAML"""
    config = load_config("test_config.yml")

    assert len(config.reviewers) == 2
    assert config.reviewers[0].username == "alice"
    assert config.reviewers[0].maxOpenPRs == 2
```

#### 2. Testing Language/Framework Features

```python
# ❌ BAD - Testing Python itself
def test_list_append():
    """Don't test that Python lists work"""
    my_list = []
    my_list.append(1)
    assert len(my_list) == 1

# ❌ BAD - Testing library behavior
def test_yaml_loads():
    """Don't test that PyYAML works"""
    result = yaml.safe_load("key: value")
    assert result == {"key": "value"}

# ✅ GOOD - Test YOUR code
def test_config_validates_required_fields():
    """Should raise error when required fields are missing"""
    with pytest.raises(ConfigValidationError, match="reviewers"):
        load_config("config_without_reviewers.yml")
```

#### 3. Over-Mocking (Too Many Mocks)

```python
# ❌ BAD - Mocking everything = testing nothing
def test_prepare_command():
    with patch('module.os') as mock_os:
        with patch('module.Path') as mock_path:
            with patch('module.yaml') as mock_yaml:
                with patch('module.find_task') as mock_find:
                    with patch('module.create_branch') as mock_branch:
                        # 5+ mocks = you're testing mocks, not code
                        cmd_prepare(args)
                        mock_branch.assert_called_once()

# ✅ GOOD - Mock boundaries, test logic
def test_prepare_command_creates_branch_with_correct_name(
    mock_git_client,
    mock_task_service,
    sample_config
):
    """Should create branch using format: claude-step-{project}-{index}"""
    # Arrange
    mock_task_service.find_next_task.return_value = Task(index=5, description="...")

    # Act
    cmd_prepare(args, mock_git_client, mock_task_service, sample_config)

    # Assert
    mock_git_client.create_branch.assert_called_once_with(
        "claude-step-my-project-5"
    )
```

#### 4. Testing Multiple Things (No Focus)

```python
# ❌ BAD - Testing too many things at once
def test_prepare_workflow():
    """Too broad - should be split into multiple tests"""
    result = cmd_prepare(args)
    assert result.exit_code == 0
    assert result.branch_created
    assert result.task_found
    assert result.reviewer_assigned
    assert result.prompt_generated
    # If any assertion fails, you don't know which part broke

# ✅ GOOD - One concept per test
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

#### 5. Brittle Tests (Coupled to Implementation)

```python
# ❌ BAD - Breaks when internal implementation changes
def test_find_task():
    with patch('module.open', mock_open(read_data="data")) as mock_file:
        find_next_task("spec.md")
        mock_file.assert_called_once_with("spec.md", "r")  # Brittle
        # Breaks if we change from 'r' to 'rt' or use Path.read_text()

# ✅ GOOD - Tests behavior, not how it's implemented
def test_find_next_task_returns_first_uncompleted(tmp_path):
    """Should return the first unchecked task from spec file"""
    # Arrange
    spec_file = tmp_path / "spec.md"
    spec_file.write_text("""
    - [x] Completed task
    - [ ] Next task to do
    - [ ] Future task
    """)

    # Act
    result = find_next_task(str(spec_file))

    # Assert
    assert result.description == "Next task to do"
    assert result.index == 2
```

### Low-Value Tests (❌ DON'T WRITE)

#### 1. Getter/Setter Tests

```python
# ❌ DON'T WRITE - Pointless, no business logic
def test_reviewer_config_sets_username():
    """Don't test trivial assignments"""
    config = ReviewerConfig(username="alice", maxOpenPRs=2)
    assert config.username == "alice"
    assert config.maxOpenPRs == 2
```

#### 2. Tests That Duplicate the Code

```python
# ❌ DON'T WRITE - Just reimplements the function
def test_calculate_completion():
    """This is just duplicating the implementation"""
    completed = 3
    total = 10
    result = calculate_completion_percentage(completed, total)
    assert result == (completed / total) * 100  # Same logic as function!

# ✅ WRITE THIS INSTEAD - Test edge cases and behavior
def test_calculate_completion_handles_zero_total():
    """Should return 0% when there are no tasks"""
    result = calculate_completion_percentage(0, 0)
    assert result == 0.0  # Not undefined or NaN
```

#### 3. Tests for Third-Party Code

```python
# ❌ DON'T WRITE - Testing PyYAML
def test_yaml_parsing():
    """Don't test libraries - they have their own tests"""
    data = yaml.safe_load("key: value")
    assert isinstance(data, dict)
```

### Test Code Smells (⚠️ WARNING SIGNS)

1. **No Assertions** - Test executes code but doesn't verify anything
2. **Magic Numbers** - Unexplained values (use constants with names)
3. **Sleep/Wait** - Tests shouldn't depend on timing (use mocks)
4. **Shared State** - Tests modify global state or depend on test order
5. **Too Many Mocks** - More than 3-4 mocks suggests poor boundaries
6. **Long Tests** - Over 20 lines suggests testing too much at once
7. **Duplicate Logic** - Test reimplements the code it's testing
8. **Vague Names** - Can't tell what's being tested from the name
9. **No Docstrings** - Purpose of test isn't clear
10. **Fixture Bloat** - Fixtures setting up data not used by the test

### Summary: Quick Checklist

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

## Implementation Plan

### Phase 1: Infrastructure & Core Utilities ✅ COMPLETE

- [x] **Set up test infrastructure** ✅
  - ✅ Add `pytest.ini` configuration file
  - ✅ Set up code coverage reporting with `pytest-cov` in CI
  - ✅ Tests run automatically in CI/CD (`.github/workflows/test.yml`)
  - ✅ Package structure supports testing (`pyproject.toml` configured)
  - Pending: Configure coverage thresholds in CI/CD
  - Pending: Document how to run tests in development

- [x] **Create common test fixtures** ✅ COMPLETE (December 27, 2025) (`tests/conftest.py`)
  - ✅ Fixture for temporary git repository (`mock_git_repo`)
  - ✅ Fixture for mock GitHub API responses (`mock_github_api`, `sample_pr_data`, `sample_pr_list`)
  - ✅ Fixture for sample project configurations (`sample_config_file`, `sample_config_dict`, `single_reviewer_config`, `no_reviewers_config`)
  - ✅ Fixture for spec.md files with various states (`sample_spec_file`, `empty_spec_file`, `all_completed_spec_file`)
  - ✅ Fixture for mocked GitHubActionsHelper (`mock_github_actions_helper`, `github_env_vars`)
  - ✅ Additional fixtures: `tmp_project_dir`, `mock_subprocess`, `config_with_deprecated_field`, `sample_reviewer_config`, `sample_task_metadata`, `sample_prompt_template`
  - **Technical Notes:**
    - All 112 existing tests still pass with new conftest.py in place
    - Fixtures follow pytest best practices with clear docstrings
    - Organized into logical categories: File System, Git, GitHub, Configuration, Domain Models, Test Data
    - Mock fixtures provide sensible defaults for common test scenarios
    - `mock_git_repo` creates actual git repositories for integration-style tests
    - Environment variable fixtures properly handle GitHub Actions context

- [x] **Test domain layer** ✅ COMPLETE (December 27, 2025) (`tests/unit/domain/`)
  - ✅ Test `exceptions.py` - Custom exception classes and inheritance (17 tests)
  - ✅ Test `models.py` - Domain model validation and serialization (37 tests)
  - ✅ Test `config.py` - Configuration loading, validation, and branchPrefix rejection (26 tests)
  - **Technical Notes:**
    - All 80 new domain layer tests pass (100% pass rate)
    - Total test count increased from 112 to 192 tests
    - Tests follow the style guide with Arrange-Act-Assert structure
    - Exception tests verify inheritance hierarchy and error messages
    - Model tests cover MarkdownFormatter (GitHub vs Slack), ReviewerCapacityResult, TeamMemberStats, ProjectStats, and StatisticsReport
    - Config tests verify YAML loading, template substitution, spec.md validation, and branchPrefix rejection with helpful error messages
    - All tests use descriptive names and docstrings explaining what they verify
    - Tests use tmp_path fixture for file system operations (no mocking of I/O)
    - Edge cases tested: empty files, missing files, invalid YAML, boundary conditions
    - Tests verify both success paths and error handling

### Phase 2: Infrastructure Layer ✅ COMPLETE

- [x] **Test pr_operations.py** ✅ COMPLETE (`tests/unit/application/services/test_pr_operations.py`)
  - 21 comprehensive tests covering branch name generation, parsing, and PR fetching
  - Branch name format validation (`claude-step-{project}-{index}`)
  - Complex project names with hyphens, invalid input handling
  - PR fetching with various states (open, merged, all)
  - Error handling for API failures

- [x] **Test git operations** ✅ COMPLETE (December 27, 2025) (`tests/unit/infrastructure/git/test_operations.py`)
  - 13 tests covering git command execution and error handling
  - Tests for `run_command()` - subprocess wrapper with output capture control
  - Tests for `run_git_command()` - git command execution with error handling
  - Error handling for git command failures with stderr capture
  - Command output processing (whitespace stripping, empty output)
  - **Technical Notes:**
    - Uses mocking to avoid actual git commands in tests
    - Tests verify proper command construction and argument passing
    - GitError exception tested with stderr message inclusion
    - All edge cases covered: empty output, multiple arguments, failure scenarios

- [x] **Test GitHub operations** ✅ COMPLETE (December 27, 2025) (`tests/unit/infrastructure/github/test_operations.py`)
  - 27 tests covering GitHub CLI and API operations
  - Tests for `run_gh_command()` - GitHub CLI command execution
  - Tests for `gh_api_call()` - REST API calls with JSON parsing
  - Tests for `download_artifact_json()` - artifact download and extraction from zip files
  - Tests for `ensure_label_exists()` - label creation with idempotency
  - Error handling for GitHub API failures, invalid JSON, missing artifacts
  - **Technical Notes:**
    - Comprehensive mocking of subprocess calls and zipfile operations
    - Tests verify proper error propagation and GitHubAPIError usage
    - Artifact download tests include cleanup verification
    - Label creation handles "already exists" gracefully
    - All edge cases covered: empty responses, malformed JSON, API errors

- [x] **Test GitHub Actions helpers** ✅ COMPLETE (December 27, 2025) (`tests/unit/infrastructure/github/test_actions.py`)
  - 17 tests covering GitHub Actions environment integration
  - Tests for `GitHubActionsHelper.__init__()` - environment variable initialization
  - Tests for `write_output()` - single-line and multi-line output with heredoc format
  - Tests for `write_step_summary()` - markdown summary writing
  - Tests for annotation methods - `set_error()`, `set_notice()`, `set_warning()`
  - Fallback behavior when environment variables not set
  - **Technical Notes:**
    - Uses tmp_path fixture for file I/O tests
    - Verifies heredoc format for multi-line values with unique delimiters
    - Tests confirm append behavior (not overwrite)
    - Annotation tests verify workflow command format
    - Tests work both with and without GitHub Actions environment

- [x] **Test filesystem operations** ✅ COMPLETE (December 27, 2025) (`tests/unit/infrastructure/filesystem/test_operations.py`)
  - 27 tests covering filesystem utilities
  - Tests for `read_file()` - file reading with error handling
  - Tests for `write_file()` - file writing with overwrite behavior
  - Tests for `file_exists()` - file existence checking (not directories)
  - Tests for `find_file()` - recursive file search with max_depth control
  - Unicode handling, newline preservation, symlink support
  - **Technical Notes:**
    - Uses tmp_path fixture for all file operations
    - Tests verify Unicode content handling (emojis, non-ASCII characters)
    - find_file() tests cover max_depth boundaries, hidden directory skipping
    - Tests confirm proper error handling for missing files
    - Edge cases tested: empty files, nested directories, permission errors

### Phase 3: Application Services Layer ✅ COMPLETE

- [x] **Test task_management.py** ✅ COMPLETE (`tests/unit/application/services/test_task_management.py`)
  - 19 tests covering task finding, marking, ID generation
  - Tests for in-progress tasks, completed tasks, edge cases

- [x] **Test statistics_collector.py** ✅ COMPLETE (`tests/unit/application/collectors/test_statistics.py`)
  - 44 tests covering progress bars, task counting, team member stats, project stats
  - Leaderboard functionality, cost extraction

- [x] **Test table_formatter.py** ✅ COMPLETE (`tests/unit/application/formatters/test_table_formatter.py`)
  - 19 tests covering visual width calculation, padding, emoji support, table formatting

- [x] **Test reviewer_management.py** ✅ COMPLETE (December 27, 2025) (`tests/unit/application/services/test_reviewer_management.py`)
  - 16 comprehensive tests covering `find_available_reviewer()` functionality
  - Tests capacity calculation with various PR states and boundary conditions
  - Tests edge cases (no reviewers, all at capacity, zero maxOpenPRs, over capacity)
  - Tests reviewer rotation logic (first available selected)
  - Tests artifact metadata parsing and PR detail storage
  - Tests handling of unknown reviewers and missing metadata
  - **Technical Notes:**
    - All 16 tests pass with comprehensive coverage of reviewer assignment logic
    - Tests mock `find_project_artifacts()` to avoid external dependencies
    - Helper method `_create_artifact_with_metadata()` simplifies test data creation
    - Tests verify both the selected reviewer and detailed ReviewerCapacityResult
    - Boundary conditions tested: exactly at capacity, one under, over capacity, zero max
    - Tests verify environment variable usage (GITHUB_REPOSITORY)
    - Tests confirm PR details stored correctly (pr_number, task_index, task_description)
    - All tests follow style guide with Arrange-Act-Assert structure and descriptive names

- [x] **Test project_detection.py** ✅ COMPLETE (December 27, 2025) (`tests/unit/application/services/test_project_detection.py`)
  - 17 comprehensive tests covering project detection and path resolution
  - Tests for `detect_project_from_pr()` - extracting project from PR branch using `parse_branch_name()`
  - Tests for `detect_project_paths()` - generating configuration, spec, and template paths
  - Tests error cases (missing branch name, invalid JSON, API failures, invalid branch formats)
  - Tests edge cases (complex project names, numeric names, single character names, minimum valid branches)
  - **Technical Notes:**
    - All 17 tests pass with comprehensive coverage of project detection logic
    - Tests mock `run_gh_command()` to avoid external GitHub CLI dependencies
    - Tests verify proper handling of GitHub API responses and JSON parsing
    - Tests confirm correct path generation with standard directory structure (claude-step/{project}/)
    - Branch name validation tests ensure only valid format (`claude-step-{project}-{index}`) is accepted
    - Tests verify graceful error handling (returns None on failures, not exceptions)
    - Path generation tests confirm correct file extensions (.yml, .md) and consistent base directory
    - All tests follow style guide with Arrange-Act-Assert structure and descriptive names

- [x] **Test artifact_operations.py** ✅ COMPLETE (December 27, 2025) (`tests/unit/application/services/test_artifact_operations.py`)
  - 31 comprehensive tests covering artifact operations API
  - Tests for `TaskMetadata.from_dict()` - parsing artifact JSON with datetime handling and default cost values
  - Tests for `ProjectArtifact.task_index` - metadata access and fallback to name parsing
  - Tests for `parse_task_index_from_name()` - extracting task index from artifact names
  - Tests for `find_project_artifacts()` - finding artifacts by project, PR state filtering, metadata download
  - Tests for `get_artifact_metadata()` - downloading and parsing individual artifacts
  - Tests for `find_in_progress_tasks()` - convenience wrapper for open PR task indices
  - Tests for `get_reviewer_assignments()` - mapping PR numbers to reviewers
  - **Technical Notes:**
    - All 31 tests pass (total test count increased from 302 to 333)
    - Tests use proper mocking strategy: mock at system boundaries (`gh_api_call`, `download_artifact_json`, `get_project_prs`)
    - Tests also mock internal functions (`_get_workflow_runs_for_branch`, `_get_artifacts_for_run`) where needed
    - Tests verify artifact deduplication logic (same artifact ID only appears once)
    - Tests verify filtering by project name prefix (`task-metadata-{project}-`)
    - Tests verify graceful error handling with warning messages printed to console
    - Tests confirm only successful workflow runs are processed (`conclusion == "success"`)
    - Documented regex limitation: `parse_task_index_from_name()` doesn't support project names with hyphens
    - Tests verify both "open" and "all" PR state handling paths
    - All tests follow style guide with Arrange-Act-Assert structure and descriptive names

### Phase 4: CLI Commands Layer

- [x] **Test prepare_summary.py** ✅ COMPLETE (`tests/unit/cli/commands/test_prepare_summary.py`)
  - 9 tests covering prompt template loading, variable substitution, output formatting
  - Tests for missing inputs, error handling, workflow URL construction

- [x] **Test prepare.py** ✅ COMPLETE (December 27, 2025) (`tests/unit/cli/commands/test_prepare.py`)
  - 19 comprehensive tests covering the full preparation workflow
  - Tests for successful preparation with all 6 steps (detect project, load config, check capacity, find task, create branch, prepare prompt)
  - Tests for merged PR detection and project name fallback
  - Tests for all error scenarios (no project, no reviewers, no capacity, no tasks, git errors, API errors)
  - Tests for branch creation using `format_branch_name()` with format `claude-step-{project}-{index}`
  - Tests for Claude prompt generation with spec content
  - Tests for all output variables being written correctly
  - Tests for label existence check and spec format validation
  - Tests for in-progress task handling
  - **Technical Notes:**
    - All 19 tests pass with comprehensive coverage of the prepare command
    - Tests mock all external dependencies (git, GitHub API, file system) at system boundaries
    - Tests verify proper error handling for FileNotFoundError, ConfigurationError, GitError, GitHubAPIError, and unexpected errors
    - Tests confirm graceful exits (return 0) when no capacity or no tasks available (not errors)
    - Tests verify step summary written with reviewer capacity information
    - All tests follow the style guide with Arrange-Act-Assert structure and descriptive names

- [ ] **Test finalize.py** (`tests/unit/cli/commands/test_finalize.py`)
  - Mock git and GitHub operations
  - Test commit creation, spec.md task marking, PR creation with template substitution
  - Test metadata artifact creation
  - Test handling no changes scenario and error recovery

- [ ] **Test discover.py** (`tests/unit/cli/commands/test_discover.py`)
  - Mock file system operations
  - Test finding all projects in claude-step/, filtering valid projects (must have spec.md)
  - Test output formatting (JSON), empty directory and invalid project structure handling

- [ ] **Test discover_ready.py** (`tests/unit/cli/commands/test_discover_ready.py`)
  - Mock GitHub API for PR queries
  - Test finding projects with available capacity, filtering by reviewer capacity
  - Test output formatting, all reviewers at capacity scenario, projects with no reviewers

- [ ] **Test statistics.py** (`tests/unit/cli/commands/test_statistics.py`)
  - Mock statistics collector
  - Test report generation workflow, output formatting (JSON, Slack)
  - Test GitHub Actions output writing, handling projects with no tasks, date range filtering

- [ ] **Test add_cost_comment.py** (`tests/unit/cli/commands/test_add_cost_comment.py`)
  - Mock GitHub API for comment posting
  - Test cost extraction and formatting, comment creation on PR
  - Test handling missing cost data and invalid PR numbers

- [ ] **Test extract_cost.py** (`tests/unit/cli/commands/test_extract_cost.py`)
  - Mock artifact reading
  - Test cost data extraction from metadata, parsing various cost formats
  - Test handling missing artifacts and output formatting

- [ ] **Test notify_pr.py** (`tests/unit/cli/commands/test_notify_pr.py`)
  - Mock Slack webhook calls
  - Test notification message formatting, webhook request construction
  - Test error handling (webhook failures) and optional notification (when webhook not configured)

### Phase 5: Integration & Quality

- [ ] **Improve existing tests**
  - Review existing tests for additional edge cases and parametrization opportunities
  - Consider adding more boundary condition tests
  - Add tests for error scenarios not currently covered

- [ ] **Add integration test coverage**
  - Test full prepare → finalize workflow (mocked)
  - Test error propagation through command chain
  - Test state management across commands
  - Test concurrent PR handling scenarios
  - Set up CI workflow to run e2e integration tests from demo repository

- [ ] **Set up coverage reporting**
  - Configure pytest-cov to track coverage (already in CI)
  - Add coverage report to CI/CD pipeline
  - Set minimum coverage threshold (start at 70%, target 80%+)
  - Generate HTML coverage reports for local development
  - Add coverage badge to README.md
  - Identify and document intentionally untested code

- [ ] **Add property-based testing** (optional, for critical paths)
  - Install `hypothesis` library
  - Add property tests for task ID generation
  - Add property tests for spec.md parsing
  - Add property tests for configuration validation

### Phase 6: Documentation & CI/CD

- [ ] **Document testing practices**
  - Create `docs/testing-guide.md` (can extract from style guide in this document)
  - Document how to run tests locally (`PYTHONPATH=src:scripts pytest tests/unit/ -v`)
  - Reference the "Test Style Guide and Conventions" section in this document
  - All new tests MUST follow the documented style guide for consistency
  - Document common fixtures and their usage (once conftest.py is created)
  - Enforce style guide in code reviews

- [x] **Set up CI/CD testing** ✅ MOSTLY COMPLETE
  - ✅ Add GitHub Actions workflow for running tests on PR (`.github/workflows/test.yml`)
  - ✅ Tests run on every push and PR to main branch
  - Pending: Add integration test workflow to run e2e tests from demo repository
  - Pending: Run tests on multiple Python versions (currently 3.11 only, add 3.12, 3.13)
  - Pending: Add test status badge to README.md
  - Pending: Configure PR merge requirements (tests must pass)
  - Pending: Add coverage reporting to PR comments

- [ ] **Performance testing** (optional)
  - Ensure test suite runs in under 10 seconds (currently ~0.7s in CI, excellent!)
  - Identify and optimize slow tests if any emerge
  - Consider splitting unit vs integration test runs as suite grows
  - Add `pytest-benchmark` for performance-critical code if needed

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
- ✅ ~~Test infrastructure and fixtures~~ - Partially complete (CI set up, need conftest.py)
- ✅ ~~pr_operations.py~~ - Complete (21 tests)
- Domain layer tests (config.py, models.py, exceptions.py)
- Infrastructure layer tests (git_operations.py, github_operations.py, github_actions.py, filesystem operations)
- reviewer_management.py (business logic)
- commands/prepare.py and commands/finalize.py (main workflows)

**Medium Priority** (implement second):
- ✅ ~~task_management.py~~ - Complete (19 tests)
- ✅ ~~statistics_collector.py~~ - Complete (44 tests)
- ✅ ~~table_formatter.py~~ - Complete (19 tests)
- project_detection.py (simplified after branch naming refactoring)
- artifact_operations.py
- commands/discover.py and commands/discover_ready.py
- ✅ ~~commands/prepare_summary.py~~ - Complete (9 tests)
- commands/statistics.py

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

**Current Progress**:
- ✅ Phase 1: 100% COMPLETE (test infrastructure, conftest.py fixtures, and domain layer tests all done)
- ✅ Phase 2: 100% COMPLETE (all infrastructure layer tests done - git, github, filesystem operations)
- ✅ Phase 3: 100% COMPLETE (all application layer tests done - task_management, statistics, table_formatter, reviewer_management, project_detection, artifact_operations)
- ✅ Phase 4: ~22% complete (prepare_summary and prepare done, need 7 more commands)
- Phase 5: Not started (integration tests and quality improvements)
- ✅ Phase 6: ~40% complete (CI set up, need documentation and enhancements)

**Remaining Effort**:
- ✅ **Phase 1**: COMPLETE (December 27, 2025)
- ✅ **Phase 2**: COMPLETE (December 27, 2025)
- ✅ **Phase 3**: COMPLETE (December 27, 2025)
- **Phase 4**: 4-5 days (8 remaining command modules)
- **Phase 5**: 2-3 days (integration tests, coverage reporting)
- **Phase 6**: 1 day (documentation, CI enhancements)

**Total Remaining: 7-9 days** (can be parallelized or spread over multiple contributors)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock guide](https://docs.python.org/3/library/unittest.mock.html)
- [Hypothesis documentation](https://hypothesis.readthedocs.io/)
- [Testing Best Practices (Python Guide)](https://docs.python-guide.org/writing/tests/)

## Next Steps

1. ~~Review and approve this proposal~~ ✅ Approved
2. ~~Set up initial testing infrastructure (Phase 1)~~ ✅ In Progress
3. Continue implementing tests following the prioritization order (see below)
4. Review and iterate based on learnings
5. Update this document with progress and adjustments

**Recommended Next Actions** (in priority order):
1. ~~Create `tests/conftest.py` with common fixtures (Phase 1)~~ ✅ COMPLETE (December 27, 2025)
2. ~~Add domain layer tests for config.py with branchPrefix rejection validation (Phase 1)~~ ✅ COMPLETE (December 27, 2025)
3. ~~Add infrastructure tests for git and github operations (Phase 2)~~ ✅ COMPLETE (December 27, 2025)
4. ~~Add application service tests for reviewer_management.py (Phase 3)~~ ✅ COMPLETE (December 27, 2025)
5. ~~Add application service tests for project_detection.py (Phase 3)~~ ✅ COMPLETE (December 27, 2025)
6. ~~Add application service tests for artifact_operations.py (Phase 3)~~ ✅ COMPLETE (December 27, 2025)
7. Add CLI command tests for prepare.py and finalize.py (Phase 4)
8. Set up CI workflow to run e2e integration tests from demo repository (Phase 5/6)

## Progress Summary

**Completed (December 2025)**:
- ✅ Architecture modernization with layered structure
- ✅ Test structure reorganized to mirror src/ layout
- ✅ CI workflow added for automated testing
- ✅ All 352 tests passing (0 failures, up from 112 initially)
- ✅ E2E tests updated and working
- ✅ Comprehensive tests for `pr_operations.py` (21 test cases)
- ✅ Comprehensive tests for `task_management.py` (19 test cases)
- ✅ Comprehensive tests for `statistics_collector.py` (44 test cases)
- ✅ Comprehensive tests for `table_formatter.py` (19 test cases)
- ✅ Comprehensive tests for `prepare_summary.py` (9 test cases)
- ✅ Comprehensive tests for `reviewer_management.py` (16 test cases) - December 27, 2025
- ✅ Comprehensive tests for `project_detection.py` (17 test cases) - December 27, 2025
- ✅ Comprehensive tests for `artifact_operations.py` (31 test cases) - December 27, 2025
- ✅ Comprehensive tests for `prepare.py` (19 test cases) - December 27, 2025
- ✅ **Common test fixtures** in `tests/conftest.py` (December 27, 2025)
  - 20+ reusable fixtures covering file system, git, GitHub, and configuration scenarios
  - All fixtures follow test style guide with clear docstrings and organized by category
- ✅ **Phase 1 Complete: Domain Layer Tests** (December 27, 2025)
  - `tests/unit/domain/test_exceptions.py` - Exception hierarchy and inheritance (17 tests)
  - `tests/unit/domain/test_models.py` - Domain models and formatters (37 tests)
  - `tests/unit/domain/test_config.py` - Configuration loading and validation (26 tests)
  - Total: 80 new tests, all following the test style guide with Arrange-Act-Assert structure
  - Tests verify both success paths and error handling with comprehensive edge case coverage
  - branchPrefix rejection validation included with helpful error messages
- ✅ **Phase 2 Complete: Infrastructure Layer Tests** (December 27, 2025)
  - `tests/unit/infrastructure/git/test_operations.py` - Git command wrappers (13 tests)
  - `tests/unit/infrastructure/github/test_operations.py` - GitHub CLI and API operations (27 tests)
  - `tests/unit/infrastructure/github/test_actions.py` - GitHub Actions helpers (17 tests)
  - `tests/unit/infrastructure/filesystem/test_operations.py` - Filesystem utilities (27 tests)
  - Total: 84 new tests added in Phase 2
  - All tests use mocking at system boundaries (subprocess, file I/O)
  - Comprehensive error handling and edge case coverage
  - Tests verify proper command construction, output processing, and error propagation
- ✅ **Phase 3 Complete: Application Services Layer Tests** (December 27, 2025)
  - `tests/unit/application/services/test_artifact_operations.py` - Artifact operations API (31 tests)
  - Total: 31 new tests added in Phase 3 (completing the layer)
  - Tests cover TaskMetadata parsing, ProjectArtifact models, artifact finding, and convenience functions
  - Tests verify deduplication logic, project filtering, metadata download, and error handling
  - Documented regex limitation for hyphenated project names in artifact name parsing
  - All tests use proper mocking at system boundaries and follow the style guide
