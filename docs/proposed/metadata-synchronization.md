# Metadata Synchronization Command

## Background

ClaudeStep follows a **metadata-first architecture** where the metadata configuration (`.claudestep/metadata.json`) serves as the single source of truth for all statistics and reporting. This metadata is kept up-to-date through merge triggers and workflow runs that automatically record PR information when tasks are finalized.

However, PRs can be modified outside the normal ClaudeStep workflow:
- Manual merges or closes via GitHub UI
- Direct git operations
- Bulk operations by administrators
- Historical PRs created before ClaudeStep adoption

When these actions occur, the metadata can drift from GitHub's actual state. The **synchronize command** will enable metadata validation, drift detection, and automatic correction by querying GitHub's API and comparing against stored metadata.

The infrastructure for GitHub PR queries already exists in `src/claudestep/infrastructure/github/operations.py` but is currently dormant, waiting for this synchronization feature to activate it.

## Phases

- [ ] Phase 1: Add synchronize command CLI interface

Create the command-line interface for the synchronize command with options:
- `--project <name>` - Synchronize specific project (default: all projects)
- `--dry-run` - Show what would be changed without modifying metadata
- `--backfill` - Import historical PRs not currently in metadata
- `--report` - Generate drift report without corrections

Files to modify:
- `src/claudestep/cli/commands/` - Add new `synchronize.py` command module
- `src/claudestep/cli/main.py` - Register synchronize command
- Update CLI documentation

Expected outcome: Users can invoke `claudestep synchronize` with appropriate flags

- [ ] Phase 2: Implement PR comparison logic

Create comparison service that detects differences between GitHub state and metadata:
- Missing PRs (in GitHub but not in metadata)
- Phantom PRs (in metadata but not in GitHub)
- Status mismatches (merged vs open)
- Metadata field differences (title, reviewer, timestamps)

Files to modify:
- Create `src/claudestep/application/services/sync_service.py`
- Define comparison result models in `src/claudestep/domain/models.py`
- Add drift detection algorithms

Technical considerations:
- Use existing `GitHubPullRequest` domain model from `github_models.py`
- Leverage `list_pull_requests()` function from `operations.py`
- Filter PRs by ClaudeStep label to identify relevant PRs
- Return structured comparison reports with actionable differences

Expected outcome: Service that can identify all discrepancies between GitHub and metadata

- [ ] Phase 3: Implement metadata update operations

Add functionality to update metadata based on GitHub state:
- Backfill missing PR entries
- Mark PRs as merged/closed when GitHub shows them merged/closed
- Update PR titles, reviewers, timestamps from GitHub
- Handle edge cases (duplicate PRs, invalid states)

Files to modify:
- Extend `src/claudestep/application/services/metadata_service.py` with update methods
- Add validation to prevent data corruption
- Implement atomic updates with rollback capability

Technical considerations:
- Preserve existing metadata that shouldn't be overwritten
- Maintain audit trail of synchronization changes
- Validate all changes before committing to storage
- Handle concurrent access safely

Expected outcome: Safe, reliable metadata updates based on GitHub truth

- [ ] Phase 4: Add drift reporting

Create human-readable reports showing metadata drift:
- Summary statistics (X PRs missing, Y status mismatches)
- Detailed line-by-line differences
- Recommendations for resolution
- Export formats (console, JSON, markdown)

Files to create:
- `src/claudestep/application/reporting/drift_report.py`

Technical considerations:
- Clear, actionable output for users
- Highlight critical vs minor discrepancies
- Support both interactive and CI/CD usage
- Include timestamps and PR links

Expected outcome: Informative reports that help users understand and fix drift

- [ ] Phase 5: Implement backfill mode

Add ability to import historical ClaudeStep PRs created before metadata tracking:
- Query GitHub for all PRs with ClaudeStep label
- Filter to PRs not already in metadata
- Prompt user for confirmation before bulk import
- Preserve original PR metadata (creation date, merge date, reviewer)

Files to modify:
- Extend `src/claudestep/application/services/sync_service.py`
- Add interactive confirmation prompts
- Handle rate limiting for large PR sets

Technical considerations:
- GitHub API rate limits (use pagination, respect limits)
- Distinguish ClaudeStep PRs from other PRs using labels
- Handle incomplete metadata gracefully (missing reviewers, etc.)
- Provide progress feedback for long-running operations

Expected outcome: Ability to populate metadata from existing GitHub PRs

- [ ] Phase 6: Add dry-run mode

Implement preview mode that shows what would change without modifying anything:
- Display all proposed changes
- Show before/after states
- Calculate impact summary
- Exit without modifications

Files to modify:
- Update `sync_service.py` to support simulation mode
- Add preview output formatting
- Ensure no side effects in dry-run mode

Expected outcome: Safe preview of synchronization operations

- [ ] Phase 7: Error handling and recovery

Add robust error handling for common failure scenarios:
- Network failures during GitHub API queries
- GitHub API rate limit exhaustion
- Corrupted metadata files
- Permission denied errors
- Partial update failures

Files to modify:
- Add exception types in `src/claudestep/domain/exceptions.py`
- Implement retry logic with exponential backoff
- Add rollback capability for failed updates
- Log errors with actionable context

Technical considerations:
- Graceful degradation when GitHub unavailable
- Clear error messages with resolution steps
- Preserve metadata integrity even on partial failures
- Support resumable operations

Expected outcome: Reliable synchronization even with network/permission issues

- [ ] Phase 8: Integration and documentation

Integrate synchronize command into existing workflows and document usage:
- Add synchronize to recommended maintenance procedures
- Update architecture documentation
- Create user guide with examples
- Add troubleshooting section

Files to modify:
- `README.md` - Add synchronize command to usage section
- `docs/architecture/architecture.md` - Update future plans to current implementation
- Create `docs/guides/synchronization.md` with detailed examples

Expected outcome: Well-documented feature ready for user adoption

- [ ] Phase 9: Validation

Test the synchronize command end-to-end:
- Unit tests for comparison logic, update operations, reporting
- Integration tests with mock GitHub API responses
- E2E tests simulating real drift scenarios (manual merges, missing PRs)
- Test dry-run mode produces no side effects
- Test backfill with various PR histories
- Verify rate limit handling
- Test error recovery and rollback

Run all tests:
```bash
pytest tests/unit/services/test_sync_service.py
pytest tests/integration/test_synchronize_command.py
pytest tests/e2e/test_synchronize_workflows.py
```

Success criteria:
- All tests pass
- Dry-run mode makes no modifications
- Backfill correctly imports historical PRs
- Drift detection catches all discrepancies
- Error handling prevents data corruption
- Documentation is complete and accurate
