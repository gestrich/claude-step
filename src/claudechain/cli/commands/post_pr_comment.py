"""
Post unified PR comment with summary and cost breakdown.

This command combines the AI-generated summary and cost breakdown into a single
comment, using the reliable Python-based posting mechanism.
"""

import os
import subprocess
import tempfile

from claudechain.domain.cost_breakdown import CostBreakdown
from claudechain.domain.formatters import MarkdownReportFormatter
from claudechain.domain.formatting import format_usd
from claudechain.domain.pr_created_report import PullRequestCreatedReport
from claudechain.domain.summary_file import SummaryFile
from claudechain.infrastructure.github.actions import GitHubActionsHelper


def cmd_post_pr_comment(
    gh: GitHubActionsHelper,
    pr_number: str,
    summary_file_path: str,
    main_execution_file: str,
    summary_execution_file: str,
    repo: str,
    run_id: str,
    task: str = "",
) -> int:
    """
    Post a unified comment with PR summary and cost breakdown.

    All parameters passed explicitly, no environment variable access.

    Args:
        gh: GitHub Actions helper for outputs and errors
        pr_number: Pull request number
        summary_file_path: Path to file containing AI-generated summary
        main_execution_file: Path to main execution file
        summary_execution_file: Path to summary execution file
        repo: Repository in format owner/repo
        run_id: Workflow run ID
        task: Task description (for workflow summary)

    Outputs:
        comment_posted: "true" if comment was posted, "false" otherwise
        cost_breakdown: JSON string with complete cost breakdown (CostBreakdown.to_json())

    Returns:
        0 on success, 1 on error
    """
    # If no PR number, skip gracefully
    if not pr_number or not pr_number.strip():
        print("::notice::No PR number provided, skipping PR comment")
        gh.write_output("comment_posted", "false")
        return 0

    if not repo:
        gh.set_error("GITHUB_REPOSITORY environment variable is required")
        return 1

    if not run_id:
        gh.set_error("GITHUB_RUN_ID environment variable is required")
        return 1

    try:
        # Extract costs from execution files
        cost_breakdown = CostBreakdown.from_execution_files(
            main_execution_file,
            summary_execution_file
        )

        # Output complete cost breakdown for downstream steps (single structured output)
        gh.write_output("cost_breakdown", cost_breakdown.to_json())

        # Use domain models for parsing and formatting
        summary = SummaryFile.from_file(summary_file_path)

        # Create report and format comment using domain model
        pr_url = f"https://github.com/{repo}/pull/{pr_number}"
        report = PullRequestCreatedReport(
            pr_number=pr_number,
            pr_url=pr_url,
            project_name="",  # Not shown in PR comment
            task=task,
            cost_breakdown=cost_breakdown,
            repo=repo,
            run_id=run_id,
            summary_content=summary.content if summary.has_content else None,
        )

        formatter = MarkdownReportFormatter()
        comment = formatter.format(report.build_comment_elements())

        # Write comment to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(comment)
            temp_file = f.name

        try:
            # Post comment to PR using gh CLI
            print(f"Posting PR comment to PR #{pr_number}...")
            subprocess.run(
                ["gh", "pr", "comment", pr_number, "--body-file", temp_file],
                check=True,
                capture_output=True,
                text=True
            )

            print(f"✅ PR comment posted to PR #{pr_number}")
            if summary.has_content:
                print("   - AI-generated summary included")
            print(f"   - Main task: {format_usd(cost_breakdown.main_cost)}")
            print(f"   - PR summary: {format_usd(cost_breakdown.summary_cost)}")
            print(f"   - Total: {format_usd(cost_breakdown.total_cost)}")

            # Write workflow summary to GITHUB_STEP_SUMMARY
            workflow_summary = formatter.format(report.build_workflow_summary_elements())
            gh.write_step_summary(workflow_summary)

            gh.write_output("comment_posted", "true")
            return 0

        finally:
            os.unlink(temp_file)

    except subprocess.CalledProcessError as e:
        gh.set_error(f"Failed to post comment: {e.stderr}")
        return 1
    except Exception as e:
        gh.set_error(f"Error posting PR comment: {str(e)}")
        return 1
