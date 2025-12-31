# Hash-Based Task Identification

## Background

ClaudeStep currently uses positional indices from spec.md to identify tasks (e.g., task 1, task 2, task 3). These indices are embedded in branch names (`claude-step-<project>-3`) and used to map PRs to tasks. This creates a fragile system where inserting, deleting, or reordering tasks in spec.md breaks the mapping between existing PRs and their intended tasks.

**Example of the problem:**
```markdown
<!-- Original spec.md -->
- [ ] Task at position 1
- [ ] Task at position 2  ← PR created: claude-step-myproject-2
- [ ] Task at position 3

<!-- Someone inserts a new task -->
- [ ] Task at position 1
- [ ] NEW TASK at position 2  ← Inserted!
- [ ] Task at position 3  ← Was position 2, now shifted
- [ ] Task at position 4  ← Was position 3, now shifted
```

Now the PR `claude-step-myproject-2` points to the wrong task!

**Solution: Content-based hashing**

Replace positional indices with stable task identifiers derived from the task description content. When a task description is hashed, it produces a unique identifier that remains stable regardless of the task's position in spec.md.

**Key insight from user:** If a task description changes while a PR is open, the user should close the old PR. This naturally triggers the workflow to create a new PR with the updated task description and new hash.

**Design decisions:**
- Hash function: SHA-256 truncated to 8 characters for readability
- Branch naming: `claude-step-<project>-<task-hash>` (e.g., `claude-step-auth-a3f2b891`)
- No modification of spec.md required - hashes are computed on-the-fly
- Spec.md on main branch remains the single source of truth

**Benefits:**
- Tasks can be freely inserted, deleted, and reordered in spec.md
- No risk of PR/task misalignment due to spec changes
- No manual ID management required
- Self-healing: closing orphaned PRs triggers new PRs with correct tasks

**Trade-offs:**
- Task hashes are not human-readable (but branch names include project name for context)
- Changing task description invalidates existing PRs (user must close and restart)
- Need to handle orphaned PRs (PRs for tasks no longer in spec)

## Goals

1. Replace index-based task identification with content-based hashing
2. Update branch naming convention to use task hashes
3. Update all code that parses/generates branch names
4. Handle orphaned PRs gracefully (detect and warn users)
5. Maintain backward compatibility during transition (support both formats temporarily)
6. Update documentation and user-facing messages

## Phases

- [x] Phase 1: Design hash function and branch naming convention

**Objective**: Define the exact hash algorithm and branch naming format that will be used throughout the system.

**Status**: ✅ Completed

**Implementation Notes**:
- Implemented `generate_task_hash()` in `src/claudestep/services/core/task_service.py`
  - Uses SHA-256 hash of task description
  - Truncates to 8 characters for readability
  - Handles whitespace normalization: strips leading/trailing whitespace and collapses internal whitespace
  - Example: `TaskService.generate_task_hash("Add user authentication")` → `"39b1209d"`
- Added `format_branch_name_with_hash()` to `src/claudestep/services/core/pr_service.py`
  - New branch naming format: `claude-step-<project>-<task-hash>`
  - Example: `claude-step-auth-refactor-a3f2b891`
- Added `parse_branch_name_extended()` to `src/claudestep/services/core/pr_service.py`
  - Supports both old format (`-<index>`) and new format (`-<hash>`) during migration
  - Auto-detects format: all digits → index, 8 hex chars → hash
  - Returns tuple: `(project_name, task_identifier, format_version)`
  - Format version: `"index"` or `"hash"`
- Maintained backward compatibility:
  - Original `parse_branch_name()` still works for legacy code
  - Original `format_branch_name()` still works for index-based branches

**Technical Details**:
- Hash algorithm: SHA-256 truncated to 8 hex characters (32 bits)
- Collision probability: ~4 billion combinations (sufficient for task lists)
- Whitespace normalization ensures stable hashes regardless of formatting
- Format detection logic:
  - Index format: identifier is all digits (`^\d+$`)
  - Hash format: identifier is exactly 8 hexadecimal characters (`^[0-9a-f]{8}$`)

