"""Finalize command - commit changes, create PR, and generate summary"""

import argparse
import json
import os
from datetime import datetime

from claudestep.domain.config import substitute_template
from claudestep.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError
from claudestep.infrastructure.git.operations import run_git_command
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.infrastructure.github.operations import run_gh_command
from claudestep.application.services.task_management import mark_task_complete


def cmd_finalize(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'finalize' subcommand - commit changes, create PR, and generate summary

    This combines: commit changes, create-pr, summary

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get environment variables
        branch_name = os.environ.get("BRANCH_NAME", "")
        task = os.environ.get("TASK", "")
        task_index = os.environ.get("TASK_INDEX", "")
        reviewer = os.environ.get("REVIEWER", "")
        project = os.environ.get("PROJECT", "")
        spec_path = os.environ.get("SPEC_PATH", "")
        pr_template_path = os.environ.get("PR_TEMPLATE_PATH", "")
        gh_token = os.environ.get("GH_TOKEN", "")
        github_repository = os.environ.get("GITHUB_REPOSITORY", "")
        github_run_id = os.environ.get("GITHUB_RUN_ID", "")
        base_branch = os.environ.get("BASE_BRANCH", "main")
        has_capacity = os.environ.get("HAS_CAPACITY", "")
        has_task = os.environ.get("HAS_TASK", "")
        label = os.environ.get("LABEL", "")

        # === Generate Summary Early (for all cases) ===
        print("\n=== Generating workflow summary ===")

        gh.write_step_summary("## ClaudeStep Summary")
        gh.write_step_summary("")

        # Check if we should skip (no capacity or no task)
        if has_capacity != "true":
            gh.write_step_summary("⏸️ **Status**: All reviewers at capacity")
            print("⏸️ All reviewers at capacity - skipping")
            return 0

        if has_task != "true":
            gh.write_step_summary("✅ **Status**: All tasks complete or in progress")
            print("✅ All tasks complete or in progress - skipping")
            return 0

        # Validate required environment variables
        if not all([branch_name, task, task_index, reviewer, project, spec_path, gh_token, github_repository]):
            raise ConfigurationError("Missing required environment variables")

        # === STEP 1: Commit Any Uncommitted Changes ===
        print("=== Step 1/3: Committing changes ===")

        # Exclude .action directory from git tracking (checked out action code, not part of user's repo)
        # We can't remove it because GitHub Actions needs it for post-action cleanup
        # Instead, add it to .git/info/exclude so git ignores it
        action_dir = os.path.join(os.getcwd(), ".action")
        if os.path.exists(action_dir):
            exclude_file = os.path.join(os.getcwd(), ".git", "info", "exclude")
            try:
                with open(exclude_file, "r") as f:
                    exclude_content = f.read()
                if ".action" not in exclude_content:
                    with open(exclude_file, "a") as f:
                        f.write("\n.action\n")
                    print("Added .action to git exclude list")
            except FileNotFoundError:
                # .git/info/exclude doesn't exist, create it
                os.makedirs(os.path.dirname(exclude_file), exist_ok=True)
                with open(exclude_file, "w") as f:
                    f.write(".action\n")
                print("Created git exclude list with .action")

        # Configure git user for commits
        run_git_command(["config", "user.name", "github-actions[bot]"])
        run_git_command(["config", "user.email", "github-actions[bot]@users.noreply.github.com"])

        # Check for any changes (staged, unstaged, or untracked)
        status_output = run_git_command(["status", "--porcelain"])
        if status_output.strip():
            print("Found uncommitted changes, staging...")
            run_git_command(["add", "-A"])

            # Check if there are actually staged changes after git add
            staged_status = run_git_command(["diff", "--cached", "--name-only"])
            if staged_status.strip():
                print(f"Committing {len(staged_status.strip().split())} file(s)...")
                run_git_command(["commit", "-m", f"Complete task: {task}"])
            else:
                print("No changes to commit after staging (files may have been committed by Claude Code)")
        else:
            print("No uncommitted changes found")

        # === STEP 2: Create PR ===
        print("\n=== Step 2/3: Creating pull request ===")

        # Check if there are commits to push
        try:
            commits_ahead = run_git_command(["rev-list", "--count", f"origin/{base_branch}..HEAD"])
            commits_count = int(commits_ahead) if commits_ahead else 0
        except (GitError, ValueError):
            commits_count = 0

        # Reconfigure git auth (Claude Code action may have changed it)
        remote_url = f"https://x-access-token:{gh_token}@github.com/{github_repository}.git"
        run_git_command(["remote", "set-url", "origin", remote_url])

        # Mark task as complete in spec.md
        try:
            mark_task_complete(spec_path, task)
            print(f"Marked task complete in {spec_path}")

            # Add the updated spec
            run_git_command(["add", spec_path])

            # Check if there are changes to commit
            status_output = run_git_command(["status", "--porcelain"])
            if status_output.strip():
                if commits_count > 0:
                    # Amend the last commit to include the spec update
                    try:
                        run_git_command(["commit", "--amend", "--no-edit"])
                        print("Added spec.md update to existing commit")
                    except GitError:
                        run_git_command(["commit", "-m", f"Mark task complete: {task}"])
                        print("Created separate commit for spec.md update")
                else:
                    run_git_command(["commit", "-m", f"Mark task complete: {task}"])
                    print("Created commit for spec.md update")
                    commits_count = 1
        except (GitError, FileNotFoundError) as e:
            gh.set_warning(f"Failed to mark task complete in spec: {str(e)}")

        if commits_count == 0:
            gh.set_warning("No changes made (including spec update), skipping PR creation")
            gh.write_output("pr_number", "")
            gh.write_output("pr_url", "")
            gh.write_output("artifact_path", "")
            gh.write_output("artifact_name", "")
            gh.write_step_summary("ℹ️ **Status**: No changes to commit")
            return 0

        print(f"Found {commits_count} commit(s) to push")

        # Push the branch
        run_git_command(["push", "-u", "origin", branch_name, "--force"])

        # Load PR template and substitute
        if os.path.exists(pr_template_path):
            with open(pr_template_path, "r") as f:
                pr_body = substitute_template(f.read(), TASK_DESCRIPTION=task)
        else:
            pr_body = f"## Task\n{task}"

        # Add GitHub Actions run link
        if github_run_id:
            actions_url = f"https://github.com/{github_repository}/actions/runs/{github_run_id}"
            pr_body += f"\n\n---\n\n*Created by [ClaudeStep run]({actions_url})*"

        # Create PR using temp file for body to avoid command-line length/escaping issues
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(pr_body)
            pr_body_file = f.name

        try:
            pr_url = run_gh_command([
                "pr", "create",
                "--title", f"ClaudeStep: {task}",
                "--body-file", pr_body_file,
                "--label", label,
                "--assignee", reviewer,
                "--head", branch_name,
                "--base", base_branch
            ])
        finally:
            # Clean up temp file
            if os.path.exists(pr_body_file):
                os.remove(pr_body_file)

        print(f"✅ Created PR: {pr_url}")

        # Query PR number
        pr_output = run_gh_command([
            "pr", "view", branch_name,
            "--json", "number"
        ])
        pr_data = json.loads(pr_output)
        pr_number = pr_data.get("number")

        # === STEP 3: Create Artifact Metadata ===
        print("\n=== Step 3/3: Creating artifact metadata ===")

        # Get cost information from environment
        main_cost = float(os.environ.get("MAIN_COST", "0"))
        summary_cost = float(os.environ.get("SUMMARY_COST", "0"))
        total_cost = main_cost + summary_cost

        metadata = {
            "task_index": int(task_index),
            "task_description": task,
            "project": project,
            "branch_name": branch_name,
            "reviewer": reviewer,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "workflow_run_id": int(github_run_id) if github_run_id else None,
            "pr_number": pr_number,
            "main_task_cost_usd": main_cost,
            "pr_summary_cost_usd": summary_cost,
            "total_cost_usd": total_cost
        }

        # Write metadata to file
        artifact_filename = f"task-metadata-{project}-{task_index}.json"
        artifact_path = os.path.join(os.getcwd(), artifact_filename)

        with open(artifact_path, "w") as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Created artifact metadata at {artifact_path}")

        # Write outputs
        gh.write_output("artifact_path", artifact_path)
        gh.write_output("artifact_name", artifact_filename)
        gh.write_output("pr_number", str(pr_number))
        gh.write_output("pr_url", pr_url)

        # Write final summary
        gh.write_step_summary("✅ **Status**: PR created successfully")
        gh.write_step_summary("")
        gh.write_step_summary(f"- **PR**: #{pr_number}")
        gh.write_step_summary(f"- **Reviewer**: {reviewer}")
        gh.write_step_summary(f"- **Task**: {task}")

        print("\n✅ Finalization complete")
        return 0

    except (GitError, GitHubAPIError, ConfigurationError) as e:
        gh.set_error(f"Finalization failed: {str(e)}")
        gh.write_step_summary("❌ **Status**: Failed to create PR")
        gh.write_step_summary(f"- **Error**: {str(e)}")
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in finalize: {str(e)}")
        gh.write_step_summary("❌ **Status**: Unexpected error")
        import traceback
        traceback.print_exc()
        return 1
