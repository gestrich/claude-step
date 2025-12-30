# Fix Timestamp Timezone Handling in Metadata

## Background

Currently, timestamps in the metadata JSON are stored without timezone information (e.g., `"2025-12-29T23:47:49.299060"`). This causes issues when comparing timestamps in Python because:

1. Stored timestamps are parsed as naive datetimes (no timezone)
2. Code creates timezone-aware datetimes for comparisons (e.g., `datetime.now(timezone.utc)`)
3. Python cannot compare naive and timezone-aware datetimes, causing errors like:
   ```
   Warning: Failed to collect stats for project e2e-test-project: can't compare offset-naive and offset-aware datetimes
   ```

**Best Practice:** Store all timestamps in ISO 8601 format WITH timezone information:
- Correct: `"2025-12-29T23:47:49.299060Z"` or `"2025-12-29T23:47:49.299060+00:00"`
- Wrong: `"2025-12-29T23:47:49.299060"` (missing timezone)

This makes timestamps:
- **Unambiguous** - Clear what timezone they represent
- **ISO 8601 compliant** - Standard format
- **Interoperable** - Works across systems
- **Self-describing** - Data itself indicates timezone
- **Bug-preventing** - Python parses them as timezone-aware automatically

**User Requirements:**
- No backward compatibility needed
- Delete existing metadata in the repo
- Regenerate with correct format
- All timestamps must be timezone-aware going forward

## Phases

- [x] Phase 1: Update domain models to parse timezone-aware datetimes ✅ **COMPLETED**

Fix the domain model parsing to handle both old (naive) and new (timezone-aware) formats during transition, but always produce timezone-aware datetimes:

Files modified:
- `src/claudestep/domain/models.py` - Updated all dataclasses to use timezone-aware parsing:
  - Added `parse_iso_timestamp()` helper function
  - Updated `PullRequest.from_dict()`
  - Updated `HybridProjectMetadata.from_dict()`
  - Updated `AIOperation.from_dict()`
  - Updated `AITask.from_dict()`
  - Updated `TaskMetadata.from_dict()`
  - Updated `ProjectMetadata.from_dict()`

Technical implementation:
- Added helper function `parse_iso_timestamp()` that:
  - Handles both "Z" suffix and "+00:00" timezone formats
  - Automatically adds `timezone.utc` to naive timestamps for backward compatibility
  - Always returns timezone-aware datetime objects
- All `from_dict()` methods now use `parse_iso_timestamp()` instead of direct `datetime.fromisoformat()`
- Added `timezone` to imports: `from datetime import datetime, timezone`

Test results:
- ✅ All 32 domain model tests passed (`tests/unit/domain/test_hybrid_metadata_models.py`)
- ✅ All 57 statistics service tests passed (`tests/unit/services/test_statistics_service.py`)
- ✅ No timezone comparison errors observed

Expected outcome: ✅ Domain models always produce timezone-aware datetimes regardless of input format

- [x] Phase 2: Update metadata writing to always include timezone ✅ **COMPLETED**

Fix all code that creates timestamps to use ISO 8601 with timezone:

Files modified:
- `src/claudestep/infrastructure/metadata/github_metadata_store.py` - Updated `save_project()` method (line 368)
- `src/claudestep/cli/commands/finalize.py` - Updated PR metadata creation (lines 246, 259, 276)
- `src/claudestep/services/metadata_service.py` - Updated `save_project()` method (line 70)
- `src/claudestep/domain/models.py` - Updated `create_empty()` methods (lines 787, 880, 1218)
- `src/claudestep/cli/commands/statistics.py` - Updated report generation timestamp (line 89)