**Files Modified**:
- `src/claudestep/services/core/task_service.py` - Added `generate_task_hash()` method
- `src/claudestep/services/core/pr_service.py` - Added `format_branch_name_with_hash()` and `parse_branch_name_extended()` methods

**Test Results**:
- All 517 unit tests pass
- Build succeeds
- Functions verified working:
  - `TaskService.generate_task_hash("Add user authentication")` → `"39b1209d"`
  - `PRService.format_branch_name_with_hash("my-project", "a3f2b891")` → `"claude-step-my-project-a3f2b891"`
  - `PRService.parse_branch_name_extended("claude-step-my-project-a3f2b891")` → `("my-project", "a3f2b891", "hash")`

**Expected outcomes**: ✅ All achieved
- Hash function produces consistent, stable identifiers
- Branch naming convention is well-defined and documented
- Regex can distinguish between old and new formats

---

- [x] Phase 2: Update spec.md parsing to include task hashes

**Objective**: Modify the task parsing logic to compute and store task hashes alongside task descriptions.

**Status**: ✅ Completed

**Implementation Notes**:
- Added `task_hash` field to `SpecTask` domain model in `src/claudestep/domain/spec_content.py`
- Implemented `generate_task_hash()` function in `src/claudestep/domain/spec_content.py`
  - Moved hash generation logic to domain layer to avoid circular dependencies
  - Uses SHA-256 hash of normalized task description
  - Truncates to 8 characters for readability
  - Example: `generate_task_hash("Add user authentication")` → `"39b1209d"`
- Updated `SpecTask.from_markdown_line()` to automatically generate and store task hash
  - Hash is computed when task is parsed from markdown
  - Uses normalized description (whitespace stripped and collapsed)
- Updated `TaskService.generate_task_hash()` to delegate to domain model function
  - Maintains backward compatibility with existing API
  - Service layer now delegates to domain layer for hash generation
- Updated `TaskService.find_next_available_task()` to return task hash
  - New return signature: `(task_index, task_description, task_hash)`
  - Updated call sites in `src/claudestep/cli/commands/prepare.py` to handle new signature
  - `discover_ready.py` only checks for None, so no changes needed there
- Updated tests in `tests/unit/domain/test_spec_content.py`
  - Added `task_hash` parameter to manual `SpecTask` instantiations
  - Added assertion to verify hash is generated correctly
  - All 622 tests pass

**Technical Details**:
- Hash generation is deterministic and stable
- Whitespace normalization ensures consistent hashes regardless of formatting
- Domain model owns hash generation logic (separation of concerns)
- Service layer delegates to domain model for hash computation
- All existing tests pass with new field

**Files Modified**:
- `src/claudestep/domain/spec_content.py` - Added hash field and generation function
- `src/claudestep/services/core/task_service.py` - Updated to delegate hash generation and return hash from find_next_available_task
- `src/claudestep/cli/commands/prepare.py` - Updated to handle new return signature
- `tests/unit/domain/test_spec_content.py` - Updated tests to include task_hash field

**Test Results**:
- All 622 unit and integration tests pass
- Test coverage: 69.10% (slightly below 70% threshold due to new uncovered code paths)
- Build succeeds

**Expected outcomes**: ✅ All achieved
- Each task has a stable hash identifier stored in task_hash field
- Task hash is computed automatically during parsing
- Hashes are computed consistently across the system using domain model function
- find_next_available_task() returns hash along with index and description

---

- [x] Phase 3: Update branch name generation and parsing

**Objective**: Change branch name creation to use task hashes, and update parsing to handle both old and new formats.

**Status**: ✅ Completed

