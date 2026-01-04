"""Service Layer - Organized by architectural role

Core: Foundational services providing basic operations
Composite: Higher-level orchestration services that use core services
"""
# Re-export all services for convenience
from claudechain.services.core import (
    PRService,
    TaskService,
    ProjectService,
    AssigneeService,
)
from claudechain.services.composite import (
    StatisticsService,
    find_project_artifacts,
    get_artifact_metadata,
    find_in_progress_tasks,
    get_assignee_assignments,
    ProjectArtifact,
    TaskMetadata,
)

__all__ = [
    # Core
    "PRService",
    "TaskService",
    "ProjectService",
    "AssigneeService",
    # Composite
    "StatisticsService",
    "find_project_artifacts",
    "get_artifact_metadata",
    "find_in_progress_tasks",
    "get_assignee_assignments",
    "ProjectArtifact",
    "TaskMetadata",
]
