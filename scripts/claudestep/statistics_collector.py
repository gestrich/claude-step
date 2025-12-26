"""Statistics collection from GitHub API and spec.md files"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from claudestep.config import load_json
from claudestep.exceptions import FileNotFoundError as ClaudeStepFileNotFoundError
from claudestep.github_operations import run_gh_command
from claudestep.models import ProjectStats, StatisticsReport, TeamMemberStats
from claudestep.task_management import get_in_progress_task_indices


def count_tasks(spec_path: str) -> Tuple[int, int]:
    """Returns (total, completed) task counts from spec.md

    Args:
        spec_path: Path to spec.md file

    Returns:
        Tuple of (total_tasks, completed_tasks)

    Raises:
        ClaudeStepFileNotFoundError: If spec file doesn't exist
    """
    if not os.path.exists(spec_path):
        raise ClaudeStepFileNotFoundError(f"Spec file not found: {spec_path}")

    with open(spec_path, "r") as f:
        content = f.read()

    # Count total tasks (both checked and unchecked)
    # Pattern matches: - [ ], - [x], - [X]
    total = len(re.findall(r"^\s*- \[[xX \]]", content, re.MULTILINE))

    # Count completed tasks
    # Pattern matches: - [x], - [X]
    completed = len(re.findall(r"^\s*- \[[xX]\]", content, re.MULTILINE))

    return total, completed


def collect_team_member_stats(
    reviewers: List[str], repo: str, days_back: int = 30, label: str = "claudestep"
) -> Dict[str, TeamMemberStats]:
    """Collect PR statistics for team members

    Args:
        reviewers: List of GitHub usernames to track
        repo: GitHub repository (owner/name)
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
                repo,
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
                repo,
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


def collect_project_stats(
    project_name: str, spec_path: str, repo: str, label: str = "claudestep"
) -> ProjectStats:
    """Collect statistics for a single project

    Args:
        project_name: Name of the project
        spec_path: Path to spec.md file
        repo: GitHub repository
        label: GitHub label for filtering

    Returns:
        ProjectStats object
    """
    print(f"Collecting statistics for project: {project_name}")

    stats = ProjectStats(project_name, spec_path)

    # Count total and completed tasks from spec.md
    try:
        total, completed = count_tasks(spec_path)
        stats.total_tasks = total
        stats.completed_tasks = completed
        print(f"  Tasks: {completed}/{total} completed")
    except ClaudeStepFileNotFoundError as e:
        print(f"  Warning: {e}")
        return stats

    # Get in-progress tasks
    try:
        in_progress_indices = get_in_progress_task_indices(repo, label, project_name)
        stats.in_progress_tasks = len(in_progress_indices)
        print(f"  In-progress: {stats.in_progress_tasks}")
    except Exception as e:
        print(f"  Warning: Failed to get in-progress tasks: {e}")
        stats.in_progress_tasks = 0

    # Calculate pending tasks
    stats.pending_tasks = max(
        0, stats.total_tasks - stats.completed_tasks - stats.in_progress_tasks
    )
    print(f"  Pending: {stats.pending_tasks}")

    return stats


def collect_all_statistics(
    config_path: Optional[str] = None, days_back: int = 30
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

    # Get GitHub repository from environment
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("Warning: GITHUB_REPOSITORY not set")
        return report

    label = "claudestep"
    all_reviewers = set()
    projects_data = []  # List of (project_name, spec_path, reviewers)

    if config_path:
        # Single project mode
        print(f"Single project mode: {config_path}")

        try:
            config = load_json(config_path)
            reviewers_config = config.get("reviewers", [])
            reviewers = [r.get("username") for r in reviewers_config if "username" in r]

            # Extract project name from path
            # Path format: refactor/{project}/configuration.json
            project_name = os.path.basename(os.path.dirname(config_path))

            # Determine spec path
            spec_path = os.path.join(os.path.dirname(config_path), "spec.md")

            projects_data.append((project_name, spec_path, reviewers))
            all_reviewers.update(reviewers)

        except Exception as e:
            print(f"Error loading config: {e}")
            return report

    else:
        # Multi-project mode - discover all projects
        print("Multi-project mode: discovering projects...")

        from claudestep.commands.discover import find_all_projects

        project_names = find_all_projects()

        if not project_names:
            print("No projects found")
            return report

        for project_name in project_names:
            try:
                project_path = os.path.join("refactor", project_name)
                config_file = os.path.join(project_path, "configuration.json")
                spec_file = os.path.join(project_path, "spec.md")

                # Load config to get reviewers
                config = load_json(config_file)
                reviewers_config = config.get("reviewers", [])
                reviewers = [
                    r.get("username") for r in reviewers_config if "username" in r
                ]

                projects_data.append((project_name, spec_file, reviewers))
                all_reviewers.update(reviewers)

            except Exception as e:
                print(f"Warning: Failed to load project {project_name}: {e}")
                continue

    print(f"\nProcessing {len(projects_data)} project(s)...")
    print(f"Tracking {len(all_reviewers)} unique reviewer(s)")

    # Collect project statistics
    for project_name, spec_path, _ in projects_data:
        try:
            project_stats = collect_project_stats(project_name, spec_path, repo, label)
            report.add_project(project_stats)
        except Exception as e:
            print(f"Error collecting stats for {project_name}: {e}")

    # Collect team member statistics across all projects
    if all_reviewers:
        try:
            team_stats = collect_team_member_stats(
                list(all_reviewers), repo, days_back, label
            )
            for username, stats in team_stats.items():
                report.add_team_member(stats)
        except Exception as e:
            print(f"Error collecting team member stats: {e}")

    return report