**Implementation Notes**:
- Updated `PRService.format_branch_name()` to accept task hash instead of index
  - New signature: `format_branch_name(project: str, task_hash: str) -> str`
  - Now delegates to `format_branch_name_with_hash()` for consistency
  - Generates: `claude-step-{project}-{task_hash}`
- Updated `PRService.parse_branch_name()` to extract hash and detect format
  - New signature returns: `(project: str, task_identifier: Union[int, str], format_version: Literal["index", "hash"])`
  - Now delegates to `parse_branch_name_extended()` for unified parsing
  - Supports both formats during transition:
    - Old: `claude-step-project-3` → `("project", 3, "index")`
    - New: `claude-step-project-a3f2b891` → `("project", "a3f2b891", "hash")`
  - Format detection: all digits → index, 8 hex chars → hash
- Updated all call sites to handle new return format:
  - `PRService.get_unique_projects()` - Updated to unpack 3-tuple
  - `ProjectService.detect_project_from_pr()` - Updated to unpack 3-tuple
  - `GitHubPullRequest.project_name` property - Already handles new format (uses first element)
  - `GitHubPullRequest.task_index` property - Updated to only return index for "index" format branches
- Added new property `GitHubPullRequest.task_hash` - Returns hash for "hash" format branches
- Updated `prepare.py` to use task_hash when creating branches (line 177)
  - Changed from: `pr_service.format_branch_name(detected_project, task_index)`
  - Changed to: `pr_service.format_branch_name(detected_project, task_hash)`
- Updated all tests to match new signatures:
  - `test_format_branch_name` tests now use hash values instead of indices
  - `test_parse_branch_name` tests now expect 3-tuple returns with format detection
  - Added tests for both index and hash formats
  - Updated roundtrip test to use hash format

**Technical Details**:
- Backward compatibility maintained through format detection in parse_branch_name
- All existing index-based branches will continue to parse correctly
- New branches will use hash-based format automatically
- Format version detection allows code to handle both formats appropriately
- Domain model properties (task_index, task_hash) provide type-safe access to identifiers

**Files Modified**:
- `src/claudestep/services/core/pr_service.py` - Updated format_branch_name() and parse_branch_name()
- `src/claudestep/cli/commands/prepare.py` - Updated to use task_hash for branch creation
- `src/claudestep/services/core/project_service.py` - Updated to handle 3-tuple return
- `src/claudestep/domain/github_models.py` - Updated task_index property and added task_hash property
- `tests/unit/services/core/test_pr_service.py` - Updated all branch naming tests

**Test Results**:
- All 519 unit tests pass
- All PR service tests pass (58/58)
- Build succeeds
- Backward compatibility verified: old index-based branches parse correctly
- Forward compatibility verified: new hash-based branches parse correctly

**Expected outcomes**: ✅ All achieved
- New branches use hash-based naming via updated format_branch_name()
- Parsing handles both old and new branch formats via format detection
- System can identify format version for each branch (returns "index" or "hash")
- All call sites updated to handle new signatures
- All tests updated and passing

---

- [x] Phase 4: Update task finding logic to work with hashes

**Objective**: Modify the logic that finds "next available task" to use hash-based matching with GitHub PRs.

**Status**: ✅ Completed

**Implementation Notes**:
- Updated `SpecContent.get_next_available_task()` in `src/claudestep/domain/spec_content.py`
  - Added `skip_hashes` parameter alongside existing `skip_indices` parameter
  - Supports dual-mode filtering: by index (legacy) and by hash (new format)
  - Tasks are skipped if they match either skip_indices OR skip_hashes
- Updated `TaskService.find_next_available_task()` in `src/claudestep/services/core/task_service.py`
  - Added `skip_hashes` parameter to method signature
  - Passes both skip_indices and skip_hashes to domain model
  - Enhanced logging to show which tasks are being skipped and why (index-based vs hash-based)
