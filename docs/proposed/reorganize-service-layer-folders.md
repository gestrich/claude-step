# Reorganize Service Layer Folder Structure

## Background

The current service layer architecture has emerged organically with all services living in a flat `src/claudestep/services/` directory. However, the dependency analysis reveals a clear two-level hierarchy:

- **Core Services**: Foundational services that provide basic operations (e.g., `PROperationsService`, `TaskManagementService`, `ReviewerManagementService`, `ProjectDetectionService`)
- **Composite Services**: Higher-level orchestration services that use multiple core services (e.g., `StatisticsService`, `ArtifactOperationsService`)

The flat structure makes it difficult to:
1. Understand service hierarchy at a glance
2. Prevent circular dependencies
3. Identify which services are foundational vs. composite
4. Navigate the codebase as it grows

This refactoring will organize services into two subdirectories that reflect their architectural role, making the dependency hierarchy explicit and preventing inappropriate cross-layer dependencies.

**User Requirements:**
- Break up folders reflecting level of services
- Two levels: core and composite
- Make the architecture visible in the folder structure
- Keep naming simple and unambiguous

**Current Structure:**
```
src/claudestep/services/
├── __init__.py
├── artifact_operations_service.py
├── pr_operations_service.py
├── project_detection_service.py
├── reviewer_management_service.py
├── statistics_service.py
└── task_management_service.py
```

**Proposed Structure:**
```
src/claudestep/services/
├── __init__.py
├── core/                           # Foundational services
│   ├── __init__.py
│   ├── pr_operations_service.py
│   ├── project_detection_service.py
│   ├── reviewer_management_service.py
│   └── task_management_service.py
└── composite/                      # Higher-level orchestration
    ├── __init__.py
    ├── artifact_operations_service.py
    └── statistics_service.py
```

## Phases

- [ ] Phase 1: Create new subdirectory structure

**Tasks:**
1. Create `src/claudestep/services/core/` directory
2. Create `src/claudestep/services/composite/` directory
3. Create `__init__.py` in each new subdirectory (empty for now)

**Files to create:**
- `src/claudestep/services/core/__init__.py`
- `src/claudestep/services/composite/__init__.py`

**Expected outcome:**
- New folder structure exists alongside current files
- No code changes yet, just scaffolding

---

- [ ] Phase 2: Move core services

**Tasks:**
1. Move `pr_operations_service.py` to `services/core/`
2. Move `task_management_service.py` to `services/core/`
3. Move `project_detection_service.py` to `services/core/`
4. Move `reviewer_management_service.py` to `services/core/`
5. Update `services/core/__init__.py` to export all four services
6. Create compatibility shims in old locations

**Files to modify:**
- Move: `src/claudestep/services/pr_operations_service.py` → `src/claudestep/services/core/pr_operations_service.py`
- Move: `src/claudestep/services/task_management_service.py` → `src/claudestep/services/core/task_management_service.py`
- Move: `src/claudestep/services/project_detection_service.py` → `src/claudestep/services/core/project_detection_service.py`
- Move: `src/claudestep/services/reviewer_management_service.py` → `src/claudestep/services/core/reviewer_management_service.py`
- Update: `src/claudestep/services/core/__init__.py`
  ```python
  """Core services - Foundational services providing basic operations."""
  from claudestep.services.core.pr_operations_service import PROperationsService
  from claudestep.services.core.task_management_service import TaskManagementService
  from claudestep.services.core.project_detection_service import ProjectDetectionService
  from claudestep.services.core.reviewer_management_service import ReviewerManagementService

  __all__ = [
      "PROperationsService",
      "TaskManagementService",
      "ProjectDetectionService",
      "ReviewerManagementService",
  ]
  ```
- Create compatibility shims for each service in old locations (one per file)
  ```python
  """Deprecated: Import from claudestep.services.core instead."""
  from claudestep.services.core.<service_name> import <ServiceClass>

  __all__ = ["<ServiceClass>"]
  ```

**Technical considerations:**
- Keep compatibility shims to avoid breaking existing imports
- Will remove shims in Phase 4 after updating all imports

**Expected outcome:**
- All core services available from both old and new paths
- No breaking changes to existing code

