"""Prepare summary command - generate prompt for PR summary"""

import argparse
import os

from claudestep.infrastructure.github.actions import GitHubActionsHelper


def cmd_prepare_summary(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'prepare-summary' subcommand - generate prompt for PR summary comment

    This command reads environment variables and generates a prompt for Claude Code
    to analyze a PR diff and post a summary comment.

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:
        # Read environment variables
        pr_number = os.environ.get("PR_NUMBER", "")
        task = os.environ.get("TASK", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        run_id = os.environ.get("GITHUB_RUN_ID", "")
        action_path = os.environ.get("ACTION_PATH", "")

        # Validate required inputs
        if not pr_number:
            gh.set_notice("No PR number provided, skipping summary generation")
            return 0  # Not an error, just skip

        if not task:
            gh.set_error("TASK environment variable is required")
            return 1

        if not repo or not run_id:
            gh.set_error("GITHUB_REPOSITORY and GITHUB_RUN_ID are required")
            return 1

        # Construct workflow URL
        workflow_url = f"https://github.com/{repo}/actions/runs/{run_id}"

        # Load prompt template
        template_path = os.path.join(action_path, "scripts/claudestep/prompts/summary_prompt.md")

        try:
            with open(template_path, "r") as f:
                template = f.read()
        except FileNotFoundError:
            gh.set_error(f"Prompt template not found: {template_path}")
            return 1

        # Substitute variables in template
        summary_prompt = template.replace("{TASK_DESCRIPTION}", task)
        summary_prompt = summary_prompt.replace("{PR_NUMBER}", pr_number)
        summary_prompt = summary_prompt.replace("{WORKFLOW_URL}", workflow_url)

        # Write output
        gh.write_output("summary_prompt", summary_prompt)

        print(f"✅ Summary prompt prepared for PR #{pr_number}")
        print(f"   Task: {task}")
        print(f"   Prompt length: {len(summary_prompt)} characters")

        return 0

    except Exception as e:
        gh.set_error(f"Failed to prepare summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
