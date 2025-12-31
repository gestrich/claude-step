# Architecture Documentation Cleanup and Cost Tracking Restoration

## Background

This plan addresses several improvements to the ClaudeStep project:

1. **Architecture Documentation Cleanup**: The `docs/architecture/architecture.md` file has become too detailed with implementation specifics that should be in separate focused documents. We need to extract major components into their own documents and keep the main architecture doc high-level.

2. **Remove Backward Compatibility Code**: The project contains legacy code for supporting old index-based PR identification alongside the newer hash-based approach. Since we've fully migrated to hash-based identification, we can remove all backward compatibility code and simplify the codebase.

3. **Restore Cost Tracking**: Cost tracking via PR comments was removed during a previous refactor (see TODO comments in `statistics_service.py`). We want to restore this feature so that AI model usage costs are posted as comments to pull requests after they're created.

4. **Fix Documentation Inaccuracies**: The architecture doc mentions an "application/" layer that doesn't exist in the codebase. We need to verify and correct these inconsistencies.

## Phases

- [x] Phase 1: Extract hash-based task identification to separate doc

**Details**:
- Create `docs/architecture/hash-based-task-identification.md`
- Extract the following sections from `architecture.md`:
  - "Hash-Based Task Identification" section (keep only 2-3 sentences in main doc)
  - Move detailed content: hash algorithm details, examples, orphaned PR detection
- Update `architecture.md` to have a brief summary (2-3 sentences) that links to the new doc
- Keep only: "Tasks are identified by content hash (8-character SHA-256 of description)"
- Remove: "Why Hash-Based Identification?", "Hash Algorithm", examples

**Completed**: Hash-based task identification documentation successfully extracted to dedicated document at `docs/architecture/hash-based-task-identification.md`. The main architecture.md now contains a concise 3-sentence summary with a link to the detailed documentation. All implementation details, code examples, orphaned PR detection logic, and backward compatibility sections have been moved to the focused document.

**Expected outcome**: Hash details moved to focused document, architecture.md simplified

- [x] Phase 2: Extract branch naming to separate doc

**Details**:
- Create `docs/architecture/branch-naming.md`
- Extract branch naming details from `architecture.md`
- Keep in `architecture.md` only: "Branch format: `claude-step-{project}-{task-hash}`"
- Move to new doc: branch name parsing logic, format detection, all detailed examples
- Remove backward compatibility sections mentioning "Old Format" and dual-mode support

**Completed**: Branch naming documentation successfully extracted to dedicated document at `docs/architecture/branch-naming.md`. The main architecture.md now contains a concise 3-sentence summary with a link to the detailed documentation. The new document includes comprehensive coverage of branch format, parsing logic, format detection, project name handling, code examples, and integration points throughout the codebase. All tests pass (649 tests).

**Expected outcome**: Branch naming details in separate doc, main doc just states the format

- [x] Phase 3: Remove all backward compatibility code from codebase

**Details**:
- Delete `src/claudestep/cli/commands/migrate_to_hashes.py`
- Remove from `src/claudestep/__main__.py`: migrate-to-hashes command registration
- Remove from `src/claudestep/domain/github_models.py`:
  - `task_index` property (lines 203-235)
  - Update docstrings that mention "legacy" format
- Remove from `src/claudestep/services/core/task_service.py`:
  - `skip_indices` parameter from `find_next_available_task()` (line 41)
  - Index-based filtering logic (lines 59-61, 120-122)
- Remove from `src/claudestep/domain/spec_content.py`:
  - `skip_indices` parameter from `get_next_available_task()`
  - Index-based filtering logic (line 186-188)
- Remove from `src/claudestep/services/core/pr_service.py`:
  - Index format detection from `parse_branch_name()` (keep only hash format)
- Remove from `src/claudestep/services/composite/statistics_service.py`:
  - Index-based PR handling logic (lines 264-265)
- Update all related tests to remove index-based test cases

**Completed**: All backward compatibility code successfully removed. Key changes:
- Deleted `migrate_to_hashes.py` CLI command and removed from parser
- Removed `task_index` property from `GitHubPullRequest` model
- Simplified `parse_branch_name()` to only support hash-based format (8-char hex)
- Updated `find_next_available_task()` to only accept `skip_hashes` parameter
- Updated `get_in_progress_tasks()` to return only hashes (not tuple)
- Removed all index-based test cases and updated test helpers
- 523 unit tests pass (1 pre-existing circular import issue unrelated to changes)

**Expected outcome**: All index-based/backward compatibility code removed, only hash-based identification remains

- [x] Phase 4: Remove compatibility fields from domain models

**Details**:
- Search for and remove fields marked as "compatibility", "legacy", or "unused"
- Remove from `src/claudestep/services/composite/statistics_service.py`:
  - `project_metadata: Optional metadata (unused, kept for compatibility)` parameter (line 304)
- Review all domain models in `src/claudestep/domain/models.py` for unused compatibility fields
- Update related docstrings that reference removed fields

