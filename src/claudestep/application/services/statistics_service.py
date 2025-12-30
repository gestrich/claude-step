"""Statistics collection from GitHub API and spec.md files"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from claudestep.domain.config import load_config_from_string
from claudestep.domain.exceptions import FileNotFoundError as ClaudeStepFileNotFoundError
from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
from claudestep.infrastructure.github.operations import get_file_from_branch, run_gh_command
from claudestep.application.services.metadata_service import MetadataService
from claudestep.domain.models import ProjectStats, StatisticsReport, TeamMemberStats


class StatisticsService:
    """Service for collecting and aggregating project statistics"""

    def __init__(self, repo: str, metadata_service: MetadataService):
        """Initialize the statistics service

        Args:
            repo: GitHub repository (owner/name)
            metadata_service: MetadataService instance for accessing metadata
        """
        self.repo = repo
        self.metadata_service = metadata_service

    # Public API methods

    def collect_all_statistics(
        self, config_path: Optional[str] = None, days_back: int = 30
    ) -> StatisticsReport:
        """Collect statistics for all projects and team members

        Args:
            config_path: Optional path to specific config (for single project mode)
            days_back: Days to look back for team member stats

        Returns:
            Complete StatisticsReport
        """
        report = StatisticsReport()
        report.generated_at = datetime.utcnow()

        if not self.repo:
            print("Warning: GITHUB_REPOSITORY not set")
            return report

        # Get base branch from environment
        base_branch = os.environ.get("BASE_BRANCH", "main")
        label = "claudestep"
        all_reviewers = set()
        projects_data = []  # List of (project_name, reviewers)

        if config_path:
            # Single project mode - fetch config from GitHub API
            print(f"Single project mode: {config_path}")

            try:
                # Extract project name from path
                # Path format: claude-step/{project}/configuration.yml
                project_name = os.path.basename(os.path.dirname(config_path))
                config_file_path = f"claude-step/{project_name}/configuration.yml"

                # Fetch configuration from GitHub API
                config_content = get_file_from_branch(self.repo, base_branch, config_file_path)
                if not config_content:
                    print(f"Error: Configuration file not found in branch '{base_branch}'")
                    return report

                config = load_config_from_string(config_content, config_file_path)
                reviewers_config = config.get("reviewers", [])
                reviewers = [r.get("username") for r in reviewers_config if "username" in r]

                projects_data.append((project_name, reviewers))
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
                    config_file_path = f"claude-step/{project_name}/configuration.yml"

                    # Fetch configuration from GitHub API
                    config_content = get_file_from_branch(self.repo, base_branch, config_file_path)
                    if not config_content:
                        print(f"Warning: Configuration file not found for project {project_name} in branch '{base_branch}', skipping")
                        continue

                    config = load_config_from_string(config_content, config_file_path)
                    reviewers_config = config.get("reviewers", [])
                    reviewers = [
                        r.get("username") for r in reviewers_config if "username" in r
                    ]

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
        self, project_name: str, base_branch: str = "main", label: str = "claudestep"
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

        spec_file_path = f"claude-step/{project_name}/spec.md"
        stats = ProjectStats(project_name, spec_file_path)

        # Fetch spec.md from GitHub API
        try:
            spec_content = get_file_from_branch(self.repo, base_branch, spec_file_path)
            if not spec_content:
                print(f"  Warning: Spec file not found in branch '{base_branch}', skipping project")
                return None

            total, completed = self.count_tasks(spec_content)
            stats.total_tasks = total
            stats.completed_tasks = completed
            print(f"  Tasks: {completed}/{total} completed")
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
        self, reviewers: List[str], days_back: int = 30, label: str = "claudestep"
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
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
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
        self, project_name: str, label: str = "claudestep"
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
    def count_tasks(spec_input: str) -> Tuple[int, int]:
        """Returns (total, completed) task counts from spec.md

        Args:
            spec_input: Either spec.md content as string OR path to spec.md file

        Returns:
            Tuple of (total_tasks, completed_tasks)

        Raises:
            ClaudeStepFileNotFoundError: If spec_input is a file path that doesn't exist
        """
        # Determine if input is a file path or content string
        # If it looks like a file path (contains / or \) and exists, read it
        if ('/' in spec_input or '\\' in spec_input) and os.path.exists(spec_input):
            # It's a file path
            with open(spec_input, "r") as f:
                content = f.read()
        elif ('/' in spec_input or '\\' in spec_input):
            # Looks like a file path but doesn't exist
            raise ClaudeStepFileNotFoundError(f"Spec file not found: {spec_input}")
        else:
            # It's content string
            content = spec_input

        # Count total tasks (both checked and unchecked)
        # Pattern matches: - [ ], - [x], - [X]
        total = len(re.findall(r"^\s*- \[[xX \]]", content, re.MULTILINE))

        # Count completed tasks
        # Pattern matches: - [x], - [X]
        completed = len(re.findall(r"^\s*- \[[xX]\]", content, re.MULTILINE))

        return total, completed

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
