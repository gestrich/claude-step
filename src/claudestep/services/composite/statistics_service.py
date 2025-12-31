"""Service Layer class for statistics operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for collecting and aggregating project statistics from GitHub API and spec.md files.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from claudestep.domain.constants import DEFAULT_PR_LABEL
from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.infrastructure.repositories.project_repository import ProjectRepository
from claudestep.services.pr_operations_service import PROperationsService
from claudestep.domain.models import ProjectStats, StatisticsReport, TeamMemberStats, PRReference


class StatisticsService:
    """Service Layer class for statistics operations.

    Coordinates statistics collection by orchestrating GitHub PR queries and
    spec.md parsing. Implements business logic for ClaudeStep's statistics
    and reporting workflows.
    """

    def __init__(
        self,
        repo: str,
        project_repository: ProjectRepository,
        pr_operations_service: PROperationsService,
        base_branch: str = "main"
    ):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            project_repository: ProjectRepository instance for loading project data
            pr_operations_service: PROperationsService instance for PR operations
            base_branch: Base branch to fetch specs from (default: "main")
        """
        self.repo = repo
        self.base_branch = base_branch
        self.project_repository = project_repository
        self.pr_operations_service = pr_operations_service

    # Public API methods

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
        project_configs = []  # List of ProjectConfiguration objects

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
                project_configs.append(config)
                all_reviewers.update(reviewers)

            except Exception as e:
                print(f"Error loading config: {e}")
                return report

        else:
            # Multi-project mode - discover all projects from GitHub PR queries
            print("Multi-project mode: discovering projects from GitHub PRs...")

            try:
                # Get unique project names using PROperationsService
                project_names = self.pr_operations_service.get_unique_projects(label=label)

                print(f"Found {len(project_names)} unique project(s)")
            except Exception as e:
                print(f"Error querying GitHub PRs: {e}")
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
                    project_configs.append(config)
                    all_reviewers.update(reviewers)

                except Exception as e:
                    print(f"Warning: Failed to load project {project_name}: {e}")
                    continue

        print(f"\nProcessing {len(project_configs)} project(s)...")
        print(f"Tracking {len(all_reviewers)} unique reviewer(s)")

        # Collect project statistics
        for config in project_configs:
            try:
                project_stats = self.collect_project_stats(
                    config.project.name, base_branch, label, project=config.project
                )
                if project_stats:  # Only add if not None (spec exists in base branch)
                    report.add_project(project_stats)
            except Exception as e:
                print(f"Error collecting stats for {config.project.name}: {e}")

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
        self, project_name: str, base_branch: str = "main", label: str = DEFAULT_PR_LABEL,
        project: Optional[Project] = None
    ) -> ProjectStats:
        """Collect statistics for a single project

        Args:
            project_name: Name of the project
            base_branch: Base branch to fetch spec from
            label: GitHub label for filtering
            project: Optional pre-loaded Project instance to avoid re-creating

        Returns:
            ProjectStats object, or None if spec files don't exist in base branch
        """
        print(f"Collecting statistics for project: {project_name}")

        if project is None:
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

        # Get in-progress tasks from GitHub (open PRs for this project)
        try:
            open_prs = self.pr_operations_service.get_open_prs_for_project(project_name, label=label)
            stats.in_progress_tasks = len(open_prs)
            print(f"  In-progress: {stats.in_progress_tasks}")
        except Exception as e:
            print(f"  Error: Failed to get in-progress tasks: {e}")
            stats.in_progress_tasks = 0

        # Calculate pending tasks
        stats.pending_tasks = max(
            0, stats.total_tasks - stats.completed_tasks - stats.in_progress_tasks
        )
        print(f"  Pending: {stats.pending_tasks}")

        # Cost tracking temporarily dropped (Phase 4)
        # TODO: Re-implement cost tracking via PR comments if needed
        stats.total_cost_usd = 0.0

        return stats

    def collect_team_member_stats(
        self, reviewers: List[str], days_back: int = 30, label: str = DEFAULT_PR_LABEL
    ) -> Dict[str, TeamMemberStats]:
        """Collect PR statistics for team members from GitHub API

        Args:
            reviewers: List of GitHub usernames to track
            days_back: Number of days to look back
            label: GitHub label for filtering PRs

        Returns:
            Dict of username -> TeamMemberStats
        """
        stats_dict = {}

        # Initialize stats for all reviewers
        for username in reviewers:
            stats_dict[username] = TeamMemberStats(username)

        print(f"Collecting team member statistics for {len(reviewers)} reviewer(s)...")

        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_iso = cutoff_date.strftime("%Y-%m-%d")

        print(f"Looking for PRs since {cutoff_iso}...")

        merged_count = 0
        open_count = 0

        try:
            # Query all PRs with claudestep label from GitHub using PROperationsService
            all_prs = self.pr_operations_service.get_all_prs(label=label, state="all", limit=500)

            for pr in all_prs:
                # Skip if no assignee or not a ClaudeStep PR
                if not pr.assignees or not pr.is_claudestep_pr:
                    continue

                # Use domain model properties instead of manual parsing
                project_name = pr.project_name
                task_index = pr.task_index

                if not project_name or task_index is None:
                    continue

                # Create PRReference from GitHub PR
                # Use task index and cleaned task description
                title = f"Task {task_index}: {pr.task_description}"

                # Determine timestamp based on state
                timestamp = pr.merged_at if pr.state == "merged" and pr.merged_at else pr.created_at

                pr_ref = PRReference(
                    pr_number=pr.number,
                    title=title,
                    project=project_name,
                    timestamp=timestamp
                )

                # Add to each assignee's stats
                for assignee in pr.assignees:
                    if assignee in stats_dict:
                        if pr.state == "merged":
                            stats_dict[assignee].add_merged_pr(pr_ref)
                            merged_count += 1
                        elif pr.state == "open":
                            stats_dict[assignee].add_open_pr(pr_ref)
                            open_count += 1

        except Exception as e:
            print(f"Warning: Failed to query GitHub PRs: {e}")

        print(f"Found {merged_count} merged PR(s)")
        print(f"Found {open_count} open PR(s)")

        return stats_dict

    def collect_project_costs(
        self, project_name: str, label: str = DEFAULT_PR_LABEL,
        project_metadata: Optional[Dict] = None
    ) -> float:
        """Collect total costs for a project (temporarily disabled in Phase 4)

        Args:
            project_name: Name of the project to collect costs for
            label: GitHub label to filter PRs (unused)
            project_metadata: Optional metadata (unused, kept for compatibility)

        Returns:
            Total cost in USD (always 0.0 in Phase 4)
        """
        # Cost tracking temporarily dropped (Phase 4)
        # TODO: Re-implement cost tracking via PR comments if needed
        return 0.0

    # Private helper methods

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
