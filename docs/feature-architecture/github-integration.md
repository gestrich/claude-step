# GitHub PR Service Integration

## Overview

ClaudeChain uses a layered architecture for GitHub PR operations, following the Service Layer pattern. PR data retrieval and parsing is centralized in `PRService`, providing type-safe domain models and hiding GitHub API details from business logic.

## Architecture

### Layer Separation

**Infrastructure Layer** (`infrastructure/github/operations.py`):
- Raw GitHub API calls via `gh` CLI
- Functions: `list_pull_requests()`, `list_open_pull_requests()`
- Returns: Raw JSON responses from GitHub API

**Domain Layer** (`domain/github_models.py`):
- Typed data models
- `GitHubPullRequest` dataclass with computed properties
- Parse-once principle: branch parsing and title cleaning happen in domain model

**Service Layer** (`services/core/pr_service.py`):
- `PRService` provides comprehensive PR querying API
- Coordinates infrastructure calls and domain model parsing
- Type-safe: all methods return `List[GitHubPullRequest]`, not dictionaries

**Application Services** (ReviewerService, TaskService, StatisticsService):
- Call through `PRService` for all PR operations
- Use domain model properties instead of manual parsing
- No direct GitHub API calls or branch name parsing

## PRService API

### Core Query Methods

**Get PRs for a project**:
```python
def get_project_prs(project: str, state: str = "all", label: str = "claudechain") -> List[GitHubPullRequest]
```

**Get open PRs for a project** (convenience):
```python
def get_open_prs_for_project(project: str, label: str = "claudechain") -> List[GitHubPullRequest]
```

**Get all PRs with label**:
```python
def get_all_prs(label: str = "claudechain", state: str = "all", limit: int = 500) -> List[GitHubPullRequest]
```

**Get PRs assigned to reviewer**:
```python
def get_open_prs_for_reviewer(username: str, label: str = "claudechain") -> List[GitHubPullRequest]
```

**Get reviewer PRs for specific project**:
```python
def get_reviewer_prs_for_project(username: str, project: str, label: str = "claudechain") -> List[GitHubPullRequest]
```

**Get reviewer PR count** (for capacity checking):
```python
def get_reviewer_pr_count(username: str, project: str, label: str = "claudechain") -> int
```

**Discover unique projects**:
```python
def get_unique_projects(label: str = "claudechain") -> Set[str]
```

### Branch Name Operations

**Format branch name**:
```python
@staticmethod
def format_branch_name(project: str, task_hash: str) -> str
    # Returns: "claude-chain-{project}-{task_hash}"
```

**Parse branch name**:
```python
@staticmethod
def parse_branch_name(branch: str) -> Tuple[str, Union[int, str], str]
    # Returns: (project_name, task_identifier, format_version)
    # format_version: "index" or "hash"
```

## GitHubPullRequest Domain Model

### Properties

All properties compute on access (no caching):

**`project_name: Optional[str]`**
- Parses branch name to extract project
- Returns `None` for invalid branch names

**`task_index: Optional[int]`**
- Extracts task index from branch name (legacy format)
- Returns `None` for hash-based branches or invalid formats

**`task_hash: Optional[str]`**
- Extracts task hash from branch name (new format)
- Returns `None` for index-based branches or invalid formats

**`task_description: str`**
- Returns PR title with "ClaudeChain: " prefix stripped if present
- Handles titles without prefix gracefully

**`is_claudechain_pr: bool`**
- Checks if branch name matches ClaudeChain pattern
- Returns `True` for valid ClaudeChain branches

### Example Usage

```python
# Get PRs via service
pr_service = PRService(repo="owner/repo")
prs = pr_service.get_open_prs_for_project("my-refactor")

# Use domain model properties
for pr in prs:
    print(f"PR #{pr.number}: {pr.task_description}")
    print(f"  Project: {pr.project_name}")
    print(f"  Task hash: {pr.task_hash}")
    print(f"  ClaudeChain PR: {pr.is_claudechain_pr}")
```

## Service Integration Pattern

### Before Refactoring (Anti-pattern)