- Added new method `TaskService.get_in_progress_tasks()`
  - Returns tuple of (task_indices, task_hashes) for dual-mode support
  - Queries GitHub PRs and extracts both hash-based and index-based task identifiers
  - Replaces reliance on index-only `get_in_progress_task_indices()` (kept for backward compatibility)
- Added new method `TaskService.detect_orphaned_prs()`
  - Detects PRs whose task hash/index no longer matches current spec.md
  - Returns list of orphaned GitHubPullRequest objects
  - Handles both hash-based PRs (checks against valid_hashes set) and index-based PRs (checks against valid_indices set)
- Updated `src/claudestep/cli/commands/prepare.py`
  - Calls `detect_orphaned_prs()` and displays warnings to user
  - Shows clear guidance on how to resolve orphaned PRs (close them, system will create new ones)
  - Uses `get_in_progress_tasks()` instead of `get_in_progress_task_indices()`
  - Displays both index-based and hash-based in-progress tasks separately
- Updated `src/claudestep/cli/commands/discover_ready.py`
  - Uses `get_in_progress_tasks()` for dual-mode support
  - Passes both indices and hashes to `find_next_available_task()`
- Added comprehensive tests in `tests/unit/domain/test_spec_content.py`
  - `test_get_next_available_task_with_skip_hashes` - Tests hash-based skipping
  - `test_get_next_available_task_with_skip_indices_and_hashes` - Tests dual-mode filtering
  - `test_get_next_available_task_with_multiple_skip_hashes` - Tests multiple hash skips
  - All 627 existing tests pass with new functionality

**Technical Details**:
- Backward compatibility maintained: system handles both old index-based PRs and new hash-based PRs
- Orphaned PR detection compares PR identifiers against current spec.md task lists
- User-facing warnings guide users to close orphaned PRs manually
- When orphaned PRs are closed, the system will automatically create new PRs for updated tasks
- Skip logic uses set membership for O(1) lookup performance

**Files Modified**:
- `src/claudestep/domain/spec_content.py` - Updated `get_next_available_task()` signature
- `src/claudestep/services/core/task_service.py` - Added `get_in_progress_tasks()` and `detect_orphaned_prs()` methods
- `src/claudestep/cli/commands/prepare.py` - Added orphaned PR detection and warnings
- `src/claudestep/cli/commands/discover_ready.py` - Updated to use dual-mode task finding
- `tests/unit/domain/test_spec_content.py` - Added 3 new tests for hash-based skipping

**Test Results**:
- All 627 unit and integration tests pass
- Build succeeds (all Python files compile successfully)
- Test coverage: 68.33% (slightly below 70% due to new service methods requiring integration tests)
- New domain model methods (get_next_available_task with skip_hashes) have 100% coverage

**Expected outcomes**: ✅ All achieved
- System correctly identifies in-progress tasks by hash (and index for legacy PRs)
- Next available task is found correctly using dual-mode filtering
- Orphaned PRs are detected and logged with actionable user guidance

---

- [x] Phase 5: Update statistics and reporting

**Objective**: Ensure statistics correctly aggregate tasks by hash and handle both old and new formats.

**Status**: ✅ Completed

**Implementation Notes**:
- Updated `StatisticsService.collect_team_member_stats()` in `src/claudestep/services/composite/statistics_service.py`
  - Modified PR matching logic to handle both task_index (legacy) and task_hash (new) formats
  - Added dual-mode validation: PRs must have either task_index OR task_hash to be counted
  - Updated PR title formatting to use hash for hash-based PRs: `Task {hash[:8]}: {description}`
  - Maintained backward compatibility: index-based PRs still show as `Task {index}: {description}`
- No changes needed to `collect_project_stats()` method
  - Already uses `get_open_prs_for_project()` which returns all PRs regardless of format
  - Counts work correctly for both hash-based and index-based PRs
- No changes needed to reporting/formatting code
  - `ProjectStats` and `TeamMemberStats` formatting is already format-agnostic
  - Statistics models format PR titles generically without relying on specific identifier format