---

- [ ] Phase 3: Move composite services

**Tasks:**
1. Move `statistics_service.py` to `services/composite/`
2. Move `artifact_operations_service.py` to `services/composite/`
3. Update `services/composite/__init__.py` to export both services
4. Create compatibility shims in old locations

**Files to modify:**
- Move: `src/claudestep/services/statistics_service.py` → `src/claudestep/services/composite/statistics_service.py`
- Move: `src/claudestep/services/artifact_operations_service.py` → `src/claudestep/services/composite/artifact_operations_service.py`
- Update: `src/claudestep/services/composite/__init__.py`
  ```python
  """Composite services - Higher-level orchestration services that use core services."""
  from claudestep.services.composite.statistics_service import StatisticsService
  from claudestep.services.composite.artifact_operations_service import (
      find_project_artifacts,
      get_artifact_metadata,
      find_in_progress_tasks,
      get_reviewer_assignments,
      ProjectArtifact,
      TaskMetadata,
  )

  __all__ = [
      "StatisticsService",
      "find_project_artifacts",
      "get_artifact_metadata",
      "find_in_progress_tasks",
      "get_reviewer_assignments",
      "ProjectArtifact",
      "TaskMetadata",
  ]
  ```
- Create compatibility shims for each service in old locations

**Expected outcome:**
- Composite services available from both old and new paths
- All services moved to new structure
- Old paths still work via shims

---

- [ ] Phase 4: Update all imports to use new structure

**Tasks:**
1. Update CLI command imports in `src/claudestep/cli/commands/`
2. Update test imports in `tests/unit/services/`
3. Update test imports in `tests/integration/cli/commands/`
4. Update any other internal imports

**Files to search and update:**
- Search for: `from claudestep.services import`
- Search for: `from claudestep.services.pr_operations_service import`
- Search for: `from claudestep.services.task_management_service import`
- Search for: `from claudestep.services.reviewer_management_service import`
- Search for: `from claudestep.services.project_detection_service import`
- Search for: `from claudestep.services.statistics_service import`
- Search for: `from claudestep.services.artifact_operations_service import`

**Replace with new structure:**
- `from claudestep.services.core import PROperationsService, TaskManagementService, ProjectDetectionService, ReviewerManagementService`
- `from claudestep.services.composite import StatisticsService, find_project_artifacts, ...`

**Technical considerations:**
- Use global search/replace to find all import statements
- Update one service at a time to minimize errors
- Run tests after each service's imports are updated

**Expected outcome:**
- All code uses new import paths
- Tests still pass
- Compatibility shims no longer needed

---

- [ ] Phase 5: Remove compatibility shims

**Tasks:**
1. Delete old service files in `src/claudestep/services/` (the shims)
2. Update `src/claudestep/services/__init__.py` to export from new locations

**Files to delete:**
- `src/claudestep/services/pr_operations_service.py` (shim)
- `src/claudestep/services/task_management_service.py` (shim)
- `src/claudestep/services/project_detection_service.py` (shim)
- `src/claudestep/services/reviewer_management_service.py` (shim)
- `src/claudestep/services/statistics_service.py` (shim)
- `src/claudestep/services/artifact_operations_service.py` (shim)

**Files to update:**
- Update: `src/claudestep/services/__init__.py`
  ```python
  """Service Layer - Organized by architectural role

  Core: Foundational services providing basic operations
  Composite: Higher-level orchestration services that use core services
  """
  # Re-export all services for convenience
  from claudestep.services.core import (
      PROperationsService,
      TaskManagementService,
      ProjectDetectionService,
      ReviewerManagementService,
  )
  from claudestep.services.composite import (
      StatisticsService,
      find_project_artifacts,
      get_artifact_metadata,
      find_in_progress_tasks,
      get_reviewer_assignments,
      ProjectArtifact,
      TaskMetadata,
  )

  __all__ = [
      # Core
      "PROperationsService",
      "TaskManagementService",
      "ProjectDetectionService",
      "ReviewerManagementService",
      # Composite
      "StatisticsService",
      "find_project_artifacts",
      "get_artifact_metadata",
      "find_in_progress_tasks",
      "get_reviewer_assignments",
      "ProjectArtifact",
      "TaskMetadata",
  ]
  ```

