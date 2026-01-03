"""Service Layer class for statistics operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for collecting and aggregating project statistics from GitHub API and spec.md files.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from claudestep.domain.constants import DEFAULT_PR_LABEL, DEFAULT_STALE_PR_DAYS, DEFAULT_STATS_DAYS_BACK
from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.infrastructure.repositories.project_repository import ProjectRepository
from claudestep.services.core.pr_service import PRService
from claudestep.domain.models import ProjectStats, StatisticsReport, TeamMemberStats, PRReference, TaskWithPR, TaskStatus
from claudestep.services.composite.artifact_service import find_project_artifacts


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
        pr_service: PRService,
        base_branch: str = "main"
    ):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            project_repository: ProjectRepository instance for loading project data
            pr_service: PRService instance for PR operations
            base_branch: Base branch to fetch specs from (default: "main")
        """
        self.repo = repo
        self.base_branch = base_branch
        self.project_repository = project_repository
        self.pr_service = pr_service

    # Public API methods

    def collect_all_statistics(
        self,
        config_path: Optional[str] = None,
        days_back: int = DEFAULT_STATS_DAYS_BACK,
        label: str = DEFAULT_PR_LABEL,
        show_assignee_stats: bool = False,
    ) -> StatisticsReport:
        """Collect statistics for all projects and team members

        Args:
            config_path: Optional path to specific config (for single project mode)
            days_back: Days to look back for team member stats
            label: GitHub label to filter PRs
            show_assignee_stats: Whether to collect reviewer statistics (default: False)

        Returns:
            Complete StatisticsReport
        """
        report = StatisticsReport(base_branch=self.base_branch)
        report.generated_at = datetime.now(timezone.utc)

        if not self.repo:
            print("Warning: GITHUB_REPOSITORY not set")
            return report

        # Use base branch from instance variable
        base_branch = self.base_branch
        all_assignees = set()
        project_configs = []  # List of ProjectConfiguration objects

        if config_path:
            # Single project mode - fetch config from GitHub API
            print(f"Single project mode: {config_path}")

            try:
                # Extract project name from path using Project domain model
                project = Project.from_config_path(config_path)

                # load_configuration returns default config if file not found
                config = self._load_project_config(project.name, base_branch)

                if config.assignee:
                    all_assignees.add(config.assignee)
                project_configs.append(config)

                if not config.assignee:
                    print("  (no assignee configured - using default config)")

            except Exception as e:
                print(f"Error loading config: {e}")
                return report

        else:
            # Multi-project mode - discover all projects from GitHub PR queries
            print("Multi-project mode: discovering projects from GitHub PRs...")

            try:
                # Get unique project names using PRService
                project_names = self.pr_service.get_unique_projects(label=label)

                print(f"Found {len(project_names)} unique project(s)")
            except Exception as e:
                print(f"Error querying GitHub PRs: {e}")
                return report

            if not project_names:
                print("No projects found")
                return report

            for project_name in project_names:
                try:
                    # load_configuration returns default config if file not found
                    config = self._load_project_config(project_name, base_branch)

                    if config.assignee:
                        all_assignees.add(config.assignee)
                    project_configs.append(config)

                except Exception as e:
                    print(f"Warning: Failed to load project {project_name}: {e}")
                    continue

        print(f"\nProcessing {len(project_configs)} project(s)...")
        print(f"Tracking {len(all_assignees)} unique assignee(s)")

        # Collect project statistics
        for config in project_configs:
            try:
                project_stats = self.collect_project_stats(
                    config.project.name, base_branch, label,
                    project=config.project,
                    stale_pr_days=config.get_stale_pr_days()
                )
                if project_stats:  # Only add if not None (spec exists in base branch)
                    report.add_project(project_stats)
            except Exception as e:
                print(f"Error collecting stats for {config.project.name}: {e}")

        # Collect team member statistics across all projects (only if enabled)
        if show_assignee_stats:
            if all_assignees:
                try:
                    team_stats = self.collect_team_member_stats(
                        list(all_assignees), days_back, label
                    )
                    for username, stats in team_stats.items():
                        report.add_team_member(stats)
                except Exception as e:
                    print(f"Error collecting team member stats: {e}")
            else:
                print("No assignees configured - skipping team member statistics")
        else:
            print("Team member statistics disabled - skipping collection")

        return report

    def collect_project_stats(
        self, project_name: str, base_branch: str = "main", label: str = DEFAULT_PR_LABEL,
        project: Optional[Project] = None,
        stale_pr_days: int = DEFAULT_STALE_PR_DAYS,
        days_back: int = DEFAULT_STATS_DAYS_BACK
    ) -> ProjectStats:
        """Collect statistics for a single project

        Args:
            project_name: Name of the project
            base_branch: Base branch to fetch spec from
            label: GitHub label for filtering
            project: Optional pre-loaded Project instance to avoid re-creating
            stale_pr_days: Number of days before a PR is considered stale
            days_back: Days to look back for merged PRs (default: 30)

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

        # Get PRs from GitHub (open and merged)
        open_prs = self.pr_service.get_open_prs_for_project(project_name, label=label)
        stats.in_progress_tasks = len(open_prs)
        print(f"  In-progress: {stats.in_progress_tasks}")

        # Store open PRs and calculate stale count
        for pr in open_prs:
            stats.open_prs.append(pr)
            if pr.is_stale(stale_pr_days):
                stats.stale_pr_count += 1

        if stats.stale_pr_count > 0:
            print(f"  Stale PRs: {stats.stale_pr_count} (>{stale_pr_days} days)")

        merged_prs = self.pr_service.get_merged_prs_for_project(
            project_name, label=label, days_back=days_back
        )
        print(f"  Merged PRs (last {days_back} days): {len(merged_prs)}")

        # Build task-PR mappings
        self._build_task_pr_mappings(stats, spec, open_prs, merged_prs)

        # Calculate pending tasks
        stats.pending_tasks = max(
            0, stats.total_tasks - stats.completed_tasks - stats.in_progress_tasks
        )
        print(f"  Pending: {stats.pending_tasks}")

        # Aggregate costs from artifacts
        stats.total_cost_usd = self._aggregate_costs_from_artifacts(
            project_name, label
        )
        if stats.total_cost_usd > 0:
            print(f"  Cost: ${stats.total_cost_usd:.2f}")

        return stats

    def _build_task_pr_mappings(
        self, stats: ProjectStats, spec, open_prs: List, merged_prs: List
    ) -> None:
        """Build task-PR mappings and identify orphaned PRs.

        For each task in spec.md:
        - Find matching PR by task hash
        - Determine status based on spec checkbox and PR state
        - Create TaskWithPR object

        For each PR:
        - If task hash doesn't match any spec task, add to orphaned_prs

        Args:
            stats: ProjectStats object to populate
            spec: SpecContent with parsed tasks
            open_prs: List of open PRs for the project
            merged_prs: List of merged PRs for the project
        """
        from claudestep.domain.github_models import GitHubPullRequest

        # Build a lookup map: task_hash -> PR
        pr_by_hash: Dict[str, GitHubPullRequest] = {}
        all_prs = open_prs + merged_prs

        for pr in all_prs:
            task_hash = pr.task_hash
            if task_hash:
                pr_by_hash[task_hash] = pr

        # Track which task hashes we've seen (to identify orphaned PRs)
        spec_task_hashes = set()

        # Process each task from spec
        for task in spec.tasks:
            spec_task_hashes.add(task.task_hash)

            # Find matching PR
            matching_pr = pr_by_hash.get(task.task_hash)

            # Determine status
            if task.is_completed:
                status = TaskStatus.COMPLETED
            elif matching_pr and matching_pr.is_open():
                status = TaskStatus.IN_PROGRESS
            else:
                status = TaskStatus.PENDING

            # Create TaskWithPR
            task_with_pr = TaskWithPR(
                task_hash=task.task_hash,
                description=task.description,
                status=status,
                pr=matching_pr
            )
            stats.tasks.append(task_with_pr)

        # Identify orphaned PRs (PRs whose task hash doesn't match any spec task)
        for pr in all_prs:
            task_hash = pr.task_hash
            if task_hash and task_hash not in spec_task_hashes:
                stats.orphaned_prs.append(pr)

        if stats.orphaned_prs:
            print(f"  Orphaned PRs: {len(stats.orphaned_prs)}")

    def _aggregate_costs_from_artifacts(
        self, project_name: str, label: str
    ) -> float:
        """Aggregate costs from task metadata artifacts.

        Downloads artifacts for the project and sums up costs from TaskMetadata.

        Args:
            project_name: Name of the project
            label: GitHub label for filtering

        Returns:
            Total cost in USD, or 0.0 if no artifacts found
        """
        artifacts = find_project_artifacts(
            repo=self.repo,
            project=project_name,
            label=label,
            pr_state="all",
            download_metadata=True,
        )

        total_cost = 0.0
        for artifact in artifacts:
            if artifact.metadata:
                total_cost += artifact.metadata.get_total_cost()

        return total_cost

    def collect_team_member_stats(
        self, assignees: List[str], days_back: int = DEFAULT_STATS_DAYS_BACK, label: str = DEFAULT_PR_LABEL
    ) -> Dict[str, TeamMemberStats]:
        """Collect PR statistics for team members from GitHub API

        Args:
            assignees: List of GitHub usernames to track
            days_back: Number of days to look back
            label: GitHub label for filtering PRs

        Returns:
            Dict of username -> TeamMemberStats
        """
        stats_dict = {}

        # Initialize stats for all assignees
        for username in assignees:
            stats_dict[username] = TeamMemberStats(username)

        print(f"Collecting team member statistics for {len(assignees)} assignee(s)...")

        # Calculate cutoff date
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)
        cutoff_iso = cutoff_date.strftime("%Y-%m-%d")

        print(f"Looking for PRs since {cutoff_iso}...")

        merged_count = 0
        open_count = 0

        try:
            # Query all PRs with claudestep label from GitHub using PRService
            all_prs = self.pr_service.get_all_prs(label=label, state="all", limit=500)

            for pr in all_prs:
                # Skip if no assignee or not a ClaudeStep PR
                if not pr.assignees or not pr.is_claudestep_pr:
                    continue

                # Use domain model properties instead of manual parsing
                project_name = pr.project_name
                task_hash = pr.task_hash

                # PR must have a project name and task_hash
                if not project_name or task_hash is None:
                    continue

                # Create PRReference from GitHub PR
                title = f"Task {task_hash[:8]}: {pr.task_description}"

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
