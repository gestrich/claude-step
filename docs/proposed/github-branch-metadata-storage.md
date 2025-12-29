# GitHub Branch-Based Metadata Storage

## Background

### ClaudeStep Overview

ClaudeStep is a GitHub Action that automates code refactoring by creating incremental pull requests for tasks defined in `spec.md` files. It runs Claude Code on individual steps, creating PRs one at a time, and automatically stages the next PR when one is merged.

Key features:
- Incremental automation with manageable review burden
- Reviewer capacity management (each reviewer has a `maxOpenPRs` limit)
- Progress tracking and team statistics
- Cost tracking per PR (AI model usage costs)

### Current State: Artifact-Based Storage (Legacy)

Currently, ClaudeStep stores PR metadata in GitHub artifacts (see `src/claudestep/application/services/artifact_operations.py`). Each PR generates an artifact named `task-metadata-{project}-{index}.json` containing flat cost data.

**Issues with Current Model:**
- Mixed concerns: PR info and cost data at same level
- Redundant `project` field in each task
- Flat cost structure doesn't track individual AI operations
- Unclear naming: "task" is ambiguous (spec.md task vs. AI task)

This data is used for:
- **Reviewer capacity checking**: Finding reviewers under their `maxOpenPRs` limit
- **Statistics reporting**: Weekly team stats and project progress (via `statistics` action)
- **Progress tracking**: Showing completion percentage across projects
- **Cost tracking**: Monitoring AI model usage costs

### Problems with Artifact Storage

1. **Limited retention** - GitHub artifacts expire after 90 days (default)
2. **Poor queryability** - Must iterate through all PRs, then all workflow runs, then download each artifact individually to build statistics
3. **Performance** - The current `find_project_artifacts()` function:
   - Queries all PRs with the `claudestep` label
   - Fetches up to 50 recent workflow runs
   - Downloads each artifact individually via GitHub API
   - Can take 30+ seconds for projects with 50+ PRs
4. **No cross-project queries** - Cannot easily answer "show all projects with activity in last 30 days" without scanning everything

### Migration Goal

