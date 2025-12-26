#!/usr/bin/env python3
"""
ClaudeStep - GitHub Actions Helper Script

Entry point for the ClaudeStep automation tool.
Run with: python3 -m claudestep <command>
"""

import argparse
import sys

from claudestep.commands.discover import main as cmd_discover
from claudestep.commands.discover_ready import main as cmd_discover_ready
from claudestep.commands.finalize import cmd_finalize
from claudestep.commands.prepare import cmd_prepare
from claudestep.commands.statistics import cmd_statistics
from claudestep.github_actions import GitHubActionsHelper


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="ClaudeStep - GitHub Actions Helper Script"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Consolidated commands
    parser_discover = subparsers.add_parser("discover", help="Discover all refactor projects in the repository")
    parser_discover_ready = subparsers.add_parser("discover-ready", help="Discover projects with capacity and available tasks")
    parser_prepare = subparsers.add_parser("prepare", help="Prepare everything for Claude Code execution")
    parser_finalize = subparsers.add_parser("finalize", help="Finalize after Claude Code execution (commit, PR, summary)")
    parser_statistics = subparsers.add_parser("statistics", help="Generate statistics and reports")

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
    elif args.command == "statistics":
        return cmd_statistics(args, gh)
    else:
        gh.set_error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