**Expected outcome:**
- Clean folder structure with no shims
- Services still importable from `claudestep.services` for convenience
- Clear architectural layers visible in directory structure

---

- [ ] Phase 6: Update architecture documentation

**Tasks:**
1. Update `docs/architecture/architecture.md` to reflect new structure
2. Add section explaining the two-level organization
3. Update module organization diagrams

**Files to modify:**
- `docs/architecture/architecture.md` - Add new section:
  ```markdown
  ### Service Layer Organization

  Services are organized into two levels:

  **Core** (`services/core/`):
  - Foundational services providing basic operations
  - Examples: PROperationsService, TaskManagementService, ReviewerManagementService, ProjectDetectionService
  - These services can be used independently or composed together

  **Composite** (`services/composite/`):
  - Higher-level orchestration services
  - Examples: StatisticsService, ArtifactOperationsService
  - Depend on multiple core services
  - Coordinate complex multi-service operations
  ```

**Expected outcome:**
- Documentation reflects new folder structure
- Clear explanation of the two-level organization
- Examples of which services belong in each level

---

- [ ] Phase 7: Update test structure to match service structure

**Tasks:**
1. Create matching subdirectories in `tests/unit/services/`
2. Move test files to match service locations
3. Update test discovery patterns if needed

**Files to reorganize:**
- Create: `tests/unit/services/core/`
- Create: `tests/unit/services/composite/`
- Move: `tests/unit/services/test_pr_operations.py` → `tests/unit/services/core/test_pr_operations_service.py`
- Move: `tests/unit/services/test_task_management.py` → `tests/unit/services/core/test_task_management_service.py`
- Move: `tests/unit/services/test_reviewer_management.py` → `tests/unit/services/core/test_reviewer_management_service.py`
- Move: `tests/unit/services/test_project_detection.py` → `tests/unit/services/core/test_project_detection_service.py`
- Move: `tests/unit/services/test_statistics_service.py` → `tests/unit/services/composite/test_statistics_service.py`
- Move: `tests/unit/services/test_artifact_operations.py` → `tests/unit/services/composite/test_artifact_operations_service.py`

**Technical considerations:**
- pytest should auto-discover tests in new locations
- May need to update test import paths to match new service locations
- Verify pytest still runs all tests with `pytest tests/unit/services/ -v`

**Expected outcome:**
- Test structure mirrors service structure
- Easy to find tests for any service
- All tests still pass

---

- [ ] Phase 8: Validation

**Testing approach:**
1. Run full unit test suite: `PYTHONPATH=src:scripts pytest tests/unit/ -v`
2. Run full integration test suite: `PYTHONPATH=src:scripts pytest tests/integration/ -v`
3. Verify test coverage hasn't decreased: `PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing`
4. Manual verification:
   - Services can be imported from new paths: `from claudestep.services.base import PROperationsService`
   - Services can be imported from convenience path: `from claudestep.services import PROperationsService`
   - Test files match service file locations

**Success criteria:**
- ✅ All 493 tests pass
- ✅ Coverage remains at 85%+
- ✅ No import errors in CLI commands
- ✅ No import errors in tests
- ✅ Folder structure clearly shows architectural layers
- ✅ Documentation updated to reflect new structure

**Commands to run:**
```bash
# Unit and integration tests
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ -v

# Coverage check
PYTHONPATH=src:scripts pytest tests/unit/ tests/integration/ --cov=src/claudestep --cov-report=term-missing --cov-fail-under=85

# Verify import paths work
python3 -c "from claudestep.services.core import PROperationsService, TaskManagementService; print('✅ Core imports work')"
python3 -c "from claudestep.services.composite import StatisticsService; print('✅ Composite imports work')"
python3 -c "from claudestep.services import PROperationsService, TaskManagementService, StatisticsService; print('✅ Convenience imports work')"
```

**Expected outcome:**
- All tests pass
- Coverage maintained
- Clean architectural organization visible in folder structure
- Easy to understand service hierarchy at a glance
