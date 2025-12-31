"""Service Layer utilities for artifact operations.

Follows Service Layer pattern (Fowler, PoEAA) - provides a unified interface for
working with GitHub workflow artifacts that contain task metadata. Eliminates code
duplication across reviewer_management, task_management, and statistics_collector
modules. Note: These are utility functions supporting the Service Layer rather than
a full service class.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.infrastructure.github.operations import download_artifact_json, gh_api_call


@dataclass
class TaskMetadata:
    """Metadata from a task artifact"""

    task_index: int
    task_description: str
    project: str
    branch_name: str
    reviewer: str
    created_at: datetime
    workflow_run_id: int
    pr_number: int
    main_task_cost_usd: float = 0.0
    pr_summary_cost_usd: float = 0.0
    total_cost_usd: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "TaskMetadata":
        """Parse from artifact JSON

        Args:
            data: Dictionary containing artifact metadata

        Returns:
            TaskMetadata instance
        """
        return cls(
            task_index=data["task_index"],
            task_description=data["task_description"],
            project=data["project"],
            branch_name=data["branch_name"],
            reviewer=data["reviewer"],
            created_at=datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            ),
            workflow_run_id=data["workflow_run_id"],
            pr_number=data["pr_number"],
            main_task_cost_usd=data.get("main_task_cost_usd", 0.0),
            pr_summary_cost_usd=data.get("pr_summary_cost_usd", 0.0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
        )


@dataclass
class ProjectArtifact:
    """An artifact with its metadata"""

    artifact_id: int
    artifact_name: str
    workflow_run_id: int
    metadata: Optional[TaskMetadata] = None

    @property
    def task_index(self) -> Optional[int]:
        """Convenience accessor for task index"""
        if self.metadata:
            return self.metadata.task_index
        # Fallback: parse from name
        return parse_task_index_from_name(self.artifact_name)


# ============================================================
# Public API functions
# ============================================================


def find_project_artifacts(
    repo: str,
    project: str,
    label: str = "claudestep",
    pr_state: str = "all",
    limit: int = 50,
    download_metadata: bool = False,
) -> List[ProjectArtifact]:
    """Find all artifacts for a project based on PRs with the given label.

    This is the primary API for getting project artifacts.

    Args:
        repo: GitHub repository (owner/name)
        project: Project name to filter artifacts
        label: GitHub label to filter PRs (default: "claudestep")
        pr_state: PR state filter - "open", "merged", or "all"
        limit: Maximum number of workflow runs to check
        download_metadata: Whether to download full metadata JSON

    Returns:
        List of ProjectArtifact objects, optionally with metadata populated

    Algorithm:
        1. Query PRs with the given label and state using get_project_prs()
        2. Get workflow runs for those PRs' branches (or recent runs for "all")
        3. Query artifacts from successful runs
        4. Filter artifacts by project name
        5. Optionally download and parse metadata JSON
    """
    from claudestep.services.pr_operations_service import PROperationsService

    result_artifacts = []
    seen_artifact_ids = set()

    # Get PRs for this project
    pr_service = PROperationsService(repo)
    prs = pr_service.get_project_prs(project, state=pr_state, label=label)
    print(f"Found {len(prs)} PR(s) for project '{project}' with state '{pr_state}'")

    # Get recent workflow runs from the repo
    # Workflows run on the base branch, not the PR's head branch,
    # so we get all recent runs and filter by project artifacts
    try:
        api_response = gh_api_call(
            f"/repos/{repo}/actions/runs?status=completed&per_page={limit}"
        )
        runs = api_response.get("workflow_runs", [])
    except GitHubAPIError as e:
        print(f"Warning: Failed to get workflow runs: {e}")
        runs = []

    print(f"Checking {len(runs)} workflow run(s) for artifacts")

    # Process workflow runs and collect artifacts
    for run in runs:
        if run.get("conclusion") != "success":
            continue

        run_id = run["id"]
        artifacts = _get_artifacts_for_run(repo, run_id)

        # Filter to project-specific artifacts
        project_artifacts = _filter_project_artifacts(artifacts, project)

        for artifact in project_artifacts:
            artifact_id = artifact["id"]

            # Skip if we've already seen this artifact
            if artifact_id in seen_artifact_ids:
                continue
            seen_artifact_ids.add(artifact_id)

            # Create ProjectArtifact
            project_artifact = ProjectArtifact(
                artifact_id=artifact_id,
                artifact_name=artifact["name"],
                workflow_run_id=run_id,
                metadata=None,
            )

            # Optionally download metadata
            if download_metadata:
                metadata_dict = download_artifact_json(repo, artifact_id)
                if metadata_dict:
                    try:
                        project_artifact.metadata = TaskMetadata.from_dict(
                            metadata_dict
                        )
                    except (KeyError, ValueError) as e:
                        print(
                            f"Warning: Failed to parse metadata for artifact {artifact_id}: {e}"
                        )

            result_artifacts.append(project_artifact)

    print(f"Found {len(result_artifacts)} artifact(s) for project '{project}'")
    return result_artifacts


def get_artifact_metadata(repo: str, artifact_id: int) -> Optional[TaskMetadata]:
    """Download and parse metadata from a specific artifact.

    Args:
        repo: GitHub repository (owner/name)
        artifact_id: Artifact ID to download

    Returns:
        TaskMetadata object or None if download fails
    """
    metadata_dict = download_artifact_json(repo, artifact_id)
    if metadata_dict:
        try:
            return TaskMetadata.from_dict(metadata_dict)
        except (KeyError, ValueError) as e:
            print(f"Warning: Failed to parse metadata for artifact {artifact_id}: {e}")
    return None


def find_in_progress_tasks(
    repo: str, project: str, label: str = "claudestep"
) -> set[int]:
    """Get task indices for all in-progress tasks (open PRs).

    This is a convenience wrapper around find_project_artifacts.

    Args:
        repo: GitHub repository
        project: Project name
        label: GitHub label for filtering

    Returns:
        Set of task indices that are currently in progress
    """
    artifacts = find_project_artifacts(
        repo=repo,
        project=project,
        label=label,
        pr_state="open",
        download_metadata=False,  # Just need names
    )

    return {a.task_index for a in artifacts if a.task_index is not None}


def get_reviewer_assignments(
    repo: str, project: str, label: str = "claudestep"
) -> dict[int, str]:
    """Get mapping of PR numbers to assigned reviewers.

    Args:
        repo: GitHub repository
        project: Project name
        label: GitHub label for filtering

    Returns:
        Dict mapping PR number -> reviewer username
    """
    artifacts = find_project_artifacts(
        repo=repo,
        project=project,
        label=label,
        pr_state="open",
        download_metadata=True,
    )

    return {
        a.metadata.pr_number: a.metadata.reviewer
        for a in artifacts
        if a.metadata and a.metadata.pr_number
    }


# ============================================================
# Module utilities
# ============================================================


def parse_task_index_from_name(artifact_name: str) -> Optional[int]:
    """Parse task index from artifact name.

    Expected format: task-metadata-{project}-{index}.json

    Args:
        artifact_name: Artifact name

    Returns:
        Task index or None if parsing fails
    """
    # Pattern: task-metadata-{project}-{index}.json
    # Example: task-metadata-myproject-1.json
    # Note: Project names can contain dashes, so we use .+ to match the entire project name
    # and capture the last number before .json
    pattern = r"task-metadata-.+-(\d+)\.json"
    match = re.match(pattern, artifact_name)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


# ============================================================
# Private helper functions
# ============================================================


def _get_workflow_runs_for_branch(
    repo: str, branch: str, limit: int = 10
) -> List[dict]:
    """Get workflow runs for a branch

    Args:
        repo: GitHub repository (owner/name)
        branch: Branch name
        limit: Maximum number of runs to fetch

    Returns:
        List of workflow run dictionaries

    Raises:
        GitHubAPIError: If API call fails
    """
    try:
        api_response = gh_api_call(
            f"/repos/{repo}/actions/runs?branch={branch}&status=completed&per_page={limit}"
        )
        return api_response.get("workflow_runs", [])
    except GitHubAPIError as e:
        print(f"Warning: Failed to get workflow runs for branch {branch}: {e}")
        return []


def _get_artifacts_for_run(repo: str, run_id: int) -> List[dict]:
    """Get artifacts from a workflow run

    Args:
        repo: GitHub repository (owner/name)
        run_id: Workflow run ID

    Returns:
        List of artifact dictionaries

    Raises:
        GitHubAPIError: If API call fails
    """
    try:
        artifacts_data = gh_api_call(f"/repos/{repo}/actions/runs/{run_id}/artifacts")
        return artifacts_data.get("artifacts", [])
    except GitHubAPIError as e:
        print(f"Warning: Failed to get artifacts for run {run_id}: {e}")
        return []


def _filter_project_artifacts(artifacts: List[dict], project: str) -> List[dict]:
    """Filter artifacts by project name pattern

    Args:
        artifacts: List of artifact dictionaries
        project: Project name to filter by

    Returns:
        List of artifacts matching the project
    """
    return [
        artifact
        for artifact in artifacts
        if artifact["name"].startswith(f"task-metadata-{project}-")
    ]
