#!/usr/bin/env python3
"""
ClaudeChain - GitHub Actions Helper Script

Entry point for the ClaudeChain automation tool.
Run with: python3 -m claudechain <command>
"""

import os
import sys

from claudechain.cli.commands.auto_start import cmd_auto_start, cmd_auto_start_summary
from claudechain.cli.commands.create_artifact import cmd_create_artifact
from claudechain.cli.commands.discover import main as cmd_discover
from claudechain.cli.commands.discover_ready import main as cmd_discover_ready
from claudechain.cli.commands.finalize import cmd_finalize
from claudechain.cli.commands.format_slack_notification import cmd_format_slack_notification
from claudechain.cli.commands.parse_claude_result import cmd_parse_claude_result
from claudechain.cli.commands.parse_event import main as cmd_parse_event
from claudechain.cli.commands.post_pr_comment import cmd_post_pr_comment
from claudechain.cli.commands.prepare import cmd_prepare
from claudechain.cli.commands.prepare_summary import cmd_prepare_summary
from claudechain.cli.commands.run_action_script import cmd_run_action_script
from claudechain.cli.commands.statistics import cmd_statistics
from claudechain.cli.parser import create_parser
from claudechain.domain.constants import DEFAULT_ALLOWED_TOOLS, DEFAULT_BASE_BRANCH
from claudechain.infrastructure.github.actions import GitHubActionsHelper


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
        # Use env var if set and non-empty, otherwise fall back to constant
        env_allowed_tools = os.environ.get("CLAUDE_ALLOWED_TOOLS", "")
        return cmd_prepare(
            args,
            gh,
            default_allowed_tools=env_allowed_tools if env_allowed_tools else DEFAULT_ALLOWED_TOOLS
        )
    elif args.command == "finalize":
        return cmd_finalize(args, gh)
    elif args.command == "prepare-summary":
        return cmd_prepare_summary(
            gh=gh,
            pr_number=os.environ.get("PR_NUMBER", ""),
            task=os.environ.get("TASK_DESCRIPTION", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
            action_path=os.environ.get("ACTION_PATH", ""),
            base_branch=os.environ.get("BASE_BRANCH", "")
        )
    elif args.command == "post-pr-comment":
        return cmd_post_pr_comment(
            gh=gh,
            pr_number=os.environ.get("PR_NUMBER", "").strip(),
            summary_file_path=os.environ.get("SUMMARY_FILE", "").strip(),
            main_execution_file=os.environ.get("MAIN_EXECUTION_FILE", ""),
            summary_execution_file=os.environ.get("SUMMARY_EXECUTION_FILE", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
            task=os.environ.get("TASK_DESCRIPTION", ""),
        )
    elif args.command == "create-artifact":
        return cmd_create_artifact(
            gh=gh,
            cost_breakdown_json=os.environ.get("COST_BREAKDOWN", ""),
            pr_number=os.environ.get("PR_NUMBER", ""),
            task=os.environ.get("TASK_DESCRIPTION", ""),
            task_index=os.environ.get("TASK_INDEX", ""),
            task_hash=os.environ.get("TASK_HASH", ""),
            project=os.environ.get("PROJECT", ""),
            branch_name=os.environ.get("BRANCH_NAME", ""),
            assignee=os.environ.get("ASSIGNEE", ""),
            run_id=os.environ.get("GITHUB_RUN_ID", ""),
        )
    elif args.command == "format-slack-notification":
        return cmd_format_slack_notification(
            gh=gh,
            pr_number=os.environ.get("PR_NUMBER", ""),
            pr_url=os.environ.get("PR_URL", ""),
            project_name=os.environ.get("PROJECT_NAME", ""),
            task=os.environ.get("TASK_DESCRIPTION", ""),
            cost_breakdown_json=os.environ.get("COST_BREAKDOWN", ""),
            repo=os.environ.get("GITHUB_REPOSITORY", ""),
            assignee=os.environ.get("ASSIGNEE", ""),
        )
    elif args.command == "statistics":
        # Use env var if set and non-empty, otherwise fall back to constant
        env_base_branch = args.base_branch or os.environ.get("BASE_BRANCH", "")
        return cmd_statistics(
            gh=gh,
            repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
            base_branch=env_base_branch if env_base_branch else DEFAULT_BASE_BRANCH,
            config_path=args.config_path or os.environ.get("CONFIG_PATH"),
            days_back=args.days_back or int(os.environ.get("STATS_DAYS_BACK", "30")),
            format_type=args.format or os.environ.get("STATS_FORMAT", "slack"),
            slack_webhook_url=os.environ.get("SLACK_WEBHOOK_URL", ""),
            show_assignee_stats=args.show_assignee_stats or os.environ.get("SHOW_ASSIGNEE_STATS", "").lower() == "true",
            run_url=os.environ.get("GITHUB_RUN_URL", ""),
        )
    elif args.command == "auto-start":
        # Parse auto_start_enabled from argument or environment variable
        # Default to True if not set. Convert string "false" to boolean False.
        auto_start_enabled_str = getattr(args, 'auto_start_enabled', None)
        if auto_start_enabled_str is None:
            env_value = os.environ.get("AUTO_START_ENABLED", "true")
            auto_start_enabled = env_value.lower() != 'false'
        else:
            auto_start_enabled = auto_start_enabled_str

        # Use env var if set and non-empty, otherwise fall back to constant
        env_base_branch_auto = args.base_branch or os.environ.get("BASE_BRANCH", "")
        return cmd_auto_start(
            gh=gh,
            repo=args.repo or os.environ.get("GITHUB_REPOSITORY", ""),
            base_branch=env_base_branch_auto if env_base_branch_auto else DEFAULT_BASE_BRANCH,
            ref_before=args.ref_before or os.environ.get("REF_BEFORE", ""),
            ref_after=args.ref_after or os.environ.get("REF_AFTER", ""),
            auto_start_enabled=auto_start_enabled,
        )
    elif args.command == "auto-start-summary":
        return cmd_auto_start_summary(
            gh=gh,
            triggered_projects=args.triggered_projects or os.environ.get("TRIGGERED_PROJECTS", ""),
            failed_projects=args.failed_projects or os.environ.get("FAILED_PROJECTS", ""),
        )
    elif args.command == "parse-claude-result":
        return cmd_parse_claude_result(
            gh=gh,
            execution_file=os.environ.get("EXECUTION_FILE", ""),
            result_type=os.environ.get("RESULT_TYPE", "main"),
        )
    elif args.command == "run-action-script":
        return cmd_run_action_script(
            gh=gh,
            script_type=args.type,
            project_path=args.project_path,
            working_directory=os.getcwd(),
        )
    elif args.command == "parse-event":
        # parse-event reads from environment variables
        # This allows it to work with the action.yml which sets env vars
        return cmd_parse_event()
    else:
        gh.set_error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
