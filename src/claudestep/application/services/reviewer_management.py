"""Reviewer capacity checking and assignment"""

import os
from collections import defaultdict
from typing import Any, Dict, List, Optional

from claudestep.application.services.artifact_operations import find_project_artifacts
from claudestep.domain.models import ReviewerCapacityResult


def find_available_reviewer(reviewers: List[Dict[str, Any]], label: str, project: str) -> tuple[Optional[str], ReviewerCapacityResult]:
    """Find first reviewer with capacity based on artifact metadata

    Args:
        reviewers: List of reviewer dicts with 'username' and 'maxOpenPRs'
        label: GitHub label to filter PRs
        project: Project name to match artifacts

    Returns:
        Tuple of (username or None, ReviewerCapacityResult)
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    result = ReviewerCapacityResult()

    # Initialize reviewer PR lists
    reviewer_prs = defaultdict(list)
    for reviewer in reviewers:
        reviewer_prs[reviewer["username"]] = []

    # Get artifacts for all open PRs with metadata
    artifacts = find_project_artifacts(
        repo=repo,
        project=project,
        label=label,
        pr_state="open",
        download_metadata=True
    )

    # Group PRs by reviewer
    for artifact in artifacts:
        if artifact.metadata:
            assigned_reviewer = artifact.metadata.reviewer
            pr_num = artifact.metadata.pr_number

            # Check if this reviewer is in our list
            if assigned_reviewer in reviewer_prs:
                # Store PR details
                pr_info = {
                    "pr_number": pr_num,
                    "task_index": artifact.metadata.task_index,
                    "task_description": artifact.metadata.task_description
                }
                reviewer_prs[assigned_reviewer].append(pr_info)
                print(f"PR #{pr_num}: reviewer={assigned_reviewer} (from artifact)")
            else:
                print(f"Warning: PR #{pr_num} has unknown reviewer: {assigned_reviewer}")

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
