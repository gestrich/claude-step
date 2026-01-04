"""
Format Slack notification message for created PR.
"""

from claudechain.domain.cost_breakdown import CostBreakdown
from claudechain.domain.pr_created_report import PullRequestCreatedReport
from claudechain.infrastructure.github.actions import GitHubActionsHelper


def cmd_format_slack_notification(
    gh: GitHubActionsHelper,
    pr_number: str,
    pr_url: str,
    project_name: str,
    task: str,
    cost_breakdown_json: str,
    repo: str,
) -> int:
    """
    Format Slack notification message for a created PR.

    All parameters passed explicitly, no environment variable access.

    Args:
        gh: GitHub Actions helper for outputs and errors
        pr_number: Pull request number
        pr_url: Pull request URL
        project_name: Name of the project
        task: Task description
        cost_breakdown_json: JSON string with complete cost breakdown (from CostBreakdown.to_json())
        repo: Repository in format owner/repo

    Outputs:
        slack_message: Formatted Slack message in mrkdwn format
        has_pr: "true" if PR was created

    Returns:
        0 on success, 1 on error
    """
    # Strip whitespace from inputs
    pr_number = pr_number.strip()
    pr_url = pr_url.strip()
    project_name = project_name.strip()
    task = task.strip()
    cost_breakdown_json = cost_breakdown_json.strip()

    # If no PR, don't send notification
    if not pr_number or not pr_url:
        gh.write_output("has_pr", "false")
        print("No PR created, skipping Slack notification")
        return 0

    try:
        # Parse cost breakdown from structured JSON
        cost_breakdown = CostBreakdown.from_json(cost_breakdown_json)

        # Format the Slack message using domain model
        message = format_pr_notification(
            pr_number=pr_number,
            pr_url=pr_url,
            project_name=project_name,
            task=task,
            cost_breakdown=cost_breakdown,
            repo=repo,
        )

        # Output for Slack
        gh.write_output("slack_message", message)
        gh.write_output("has_pr", "true")

        print("=== Slack Notification Message ===")
        print(message)
        print()

        return 0

    except Exception as e:
        gh.set_error(f"Error generating PR notification: {str(e)}")
        gh.write_output("has_pr", "false")
        return 1


def format_pr_notification(
    pr_number: str,
    pr_url: str,
    project_name: str,
    task: str,
    cost_breakdown: CostBreakdown,
    repo: str,
) -> str:
    """
    Format PR notification for Slack in mrkdwn format.

    Args:
        pr_number: PR number
        pr_url: PR URL
        project_name: Project name
        task: Task description
        cost_breakdown: CostBreakdown with costs and per-model data
        repo: Repository name (used for workflow URL generation)

    Returns:
        Formatted Slack message in mrkdwn
    """
    # Create domain model and use its notification formatting
    # Note: run_id is not needed for Slack notification (no workflow link)
    report = PullRequestCreatedReport(
        pr_number=pr_number,
        pr_url=pr_url,
        project_name=project_name,
        task=task,
        cost_breakdown=cost_breakdown,
        repo=repo,
        run_id="",  # Not used for Slack notification
    )

    return report.build_notification_elements()
