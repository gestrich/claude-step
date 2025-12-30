# ADR-001: Metadata as Source of Truth for Statistics

**Status**: Accepted

**Date**: 2025-12-30

**Context**: StatisticsService Refactoring (Phases 1-9)

## Context

The original `StatisticsService` implementation queried the GitHub API directly to collect statistics about pull requests and team member activity. This approach had several architectural problems:

1. **Service layer violated layering principles**: Service layer executed raw GitHub CLI commands and parsed JSON responses
2. **No type safety**: Services navigated JSON dictionaries with string keys, leading to runtime errors
3. **Dual source of truth**: Statistics came from GitHub API while metadata storage tracked the same information
4. **Rate limiting concerns**: Direct GitHub API queries could hit rate limits with many projects
5. **Tight coupling**: Service layer coupled to GitHub CLI command syntax and API response format

The codebase already had a metadata storage system (via `GitHubMetadataStore`) that stored project and PR information, updated by merge triggers during workflow runs. However, statistics bypassed this system and went straight to the GitHub API.

## Decision

We decided to use **metadata configuration as the single source of truth** for all statistics operations, rather than querying the GitHub API directly.

### Implementation

The refactoring proceeded through 9 phases (documented in `docs/proposed/refactor-statistics-service-architecture.md`):

1. **Phase 1-2**: Created GitHub domain models and infrastructure layer operations for potential future use
2. **Phase 3**: Refactored `collect_team_member_stats()` to use metadata service instead of GitHub API
3. **Phase 4**: Created `PRReference` domain model to replace raw dictionaries
4. **Phase 5**: Added PR title field to metadata model
5. **Phase 6**: Verified PR title usage from metadata with proper fallbacks
6. **Phase 7**: Removed all GitHub API dependencies from StatisticsService
7. **Phase 8**: Documented GitHub operations for future synchronize command
8. **Phase 9**: Updated architecture documentation (this ADR)

### Key Changes

**Before**:
```python
class StatisticsService:
    def collect_team_member_stats(self, days_back: int, label: str):
        # Direct GitHub API calls
        merged_prs_json = run_gh_command("pr list --state merged ...")
        merged_prs = json.loads(merged_prs_json)

        # String-based dictionary navigation
        for pr in merged_prs:
            reviewer = pr["assignees"][0]["login"]  # No type safety
```

**After**:
```python
class StatisticsService:
    def collect_team_member_stats(self, days_back: int) -> Dict[str, TeamMemberStats]:
        # Query metadata service (single source of truth)
        projects = self.metadata_service.list_project_names()

        for project in projects:
            metadata = self.metadata_service.get_project(project)

            # Type-safe access to domain models
            for pr in metadata.pull_requests:
                reviewer = pr.reviewer  # Type-safe property
                pr_ref = PRReference.from_metadata_pr(pr, project)
```

## Consequences

### Positive Consequences

1. **Single source of truth**: Metadata configuration is the authoritative source for all statistics
2. **Proper layering**: Service layer uses domain models, infrastructure layer hidden behind repositories
3. **Type safety**: Services work with typed `PullRequest` and `PRReference` models, not JSON dictionaries
4. **No rate limiting**: Statistics queries don't hit GitHub API, avoiding rate limit concerns
5. **Cross-project aggregation**: Easy to aggregate statistics across multiple projects from metadata
6. **Better testability**: Mock domain models instead of JSON strings and GitHub CLI responses
7. **Consistency**: Statistics always match the state tracked by workflow runs
8. **Performance**: No external API calls for statistics generation

### Negative Consequences / Trade-offs

1. **Metadata dependency**: Statistics rely on metadata being up-to-date via merge triggers
2. **No real-time sync**: Statistics reflect last workflow run, not immediate GitHub state
3. **Manual PRs not tracked**: PRs created/merged outside ClaudeStep workflow won't appear in statistics until metadata is updated
4. **Historical data limited**: Only PRs tracked after ClaudeStep adoption appear in statistics

### Mitigation Strategies

