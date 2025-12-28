# Test Structure Reorganization

## Overview

This document outlines the plan to reorganize ClaudeStep's test structure to align with Python ecosystem best practices by clearly separating unit, integration, and e2e tests.

## Current State

```
tests/
├── unit/              # Contains both unit AND integration tests (CLI commands)
│   ├── domain/
│   ├── infrastructure/
│   ├── application/
│   └── cli/          # ← Integration tests (mock external deps, test multiple components)
├── e2e/              # True E2E tests (real GitHub API, real workflows)
└── builders/         # Test helpers/factories
```

**Problem:**
- CLI tests in `tests/unit/cli/` are actually integration tests (test command orchestration across multiple components)
- Naming doesn't match actual test types, causing confusion
- Doesn't align with Python ecosystem conventions
- Documentation acknowledges "CLI integration tests" but structure doesn't reflect this

## Target State

```
tests/
├── unit/              # Pure unit tests (isolated functions, minimal mocking)
│   ├── domain/
│   ├── infrastructure/
│   └── application/
├── integration/       # Integration tests (components together, mocked external deps)
│   └── cli/
│       ├── commands/
│       │   ├── test_prepare.py
│       │   ├── test_finalize.py
│       │   ├── test_discover.py
│       │   ├── test_discover_ready.py
│       │   ├── test_statistics.py
│       │   ├── test_add_cost_comment.py
│       │   ├── test_extract_cost.py
│       │   ├── test_notify_pr.py
│       │   └── test_prepare_summary.py
│       └── __init__.py
├── e2e/               # True E2E tests (real services, production-like environment)
└── builders/          # Test helpers/factories
```

## Benefits

