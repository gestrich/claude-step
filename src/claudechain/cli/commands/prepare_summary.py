"""Prepare summary command - generate prompt for PR summary"""

import os

from claudechain.infrastructure.github.actions import GitHubActionsHelper
from claudechain.domain.constants import PR_SUMMARY_FILE_PATH


def cmd_prepare_summary(
    gh: GitHubActionsHelper,
    pr_number: str,
    task: str,
    repo: str,
    run_id: str,
    action_path: str
) -> int:
    """Handle 'prepare-summary' subcommand - generate prompt for PR summary comment

    This command generates a prompt for Claude Code to analyze a PR diff and post
    a summary comment.

    All parameters passed explicitly, no environment variable access.

    Args:
        gh: GitHub Actions helper instance
        pr_number: PR number to generate summary for
        task: Task description
        repo: GitHub repository (owner/name format)
        run_id: GitHub Actions run ID
        action_path: Path to the action directory

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    try:

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
        # Use new resources path in src/claudechain/resources/prompts/
        template_path = os.path.join(action_path, "src/claudechain/resources/prompts/summary_prompt.md")

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
        summary_prompt = summary_prompt.replace("{SUMMARY_FILE_PATH}", PR_SUMMARY_FILE_PATH)

        # Write output
        gh.write_output("summary_prompt", summary_prompt)
        gh.write_output("summary_file", PR_SUMMARY_FILE_PATH)

        print(f"✅ Summary prompt prepared for PR #{pr_number}")
        print(f"   Task: {task}")
        print(f"   Prompt length: {len(summary_prompt)} characters")

        return 0

    except Exception as e:
        gh.set_error(f"Failed to prepare summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
