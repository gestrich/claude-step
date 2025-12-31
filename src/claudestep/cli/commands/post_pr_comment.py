"""
Post unified PR comment with summary and cost breakdown.

This command combines the AI-generated summary and cost breakdown into a single
comment, using the reliable Python-based posting mechanism.
"""

import os
import subprocess
import tempfile


def cmd_post_pr_comment(args, gh):
    """
    Post a unified comment with PR summary and cost breakdown.

    Reads from environment:
    - PR_NUMBER: Pull request number
    - SUMMARY_FILE: Path to file containing AI-generated summary
    - MAIN_COST: Cost of main refactoring task (USD)
    - SUMMARY_COST: Cost of PR summary generation (USD)
    - TOTAL_COST: Total cost (USD)
    - GITHUB_REPOSITORY: Repository in format owner/repo
    - GITHUB_RUN_ID: Workflow run ID

    Outputs:
    - comment_posted: "true" if comment was posted, "false" otherwise
    """
    # Get required environment variables
    pr_number = os.environ.get("PR_NUMBER", "").strip()
    summary_file = os.environ.get("SUMMARY_FILE", "").strip()
    main_cost = os.environ.get("MAIN_COST", "0").strip()
    summary_cost = os.environ.get("SUMMARY_COST", "0").strip()
    total_cost = os.environ.get("TOTAL_COST", "0").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")

    # If no PR number, skip gracefully
    if not pr_number:
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
        # Parse costs as floats
        try:
            main_cost_val = float(main_cost)
        except ValueError:
            main_cost_val = 0.0

        try:
            summary_cost_val = float(summary_cost)
        except ValueError:
            summary_cost_val = 0.0

        try:
            total_cost_val = float(total_cost)
        except ValueError:
            total_cost_val = 0.0

        # Read summary file if it exists
        summary_content = None
        if summary_file and os.path.exists(summary_file):
            try:
                with open(summary_file, 'r') as f:
                    summary_content = f.read().strip()
                    if not summary_content:
                        summary_content = None
            except Exception as e:
                print(f"::warning::Could not read summary file: {e}")
                summary_content = None

        # Format the unified comment
        comment = format_unified_comment(
            summary_content=summary_content,
            main_cost=main_cost_val,
            summary_cost=summary_cost_val,
            total_cost=total_cost_val,
            repo=repo,
            run_id=run_id
        )

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
            if summary_content:
                print("   - AI-generated summary included")
            print(f"   - Main task: ${main_cost_val:.6f}")
            print(f"   - PR summary: ${summary_cost_val:.6f}")
            print(f"   - Total: ${total_cost_val:.6f}")

            gh.write_output("comment_posted", "true")
            return 0

        finally:
            # Clean up temp file
            os.unlink(temp_file)

    except subprocess.CalledProcessError as e:
        gh.set_error(f"Failed to post comment: {e.stderr}")
        return 1
    except Exception as e:
        gh.set_error(f"Error posting PR comment: {str(e)}")
        return 1


def format_unified_comment(
    summary_content: str | None,
    main_cost: float,
    summary_cost: float,
    total_cost: float,
    repo: str,
    run_id: str
) -> str:
    """
    Format the unified PR comment with summary and cost breakdown.

    Args:
        summary_content: AI-generated summary text (or None if not available)
        main_cost: Cost of main task in USD
        summary_cost: Cost of PR summary in USD
        total_cost: Total cost in USD
        repo: Repository name (owner/repo)
        run_id: Workflow run ID

    Returns:
        Formatted markdown comment
    """
    workflow_url = f"https://github.com/{repo}/actions/runs/{run_id}"

    # Start with summary if available
    parts = []
    if summary_content:
        parts.append(summary_content)
        parts.append("\n---\n")

    # Add cost breakdown
    cost_section = f"""## 💰 Cost Breakdown

This PR was generated using Claude Code with the following costs:

| Component | Cost (USD) |
|-----------|------------|
| Main refactoring task | ${main_cost:.6f} |
| PR summary generation | ${summary_cost:.6f} |
| **Total** | **${total_cost:.6f}** |

---
*Cost tracking by ClaudeStep • [View workflow run]({workflow_url})*
"""
    parts.append(cost_section)

    return "".join(parts)