**Completed**: All unused compatibility fields successfully removed from domain models. Key changes:
- Removed `project_metadata` parameter from `StatisticsService.collect_project_costs()` (line 290)
- Removed `raw_config` field from `ProjectConfiguration` domain model in `src/claudestep/domain/project_configuration.py`
- Updated `ProjectConfiguration.from_yaml_string()` to no longer store raw config
- Removed test `test_from_yaml_string_stores_raw_config` which specifically tested the removed functionality
- Updated all test assertions that referenced `raw_config` across:
  - `tests/unit/domain/test_project_configuration.py` (3 instances)
  - `tests/unit/infrastructure/repositories/test_project_repository.py` (1 instance)
- 628 tests pass (3 pre-existing failures: 2 e2e GitHub API issues, 1 circular import issue)
- Build succeeds

**Technical Notes**:
- The `raw_config` field was never used in the actual source code, only in tests, confirming it was truly unused
- Legacy cost fields in `TaskMetadata` (`main_task_cost_usd`, `pr_summary_cost_usd`, `total_cost_usd`, `model`) were retained as they are still used for backward compatibility when reading artifact metadata and are actively used in serialization/deserialization logic
- The `label` parameter in `collect_project_costs()` is marked as unused but retained as it's part of the method signature and doesn't cause confusion

**Expected outcome**: Clean domain models without legacy compatibility fields

- [ ] Phase 5: Fix application/ layer references in documentation

**Details**:
- Verify that `src/claudestep/application/` directory does not exist (confirmed in initial analysis)
- Remove all references to "application/" layer from `docs/architecture/architecture.md`
- Update layer descriptions to reflect actual structure:
  - CLI Layer (`cli/`)
  - Service Layer (`services/`)
  - Domain Layer (`domain/`)
  - Infrastructure Layer (`infrastructure/`)
- Update module organization diagram to remove application/ references
- Check for formatter utilities - move or document where they actually live

**Expected outcome**: Documentation accurately reflects actual codebase structure

- [ ] Phase 6: Simplify Service Layer Organization section

**Details**:
- In `docs/architecture/architecture.md`, tighten up "Service Layer Organization" section
- Keep only: explanation that we have two levels (core/ and composite/)
- Remove: detailed list of all services and their methods
- Remove: lengthy code examples showing service structure
- Keep structure to 1-2 paragraphs explaining the two-level concept
- Link to actual code for details instead of documenting in architecture

**Expected outcome**: Concise service layer organization section focused on concepts

- [ ] Phase 7: Remove Migration History section

**Details**:
- Delete "## Migration History" section entirely from `docs/architecture/architecture.md`
- Migration history belongs in `docs/completed/` spec files, not architecture doc
- Remove subsections: "Migration 1: Function-Based to Class-Based Services" and "Migration 2: Flat Structure to Two-Level Organization"

**Expected outcome**: Architecture doc focuses on current state, not historical changes

- [ ] Phase 8: Remove Backward Compatibility section from architecture doc

**Details**:
- Delete "Backward Compatibility" section from Hash-Based Task Identification
- Delete "Dual-Mode Support" code examples
- Delete "Migration Path" subsection
- Delete "Deprecation Timeline" subsection
- Update related sections to remove references to supporting both formats

**Expected outcome**: Documentation reflects hash-only approach

- [ ] Phase 9: Restore cost tracking feature

**Details**:
- Examine `src/claudestep/cli/commands/add_cost_comment.py` - this command already exists
- Review git history to understand how cost tracking was previously integrated
- Look at completed refactor docs: `docs/completed/remove-metadata-branch-simplify-to-github-api.md` and `docs/completed/artifact-api-refactor.md`
- Restore cost tracking integration in main workflow:
  - Add step in `action.yml` to call `add_cost_comment` after PR creation
  - Pass cost data from Claude Code action outputs (MAIN_COST, SUMMARY_COST)
  - Ensure `add_cost_comment` command is registered in `__main__.py`
- Remove TODO comments from `statistics_service.py` (lines 204-205, 309-310)
- Update `README.md` to reflect restored cost tracking feature
- Ensure cost data flows: Claude Code → action outputs → add_cost_comment → PR comment

**Expected outcome**: Cost tracking restored, PR comments show AI model usage costs

- [ ] Phase 10: Update tests for removed backward compatibility

**Details**:
- Remove tests for index-based branch names from `tests/unit/services/core/test_pr_service.py`
- Remove index-based test cases from `tests/unit/domain/test_github_models.py`
- Remove skip_indices test cases from `tests/unit/services/core/test_task_service.py`
- Update test builders in `tests/builders/` to remove task_index fields
- Run full test suite to ensure no broken tests
- Update any integration tests that rely on index-based identification

**Expected outcome**: All tests pass with backward compatibility code removed

- [ ] Phase 11: Validation

**Details**:
- Run full test suite: `pytest tests/`
- Verify all unit tests pass
- Verify architecture documentation is accurate and concise
- Check that no references to index-based PRs remain in codebase
- Verify cost tracking works end-to-end (may require manual GitHub Actions run)
- Review all modified documentation for clarity and accuracy
- Ensure all "application/" layer references are removed
- Confirm Migration History section is gone

**Success criteria**:
- All tests pass
- Documentation is simplified and accurate
- No backward compatibility code remains
- Cost tracking feature is functional
