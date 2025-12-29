"""Reviewer capacity checking and assignment"""

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
from claudestep.application.services.metadata_service import MetadataService
from claudestep.domain.models import ReviewerCapacityResult


def find_available_reviewer(reviewers: List[Dict[str, Any]], label: str, project: str) -> tuple[Optional[str], ReviewerCapacityResult]:
    """Find first reviewer with capacity based on metadata storage

    Args:
        reviewers: List of reviewer dicts with 'username' and 'maxOpenPRs'
        label: GitHub label to filter PRs (unused, kept for compatibility)
        project: Project name to match

    Returns:
        Tuple of (username or None, ReviewerCapacityResult)
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    result = ReviewerCapacityResult()

    # Initialize reviewer PR lists
    reviewer_prs = defaultdict(list)
    for reviewer in reviewers:
        reviewer_prs[reviewer["username"]] = []

    # Load from metadata storage
    try:
        metadata_store = GitHubMetadataStore(repo)
        metadata_service = MetadataService(metadata_store)
        project_metadata = metadata_service.get_project(project)

        if project_metadata:
            # Group open PRs by reviewer from metadata
            for pr in project_metadata.pull_requests:
                if pr.pr_state == "open":
                    assigned_reviewer = pr.reviewer

                    # Check if this reviewer is in our list
                    if assigned_reviewer in reviewer_prs:
                        # Get task description from project tasks
                        task = project_metadata.get_task_by_index(pr.task_index)
                        task_description = task.description if task else f"Task {pr.task_index}"

                        pr_info = {
                            "pr_number": pr.pr_number,
                            "task_index": pr.task_index,
                            "task_description": task_description
                        }
                        reviewer_prs[assigned_reviewer].append(pr_info)
                        print(f"PR #{pr.pr_number}: reviewer={assigned_reviewer}")
                    else:
                        print(f"Warning: PR #{pr.pr_number} has unknown reviewer: {assigned_reviewer}")
    except Exception as e:
        print(f"Error: Failed to read from metadata storage: {e}")

    # Build result and find first available reviewer
    selected_reviewer = None
    for reviewer in reviewers:
        username = reviewer["username"]
        max_prs = reviewer["maxOpenPRs"]
        open_prs = reviewer_prs[username]
        has_capacity = len(open_prs) < max_prs

        # Add to result
        result.add_reviewer(username, max_prs, open_prs, has_capacity)

        print(f"Reviewer {username}: {len(open_prs)} open PRs (max: {max_prs})")

        # Select first available reviewer
        if has_capacity and selected_reviewer is None:
            selected_reviewer = username
            print(f"Selected reviewer: {username}")

    result.selected_reviewer = selected_reviewer
    result.all_at_capacity = (selected_reviewer is None)

    return selected_reviewer, result