Technical implementation:
- Added `timezone` to imports in all affected files
- Replaced all `datetime.now()` with `datetime.now(timezone.utc)`
- Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)`
- All timestamp fields now serialize with `+00:00` timezone suffix via `.isoformat()`
- Consistent timezone-aware timestamp generation across the codebase

Test results:
- ✅ All 32 domain model tests passed (`tests/unit/domain/test_hybrid_metadata_models.py`)
- ✅ All 57 statistics service tests passed (`tests/unit/services/test_statistics_service.py`)
- ✅ Manual verification: `HybridProjectMetadata.create_empty('test').last_updated.isoformat()` produces `"2025-12-30T21:09:49.002316+00:00"`

Expected outcome: ✅ All new metadata written with proper timezone information (`+00:00` format)

- [ ] Phase 3: Update tests to use timezone-aware datetimes

Fix all tests that create datetime objects for assertions:

Files to modify:
- `tests/unit/domain/test_hybrid_metadata_models.py`
- `tests/unit/infrastructure/metadata/test_github_metadata_store.py`
- `tests/unit/services/test_metadata_service.py`
- `tests/unit/services/test_statistics_service.py`
- Any other tests using datetime objects

Technical considerations:
- Replace `datetime(2025, 12, 30, ...)` with `datetime(2025, 12, 30, ..., tzinfo=timezone.utc)`
- Update test fixtures with timezone-aware timestamps
- Ensure test assertions compare timezone-aware datetimes
- Run tests to verify no comparison errors

Expected outcome: All tests pass with timezone-aware datetimes

- [ ] Phase 4: Delete existing metadata in claudestep-metadata branch

Delete all existing metadata files to force regeneration with correct format:

Files to delete (in `claudestep-metadata` branch):
- `projects/e2e-test-project.json`
- Any other `projects/*.json` files

Technical considerations:
- Use GitHub API to delete files (or manual PR)
- Keep the branch structure (`projects/` directory)
- Keep `README.md` if it exists
- This is a one-time destructive operation
- No backup needed per user requirements

Commands:
```bash
# Checkout metadata branch
git fetch origin claudestep-metadata
git checkout claudestep-metadata

# Delete project metadata files
rm -rf projects/*.json

# Commit deletion
git add projects/
git commit -m "Delete legacy metadata with naive timestamps

Will be regenerated with timezone-aware timestamps per ISO 8601 best practices."

# Push
git push origin claudestep-metadata

# Return to main
git checkout main
```

Expected outcome: Clean slate for metadata generation

- [ ] Phase 5: Add validation to prevent naive datetimes

Add runtime checks to catch naive datetime bugs early:

Files to modify:
- `src/claudestep/domain/models.py` - Add `__post_init__` validation to dataclasses
- Raise error if any datetime field is naive (missing tzinfo)

Technical considerations:
- Use `__post_init__` in dataclasses to validate after construction
- Check `dt.tzinfo is not None` for all datetime fields
- Raise `ValueError` with clear message if naive datetime detected
- This prevents bugs from being introduced in future

Example validation:
```python
@dataclass
class PullRequest:
    created_at: datetime
    merged_at: Optional[datetime] = None

    def __post_init__(self):
        """Validate that all datetimes are timezone-aware"""
        if self.created_at.tzinfo is None:
            raise ValueError(f"created_at must be timezone-aware, got: {self.created_at}")
        if self.merged_at and self.merged_at.tzinfo is None:
            raise ValueError(f"merged_at must be timezone-aware, got: {self.merged_at}")
```

Expected outcome: Future code cannot create naive datetimes in domain models

- [ ] Phase 6: Document timezone handling convention

Add documentation about timezone handling to architecture docs:

Files to modify:
- `docs/architecture/python-code-style.md` - Add "Datetime and Timezone Handling" section
- `docs/architecture/metadata-schema.md` - Update timestamp field documentation

Content to add:
- Always use timezone-aware datetimes (never naive)
- Always use UTC for storage and internal operations
- ISO 8601 format with timezone for JSON serialization
- Example of correct usage
- Common pitfalls to avoid

Expected outcome: Clear guidance for future development

- [ ] Phase 7: Validation

Test the complete timezone handling fix:

**Unit tests:**
```bash
pytest tests/unit/domain/test_hybrid_metadata_models.py -v
pytest tests/unit/infrastructure/metadata/test_github_metadata_store.py -v
pytest tests/unit/services/test_statistics_service.py -v
```

**Integration tests:**
```bash
pytest tests/integration/ -v
```

**Manual verification:**
1. Run finalize command to create new metadata
2. Verify JSON contains timestamps with timezone: `"created_at": "..+00:00"` or `"...Z"`
3. Run statistics command with `--repo gestrich/claude-step`
4. Verify no timezone comparison errors
5. Verify team member stats are collected correctly

**Success criteria:**
- All unit tests pass
- All integration tests pass
- Statistics command runs without timezone errors
- Team member stats show correct merged/open PR counts
- All timestamps in metadata JSON have timezone information
- Domain models reject naive datetimes in validation
- No `can't compare offset-naive and offset-aware datetimes` errors
