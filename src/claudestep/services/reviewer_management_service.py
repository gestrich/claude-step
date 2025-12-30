"""Reviewer capacity checking and assignment"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

from claudestep.services.artifact_operations_service import find_project_artifacts
from claudestep.services.metadata_service import MetadataService
from claudestep.domain.models import ReviewerCapacityResult


class ReviewerManagementService:
    """Service for reviewer capacity checking and assignment"""

    def __init__(self, repo: str, metadata_service: MetadataService):
        self.repo = repo
        self.metadata_service = metadata_service

    # Public API methods

    def find_available_reviewer(
        self, reviewers: List[Dict[str, Any]], label: str, project: str
    ) -> tuple[Optional[str], ReviewerCapacityResult]:
        """Find first reviewer with capacity based on artifact metadata

        Args:
            reviewers: List of reviewer dicts with 'username' and 'maxOpenPRs'
            label: GitHub label to filter PRs
            project: Project name to match

        Returns:
            Tuple of (username or None, ReviewerCapacityResult)
        """
        result = ReviewerCapacityResult()

        # Initialize reviewer PR lists
        reviewer_prs = defaultdict(list)
        for reviewer in reviewers:
            reviewer_prs[reviewer["username"]] = []

        # Find open PR artifacts for this project
        artifacts = find_project_artifacts(
            repo=self.repo,
            project=project,
            label=label,
            pr_state="open",
            download_metadata=True
        )

        # Group open PRs by reviewer from artifact metadata
        for artifact in artifacts:
            if artifact.metadata:
                assigned_reviewer = artifact.metadata.reviewer

                # Check if this reviewer is in our list
                if assigned_reviewer in reviewer_prs:
                    task_description = artifact.metadata.task_description or f"Task {artifact.metadata.task_index}"

                    pr_info = {
                        "pr_number": artifact.metadata.pr_number,
                        "task_index": artifact.metadata.task_index,
                        "task_description": task_description
                    }
                    reviewer_prs[assigned_reviewer].append(pr_info)
                    print(f"PR #{artifact.metadata.pr_number}: reviewer={assigned_reviewer}")
                else:
                    print(f"Warning: PR #{artifact.metadata.pr_number} has unknown reviewer: {assigned_reviewer}")

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
