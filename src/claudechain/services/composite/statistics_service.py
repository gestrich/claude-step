"""Service Layer class for statistics operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for collecting and aggregating project statistics from GitHub API and spec.md files.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from claudechain.domain.constants import DEFAULT_PR_LABEL, DEFAULT_STALE_PR_DAYS, DEFAULT_STATS_DAYS_BACK
from claudechain.domain.project import Project
from claudechain.domain.project_configuration import ProjectConfiguration
from claudechain.infrastructure.repositories.project_repository import ProjectRepository
from claudechain.services.core.pr_service import PRService
from claudechain.domain.models import ProjectStats, StatisticsReport, TeamMemberStats, PRReference, TaskWithPR, TaskStatus
from claudechain.services.composite.artifact_service import find_project_artifacts


class StatisticsService:
    """Service Layer class for statistics operations.

    Coordinates statistics collection by orchestrating GitHub PR queries and
    spec.md parsing. Implements business logic for ClaudeChain's statistics
    and reporting workflows.
    """

    def __init__(
        self,
        repo: str,
        project_repository: ProjectRepository,
        pr_service: PRService,
    ):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            project_repository: ProjectRepository instance for loading project data
            pr_service: PRService instance for PR operations
        """
        self.repo = repo
        self.project_repository = project_repository
        self.pr_service = pr_service

    # Public API methods

    def collect_all_statistics(
        self,
        projects: List[tuple],
        days_back: int = DEFAULT_STATS_DAYS_BACK,
        label: str = DEFAULT_PR_LABEL,
        show_assignee_stats: bool = False,
    ) -> StatisticsReport:
        """Collect statistics for provided projects and team members.

        Args:
            projects: List of (project_name, spec_branch) tuples. The caller is
                responsible for discovering projects (single or multi-project mode).
            days_back: Days to look back for team member stats
            label: GitHub label to filter PRs
            show_assignee_stats: Whether to collect reviewer statistics (default: False)

        Returns:
            Complete StatisticsReport
        """
        start_time = datetime.now(timezone.utc)
        report = StatisticsReport()
        report.generated_at = start_time

        if not self.repo:
            print("Warning: GITHUB_REPOSITORY not set")
            return report

        if not projects:
            print("No projects provided")
            return report

        # Load configurations for all projects
        all_assignees: set = set()
        project_configs: List[tuple] = []  # List of (ProjectConfiguration, spec_branch)

        for project_name, spec_branch in projects:
            try:
                config = self._load_project_config(project_name, spec_branch)
                if config.assignee:
                    all_assignees.add(config.assignee)
                project_configs.append((config, spec_branch))
            except Exception as e:
                print(f"Warning: Failed to load project {project_name}: {e}")
                continue

        print(f"Processing {len(project_configs)} project(s)...")
        print(f"Tracking {len(all_assignees)} unique assignee(s)")

        # Collect project statistics
        for config, spec_branch in project_configs:
            try:
                project_stats = self.collect_project_stats(
                    config.project.name, spec_branch, label,
                    project=config.project,
                    stale_pr_days=config.get_stale_pr_days()
                )
                if project_stats:  # Only add if not None (spec exists in spec_branch)
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

        # Calculate generation time
        end_time = datetime.now(timezone.utc)
        report.generation_time_seconds = (end_time - start_time).total_seconds()

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

        # Fetch costs from artifacts (keyed by PR number)
        costs_by_pr = self._get_costs_by_pr(project_name, label)

        # Build task-PR mappings (with costs)
        self._build_task_pr_mappings(stats, spec, open_prs, merged_prs, costs_by_pr)

        # Calculate pending tasks
        stats.pending_tasks = max(
            0, stats.total_tasks - stats.completed_tasks - stats.in_progress_tasks
        )
        print(f"  Pending: {stats.pending_tasks}")

        # Aggregate total cost from all tasks
        stats.total_cost_usd = sum(task.cost_usd for task in stats.tasks)
        if stats.total_cost_usd > 0:
            print(f"  Cost: ${stats.total_cost_usd:.2f}")

        return stats

    def _build_task_pr_mappings(
        self, stats: ProjectStats, spec, open_prs: List, merged_prs: List,
        costs_by_pr: Dict[int, float]
    ) -> None:
        """Build task-PR mappings and identify orphaned PRs.

        For each task in spec.md:
        - Find matching PR by task hash
        - Determine status based on spec checkbox and PR state
        - Look up cost from artifacts by PR number
        - Create TaskWithPR object

        For each PR:
        - If task hash doesn't match any spec task, add to orphaned_prs

        Args:
            stats: ProjectStats object to populate
            spec: SpecContent with parsed tasks
            open_prs: List of open PRs for the project
            merged_prs: List of merged PRs for the project
            costs_by_pr: Dict mapping PR number -> cost in USD
        """
        from claudechain.domain.github_models import GitHubPullRequest

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

            # Look up cost by PR number
            cost_usd = 0.0
            if matching_pr:
                cost_usd = costs_by_pr.get(matching_pr.number, 0.0)

            # Create TaskWithPR
            task_with_pr = TaskWithPR(
                task_hash=task.task_hash,
                description=task.description,
                status=status,
                pr=matching_pr,
                cost_usd=cost_usd
            )
            stats.tasks.append(task_with_pr)

        # Identify orphaned PRs (PRs whose task hash doesn't match any spec task)
        for pr in all_prs:
            task_hash = pr.task_hash
            if task_hash and task_hash not in spec_task_hashes:
                stats.orphaned_prs.append(pr)

        if stats.orphaned_prs:
            print(f"  Orphaned PRs: {len(stats.orphaned_prs)}")

    def _get_costs_by_pr(
        self, project_name: str, label: str
    ) -> Dict[int, float]:
        """Get costs from task metadata artifacts, keyed by PR number.

        Downloads artifacts for the project and builds a dict mapping PR number
        to total cost for that PR.

        Args:
            project_name: Name of the project
            label: GitHub label for filtering

        Returns:
            Dict mapping PR number -> cost in USD
        """
        artifacts = find_project_artifacts(
            repo=self.repo,
            project=project_name,
            label=label,
            pr_state="all",
            download_metadata=True,
        )

        costs_by_pr: Dict[int, float] = {}
        for artifact in artifacts:
            if artifact.metadata and artifact.metadata.pr_number:
                pr_number = artifact.metadata.pr_number
                cost = artifact.metadata.get_total_cost()
                # Sum costs in case there are multiple artifacts for same PR
                costs_by_pr[pr_number] = costs_by_pr.get(pr_number, 0.0) + cost

        return costs_by_pr

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
            # Query all PRs with claudechain label from GitHub using PRService
            all_prs = self.pr_service.get_all_prs(label=label, state="all", limit=500)

            for pr in all_prs:
                # Skip if no assignee or not a ClaudeChain PR
                if not pr.assignees or not pr.is_claudechain_pr:
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