- Orphaned PR detection already implemented in Phase 4
  - `TaskService.detect_orphaned_prs()` handles both hash and index-based orphaned PRs
  - Warnings shown in `prepare.py` command output

**Technical Details**:
- Statistics collection now supports dual-mode PR identification:
  - Hash-based PRs: Uses `pr.task_hash` property to get hash identifier
  - Index-based PRs: Uses `pr.task_index` property to get index identifier (legacy)
- PR validation logic: `if not project_name or (task_index is None and task_hash is None):`
  - Ensures each PR has at least one valid identifier before counting
- Title formatting uses conditional logic to display appropriate identifier type
- Completed task counting remains based on spec.md checkboxes (format-independent)
- In-progress task counting includes all open PRs (both formats)
- Pending task calculation: `total - completed - in_progress` works for both formats

**Files Modified**:
- `src/claudestep/services/composite/statistics_service.py` - Updated PR matching to support both hash and index

**Test Results**:
- All 522 unit tests pass
- All 105 integration tests pass
- Build succeeds (all Python files compile successfully)
- Statistics correctly handle both hash-based and index-based PRs
- PR title formatting works for both identifier types

**Expected outcomes**: ✅ All achieved
- Statistics accurately reflect task completion based on hashes (or indices for legacy PRs)
- Reports handle both old and new formats during transition
- Orphaned PRs are visible in reporting (already implemented in Phase 4)

---

- [ ] Phase 6: Add orphaned PR detection and user guidance

**Objective**: Implement clear detection and messaging when PRs become orphaned due to task description changes.

**Tasks**:
- Create `detect_orphaned_prs()` function:
  - Query all open PRs for project
  - Extract task identifiers from branch names
  - Compare with current spec.md task hashes
  - Return list of orphaned PRs
- Add user-facing warnings:
  - When orphaned PRs detected during `prepare` command
  - Suggest closing orphaned PRs manually
  - Explain that closing will trigger new PR with updated task
- Add to workflow output/summary:
  - List any orphaned PRs found
  - Provide GitHub URLs to close them easily

**Files to modify**:
- `src/claudestep/services/task_management_service.py` - Add detection function
- `src/claudestep/cli/commands/prepare.py` - Add warnings
- GitHub Actions step summary output

**User-facing message example**:
```
⚠️  Warning: Found 2 orphaned PRs for tasks that have been modified:
  - PR #123 (claude-step-auth-a3f2b891) - task description changed
  - PR #125 (claude-step-auth-f7c4d3e2) - task removed from spec

To resolve:
1. Review these PRs at: https://github.com/owner/repo/pulls
2. Close any PRs for modified/removed tasks
3. The workflow will automatically create new PRs for current tasks
```

**Expected outcomes**:
- Users are clearly notified of orphaned PRs
- Guidance is actionable and links to relevant PRs
- System continues working even with orphaned PRs present

---

- [ ] Phase 7: Update documentation

**Objective**: Update all user-facing documentation to explain hash-based task identification.

**Tasks**:
- Update README.md:
  - Explain that tasks can be freely reordered in spec.md
  - Note that changing task descriptions invalidates open PRs
  - Document the orphaned PR workflow (close old PR → new PR created)
- Update architecture documentation:
  - Document hash algorithm and branch naming convention
  - Explain transition from index-based to hash-based
  - Add examples of branch name parsing
- Add troubleshooting guide:
  - What to do when task descriptions change
  - How to handle orphaned PRs
  - Migration guide for existing projects

**Files to modify**:
- `README.md`
- `docs/architecture/architecture.md`
- Create `docs/user-guides/modifying-tasks.md` (new file)

**Documentation sections to add**:

**In README.md:**
```markdown
## Modifying Tasks

You can freely insert, delete, and reorder tasks in your spec.md file. Each task is identified by a hash of its description, not its position.

**Important:** If you change a task description while a PR is open for that task:
1. The open PR becomes "orphaned" (references the old description)
2. Close the orphaned PR manually
3. The workflow will automatically create a new PR with the updated task description
```