1. **Clarity**: Test type is obvious from directory structure
2. **Alignment**: Matches Python ecosystem best practices ([pytest docs](https://docs.pytest.org/en/stable/explanation/goodpractices.html))
3. **Selective Execution**: Easy to run only unit tests, or skip slow E2E tests
4. **Documentation Accuracy**: Structure matches what docs describe
5. **CI Optimization**: Can run unit tests on every commit, integration tests on PR, E2E manually

## Implementation Phases

### Phase 1: Create Integration Test Directory Structure
- [ ] Create `tests/integration/` directory
- [ ] Create `tests/integration/__init__.py`
- [ ] Create `tests/integration/cli/` directory
- [ ] Create `tests/integration/cli/__init__.py`
- [ ] Create `tests/integration/cli/commands/` directory
- [ ] Create `tests/integration/cli/commands/__init__.py`
- [ ] Verify directory structure is correct

**Success Criteria:**
- Directory structure exists
- All `__init__.py` files created
- `ls tests/integration/cli/commands/` shows empty directory

**Estimated Time:** 5 minutes

---

### Phase 2: Move CLI Tests to Integration
- [ ] Move `tests/unit/cli/commands/test_prepare.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_finalize.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_discover.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_discover_ready.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_statistics.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_add_cost_comment.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_extract_cost.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_notify_pr.py` → `tests/integration/cli/commands/`
- [ ] Move `tests/unit/cli/commands/test_prepare_summary.py` → `tests/integration/cli/commands/`
- [ ] Delete empty `tests/unit/cli/` directory structure
- [ ] Run tests to verify imports still work: `pytest tests/integration/ -v`

**Success Criteria:**
- All CLI command tests moved to `tests/integration/cli/commands/`
- Old `tests/unit/cli/` directory removed
- Tests run successfully from new location
- No import errors

**Estimated Time:** 10 minutes

---

### Phase 3: Add Pytest Markers and Update Configuration
- [ ] Add pytest markers to `pyproject.toml`:
  ```toml
  [tool.pytest.ini_options]
  markers = [
      "unit: Fast unit tests with no external dependencies",
      "integration: Integration tests with mocked external services",
      "e2e: End-to-end tests using real GitHub API and workflows",
      "slow: Tests that take significant time to run",
  ]
  ```
- [ ] Verify markers work: `pytest --markers`
- [ ] Test selective execution:
  - [ ] `pytest tests/unit/ -v` (should run only unit tests)
  - [ ] `pytest tests/integration/ -v` (should run only integration tests)
  - [ ] `pytest tests/e2e/ -v` (should run only e2e tests)
  - [ ] `pytest tests/unit/ tests/integration/ -v` (should run unit + integration)

**Success Criteria:**
- Markers defined in `pyproject.toml`
- Can run each test type independently
- All test paths work correctly
- No test failures

**Estimated Time:** 10 minutes

---

### Phase 4: Update Documentation and CI Workflows
- [ ] Update `docs/architecture/testing-guide.md`:
  - [ ] Update directory structure example to show `tests/integration/`
  - [ ] Update "Test Architecture" section to clarify unit vs integration
  - [ ] Add examples of running different test types
- [ ] Update `docs/architecture/tests.md`:
  - [ ] Update directory structure diagram
  - [ ] Revise "Integration vs Unit Test Boundaries" section
  - [ ] Update line 339 to reflect new structure
- [ ] Update `.github/workflows/test.yml`:
  - [ ] Rename job from "test" to "unit-and-integration-tests"
  - [ ] Update workflow name from "Unit Tests" to "Unit & Integration Tests"
  - [ ] Change test command to: `pytest tests/unit/ tests/integration/ -v`
  - [ ] Update comments to reflect running both test types
- [ ] Update `tests/e2e/README.md`:
  - [ ] Update reference to integration tests location
  - [ ] Clarify what should be in e2e vs integration
- [ ] Update `README.md` (if it mentions test structure)

**Success Criteria:**
- All documentation reflects new structure
- CI workflow runs both unit and integration tests
- No broken documentation links
- Documentation examples are accurate

**Estimated Time:** 20 minutes

---

### Phase 5: Run All Tests and Verify CI
- [ ] Run all tests locally:
  - [ ] `pytest tests/unit/ -v` (expect ~400+ tests, all pass)
  - [ ] `pytest tests/integration/ -v` (expect ~19 tests from CLI commands, all pass)
  - [ ] `pytest tests/e2e/ -v` (optional, takes 5-10 min)
  - [ ] `pytest tests/unit/ tests/integration/ -v --cov=src/claudestep --cov-report=term-missing` (verify coverage ≥70%)
- [ ] Commit changes with message:
  ```
  Reorganize tests: separate unit and integration tests

  - Move CLI command tests from tests/unit/cli/ to tests/integration/cli/
  - Add pytest markers for unit, integration, e2e test types
  - Update CI to run unit + integration tests together
  - Update documentation to reflect new test structure

  This aligns with Python ecosystem best practices and makes test
  types clearer from directory structure alone.
  ```
- [ ] Push to branch and create PR
- [ ] Watch CI workflows:
  - [ ] `.github/workflows/test.yml` should pass (unit + integration)
  - [ ] Verify coverage report shows ≥70%
  - [ ] Check no import errors or path issues
- [ ] Verify coverage report is generated correctly
- [ ] Confirm all CI checks are green

**Success Criteria:**
- All local test runs pass
- CI workflow completes successfully
- Coverage meets threshold (≥70%)
- No regressions in test count or coverage
- PR is ready for review

**Estimated Time:** 15 minutes

---

## Total Estimated Time

**~60 minutes** (1 hour)

## Rollback Plan

If issues arise, rollback is simple:
1. Revert the commit: `git revert HEAD`
2. Or move files back: `git mv tests/integration/cli tests/unit/cli`
3. Restore `pyproject.toml` and workflows from git history

## Test Count Verification

**Before:**
- Unit tests: ~493 tests (includes CLI integration tests)
- E2E tests: ~3-4 tests

**After:**
- Unit tests: ~474 tests (domain + infrastructure + application)
- Integration tests: ~19 tests (CLI commands)
- E2E tests: ~3-4 tests
- **Total: Same number of tests, just reorganized**

## References

- [pytest Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [Pytest Best Practices - Test Organization](https://pytest-with-eric.com/pytest-best-practices/pytest-organize-tests/)
- [Typical Python Test Directory Structure](https://gist.github.com/tasdikrahman/2bdb3fb31136a3768fac)

## Notes

- This is purely organizational - no test code changes required
- Import paths remain the same (pytest handles test discovery)
- Fixtures in `tests/conftest.py` remain accessible to all tests
- Can add `tests/integration/conftest.py` later for integration-specific fixtures
