"""
CLI Argument Parser

This module handles command-line argument parsing for ClaudeStep.
"""

import argparse


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser for ClaudeStep CLI.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="ClaudeStep - GitHub Actions Helper Script"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Consolidated commands
    parser_discover = subparsers.add_parser(
        "discover",
        help="Discover all refactor projects in the repository"
    )
    parser_discover_ready = subparsers.add_parser(
        "discover-ready",
        help="Discover projects with capacity and available tasks"
    )
    parser_prepare = subparsers.add_parser(
        "prepare",
        help="Prepare everything for Claude Code execution"
    )
    parser_finalize = subparsers.add_parser(
        "finalize",
        help="Finalize after Claude Code execution (commit, PR, summary)"
    )
    parser_prepare_summary = subparsers.add_parser(
        "prepare-summary",
        help="Prepare prompt for PR summary generation"
    )
    parser_extract_cost = subparsers.add_parser(
        "extract-cost",
        help="Extract cost from workflow logs"
    )
    parser_add_cost_comment = subparsers.add_parser(
        "add-cost-comment",
        help="Post cost breakdown comment to PR"
    )
    parser_notify_pr = subparsers.add_parser(
        "notify-pr",
        help="Generate Slack notification for created PR"
    )
    parser_statistics = subparsers.add_parser(
        "statistics",
        help="Generate statistics and reports"
    )
    parser_statistics.add_argument(
        "--repo",
        help="GitHub repository (owner/name)"
    )
    parser_statistics.add_argument(
        "--base-branch",
        help="Base branch to fetch specs from (default: main)"
    )
    parser_statistics.add_argument(
        "--config-path",
        help="Path to configuration file"
    )
    parser_statistics.add_argument(
        "--days-back",
        type=int,
        help="Days to look back for statistics (default: 30)"
    )
    parser_statistics.add_argument(
        "--format",
        choices=["slack", "json"],
        help="Output format (default: slack)"
    )
    parser_auto_start = subparsers.add_parser(
        "auto-start",
        help="Detect new projects and trigger workflows"
    )
    parser_auto_start.add_argument(
        "--repo",
        help="GitHub repository (owner/name)"
    )
    parser_auto_start.add_argument(
        "--base-branch",
        help="Base branch to fetch specs from (default: main)"
    )
    parser_auto_start.add_argument(
        "--ref-before",
        help="Git ref before the push"
    )
    parser_auto_start.add_argument(
        "--ref-after",
        help="Git ref after the push"
    )
    parser_auto_start.add_argument(
        "--auto-start-enabled",
        type=lambda x: x.lower() != 'false',
        help="Whether auto-start is enabled (default: true, set to 'false' to disable)"
    )
    parser_auto_start_summary = subparsers.add_parser(
        "auto-start-summary",
        help="Generate summary for auto-start workflow"
    )
    parser_auto_start_summary.add_argument(
        "--triggered-projects",
        help="Space-separated list of successfully triggered projects"
    )
    parser_auto_start_summary.add_argument(
        "--failed-projects",
        help="Space-separated list of projects that failed to trigger"
    )

    return parser
