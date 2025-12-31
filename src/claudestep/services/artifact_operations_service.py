"""Deprecated: Import from claudestep.services.composite instead."""
from claudestep.services.composite.artifact_service import (
    find_project_artifacts,
    get_artifact_metadata,
    find_in_progress_tasks,
    get_reviewer_assignments,
    ProjectArtifact,
    TaskMetadata,
    parse_task_index_from_name,
)

# Re-export infrastructure functions for backward compatibility with tests
from claudestep.infrastructure.github.operations import download_artifact_json, gh_api_call

__all__ = [
    "find_project_artifacts",
    "get_artifact_metadata",
    "find_in_progress_tasks",
    "get_reviewer_assignments",
    "ProjectArtifact",
    "TaskMetadata",
    "parse_task_index_from_name",
    "download_artifact_json",
    "gh_api_call",
]
