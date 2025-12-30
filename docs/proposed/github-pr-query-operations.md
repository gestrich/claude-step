# GitHub PR Query Operations Enhancement

## Background

ClaudeStep currently includes GitHub PR query functions in `src/claudestep/infrastructure/github/operations.py` that provide type-safe access to GitHub's actual PR state. These functions were built to support future metadata synchronization but are currently **dormant** - tested, documented, and available but not actively used in normal operations.

The current implementation includes:
- `list_pull_requests()` - Fetch PRs with filtering options
- `GitHubPullRequest` domain model - Type-safe representation of GitHub PRs
- JSON parsing into well-formed domain models
- Support for state filtering, labels, time ranges, and pagination

However, these operations could be enhanced to better support the planned synchronize command and other future features that need to query GitHub's state. This document outlines improvements to make the GitHub PR query infrastructure more robust, performant, and feature-complete.

## Phases

- [ ] Phase 1: Add PR detail queries

Extend GitHub operations to fetch detailed information for individual PRs:
- PR comments and review threads
- PR check statuses and CI results
- PR file changes and diff statistics
- PR timeline events (labeled, assigned, etc.)

Files to modify:
- `src/claudestep/infrastructure/github/operations.py` - Add `get_pull_request_details()`
- `src/claudestep/domain/github_models.py` - Extend `GitHubPullRequest` with detail fields
- Add factory methods for parsing detailed PR JSON

Technical considerations:
- Use GitHub CLI's `gh pr view --json` with comprehensive field list
- Maintain type safety with domain model extensions
- Parse nested JSON structures (comments, reviews, checks)
- Handle PRs with large numbers of comments/files efficiently

Expected outcome: Ability to fetch complete PR information beyond basic metadata

- [ ] Phase 2: Implement caching layer

Add intelligent caching to reduce GitHub API calls and improve performance:
- Cache PR lists with TTL (time-to-live)
- Cache individual PR details
- Cache invalidation on known changes
- Respect GitHub rate limits

Files to create:
- `src/claudestep/infrastructure/github/cache.py` - Caching implementation
- Configuration for cache TTL and size limits

Files to modify:
- `operations.py` - Integrate caching into query functions
- Add cache statistics and monitoring

Technical considerations:
- Use in-memory cache with LRU eviction
- Store parsed domain models, not raw JSON
- Include cache-control headers from GitHub API
- Provide cache bypass option for synchronize command

Expected outcome: Faster queries with reduced API usage

- [ ] Phase 3: Add batch query operations

Implement efficient batch queries for multiple PRs:
- Fetch multiple PRs by number in single operation
- Parallel queries with controlled concurrency
- Aggregate results into cohesive response
- Progress reporting for large batches

Files to modify:
- `operations.py` - Add `get_pull_requests_batch(pr_numbers: List[int])`
- Implement concurrent query execution with thread pool
- Add rate limit awareness to prevent exhaustion

Technical considerations:
- Use `concurrent.futures` for parallel execution
- Respect GitHub rate limits (max 5000 requests/hour)
- Handle partial failures gracefully (some PRs succeed, others fail)
- Return results as soon as available (streaming)

Expected outcome: Efficient bulk PR queries for synchronization operations

- [ ] Phase 4: Enhanced filtering and search

Extend filtering capabilities beyond basic state and label:
- Filter by date ranges (created, updated, merged, closed)
- Filter by author, reviewer, assignee
- Full-text search in PR titles and bodies
- Combine multiple filter criteria

Files to modify:
- `operations.py` - Extend `list_pull_requests()` with additional filter parameters
- Add GitHub CLI search query construction
- Parse and validate filter combinations

Technical considerations:
- Use GitHub's search syntax for complex queries
- Validate filter combinations are supported by GitHub
- Handle search result pagination
- Return empty results gracefully when no matches

Expected outcome: Powerful PR discovery for audit and backfill operations

- [ ] Phase 5: Rate limit management

Implement comprehensive rate limit handling:
- Check current rate limit status before queries
- Automatic backoff when approaching limits
- Queue requests when limit exceeded
- Inform users of rate limit status

Files to create:
- `src/claudestep/infrastructure/github/rate_limiter.py`

Files to modify:
- `operations.py` - Integrate rate limiter into all GitHub calls
- Add rate limit status to error messages

Technical considerations:
- Use `gh api rate_limit` to check current status
- Implement exponential backoff with jitter
- Respect rate limit reset timestamps
- Provide user feedback during rate limit waits
- Allow configuration of rate limit thresholds

Expected outcome: Reliable GitHub operations that never hit rate limits unexpectedly

- [ ] Phase 6: Error handling and retries

Add sophisticated error handling for GitHub API operations:
- Distinguish transient vs permanent failures
- Automatic retries with exponential backoff
- Network timeout handling
- Graceful degradation on GitHub outages

Files to modify:
- `operations.py` - Wrap all GitHub calls with retry logic
- `src/claudestep/domain/exceptions.py` - Add GitHub-specific exception types

Technical considerations:
- Retry on 502, 503, 504 HTTP errors
- Don't retry on 401, 403, 404 (permanent failures)
- Use exponential backoff: 1s, 2s, 4s, 8s delays
- Log retry attempts for debugging
- Provide clear error messages with resolution guidance

Expected outcome: Robust GitHub operations that handle transient failures automatically

- [ ] Phase 7: Query result pagination

Implement proper pagination for large result sets:
- Handle GitHub's 100-item page limit
- Automatic page fetching with streaming results
- Configurable page size
- Total result count estimation

Files to modify:
- `operations.py` - Add pagination support to `list_pull_requests()`
- Yield results incrementally for memory efficiency
- Add `max_results` parameter to limit total items

Technical considerations:
- Use GitHub CLI's `--limit` parameter
- Detect when more pages are available
- Stream results to avoid loading thousands of PRs in memory
- Provide progress feedback for multi-page queries

Expected outcome: Efficient handling of repositories with hundreds/thousands of PRs

- [ ] Phase 8: Validation

Test GitHub PR query operations comprehensively:
- Unit tests for query construction, JSON parsing, domain model creation
- Integration tests with mock GitHub CLI responses
- Rate limit simulation tests
- Pagination tests with large result sets
- Error handling tests (network failures, API errors, rate limits)
- Cache correctness tests (TTL, invalidation, bypass)
- Batch query tests (concurrency, partial failures)

Run all tests:
```bash
pytest tests/unit/infrastructure/github/test_operations.py
pytest tests/integration/infrastructure/github/test_github_queries.py
pytest tests/unit/infrastructure/github/test_cache.py
pytest tests/unit/infrastructure/github/test_rate_limiter.py
```

Success criteria:
- All tests pass
- Rate limiter prevents API limit exhaustion
- Caching reduces redundant API calls
- Batch queries handle 100+ PRs efficiently
- Error handling gracefully manages failures
- Pagination works with repositories of any size
- Domain models maintain type safety
