"""CLI command for statistics workflow.

Orchestrates Service Layer classes to coordinate statistics collection and reporting.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import json
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from claudechain.domain.project import Project
from claudechain.infrastructure.github.actions import GitHubActionsHelper
from claudechain.infrastructure.repositories.project_repository import ProjectRepository
from claudechain.services.composite.statistics_service import StatisticsService
from claudechain.services.core.pr_service import PRService


def cmd_statistics(
    gh: GitHubActionsHelper,
    repo: str,
    base_branch: str = "main",
    config_path: Optional[str] = None,
    days_back: int = 30,
    format_type: str = "slack",
    slack_webhook_url: str = "",
    show_assignee_stats: bool = False,
    run_url: str = "",
) -> int:
    """Orchestrate statistics workflow using Service Layer classes.

    This command instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern
    where CLI acts as thin orchestration layer.

    Args:
        gh: GitHub Actions helper instance
        repo: GitHub repository (owner/name)
        base_branch: Base branch for single-project mode (default: "main")
        config_path: Optional path to configuration file (single-project mode)
        days_back: Days to look back for statistics (default: 30)
        format_type: Output format - "slack" or "json" (default: "slack")
        slack_webhook_url: Slack webhook URL for posting statistics (default: "")
        show_assignee_stats: Whether to show assignee leaderboard (default: False)
        run_url: GitHub Actions run URL for "See details" footer (default: "")

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:

        print("=== ClaudeChain Statistics Collection ===")
        print(f"Days back: {days_back}")

        # Initialize services (dependency injection pattern)
        project_repository = ProjectRepository(repo)
        pr_service = PRService(repo)
        statistics_service = StatisticsService(repo, project_repository, pr_service)

        # Discover projects (CLI handles discovery, service handles collection)
        projects = _discover_projects(config_path, base_branch, pr_service)

        if not projects:
            print("No projects found")
            gh.write_output("has_statistics", "false")
            return 0

        print()

        # Collect all statistics
        report = statistics_service.collect_all_statistics(
            projects=projects,
            days_back=days_back,
            show_assignee_stats=show_assignee_stats,
        )

        print(f"\n=== Collection Complete ===")
        print(f"Projects found: {len(report.project_stats)}")
        print(f"Team members tracked: {len(report.team_stats)}")
        print()

        # Generate outputs based on format
        if format_type == "slack":
            # DEBUG: Print project data before formatting
            print("=== DEBUG: Project Data Before Formatting ===")
            for project_name, stats in report.project_stats.items():
                print(f"Project: {project_name}")
                print(f"  - completed_tasks: {stats.completed_tasks}")
                print(f"  - total_tasks: {stats.total_tasks}")
                print(f"  - total_cost_usd: {stats.total_cost_usd}")
                print(f"  - open_prs count: {len(stats.open_prs)}")
                for i, pr in enumerate(stats.open_prs):
                    print(f"  - open_pr[{i}]:")
                    print(f"      number: {pr.number}")
                    print(f"      title: {pr.title}")
                    print(f"      task_description: {pr.task_description}")
                    print(f"      url: {pr.url}")
                    print(f"      days_open: {pr.days_open}")
            print()

            # Generate Block Kit JSON for Slack webhook
            slack_payload = report.format_for_slack_blocks(
                show_assignee_stats=show_assignee_stats,
                run_url=run_url or None,
            )

            # DEBUG: Print the blocks array to verify formatting
            print("=== DEBUG: Generated Blocks ===")
            for i, block in enumerate(slack_payload.get("blocks", [])):
                block_type = block.get("type", "unknown")
                if block_type == "section":
                    text_obj = block.get("text", {})
                    text_content = text_obj.get("text", "")
                    print(f"Block[{i}] type=section: {repr(text_content[:100])}")
                elif block_type == "context":
                    elements = block.get("elements", [])
                    if elements:
                        text_content = elements[0].get("text", "")
                        print(f"Block[{i}] type=context: {repr(text_content[:100])}")
                else:
                    print(f"Block[{i}] type={block_type}")
            print()

            slack_json = json.dumps(slack_payload)
            gh.write_output("slack_message", slack_json)
            gh.write_output("has_statistics", "true")
            gh.write_output("slack_webhook_url", slack_webhook_url)
            print("=== Slack Output (Block Kit JSON) ===")
            print(json.dumps(slack_payload, indent=2))
            print()

        if format_type == "json" or format_type == "slack":
            # Always output JSON for programmatic access
            json_data = report.to_json()
            gh.write_output("statistics_json", json_data)

        # Write GitHub Step Summary
        gh.write_step_summary("# ClaudeChain Statistics Report")
        gh.write_step_summary("")
        gh.write_step_summary(f"*Generated: {datetime.now(timezone.utc).isoformat()}*")
        gh.write_step_summary("")

        # Add leaderboard to step summary (only if enabled)
        if show_assignee_stats:
            leaderboard = report.format_leaderboard()
            if leaderboard:
                gh.write_step_summary(leaderboard)
                gh.write_step_summary("")

        # Add project summaries to step summary
        if report.project_stats:
            gh.write_step_summary("## Project Progress")
            gh.write_step_summary("")
            for project_name in sorted(report.project_stats.keys()):
                stats = report.project_stats[project_name]
                gh.write_step_summary(stats.format_summary())
                gh.write_step_summary("")

            # Add warnings section if there are projects needing attention
            warnings_section = report.format_warnings_section(for_slack=False)
            if warnings_section:
                gh.write_step_summary(warnings_section)
                gh.write_step_summary("")

            # Add detailed task view with orphaned PRs
            gh.write_step_summary("## Detailed Task View")
            gh.write_step_summary("")
            gh.write_step_summary(report.format_project_details())
            gh.write_step_summary("")
        else:
            gh.write_step_summary("## Project Progress")
            gh.write_step_summary("")
            gh.write_step_summary("*No projects found*")
            gh.write_step_summary("")

        # Add team member summaries (detailed view, only if enabled)
        if show_assignee_stats:
            if report.team_stats:
                gh.write_step_summary("## Team Member Activity (Detailed)")
                gh.write_step_summary("")
                # Sort by activity level (merged PRs desc, then username)
                sorted_members = sorted(
                    report.team_stats.items(), key=lambda x: (-x[1].merged_count, x[0])
                )
                for username, stats in sorted_members:
                    gh.write_step_summary(stats.format_summary())
                    gh.write_step_summary("")
            else:
                gh.write_step_summary("## Team Member Activity")
                gh.write_step_summary("")
                gh.write_step_summary("*No team member activity found*")
                gh.write_step_summary("")

        print("✅ Statistics generated successfully")
        return 0

    except Exception as e:
        gh.set_error(f"Statistics collection failed: {str(e)}")
        gh.write_output("has_statistics", "false")
        gh.write_step_summary("# ClaudeChain Statistics Report")
        gh.write_step_summary("")
        gh.write_step_summary(f"❌ **Error**: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1


def _discover_projects(
    config_path: Optional[str],
    base_branch: str,
    pr_service: PRService,
) -> List[Tuple[str, str]]:
    """Discover projects to collect statistics for.

    CLI is responsible for project discovery. This function handles both:
    - Single-project mode: when config_path is provided
    - Multi-project mode: discovers from labeled PRs

    Args:
        config_path: Optional path to configuration file (single-project mode)
        base_branch: Base branch for single-project mode
        pr_service: PRService instance for multi-project discovery

    Returns:
        List of (project_name, spec_branch) tuples
    """
    if config_path:
        # Single project mode
        print(f"Single project mode: {config_path}")
        project = Project.from_config_path(config_path)
        return [(project.name, base_branch)]

    # Multi-project mode - discover from labeled PRs
    print("Multi-project mode: discovering projects from GitHub PRs...")
    project_branches = pr_service.get_unique_projects(label="claudechain")
    print(f"Found {len(project_branches)} unique project(s)")

    return list(project_branches.items())