1. **Keep GitHub infrastructure ready**: GitHub PR query operations (`list_pull_requests()`, etc.) are implemented and tested for future use
2. **Future synchronize command**: Infrastructure layer supports a future command to:
   - Detect PRs closed outside normal workflow
   - Backfill metadata from existing PRs
   - Audit metadata accuracy against GitHub
   - Correct drift between metadata and actual PR state
3. **Document for future**: GitHub operations are documented with examples for synchronize command use cases
4. **PR title in metadata**: Added PR title field to metadata (Phase 5) for better statistics display

## Alternatives Considered

### Alternative 1: Keep Direct GitHub API Queries

**Pros**:
- Real-time accuracy (statistics always reflect current GitHub state)
- No dependency on metadata system
- Historical PRs automatically included

**Cons**:
- Violates layering architecture (service layer knows GitHub CLI syntax)
- No type safety (JSON dictionary navigation)
- Rate limiting concerns with many projects
- Harder to test (must mock GitHub API responses)
- Mixed sources of truth (GitHub for stats, metadata for workflow)

**Rejected because**: Architectural violations outweigh real-time accuracy benefits. Metadata-first approach is cleaner and more maintainable.

### Alternative 2: Hybrid Approach (Metadata + GitHub API)

**Pros**:
- Can use GitHub API for edge cases
- Metadata for common case, API for validation

**Cons**:
- Complexity of maintaining two code paths
- Still has rate limiting concerns
- Unclear which source is authoritative
- Harder to test (must mock both systems)

**Rejected because**: Added complexity doesn't justify benefits. Single source of truth is simpler and more reliable.

### Alternative 3: Real-time Webhook Updates

**Pros**:
- Metadata always current without polling
- No manual synchronize command needed

**Cons**:
- Requires webhook infrastructure and event handling
- Adds operational complexity
- Overkill for statistics use case
- Still need synchronize for backfilling historical data

**Rejected because**: Merge triggers already update metadata when workflows run. Webhooks add unnecessary complexity.

## Future Evolution

The decision to use metadata as source of truth doesn't preclude future improvements:

### Planned: Synchronize Command

A future `synchronize` command (using the GitHub infrastructure built in Phases 1-2) will enable:

```bash
# Backfill historical PRs into metadata
python -m claudestep synchronize --backfill --days-back 90

# Audit metadata against GitHub
python -m claudestep synchronize --audit

# Correct drift
python -m claudestep synchronize --repair
```

This allows metadata-first architecture while maintaining ability to validate and correct against GitHub when needed.

### Possible: Selective Real-time Queries

For specific use cases (e.g., admin dashboard), we could add optional real-time queries:

```python
# Statistics service stays metadata-based
stats_service.collect_all_statistics()  # Uses metadata

# New admin service for real-time queries
admin_service.get_current_pr_state(pr_number)  # Uses GitHub API
```

This keeps statistics fast and metadata-based while allowing opt-in real-time queries.

## Related Documentation

- **Refactoring process**: `docs/proposed/refactor-statistics-service-architecture.md` - Complete 9-phase refactoring
- **Architecture overview**: `docs/architecture/architecture.md` - "Future: Metadata Synchronization" section
- **Code style guide**: `docs/architecture/python-code-style.md` - "Domain Models and Data Parsing" section
- **Domain models**: `src/claudestep/domain/models.py` - `PullRequest`, `PRReference`, `HybridProjectMetadata`
- **GitHub models**: `src/claudestep/domain/github_models.py` - `GitHubPullRequest` (for future use)
- **GitHub operations**: `src/claudestep/infrastructure/github/operations.py` - PR query functions (dormant, ready for synchronize)
- **Statistics service**: `src/claudestep/application/services/statistics_service.py` - Refactored implementation

## References

- Martin Fowler's Service Layer pattern: https://martinfowler.com/eaaCatalog/serviceLayer.html
- ClaudeStep architecture documentation: `docs/architecture/architecture.md`
- Repository Pattern for infrastructure abstraction