Migrate to a branch-based storage system that:
- Keeps all dependencies within the GitHub ecosystem (no external services)
- Provides efficient querying capabilities for statistics and reporting
- Stores metadata as JSON files in a dedicated `claudestep-metadata` branch per repository
- Presents a REST-like API interface to Python clients (following ClaudeStep's layered architecture)
- Enables the `statistics` action to generate reports in <5 seconds instead of 30+ seconds

**Note:** Since ClaudeStep has not been released yet, no migration from artifacts is needed. The artifact upload/download code can remain in the codebase (unused) for potential future use, but all new implementations will use branch-based storage exclusively.

## Key Design Decisions

### Storage Strategy
- Use a dedicated branch (e.g., `claudestep-metadata`) per repository
- Store project data as JSON files, one file per project
- Each project JSON contains all associated PR metadata (matching current `TaskMetadata` schema)
- Avoid binary formats (e.g., SQLite) to keep data human-readable in version control
- Maintain same data structure as current artifacts to minimize migration impact

### API Design Goals
- REST-like interface from the Python client perspective
- Hide GitHub/JSON implementation details behind the API layer
- Follow ClaudeStep's layered architecture (domain → infrastructure → application → cli)
- Support operations needed by current codebase:
  - `find_project_artifacts()` - List all PRs for a project (replacing artifact-based version)
  - `find_in_progress_tasks()` - Get open PR task indices (for capacity checking)
  - `get_reviewer_assignments()` - Map PR numbers to reviewers
  - List projects modified/created/completed in last N days (for statistics action)
  - Store/retrieve TaskMetadata with all existing fields

### Integration Points

The new storage system will replace artifact usage in:

1. **`finalize` command** (`src/claudestep/cli/commands/finalize.py`)
   - Currently uploads artifacts after PR creation
   - Will write TaskMetadata to branch-based storage instead
   - Artifact upload code can be removed/commented out

2. **`statistics` command** (`src/claudestep/cli/commands/statistics.py`)
   - Currently uses `find_project_artifacts()` to collect data
   - Will read from branch-based storage for 6x faster queries

3. **Reviewer capacity checking** (used by `prepare` command)
   - Currently calls `find_in_progress_tasks()` and `get_reviewer_assignments()`
   - Will use equivalent functions from new metadata service

4. **Statistics collector** (`src/claudestep/application/collectors/statistics_collector.py`)
   - Currently builds `ProjectStats` and `TeamMemberStats` from artifacts
   - Will build from branch-based metadata instead

**Note:** The existing `artifact_operations.py` module will remain in the codebase but be unused. It can serve as reference for the data structure and potentially be used in the future if needed.

## Research & Exploration

### Phase 1: GitHub API Capabilities Research ✅ COMPLETED

**Status:** ✅ Completed on 2025-12-29

**Key Findings:**

#### 1. File Operations Without Checkout ✅

**Can we read/write files via GitHub API without cloning?**
- **YES** - GitHub's REST API allows creating, reading, updating, and deleting files without cloning
- Use Contents API: `GET/PUT /repos/:owner/:repo/contents/:path`
- Content is Base64 encoded in API requests/responses

**File size limits:**
- **100 MB maximum** for both GET and PUT operations (increased from 1 MB in 2022)
- Files >1 MB require custom media type header: `Accept: application/vnd.github.v3.raw`
- For our use case (JSON metadata files): **well within limits** (typical project JSON ~10-50 KB)

**Recommendation:** ✅ Use Contents API for direct file operations without checkout

**Sources:**
- [REST API endpoints for repository contents - GitHub Docs](https://docs.github.com/en/rest/repos/contents)
- [Increased file size limit - GitHub Changelog](https://github.blog/changelog/2022-05-03-increased-file-size-limit-when-retrieving-file-contents-via-rest-api/)

#### 2. Directory Listing ✅

**Can we list all files in a directory recursively?**
- **Contents API**: Limited to 1,000 files per directory
- **Git Tree API**: ✅ **RECOMMENDED** - Supports recursive listing with `?recursive=1`
  - Endpoint: `GET /repos/:owner/:repo/git/trees/:tree_sha?recursive=1`
  - Limit: 100,000 entries or 7 MB response size
  - Returns full file paths, SHAs, and metadata

**For our use case:**
- Typical `claudestep-metadata` branch will have 5-20 project JSON files
- Git Tree API is **perfect fit** - can list entire branch in one API call

**File metadata available:**
- File path, SHA, size, type (blob/tree)
- Commit history requires separate commits API call

**Recommendation:** ✅ Use Git Tree API for listing project files

**Sources:**
- [GitHub REST API Tree API tutorial](https://itsallbinary.com/github-rest-api-tree-api-to-get-remote-repo-files-list-metadata-recursively-programmatically-without-cloning-in-local/)
- [REST API endpoints for Git trees - GitHub Docs](https://developer.github.com/v3/git/trees//)

#### 3. Concurrency Handling ✅

**How does GitHub API handle concurrent writes?**
- ⚠️ **WARNING**: GitHub's Contents API explicitly states concurrent requests will conflict
- Must use Contents API **serially** for same file
- GitHub **does NOT** provide built-in distributed locking

**Optimistic locking via SHA:**
- ✅ **YES** - SHA-based conditional updates supported
- When updating a file, must provide current blob SHA
- If SHA doesn't match (file was modified), API returns error (409 Conflict)
- **Pattern:**
  1. GET file to retrieve current SHA
  2. Make changes
  3. PUT with retrieved SHA
  4. If conflict (409), retry from step 1

**For our use case:**
- Low concurrency risk: Only one workflow per PR (finalize command)
- Multiple projects can update in parallel (different files)
- Same project concurrent updates: **extremely rare** (would require manually triggering multiple workflows)

**Recommendation:**
- ✅ Implement SHA-based optimistic locking with retry logic (max 3 retries)
- Use existing `GitHubAPIError` exception for conflict handling
- Log conflicts for debugging (should be rare)

**Sources:**
- [API request SHA doesn't match Issue](https://github.com/gitbucket/gitbucket/issues/2761)
- [Gotchas with Git and GitHub API - Retool Blog](https://retool.com/blog/gotchas-git-github-api)

#### 4. Branch Operations ✅

**GitHub Actions checkout performance:**
- Default behavior: Shallow clone (fetch-depth=1) is **very fast**
- Switching branches: Use `actions/checkout` with `ref` parameter
- **No need to checkout metadata branch** - can read/write via API directly

**Can we read from one branch while checked out on another?**
- ✅ **YES** - GitHub API operations are independent of current checkout
- Can read/write to any branch via API without switching

**Recommendation:**
- ✅ **Use API-only approach** - Never checkout metadata branch
- Stay checked out on working branch (main or PR branch)
- All metadata operations via Contents API
- **Performance benefit:** Eliminates branch switching overhead entirely

**Sources:**
- [GitHub Actions Checkout documentation](https://github.com/actions/checkout)
- [Using Checkout Action in GitHub Actions Workflow](https://spacelift.io/blog/github-actions-checkout)

#### 5. Query Capabilities ✅

**Filter files by modification date:**
- ❌ **NOT directly supported** by Contents or Tree APIs
- Workaround: Use Commits API with `since` and `until` parameters
  - `GET /repos/:owner/:repo/commits?since=2025-01-01T00:00:00Z&path=projects/`
  - Can filter commits affecting specific paths
  - ISO 8601 timestamp format

**Get commit history for specific files:**
- ✅ **YES** - Use Commits API with `path` parameter
- Returns list of commits that modified the file
- Includes author, date, message, SHA

**For our use case:**
- Each project JSON has `last_updated` timestamp in the file itself
- Can read all project files and filter in-memory (fast with 5-20 files)
- **No need for commit history queries** - file contents have timestamps

**Recommendation:**
- ✅ Store `last_updated` in JSON files
- Filter by date in Python code (read all files, filter in-memory)
- Use Git Tree API to list all files, then read relevant ones
- **Trade-off:** Simple implementation, acceptable performance (<2 seconds for 20 files)

**Sources:**
- [REST API endpoints for commits - GitHub Docs](https://docs.github.com/en/rest/commits/commits)
- [Date range filtering in GitHub discussion](https://github.com/orgs/community/discussions/56097)

---

#### Rate Limits & Performance Considerations

**Primary Rate Limits (2025):**
- **GitHub Actions with GITHUB_TOKEN:** 1,000 requests/hour per repo (standard)
- **Enterprise Cloud:** 15,000 requests/hour per repo
- Our use case: ~2-5 API calls per workflow run (well within limits)

**Secondary Rate Limits:**
- Content creation: Max 80 requests/minute, 500 requests/hour
- No more than 100 concurrent requests
- Our use case: **Not a concern** (sequential operations)

**API Calls per Operation:**
- Save metadata: 2 calls (GET current file + PUT update)
- List projects: 1 call (Git Tree API)
- Get statistics: 1 call (Tree) + N calls (read each project file)
- **Total for statistics (20 projects):** ~21 API calls (<5 seconds)

**Sources:**
- [Rate limits for the REST API - GitHub Docs](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)
- [A Developer's Guide: Managing Rate Limits](https://www.lunar.dev/post/a-developers-guide-managing-rate-limits-for-the-github-api)

---

### Final Recommendation: API-Based Implementation ✅

**Approach:** Use GitHub Contents API exclusively, no branch checkout needed

**Key Benefits:**
1. ✅ **No branch switching overhead** - All operations via API
2. ✅ **Simple implementation** - Leverage existing `gh_api_call()` in codebase
3. ✅ **Well within rate limits** - <25 API calls for typical workflow
4. ✅ **Built-in optimistic locking** - SHA-based conflict detection
5. ✅ **100 MB file size limit** - More than sufficient for JSON metadata

**Implementation Plan:**
1. Use `GET /repos/:owner/:repo/contents/projects/{project}.json` to read metadata
2. Use `PUT /repos/:owner/:repo/contents/projects/{project}.json` to write (with SHA)
3. Use `GET /repos/:owner/:repo/git/trees/:branch_sha?recursive=1` to list all projects
4. Implement retry logic for 409 Conflict errors (SHA mismatch)
5. Store metadata on `claudestep-metadata` branch (create if not exists)

**Alternative Considered:** Git commands with branch checkout - **Rejected**
- Reason: Unnecessary complexity, slower, requires managing git state

---

**Phase 1 Completion Summary:**
- All key questions answered with concrete findings
- API-based approach validated and recommended
- Rate limits and performance verified as acceptable
- Ready to proceed to Phase 2: Data Structure & Schema Design

### Phase 2: Data Structure & Schema Design ✅ COMPLETED

**Status:** ✅ Completed on 2025-12-29

**Recent Update (2025-12-29):** Restructured data model with clearer naming and separation of concerns

**Tasks Completed:**

1. **✅ Cleaner Data Model Design**
   - Structure: `Project` → `Step` → `AITask`
   - Clear naming: "Step" = spec.md task (with PR info), "AITask" = AI operation
   - Removed redundant fields: No more `project` field in each step
   - Removed deprecated fields: Cost/model info exclusively in `ai_tasks`
   - Clean separation: PR properties vs. AI operation metrics

2. **✅ Typical 2-AITask Pattern**
   - Most steps have exactly 2 AI tasks:
     1. `PRCreation`: Claude Code generates the code
     2. `PRSummary`: AI writes the PR description
   - Complex steps may have additional tasks (e.g., `PRRefinement`)
   - Each AITask encapsulates: type, model, cost, tokens, duration

3. **✅ JSON Schema Defined**
   - Designed project JSON structure to store list of Step objects
   - Each step contains PR info + list of AI tasks
   - Final schema:
     ```json
     {
       "schema_version": "1.0",
       "project": "my-refactor",
       "last_updated": "2025-01-15T10:30:00Z",
       "steps": [
         {
           "step_index": 1,
           "step_description": "Refactor authentication module",
           "branch_name": "claude-step-my-refactor-1",
           "reviewer": "alice",
           "pr_number": 42,
           "pr_state": "merged",
           "created_at": "2025-01-10T14:22:00Z",
           "workflow_run_id": 123456,
           "ai_tasks": [
             {
               "type": "PRCreation",
               "model": "claude-sonnet-4",
               "cost_usd": 0.15,
               "created_at": "2025-01-10T14:22:00Z",
               "tokens_input": 8500,
               "tokens_output": 1200,
               "duration_seconds": 12.5
             },
             {
               "type": "PRSummary",
               "model": "claude-sonnet-4",
               "cost_usd": 0.02,
               "created_at": "2025-01-10T14:23:00Z",
               "tokens_input": 1200,
               "tokens_output": 150,
               "duration_seconds": 2.1
             }
           ]
         }
       ]
     }
     ```
   - Key changes: `tasks` → `steps`, `task_index` → `step_index`, `task_description` → `step_description`
   - Removed redundant `project` field from each step
   - Removed deprecated cost fields (`model`, `main_task_cost_usd`, `pr_summary_cost_usd`, `total_cost_usd`)
   - Added `schema_version` for future migrations
   - Added `pr_state` field (open, merged, closed) for filtering
   - Included `last_updated` timestamp for optimization
   - `ai_tasks` array tracks individual AI operations (typically 2 per step)
   - Each AI task encapsulates: type, model, cost, tokens, duration, timestamp

4. **✅ Index Strategy Decided: No Index**
   - **Decision**: Start without separate `index.json` file
   - **Rationale**:
     - Simpler implementation with fewer moving parts
     - Acceptable performance: Reading 5-20 project files takes <2 seconds
     - Atomic updates: Each project file updates independently
     - No synchronization complexity between index and project files
   - **Query Performance**:
     - List all projects: Single Git Tree API call (instant)
     - Get project metadata: 1 API call per project (~100ms each)
     - Filter by date: Read all files, filter in-memory (<2 seconds for 20 projects)
   - **Future**: Add optional index if 100+ projects become common

3. **✅ Directory Organization Finalized**
   - Final structure for `claudestep-metadata` branch:
     ```
     claudestep-metadata/
     ├── projects/
     │   ├── my-refactor.json
     │   ├── another-project.json
     │   └── legacy-cleanup.json
     └── README.md
     ```
   - **Flat structure**: Simple, efficient for typical 5-20 projects per repo
   - **File naming**: `{project-name}.json` (matches project directory name)
   - **No index file**: Keeps implementation simple

**Deliverables Created:**

1. **Schema Documentation** (`docs/metadata-schema.md`):
   - **Complete redesign** with clearer naming and structure
   - Data model: `Project` → `Step` → `AITask`
   - Removed legacy/deprecated fields for clean implementation
   - Documented typical 2-AITask pattern (PRCreation + PRSummary)
   - Field definitions for Project, Step, and AITask levels
   - Comprehensive examples showing simple and complex steps

2. **Domain Models** (`src/claudestep/domain/models.py`) - **TO BE REFACTORED**:
   - Current: `AITask`, `TaskMetadata`, `ProjectMetadata` (with legacy fields)
   - Planned refactoring:
     - `AITask`: Add `workflow_run_id` field (each AI operation runs in a specific workflow)
     - `TaskMetadata` → `Step`: Rename class, rename fields, remove deprecated fields, make most fields optional
     - `ProjectMetadata` → `Project`: Rename `tasks` → `steps`
   - Changes needed in Step:
     - `task_index` → `step_index`
     - `task_description` → `step_description`
     - Remove `project` field (redundant - already at project level)
     - Remove `workflow_run_id` field (moved to AITask)
     - Remove deprecated cost fields: `model`, `main_task_cost_usd`, `pr_summary_cost_usd`, `total_cost_usd`
     - Make most fields optional (except `step_index` and `step_description`) to support not-yet-started steps
   - Changes needed in AITask:
     - Add `workflow_run_id: int` field (required)
   - Changes needed in Project:
     - `tasks` → `steps`

3. **Branch README Template** (`docs/metadata-branch-README.md`):
   - User-facing documentation for the metadata branch
   - Explains purpose and structure
   - Includes manual inspection commands
   - Privacy and security notes
   - Ready to be placed in `claudestep-metadata` branch

**Technical Notes:**

- **Backward Compatibility**: The new `TaskMetadata` model is fully compatible with the existing artifact-based storage format, with the addition of the `pr_state` field (defaults to "open")
- **Serialization**: Both models use ISO 8601 timestamps with proper timezone handling
- **Testing**: All existing domain tests pass (80/80 tests)
- **Build Status**: ✅ All imports work correctly, models serialize/deserialize properly

**Key Decisions:**

1. **No Index File**: Keeping it simple - list files via Git Tree API, filter in-memory
2. **Flat Directory**: One `projects/` folder with all project JSON files
3. **Schema Version**: Starting with "1.0", future-proofed for migrations
4. **PR State Field**: New field added to track "open", "merged", "closed" states

**Next Steps:**

Ready to proceed to **Phase 3: Core API Layer Design**:
- Define abstract `MetadataStore` interface
- Create application service layer (`metadata_service.py`)
- Design API compatible with current `artifact_operations.py` functions

**Files Modified:**
- `src/claudestep/domain/models.py` - Added TaskMetadata and ProjectMetadata models

**Files Created:**
- `docs/metadata-schema.md` - Complete schema documentation
- `docs/metadata-branch-README.md` - User-facing README for metadata branch

## Implementation Phases

### Phase 3: Core API Layer Design

**Tasks:**

1. **Define Domain Models** (`src/claudestep/domain/models.py` or new file)
   - Reuse existing `TaskMetadata` from `artifact_operations.py`
   - Create `ProjectMetadata` model to wrap list of TaskMetadata
   - Add methods for JSON serialization/deserialization
   - Include schema version for future migrations

2. **Create Infrastructure Layer** (`src/claudestep/infrastructure/metadata/`)
   - New module: `src/claudestep/infrastructure/metadata/operations.py`
   - Define abstract interface:
     ```python
     class MetadataStore(ABC):
         @abstractmethod
         def save_task_metadata(project: str, metadata: TaskMetadata) -> None

         @abstractmethod
         def get_project_metadata(project: str) -> List[TaskMetadata]

         @abstractmethod
         def get_all_projects() -> List[str]

         @abstractmethod
         def get_projects_modified_since(date: datetime) -> List[str]
     ```
   - Git/GitHub-backed implementation in `github_metadata_store.py`

3. **Create Application Service** (`src/claudestep/application/services/`)
   - New file: `metadata_service.py`
   - Provides high-level operations that mirror current `artifact_operations.py`:
     ```python
     def find_project_metadata(repo: str, project: str, pr_state: str) -> List[TaskMetadata]
     def find_in_progress_tasks(repo: str, project: str) -> set[int]
     def get_reviewer_assignments(repo: str, project: str) -> dict[int, str]
     def save_pr_metadata(repo: str, project: str, metadata: TaskMetadata) -> None
     ```
   - Uses `MetadataStore` interface internally

**Expected Outcome:**
- Abstract API interface defined following ClaudeStep's layered architecture
- Clear separation: domain (models) → infrastructure (storage) → application (business logic)
- API compatible with current `artifact_operations.py` for easy migration

### Phase 4: GitHub Storage Backend Implementation

**Tasks:**

1. **Implement `GitHubMetadataStore`** (`src/claudestep/infrastructure/metadata/github_metadata_store.py`)
   - Implements `MetadataStore` abstract interface
   - Based on Phase 1 research, use either:
     - Direct GitHub API file operations via `gh_api_call()` (preferred), OR
     - Git commands via existing `src/claudestep/infrastructure/git/operations.py` if needed
   - Leverage existing infrastructure:
     - `src/claudestep/infrastructure/github/operations.py` - Has `gh_api_call()`, `run_gh_command()`
     - `src/claudestep/infrastructure/git/operations.py` - Has git command wrappers

2. **Branch Management**
   - Create `claudestep-metadata` branch on first write (if not exists)
   - Use existing git operations from `git/operations.py`
   - Handle branch creation gracefully (check existence first)

3. **File Operations**
   - Write project metadata to `projects/{project-name}.json`
   - Optional: Maintain index file at `index.json` for fast lookups
   - Use atomic writes to prevent corruption
   - Handle JSON serialization using TaskMetadata.from_dict() pattern

4. **Error Handling**
   - Leverage existing `GitHubAPIError` from `src/claudestep/domain/exceptions.py`
   - Implement retry logic for transient failures
   - Handle concurrency conflicts (based on Phase 1 findings)
   - Add detailed logging using Python's logging module

5. **Testing**
   - Follow `docs/architecture/testing-guide.md` conventions
   - Unit tests in `tests/unit/infrastructure/metadata/`
   - Mock `gh_api_call()` for isolation
   - Test error conditions and edge cases

**Expected Outcome:**
- Working GitHub-backed storage implementation
- Follows ClaudeStep's infrastructure patterns
- Comprehensive unit tests (70%+ coverage)

### Phase 5: Index Management (If Needed)

**Tasks:**

1. Based on Phase 2 decisions, implement index file management
2. Automatically update index when projects are modified
3. Implement index-based query optimizations
4. Handle index corruption/recovery

**Expected Outcome:** Efficient querying for time-based project lists without scanning all files.

### Phase 6: Integration with Existing ClaudeStep Code

**Tasks:**

1. **Update `finalize` Command** (`src/claudestep/cli/commands/finalize.py`)
   - Replace artifact upload with branch-based metadata write
   - Call `metadata_service.save_pr_metadata()`
   - Remove or comment out artifact upload code (keep for reference)
   - Update integration tests in `tests/integration/cli/commands/test_finalize.py`

2. **Update `statistics` Command** (`src/claudestep/cli/commands/statistics.py`)
   - Replace `find_project_artifacts()` calls with `metadata_service.find_project_metadata()`
   - Verify `StatisticsReport` works with new data source
   - Test performance improvement (should be <5 seconds vs. 30+ seconds)
   - Update integration tests in `tests/integration/cli/commands/test_statistics.py`

3. **Update `prepare` Command** (`src/claudestep/cli/commands/prepare.py`)
   - Update reviewer capacity checking to use new metadata service
   - Replace `find_in_progress_tasks()` and `get_reviewer_assignments()` calls
   - Verify capacity limits work correctly
   - Update integration tests in `tests/integration/cli/commands/test_prepare.py`

4. **Update Statistics Collector** (`src/claudestep/application/collectors/statistics_collector.py`)
   - Modify to work with branch-based metadata
   - Ensure `ProjectStats` and `TeamMemberStats` build correctly
   - Test cross-project queries (last 30 days, etc.)

5. **Clean Up Artifact Code**
   - Keep `artifact_operations.py` in codebase but mark functions as unused
   - Add comments explaining these are legacy/unused but kept for reference
   - Remove imports of artifact operations from active code paths

**Expected Outcome:**
- All ClaudeStep commands use new branch-based storage exclusively
- Artifact code remains in codebase but unused
- Integration tests pass with new backend
- Performance improvements measurable in statistics action

### Phase 7: Testing & Validation

Follow ClaudeStep's testing conventions from `docs/architecture/testing-guide.md`.

**Testing Strategy:**

1. **Unit Tests** (90%+ coverage target)
   - **Domain Layer** (`tests/unit/domain/`)
     - Test `ProjectMetadata` model serialization/deserialization
     - Test schema versioning
   - **Infrastructure Layer** (`tests/unit/infrastructure/metadata/`)
     - Test `GitHubMetadataStore` with mocked `gh_api_call()`
     - Test branch creation, file operations
     - Test error handling (API failures, network errors, conflicts)
     - Mock at system boundaries only
   - **Application Layer** (`tests/unit/application/services/`)
     - Test `metadata_service.py` functions
     - Mock `MetadataStore` interface
     - Test business logic (filtering, aggregation)

2. **Integration Tests** (70%+ coverage target)
   - **CLI Commands** (`tests/integration/cli/commands/`)
     - Test `prepare`, `finalize`, `statistics` commands end-to-end
     - Use temporary directories and mock GitHub API
     - Verify outputs match expected formats
     - Test metadata storage and retrieval operations

3. **End-to-End Tests** (`tests/e2e/`)
   - Run full ClaudeStep workflow with new storage
   - Create test projects in `claude-step/test-*`
   - Verify metadata persists across PR lifecycle
   - Test with real GitHub repository (recursive pattern)
   - Clean up test resources automatically

4. **Performance Testing**
   - Benchmark statistics collection (target: <5 seconds vs. 30+ seconds)
   - Test with mock projects having 50+, 100+ PRs
   - Measure GitHub Actions workflow runtime impact
   - Document performance improvements

**Test Conventions:**
- Follow Arrange-Act-Assert pattern
- Use descriptive test names: `test_<what>_<when>_<condition>`
- Add docstrings explaining test purpose
- Use pytest parametrization for boundary conditions
- Mock external dependencies (GitHub API, git commands)
- One concept per test

**CI Requirements:**
- All tests must pass (493+ tests expected)
- Minimum 70% coverage (aim for 85%+)
- No breaking changes to existing tests
- Performance regression tests pass

**Success Criteria:**
- All 493+ existing tests pass with new backend
- New code has 85%+ test coverage
- Statistics action completes in <5 seconds (6x improvement)
- Clean separation of concerns following layered architecture
- E2E tests pass on real GitHub repository
- Artifact code preserved but clearly marked as unused

## Architecture Alignment

### ClaudeStep's Layered Architecture

This implementation follows ClaudeStep's established architecture pattern:

```
┌─────────────────────────────────────────┐
│ CLI Layer (commands/)                   │
│  - finalize, prepare, statistics        │
│  - Calls application services           │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Application Layer (services/)           │
│  - metadata_service.py                  │
│  - Orchestrates business logic          │
│  - Uses infrastructure abstractions     │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Infrastructure Layer (infrastructure/)  │
│  - metadata/github_metadata_store.py    │
│  - Implements MetadataStore interface   │
│  - Uses gh_api_call(), git operations   │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ Domain Layer (domain/)                  │
│  - TaskMetadata, ProjectMetadata models │
│  - GitHubAPIError exception             │
│  - No external dependencies             │
└─────────────────────────────────────────┘
```

### Python-First Approach

Following ClaudeStep's convention:
- **Business logic in Python** - All metadata operations in Python modules
- **Minimal YAML** - GitHub Action files just invoke Python commands
- **Command dispatcher** - New `migrate-metadata` command added to `__main__.py`
- **Testable** - Unit tests for all layers, integration tests for commands

### Key Files Modified

- `src/claudestep/domain/models.py` - Add ProjectMetadata model
- `src/claudestep/infrastructure/metadata/` - New metadata storage infrastructure
- `src/claudestep/application/services/metadata_service.py` - New service layer
- `src/claudestep/cli/commands/finalize.py` - Use new storage
- `src/claudestep/cli/commands/statistics.py` - Use new storage
- `src/claudestep/cli/commands/prepare.py` - Use new storage for capacity
- `src/claudestep/application/services/artifact_operations.py` - Backward compat fallback

## Open Questions & Considerations

### GitHub API Capabilities (Phase 1 Research)
- Can we read/write files without cloning? (via GitHub REST API or `gh api`)
- How to handle concurrent writes? (optimistic locking via SHA, retry logic)
- Rate limits for API calls? (5000/hour for authenticated, may need caching)
- Best approach: Direct API calls vs. git commands?

### Scalability
- What happens when a project JSON file becomes very large (hundreds of PRs)?
  - **Typical ClaudeStep project**: 20-50 tasks
  - **Large project**: 100-200 tasks
  - **Mitigation**: Archive completed PRs to separate files if needed
- Should we implement pagination or file splitting?
- GitHub API rate limits - do we need request throttling or caching?

### Data Consistency
- How to ensure atomic updates across multiple files (project + index)?
  - **Option 1**: Single commit updates both files
  - **Option 2**: Rebuild index on read if stale
  - **Recommendation**: Keep it simple - single project file, optional index
- What's the recovery strategy if a write partially fails?
  - **Approach**: Use git commits as transaction log, retry on next run

### User Experience
- Should the metadata branch be visible to users?
  - **Yes** - Transparency is good; users can inspect/debug
  - Add `.nojekyll` to prevent GitHub Pages from processing it
- Do we need tools for users to inspect/modify metadata manually?
  - Nice-to-have: `claudestep metadata show <project>` command
  - Can always use `gh api` or clone the metadata branch
- Documentation updates needed:
  - Mention metadata branch in README
  - Explain that users can inspect `claudestep-metadata` branch for debugging
  - Note that artifact upload code exists but is unused

### Security & Privacy
- Are there any security implications of storing metadata in a public branch?
  - **Metadata stored**: PR numbers, task descriptions, reviewer usernames, costs
  - **Not stored**: API keys, tokens, or sensitive code
  - **Risk**: Low - metadata already visible in PRs and artifacts
- Should we support private metadata branches?
  - **Default**: Use same visibility as main repo
  - **Future**: Add configuration option if users request it
- Do we need to sanitize any data before storing?
  - **Task descriptions** come from spec.md (user-controlled)
  - **No injection risk** - just JSON storage, no code execution

### Performance & Optimization
- Target: 6x improvement (30 seconds → 5 seconds for statistics)
- How to achieve:
  1. Single API call per project (not per PR)
  2. Optional: Cache index in memory during GitHub Actions run
  3. Parallel fetching for multiple projects
- Measure before/after with real repositories

## Summary

This migration from artifact-based to branch-based metadata storage addresses critical limitations in ClaudeStep's current architecture:

**Problems Solved:**
1. ✅ Eliminates artifact retention limits (90-day expiration)
2. ✅ Dramatically improves query performance (6x faster statistics)
3. ✅ Enables efficient cross-project queries
4. ✅ Stays within GitHub ecosystem (no external dependencies)
5. ✅ Maintains human-readable metadata (JSON in version control)

**Key Benefits:**
- **Performance**: Statistics generation <5 seconds vs. 30+ seconds
- **Scalability**: Single API call per project instead of per PR
- **Reliability**: No data loss from artifact expiration
- **Transparency**: Users can inspect metadata branch
- **Maintainability**: Follows ClaudeStep's layered architecture

**Implementation Approach:**
- 7 phases: Research (1-2) → Implementation (3-5) → Integration (6) → Testing (7)
- No migration needed (app not yet released)
- Artifact code kept in codebase but unused
- Comprehensive testing (unit, integration, e2e)
- Follows ClaudeStep's Python-first, layered architecture

**Next Steps:**
1. Begin with Phase 1: GitHub API research to determine optimal implementation approach
2. Validate data schema design in Phase 2
3. Implement in phases 3-5, following ClaudeStep's architecture patterns
4. Integrate with existing commands in Phase 6
5. Validate and test in Phase 7

**Success Metrics:**
- All 493+ existing tests pass
- Statistics action completes in <5 seconds (6x improvement)
- 85%+ test coverage maintained
- Clean implementation following ClaudeStep architecture
- Artifact code preserved but unused
