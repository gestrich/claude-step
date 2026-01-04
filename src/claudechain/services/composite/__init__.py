"""Composite services - Higher-level orchestration services that use core services."""
from claudechain.services.composite.statistics_service import StatisticsService
from claudechain.services.composite.auto_start_service import AutoStartService
from claudechain.services.composite.workflow_service import WorkflowService
from claudechain.services.composite.artifact_service import (
    find_project_artifacts,
    get_artifact_metadata,
    find_in_progress_tasks,
    get_assignee_assignments,
    ProjectArtifact,
    TaskMetadata,
    parse_task_index_from_name,
)

__all__ = [
    "StatisticsService",
    "AutoStartService",
    "WorkflowService",
    "find_project_artifacts",
    "get_artifact_metadata",
    "find_in_progress_tasks",
    "get_assignee_assignments",
    "ProjectArtifact",
    "TaskMetadata",
    "parse_task_index_from_name",
]
