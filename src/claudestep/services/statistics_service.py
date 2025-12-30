"""Service Layer class for statistics operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for collecting and aggregating project statistics from GitHub API and spec.md files.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from claudestep.domain.config import load_config_from_string
from claudestep.domain.constants import DEFAULT_PR_LABEL
from claudestep.domain.exceptions import FileNotFoundError as ClaudeStepFileNotFoundError
from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
from claudestep.infrastructure.github.operations import get_file_from_branch, run_gh_command
from claudestep.infrastructure.repositories.project_repository import ProjectRepository
from claudestep.services.metadata_service import MetadataService
from claudestep.domain.models import ProjectStats, StatisticsReport, TeamMemberStats


class StatisticsService:
    """Service Layer class for statistics operations.

    Coordinates statistics collection by orchestrating metadata queries, GitHub
    API interactions, and spec.md parsing. Implements business logic for
    ClaudeStep's statistics and reporting workflows.
    """

    def __init__(
        self,
        repo: str,
        metadata_service: MetadataService,
        base_branch: str = "main",
        project_repository: Optional[ProjectRepository] = None
    ):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            metadata_service: MetadataService instance for accessing metadata
            base_branch: Base branch to fetch specs from (default: "main")
            project_repository: Optional ProjectRepository instance (defaults to new instance)
        """
        self.repo = repo
        self.metadata_service = metadata_service
        self.base_branch = base_branch
        self.project_repository = project_repository or ProjectRepository(repo)

    # Public API methods

    def _load_project_config(
        self, project_name: str, base_branch: str
    ) -> Optional[ProjectConfiguration]:
        """Load project configuration using repository

        Args:
            project_name: Name of the project
            base_branch: Base branch to fetch config from

        Returns:
            ProjectConfiguration domain model, or None if config couldn't be loaded
        """
        project = Project(project_name)
        return self.project_repository.load_configuration(project, base_branch)

    def collect_all_statistics(
        self, config_path: Optional[str] = None, days_back: int = 30, label: str = DEFAULT_PR_LABEL
    ) -> StatisticsReport:
        """Collect statistics for all projects and team members

        Args:
            config_path: Optional path to specific config (for single project mode)
            days_back: Days to look back for team member stats
            label: GitHub label to filter PRs

        Returns:
            Complete StatisticsReport
        """
        report = StatisticsReport()
        report.generated_at = datetime.now(timezone.utc)

        if not self.repo:
            print("Warning: GITHUB_REPOSITORY not set")
            return report

        # Use base branch from instance variable
        base_branch = self.base_branch
        all_reviewers = set()
        projects_data = []  # List of (project_name, reviewers)

        if config_path:
            # Single project mode - fetch config from GitHub API
            print(f"Single project mode: {config_path}")

            try:
                # Extract project name from path using Project domain model
                project = Project.from_config_path(config_path)

                config = self._load_project_config(project.name, base_branch)
                if config is None:
                    print(f"Error: Configuration file not found in branch '{base_branch}'")
                    return report

                reviewers = config.get_reviewer_usernames()
                projects_data.append((project.name, reviewers))
                all_reviewers.update(reviewers)

            except Exception as e:
                print(f"Error loading config: {e}")
                return report

        else:
            # Multi-project mode - discover all projects from metadata storage
            print("Multi-project mode: discovering projects from metadata storage...")

            try:
                project_names = self.metadata_service.list_project_names()
            except Exception as e:
                print(f"Error accessing metadata storage: {e}")
                return report

            if not project_names:
                print("No projects found")
                return report

            for project_name in project_names:
                try:
                    config = self._load_project_config(project_name, base_branch)
                    if config is None:
                        print(f"Warning: Configuration file not found for project {project_name} in branch '{base_branch}', skipping")
                        continue

                    reviewers = config.get_reviewer_usernames()
                    projects_data.append((project_name, reviewers))
                    all_reviewers.update(reviewers)

                except Exception as e:
                    print(f"Warning: Failed to load project {project_name}: {e}")
                    continue

        print(f"\nProcessing {len(projects_data)} project(s)...")
        print(f"Tracking {len(all_reviewers)} unique reviewer(s)")

        # Collect project statistics
        for project_name, _ in projects_data:
            try:
                project_stats = self.collect_project_stats(project_name, base_branch, label)
                if project_stats:  # Only add if not None (spec exists in base branch)
                    report.add_project(project_stats)
            except Exception as e:
                print(f"Error collecting stats for {project_name}: {e}")

        # Collect team member statistics across all projects
        if all_reviewers:
            try:
                team_stats = self.collect_team_member_stats(
                    list(all_reviewers), days_back, label
                )
                for username, stats in team_stats.items():
                    report.add_team_member(stats)
            except Exception as e:
                print(f"Error collecting team member stats: {e}")

        return report

    def collect_project_stats(
        self, project_name: str, base_branch: str = "main", label: str = DEFAULT_PR_LABEL
    ) -> ProjectStats:
        """Collect statistics for a single project

        Args:
            project_name: Name of the project
            base_branch: Base branch to fetch spec from
            label: GitHub label for filtering

        Returns:
            ProjectStats object, or None if spec files don't exist in base branch
        """
        print(f"Collecting statistics for project: {project_name}")

        project = Project(project_name)
        stats = ProjectStats(project_name, project.spec_path)

        # Fetch and parse spec.md using repository
        try:
            spec = self.project_repository.load_spec(project, base_branch)
            if not spec:
                print(f"  Warning: Spec file not found in branch '{base_branch}', skipping project")
                return None

            stats.total_tasks = spec.total_tasks
            stats.completed_tasks = spec.completed_tasks
            print(f"  Tasks: {stats.completed_tasks}/{stats.total_tasks} completed")
        except Exception as e:
            print(f"  Warning: Failed to fetch spec file: {e}")
            return None

        # Get in-progress tasks from metadata storage
        try:
            in_progress_indices = self.metadata_service.find_in_progress_tasks(project_name)
            stats.in_progress_tasks = len(in_progress_indices)
            print(f"  In-progress: {stats.in_progress_tasks}")
        except Exception as e:
            print(f"  Error: Failed to get in-progress tasks: {e}")
            stats.in_progress_tasks = 0

        # Calculate pending tasks
        stats.pending_tasks = max(
            0, stats.total_tasks - stats.completed_tasks - stats.in_progress_tasks
        )
        print(f"  Pending: {stats.pending_tasks}")

        # Collect costs from merged PRs
        try:
            stats.total_cost_usd = self.collect_project_costs(project_name, label)
        except Exception as e:
            print(f"  Warning: Failed to collect costs: {e}")
            stats.total_cost_usd = 0.0

        return stats

    def collect_team_member_stats(
        self, reviewers: List[str], days_back: int = 30, label: str = DEFAULT_PR_LABEL
    ) -> Dict[str, TeamMemberStats]:
        """Collect PR statistics for team members

        Args:
            reviewers: List of GitHub usernames to track
            days_back: Number of days to look back for merged PRs
            label: GitHub label to filter PRs

        Returns:
            Dict of username -> TeamMemberStats
        """
        stats_dict = {}

        # Initialize stats for all reviewers
        for username in reviewers:
            stats_dict[username] = TeamMemberStats(username)

        print(f"Collecting team member statistics for {len(reviewers)} reviewer(s)...")

        # Calculate cutoff date for merged PRs
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_iso = cutoff_date.strftime("%Y-%m-%d")

        # Collect merged PRs
        try:
            print(f"Querying merged PRs since {cutoff_iso}...")
            merged_output = run_gh_command(
                [
                    "pr",
                    "list",
                    "--repo",
                    self.repo,
                    "--label",
                    label,
                    "--state",
                    "merged",
                    "--json",
                    "number,title,mergedAt,assignees",
                    "--limit",
                    "100",
                ]
            )
            merged_prs = json.loads(merged_output) if merged_output else []
            print(f"Found {len(merged_prs)} merged PR(s)")

            # Filter by date and group by assignee
            for pr in merged_prs:
                merged_at_str = pr.get("mergedAt", "")
                if not merged_at_str:
                    continue

                # Parse merged date
                try:
                    merged_at = datetime.strptime(
                        merged_at_str.replace("Z", "+00:00").split("+")[0],
                        "%Y-%m-%dT%H:%M:%S",
                    )
                except (ValueError, IndexError):
                    continue

                # Check if within date range
                if merged_at < cutoff_date:
                    continue

                # Get assignees
                assignees = pr.get("assignees", [])
                for assignee in assignees:
                    username = assignee.get("login")
                    if username in stats_dict:
                        stats_dict[username].merged_prs.append(
                            {
                                "pr_number": pr.get("number"),
                                "title": pr.get("title"),
                                "merged_at": merged_at_str,
                                "project": "unknown",  # Could be extracted from labels if needed
                            }
                        )

        except Exception as e:
            print(f"Warning: Failed to collect merged PRs: {e}")

        # Collect open PRs
        try:
            print("Querying open PRs...")
            open_output = run_gh_command(
                [
                    "pr",
                    "list",
                    "--repo",
                    self.repo,
                    "--label",
                    label,
                    "--state",
                    "open",
                    "--json",
                    "number,title,createdAt,assignees",
                    "--limit",
                    "100",
                ]
            )
            open_prs = json.loads(open_output) if open_output else []
            print(f"Found {len(open_prs)} open PR(s)")

            # Group by assignee
            for pr in open_prs:
                assignees = pr.get("assignees", [])
                for assignee in assignees:
                    username = assignee.get("login")
                    if username in stats_dict:
                        stats_dict[username].open_prs.append(
                            {
                                "pr_number": pr.get("number"),
                                "title": pr.get("title"),
                                "created_at": pr.get("createdAt"),
                                "project": "unknown",
                            }
                        )

        except Exception as e:
            print(f"Warning: Failed to collect open PRs: {e}")

        return stats_dict

    def collect_project_costs(
        self, project_name: str, label: str = DEFAULT_PR_LABEL
    ) -> float:
        """Collect total costs for a project from metadata storage

        Args:
            project_name: Name of the project to collect costs for
            label: GitHub label to filter PRs (unused, kept for compatibility)

        Returns:
            Total cost in USD across all merged PRs for this project
        """
        print(f"  Collecting costs from metadata storage...")

        try:
            project_metadata = self.metadata_service.get_project(project_name)

            if project_metadata:
                # Use the hybrid model to get total cost from merged PRs
                merged_prs = [pr for pr in project_metadata.pull_requests if pr.pr_state == "merged"]
                if merged_prs:
                    total_cost = sum(pr.get_total_cost() for pr in merged_prs)
                    print(f"  Found {len(merged_prs)} merged PR(s)")
                    print(f"  Total cost: ${total_cost:.6f}")
                    return total_cost
                else:
                    print(f"  No merged PRs found")
                    return 0.0
            else:
                print(f"  Project not found in metadata storage")
                return 0.0
        except Exception as e:
            print(f"  Error: Failed to read from metadata storage: {e}")
            return 0.0

    # Static utility methods

    @staticmethod
    def extract_cost_from_comment(comment_body: str) -> Optional[float]:
        """Extract total cost from a cost breakdown comment

        Args:
            comment_body: The PR comment body text

        Returns:
            Total cost in USD, or None if not found
        """
        # Look for the total cost line: | **Total** | **$X.XXXXXX** |
        pattern = r'\|\s*\*\*Total\*\*\s*\|\s*\*\*\$(\d+\.\d+)\*\*\s*\|'
        match = re.search(pattern, comment_body)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None
