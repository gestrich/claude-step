"""CLI command for finalize workflow.

Orchestrates Service Layer classes to coordinate finalization workflow.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import argparse
import json
import os
from datetime import datetime, timezone

from claudestep.domain.config import substitute_template
from claudestep.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError
from claudestep.domain.models import AIOperation, PullRequest, Task, TaskStatus
from claudestep.infrastructure.git.operations import run_git_command
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.infrastructure.github.operations import run_gh_command, get_file_from_branch
from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
from claudestep.services.metadata_service import MetadataService
from claudestep.services.task_management_service import TaskManagementService


def cmd_finalize(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Orchestrate finalization workflow using Service Layer classes.

    This command instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern
    where CLI acts as thin orchestration layer.

    Workflow: commit changes, create-pr, summary

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # === Get common dependencies ===
        github_repository = os.environ.get("GITHUB_REPOSITORY", "")

        # Initialize infrastructure
        metadata_store = GitHubMetadataStore(github_repository)
        metadata_service = MetadataService(metadata_store)

        # Get environment variables
        branch_name = os.environ.get("BRANCH_NAME", "")
        task = os.environ.get("TASK", "")
        task_index = os.environ.get("TASK_INDEX", "")
        reviewer = os.environ.get("REVIEWER", "")
        project = os.environ.get("PROJECT", "")
        spec_path = os.environ.get("SPEC_PATH", "")
        pr_template_path = os.environ.get("PR_TEMPLATE_PATH", "")
        gh_token = os.environ.get("GH_TOKEN", "")
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

        # Reconfigure git auth (Claude Code action may have changed it)
        remote_url = f"https://x-access-token:{gh_token}@github.com/{github_repository}.git"
        run_git_command(["remote", "set-url", "origin", remote_url])

        # Fetch spec.md from base branch and mark task as complete
        print("Fetching spec.md from base branch...")
        try:
            spec_content = get_file_from_branch(github_repository, base_branch, spec_path)
            if spec_content:
                # Write spec content to local file in PR branch
                spec_file_path = os.path.join(os.getcwd(), spec_path)
                spec_dir = os.path.dirname(spec_file_path)
                if spec_dir:  # Only create directory if there is one
                    os.makedirs(spec_dir, exist_ok=True)
                with open(spec_file_path, "w") as f:
                    f.write(spec_content)

                # Mark task as complete in the spec file
                print(f"Marking task {task_index} as complete in spec.md...")
                TaskManagementService.mark_task_complete(spec_file_path, task)

                # Stage and commit the updated spec.md
                run_git_command(["add", spec_file_path])
                spec_status = run_git_command(["diff", "--cached", "--name-only"])
                if spec_status.strip():
                    print("Committing spec.md update...")
                    run_git_command(["commit", "-m", f"Mark task {task_index} as complete in spec.md"])
            else:
                print(f"Warning: Could not fetch spec.md from {base_branch}, skipping spec update")
        except Exception as e:
            print(f"Warning: Failed to update spec.md: {e}")

        # Check if there are commits to push (after spec.md update)
        try:
            commits_ahead = run_git_command(["rev-list", "--count", f"origin/{base_branch}..HEAD"])
            commits_count = int(commits_ahead) if commits_ahead else 0
        except (GitError, ValueError):
            commits_count = 0

        if commits_count == 0:
            gh.set_warning("No changes made, skipping PR creation")
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

        # Query PR number and title
        pr_output = run_gh_command([
            "pr", "view", branch_name,
            "--json", "number,title"
        ])
        pr_data = json.loads(pr_output)
        pr_number = pr_data.get("number")
        pr_title = pr_data.get("title")

        # === STEP 3: Save to Metadata Storage ===
        print("\n=== Step 3/3: Saving metadata ===")

        # Get cost information from environment
        main_cost = float(os.environ.get("MAIN_COST", "0"))
        summary_cost = float(os.environ.get("SUMMARY_COST", "0"))

        # Get model information from environment
        claude_model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4")

        # Create AI operations list
        ai_operations = []

        # Add main task operation
        if main_cost > 0:
            ai_operations.append(AIOperation(
                type="PRCreation",
                model=claude_model,
                cost_usd=main_cost,
                created_at=datetime.now(timezone.utc),
                workflow_run_id=int(github_run_id) if github_run_id else 0,
                tokens_input=0,  # TODO: Extract from Claude Code output
                tokens_output=0,
                duration_seconds=0.0
            ))

        # Add PR summary operation
        if summary_cost > 0:
            ai_operations.append(AIOperation(
                type="PRSummary",
                model=claude_model,
                cost_usd=summary_cost,
                created_at=datetime.now(timezone.utc),
                workflow_run_id=int(github_run_id) if github_run_id else 0,
                tokens_input=0,
                tokens_output=0,
                duration_seconds=0.0
            ))

        # Save to metadata storage
        print("Saving to GitHub metadata storage...")

        # Create PullRequest object
        pr_obj = PullRequest(
            task_index=int(task_index),
            pr_number=pr_number,
            branch_name=branch_name,
            reviewer=reviewer,
            pr_state="open",
            created_at=datetime.now(timezone.utc),
            title=pr_title,
            ai_operations=ai_operations
        )

        # Get or create project metadata
        project_metadata = metadata_service.get_project(project)
        if project_metadata is None:
            # Create new project with task
            from claudestep.domain.models import HybridProjectMetadata
            project_metadata = HybridProjectMetadata.create_empty(project)
            # Add task if it doesn't exist
            task_obj = Task(
                index=int(task_index),
                description=task,
                status=TaskStatus.PENDING
            )
            project_metadata.tasks.append(task_obj)
        else:
            # Ensure task exists in project
            existing_task = project_metadata.get_task_by_index(int(task_index))
            if existing_task is None:
                task_obj = Task(
                    index=int(task_index),
                    description=task,
                    status=TaskStatus.PENDING
                )
                project_metadata.tasks.append(task_obj)

        # Add PR to project
        metadata_service.add_pr_to_project(project, task_index=int(task_index), pr=pr_obj)
        print(f"✅ Saved metadata to GitHub branch storage")

        # Write outputs
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
