# Consolidate Pytest Configuration

## Overview

Consolidate all pytest configuration from `pytest.ini` into `pyproject.toml` and remove the `pytest.ini` file to maintain a single source of truth for project configuration.

## Problem

Currently, pytest configuration is split across two files:
- `pytest.ini` - Contains pytest-specific settings, markers, and test options
- `pyproject.toml` - Contains some pytest settings (test paths, discovery patterns) and coverage settings

This duplication creates:
- Potential for conflicts between the two files
- Confusion about which file controls which settings
- Maintenance overhead when updating test configuration
- Non-standard approach (modern Python projects use `pyproject.toml`)

## Proposed Solution

Migrate all pytest configuration to `pyproject.toml` and delete `pytest.ini`.

### Changes Required

#### 1. Update `pyproject.toml`

Replace the existing `[tool.pytest.ini_options]` section with:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
    "--disable-warnings",
    "--cov=src/claudestep",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=70",
]
markers = [
    "integration: End-to-end integration tests (may be slow)",
    "unit: Fast unit tests",
]
```

#### 2. Delete `pytest.ini`

Remove the file entirely since all configuration will be in `pyproject.toml`.

## Benefits

1. **Single source of truth** - All project configuration in one standardized file
2. **Modern Python standard** - Aligns with PEP 518/621 recommendations
3. **Reduced duplication** - No risk of conflicting settings between files
4. **Easier maintenance** - One place to update test configuration
5. **Clearer project structure** - Fewer config files at project root

## Testing Plan

1. Make the changes described above
2. Run `pytest` to verify all tests still pass
3. Run `pytest -v --co` to verify test collection still works correctly
4. Run `pytest --markers` to verify custom markers are recognized
5. Verify coverage reports are still generated as expected

## Risks

**Low Risk** - This is a configuration migration with no code changes:
- Pytest fully supports `pyproject.toml` configuration
- The settings remain identical, just in a different file
- Easy to revert if any issues arise

## Implementation Steps

### Phase 1: Update pyproject.toml with consolidated pytest settings ✅

**Status:** Completed on 2025-12-28

**Changes made:**
- Updated `[tool.pytest.ini_options]` section in `pyproject.toml` with all settings from `pytest.ini`
- Added `addopts` array with all command-line options (verbose, strict-markers, coverage settings, etc.)
- Added `markers` array with custom test markers (integration, unit)
- Deleted `pytest.ini` file
- Verified all tests pass and coverage reports generate correctly

**Technical notes:**
- Configuration migration was successful - all 494 passing tests still pass
- Coverage reporting works correctly (84.78% total coverage)
- Custom markers are properly recognized by pytest
- No breaking changes or compatibility issues detected

### Phase 2: Delete pytest.ini

1. ~~Update `pyproject.toml` with consolidated pytest settings~~
2. ~~Delete `pytest.ini`~~
3. ~~Run full test suite to verify functionality~~
4. Commit changes with message describing the consolidation

## References

- [PEP 518 - Specifying Minimum Build System Requirements](https://peps.python.org/pep-0518/)
- [Pytest Configuration Documentation](https://docs.pytest.org/en/stable/reference/customize.html)
