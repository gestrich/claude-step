"""Statistics command - generate and output reports"""

import argparse
import os
from datetime import datetime

from claudestep.domain.exceptions import ConfigurationError
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.application.collectors.statistics_collector import collect_all_statistics


def cmd_statistics(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'statistics' subcommand - compute and output reports

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get environment variables
        config_path = os.environ.get("CONFIG_PATH", "")
        days_back = int(os.environ.get("STATS_DAYS_BACK", "30"))
        format_type = os.environ.get(
            "STATS_FORMAT", "slack"
        )  # slack, json, summary

        print("=== ClaudeStep Statistics Collection ===")
        print(f"Days back: {days_back}")
        if config_path:
            print(f"Config path: {config_path}")
        else:
            print("Mode: All projects")
        print()

        # Collect all statistics
        report = collect_all_statistics(
            config_path=config_path if config_path else None, days_back=days_back
        )

        print(f"\n=== Collection Complete ===")
        print(f"Projects found: {len(report.project_stats)}")
        print(f"Team members tracked: {len(report.team_stats)}")
        print()

        # Generate outputs based on format
        if format_type == "slack":
            slack_text = report.format_for_slack()
            gh.write_output("slack_message", slack_text)
            gh.write_output("has_statistics", "true")
            print("=== Slack Output ===")
            print(slack_text)
            print()

        if format_type == "json" or format_type == "slack":
            # Always output JSON for programmatic access
            json_data = report.to_json()
            gh.write_output("statistics_json", json_data)

        # Write GitHub Step Summary
        gh.write_step_summary("# ClaudeStep Statistics Report")
        gh.write_step_summary("")
        gh.write_step_summary(f"*Generated: {datetime.now().isoformat()}*")
        gh.write_step_summary("")

        # Add leaderboard to step summary (show first - most engaging!)
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
        else:
            gh.write_step_summary("## Project Progress")
            gh.write_step_summary("")
            gh.write_step_summary("*No projects found*")
            gh.write_step_summary("")

        # Add team member summaries (detailed view)
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
        gh.write_step_summary("# ClaudeStep Statistics Report")
        gh.write_step_summary("")
        gh.write_step_summary(f"❌ **Error**: {str(e)}")
        import traceback

        traceback.print_exc()
        return 1
