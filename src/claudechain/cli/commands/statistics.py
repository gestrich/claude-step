"""CLI command for statistics workflow.

Orchestrates Service Layer classes to coordinate statistics collection and reporting.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

from datetime import datetime, timezone
from typing import Optional

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
) -> int:
    """Orchestrate statistics workflow using Service Layer classes.

    This command instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern
    where CLI acts as thin orchestration layer.

    Args:
        gh: GitHub Actions helper instance
        repo: GitHub repository (owner/name)
        base_branch: Base branch to fetch specs from (default: "main")
        config_path: Optional path to configuration file
        days_back: Days to look back for statistics (default: 30)
        format_type: Output format - "slack" or "json" (default: "slack")
        slack_webhook_url: Slack webhook URL for posting statistics (default: "")
        show_assignee_stats: Whether to show assignee leaderboard (default: False)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:

        print("=== ClaudeChain Statistics Collection ===")
        print(f"Days back: {days_back}")
        if config_path:
            print(f"Config path: {config_path}")
        else:
            print("Mode: All projects")
        print()

        # Initialize services (dependency injection pattern)
        project_repository = ProjectRepository(repo)
        pr_service = PRService(repo)
        statistics_service = StatisticsService(repo, project_repository, pr_service, base_branch)

        # Collect all statistics
        report = statistics_service.collect_all_statistics(
            config_path=config_path if config_path else None,
            days_back=days_back,
            show_assignee_stats=show_assignee_stats,
        )

        print(f"\n=== Collection Complete ===")
        print(f"Projects found: {len(report.project_stats)}")
        print(f"Team members tracked: {len(report.team_stats)}")
        print()

        # Generate outputs based on format
        if format_type == "slack":
            slack_text = report.format_for_slack(
                show_assignee_stats=show_assignee_stats,
            )
            gh.write_output("slack_message", slack_text)
            gh.write_output("has_statistics", "true")
            gh.write_output("slack_webhook_url", slack_webhook_url)
            print("=== Slack Output ===")
            print(slack_text)
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