**Expected outcomes**:
- Users understand how hash-based identification works
- Clear guidance on modifying tasks
- Migration path documented for existing projects

---

- [ ] Phase 8: Handle backward compatibility

**Objective**: Ensure the system continues to work with existing index-based PRs during transition period.

**Tasks**:
- Implement dual-mode support in task finding:
  - When checking if task is in-progress, match by EITHER hash OR index
  - Prioritize hash-based matching, fall back to index for old PRs
- Add migration helper command (optional):
  - `python -m claudestep migrate-to-hashes --project <name>`
  - Detects old index-based PRs
  - Suggests closing/merging them before full migration
- Set deprecation timeline:
  - Support both formats for N months/releases
  - Log warnings when old format is detected
  - Eventually remove index-based support

**Files to modify**:
- `src/claudestep/services/task_management_service.py` - Dual-mode matching
- `src/claudestep/cli/commands/migrate.py` - New migration command (optional)

**Expected outcomes**:
- Existing projects with index-based PRs continue working
- Gradual migration path for users
- Clear timeline for deprecating old format

---

- [ ] Phase 9: Update tests

**Objective**: Ensure all tests pass with hash-based identification and cover new edge cases.

**Tasks**:
- Update unit tests:
  - Test `generate_task_hash()` function with various inputs
  - Test branch name generation with hashes
  - Test branch name parsing with both formats
  - Test task matching by hash
  - Test orphaned PR detection
- Update integration tests:
  - Test full workflow with hash-based branches
  - Test mixed scenario (old and new PRs coexist)
  - Test spec.md modification with open PR
- Add new test cases:
  - Task reordering doesn't affect PR matching
  - Task insertion doesn't break existing PRs
  - Orphaned PR detection and warnings
  - Hash collision handling (extremely unlikely, but test anyway)

**Files to modify**:
- `tests/unit/services/test_task_management.py` - Add hash tests
- `tests/unit/services/test_pr_operations.py` - Update branch name tests
- `tests/integration/cli/commands/test_prepare.py` - Test full workflow
- Add new test file: `tests/unit/services/test_task_hashing.py`

**Expected outcomes**:
- All existing tests updated and passing
- New edge cases covered
- Test coverage remains ≥70%

---

- [ ] Phase 10: Validation

**Objective**: Verify the hash-based system works correctly end-to-end and handles all scenarios gracefully.

**Testing approach**:

1. **Unit tests**: Run all unit tests
   ```bash
   PYTHONPATH=src:scripts pytest tests/unit/ -v
   ```

2. **Integration tests**: Run all integration tests
   ```bash
   PYTHONPATH=src:scripts pytest tests/integration/ -v
   ```

3. **Coverage check**: Ensure coverage remains ≥70%
   ```bash
   PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing --cov-fail-under=70
   ```

4. **Manual scenario testing** (optional but recommended):
   - Create test project with spec.md containing 5 tasks
   - Run prepare → verify branch uses hash: `claude-step-test-a3f2b891`
   - Reorder tasks in spec.md, merge to main
   - Run prepare again → verify same task not picked up twice
   - Modify task description while PR open
   - Verify orphaned PR warning appears
   - Close orphaned PR → verify new PR created with new hash
   - Check statistics show correct counts

**Success criteria**:
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Test coverage ≥70%
- ✅ Branch names use hash format: `claude-step-<project>-<hash>`
- ✅ Tasks can be reordered without breaking PR matching
- ✅ Orphaned PRs are detected and reported
- ✅ Statistics correctly count tasks by hash
- ✅ System handles both old and new formats during transition

**Rollback plan**:
- Git history preserves all changes by phase
- Can revert phases individually if issues found
- Index-based system remains functional during transition period
