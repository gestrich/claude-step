"""Prepare summary command - generate prompt for PR summary"""

import os

from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.domain.cost_breakdown import CostBreakdown
from claudestep.domain.constants import PR_SUMMARY_FILE_PATH


def cmd_prepare_summary(
    gh: GitHubActionsHelper,
    pr_number: str,
    task: str,
    repo: str,
    run_id: str,
    action_path: str,
    main_execution_file: str,
    summary_execution_file: str
) -> int:
    """Handle 'prepare-summary' subcommand - generate prompt for PR summary comment

    This command generates a prompt for Claude Code to analyze a PR diff and post
    a summary comment. It also extracts cost information from both the main task
    execution and any previous summary generation.

    All parameters passed explicitly, no environment variable access.

    Args:
        gh: GitHub Actions helper instance
        pr_number: PR number to generate summary for
        task: Task description
        repo: GitHub repository (owner/name format)
        run_id: GitHub Actions run ID
        action_path: Path to the action directory
        main_execution_file: Path to main execution file
        summary_execution_file: Path to summary execution file

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
        # Use new resources path in src/claudestep/resources/prompts/
        template_path = os.path.join(action_path, "src/claudestep/resources/prompts/summary_prompt.md")

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

        print(f"✅ Summary prompt prepared for PR #{pr_number}")
        print(f"   Task: {task}")
        print(f"   Prompt length: {len(summary_prompt)} characters")

        # Extract costs using domain model
        cost_breakdown = CostBreakdown.from_execution_files(
            main_execution_file,
            summary_execution_file
        )

        # Output cost values
        gh.write_output("main_cost", f"{cost_breakdown.main_cost:.6f}")
        gh.write_output("summary_cost", f"{cost_breakdown.summary_cost:.6f}")
        gh.write_output("total_cost", f"{cost_breakdown.total_cost:.6f}")
        gh.write_output("summary_file", PR_SUMMARY_FILE_PATH)

        print(f"💰 Cost extraction:")
        print(f"   Main task: ${cost_breakdown.main_cost:.6f} USD")
        print(f"   Summary generation: ${cost_breakdown.summary_cost:.6f} USD")
        print(f"   Total: ${cost_breakdown.total_cost:.6f} USD")

        return 0

    except Exception as e:
        gh.set_error(f"Failed to prepare summary: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
