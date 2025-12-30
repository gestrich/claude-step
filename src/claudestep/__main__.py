#!/usr/bin/env python3
"""
ClaudeStep - GitHub Actions Helper Script

Entry point for the ClaudeStep automation tool.
Run with: python3 -m claudestep <command>
"""

import os
import sys

from claudestep.cli.commands.add_cost_comment import cmd_add_cost_comment
from claudestep.cli.commands.discover import main as cmd_discover
from claudestep.cli.commands.discover_ready import main as cmd_discover_ready
from claudestep.cli.commands.extract_cost import cmd_extract_cost
from claudestep.cli.commands.finalize import cmd_finalize
from claudestep.cli.commands.notify_pr import cmd_notify_pr
from claudestep.cli.commands.prepare import cmd_prepare
from claudestep.cli.commands.prepare_summary import cmd_prepare_summary
from claudestep.cli.commands.statistics import cmd_statistics
from claudestep.cli.parser import create_parser
from claudestep.infrastructure.github.actions import GitHubActionsHelper


def main():
    """Main entry point for the script"""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize GitHub Actions helper
    gh = GitHubActionsHelper()

    # Route to appropriate command handler
    if args.command == "discover":
        cmd_discover()
        return 0
    elif args.command == "discover-ready":
        return cmd_discover_ready()
    elif args.command == "prepare":
        return cmd_prepare(args, gh)
    elif args.command == "finalize":
        return cmd_finalize(args, gh)
    elif args.command == "prepare-summary":
        return cmd_prepare_summary(args, gh)
    elif args.command == "extract-cost":
        return cmd_extract_cost(args, gh)
    elif args.command == "add-cost-comment":
        return cmd_add_cost_comment(args, gh)
    elif args.command == "notify-pr":
        return cmd_notify_pr(args, gh)
    elif args.command == "statistics":
        return cmd_statistics(
            gh=gh,
            repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
            base_branch=args.base_branch or os.environ.get("BASE_BRANCH", "main"),
            config_path=args.config_path or os.environ.get("CONFIG_PATH"),
            days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30")),
            format_type=args.format or os.environ.get("STATS_FORMAT", "slack"),
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
        )
    else:
        gh.set_error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