```python
# ❌ Service makes direct GitHub API calls
class ReviewerService:
    def find_available_reviewer(self, reviewers, project):
        # Direct infrastructure call
        prs = list_open_pull_requests(label="claudechain", assignee=reviewer)

        # Manual branch parsing
        for pr in prs:
            match = re.match(r"claude-chain-([^-]+)-(\d+)", pr["headRefName"])
            project_name = match.group(1) if match else None

        # Manual title prefix stripping
        description = pr["title"]
        if description.startswith("ClaudeChain: "):
            description = description[len("ClaudeChain: "):]
```

### After Refactoring (Clean pattern)

```python
# ✅ Service uses PRService abstraction
class ReviewerService:
    def __init__(self, repo: str, pr_service: PRService, metadata_service: MetadataService):
        self.pr_service = pr_service
        # ...

    def find_available_reviewer(self, reviewers, project):
        # Use service API
        prs = self.pr_service.get_reviewer_prs_for_project(reviewer, project)

        # Use domain model properties
        for pr in prs:
            project_name = pr.project_name  # No parsing needed
            description = pr.task_description  # Prefix already stripped
```

## Dependency Injection

Services receive `PRService` via constructor:

```python
# CLI instantiates and passes PRService
def cmd_prepare(args, gh):
    pr_service = PRService(repo)
    task_service = TaskService(repo, pr_service, metadata_service)
    reviewer_service = ReviewerService(repo, pr_service, metadata_service)

    # Services use PRService for PR operations
    task = task_service.find_next_available_task(spec_content)
    reviewer = reviewer_service.find_available_reviewer(reviewers, project)
```

## Benefits

1. **Single Responsibility**: PRService owns all PR querying logic
2. **Type Safety**: Typed domain models instead of dictionaries
3. **Testability**: Services can mock PRService instead of infrastructure
4. **Maintainability**: Branch parsing in one place (domain model)
5. **Consistency**: All services use same PR data access pattern
6. **Reusability**: Domain model properties eliminate code duplication

## Testing

### Unit Testing PRService

```python
def test_get_open_prs_for_project():
    # Mock infrastructure layer
    mock_github = Mock()
    mock_github.list_pull_requests.return_value = [
        {"number": 1, "title": "ClaudeChain: Task 1", "headRefName": "claude-chain-auth-a3f2b891"}
    ]

    # Test service
    with patch('claudechain.services.core.pr_service.list_pull_requests', mock_github.list_pull_requests):
        pr_service = PRService(repo="owner/repo")
        prs = pr_service.get_open_prs_for_project("auth")

    # Assert typed domain models returned
    assert len(prs) == 1
    assert isinstance(prs[0], GitHubPullRequest)
    assert prs[0].project_name == "auth"
```

### Unit Testing Domain Model

```python
def test_github_pull_request_properties():
    pr = GitHubPullRequest(
        number=123,
        title="ClaudeChain: Add authentication",
        headRefName="claude-chain-auth-a3f2b891",
        baseRefName="main",
        state="OPEN",
        url="https://github.com/owner/repo/pull/123"
    )

    assert pr.project_name == "auth"
    assert pr.task_hash == "a3f2b891"
    assert pr.task_description == "Add authentication"
    assert pr.is_claudechain_pr is True
```

### Integration Testing Services

```python
def test_reviewer_service_uses_pr_service():
    # Mock PRService (not infrastructure)
    mock_pr_service = Mock()
    mock_pr_service.get_reviewer_prs_for_project.return_value = [
        GitHubPullRequest(number=1, title="Task 1", headRefName="claude-chain-auth-abc123")
    ]

    # Test ReviewerService
    reviewer_service = ReviewerService(repo="owner/repo", pr_service=mock_pr_service, metadata_service=mock_metadata)
    result = reviewer_service.find_available_reviewer(reviewers, "auth")

    # Verify PRService was used
    mock_pr_service.get_reviewer_prs_for_project.assert_called_once()
```

## Key Files

| File | Purpose |
|------|---------|
| `src/claudechain/services/core/pr_service.py` | PRService implementation |
| `src/claudechain/domain/github_models.py` | GitHubPullRequest domain model |
| `src/claudechain/infrastructure/github/operations.py` | Raw GitHub API calls |
| `tests/unit/services/core/test_pr_service.py` | PRService unit tests (96% coverage) |
| `tests/unit/domain/test_github_models.py` | Domain model tests (100% coverage) |
