"""CLI command for prepare workflow.

Orchestrates Service Layer classes to coordinate preparation workflow.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import argparse
import json
import os

from claudestep.domain.config import load_config, load_config_from_string, validate_spec_format, validate_spec_format_from_string
from claudestep.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError
from claudestep.domain.project import Project
from claudestep.infrastructure.git.operations import run_git_command
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.infrastructure.github.operations import ensure_label_exists, file_exists_in_branch, get_file_from_branch
from claudestep.infrastructure.repositories.project_repository import ProjectRepository
from claudestep.services.core.pr_service import PRService
from claudestep.services.core.project_service import ProjectService
from claudestep.services.core.reviewer_service import ReviewerService
from claudestep.services.core.task_service import TaskService


def cmd_prepare(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Orchestrate preparation workflow using Service Layer classes.

    This command instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern
    where CLI acts as thin orchestration layer.

    Workflow: detect-project, setup, check-capacity, find-task, create-branch, prepare-prompt

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, non-zero for various failure modes)
    """
    try:
        # === Get common dependencies ===
        repo = os.environ.get("GITHUB_REPOSITORY", "")

        # Initialize infrastructure
        project_repository = ProjectRepository(repo)

        # Initialize services
        pr_service = PRService(repo)
        project_service = ProjectService(repo)
        task_service = TaskService(repo, pr_service)
        reviewer_service = ReviewerService(repo, pr_service)

        # === STEP 1: Detect Project ===
        print("=== Step 1/6: Detecting project ===")
        project_name = os.environ.get("PROJECT_NAME", "")
        merged_pr_number = os.environ.get("MERGED_PR_NUMBER", "")

        detected_project = None

        # If merged PR number provided, detect project from PR labels
        if merged_pr_number:
            detected_project = project_service.detect_project_from_pr(merged_pr_number)
            if not detected_project:
                gh.set_error(f"No refactor project found with matching label for PR #{merged_pr_number}")
                return 1

            # No need to update metadata - PR state is tracked via GitHub API
            print(f"Processing merged PR #{merged_pr_number} for project '{detected_project}'")
            print("Proceeding to prepare next task...")

        elif project_name:
            detected_project = project_name
            print(f"Using provided project name: {detected_project}")
        else:
            gh.set_error("project_name must be provided (use discovery action to find projects)")
            return 1

        # Create Project domain model
        project = Project(detected_project)

        # Get default base branch from environment (workflow provides this)
        default_base_branch = os.environ.get("BASE_BRANCH", "main")
        print(f"Validating spec files exist in branch '{default_base_branch}'...")

        # Check if spec.md exists (use default branch to locate config files)
        spec_exists = file_exists_in_branch(repo, default_base_branch, project.spec_path)
        config_exists = file_exists_in_branch(repo, default_base_branch, project.config_path)

        if not spec_exists or not config_exists:
            missing_files = []
            if not spec_exists:
                missing_files.append(f"  - {project.spec_path}")
            if not config_exists:
                missing_files.append(f"  - {project.config_path}")

            error_msg = f"""Error: Spec files not found in branch '{default_base_branch}'
Required files:
{chr(10).join(missing_files)}

Please merge your spec files to the '{default_base_branch}' branch before running ClaudeStep."""
            gh.set_error(error_msg)
            return 1

        print(f"✅ Spec files validated in branch '{default_base_branch}'")

        # === STEP 2: Load and Validate Configuration ===
        print("\n=== Step 2/6: Loading configuration ===")

        # Load configuration using ProjectRepository (use default branch to fetch config)
        config = project_repository.load_configuration(project, default_base_branch)
        if not config:
            gh.set_error(f"Failed to load configuration file from branch '{default_base_branch}'")
            return 1

        # Resolve actual base branch (config override or default)
        base_branch = config.get_base_branch(default_base_branch)
        if base_branch != default_base_branch:
            print(f"Base branch: {base_branch} (overridden from default: {default_base_branch})")
        else:
            print(f"Base branch: {base_branch}")

        slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")  # From action input
        label = os.environ.get("PR_LABEL", "claudestep")  # From action input, defaults to "claudestep"

        if not config.reviewers:
            raise ConfigurationError("Missing required field: reviewers")

        # Ensure label exists
        ensure_label_exists(label, gh)

        # Load and validate spec using ProjectRepository
        spec = project_repository.load_spec(project, default_base_branch)
        if not spec:
            gh.set_error(f"Failed to load spec file from branch '{default_base_branch}'")
            return 1

        validate_spec_format_from_string(spec.content, project.spec_path)

        print(f"✅ Configuration loaded: label={label}, reviewers={len(config.reviewers)}")

        # === STEP 3: Check Reviewer Capacity ===
        print("\n=== Step 3/6: Checking reviewer capacity ===")

        selected_reviewer, capacity_result = reviewer_service.find_available_reviewer(config, label, detected_project)

        summary = capacity_result.format_summary()
        gh.write_step_summary(summary)
        print("\n" + summary)

        if not selected_reviewer:
            gh.write_output("has_capacity", "false")
            gh.write_output("reviewer", "")
            gh.set_notice("All reviewers at capacity, skipping PR creation")
            return 0  # Not an error, just no capacity

        gh.write_output("has_capacity", "true")
        gh.write_output("reviewer", selected_reviewer)
        print(f"✅ Selected reviewer: {selected_reviewer}")

        # === STEP 4: Find Next Task ===
        print("\n=== Step 4/6: Finding next task ===")

        # Detect orphaned PRs (PRs for tasks that have been modified or removed)
        orphaned_prs = task_service.detect_orphaned_prs(label, detected_project, spec)
        if orphaned_prs:
            print(f"\n⚠️  Warning: Found {len(orphaned_prs)} orphaned PR(s):")

            # Build console output and GitHub Actions summary
            orphaned_list = []
            for pr in orphaned_prs:
                if pr.task_hash:
                    msg = f"PR #{pr.number} ({pr.head_ref_name}) - task hash {pr.task_hash} no longer matches any task"
                    print(f"  - {msg}")
                    orphaned_list.append(f"- {msg}")
                elif pr.task_index:
                    msg = f"PR #{pr.number} ({pr.head_ref_name}) - task index {pr.task_index} no longer valid"
                    print(f"  - {msg}")
                    orphaned_list.append(f"- {msg}")

            print("\nTo resolve:")
            print("  1. Review these PRs and verify if they should be closed")
            print("  2. Close any PRs for modified/removed tasks")
            print("  3. ClaudeStep will automatically create new PRs for current tasks")
            print()

            # Add to GitHub Actions step summary with PR links
            repo = os.environ.get("GITHUB_REPOSITORY", "")
            if repo:
                summary = f"\n## ⚠️ Orphaned PRs Detected\n\n"
                summary += f"Found {len(orphaned_prs)} PR(s) for tasks that have been modified or removed:\n\n"
                for pr in orphaned_prs:
                    pr_url = f"https://github.com/{repo}/pull/{pr.number}"
                    if pr.task_hash:
                        summary += f"- [PR #{pr.number}]({pr_url}) (`{pr.head_ref_name}`) - task hash `{pr.task_hash}` no longer matches any task\n"
                    elif pr.task_index:
                        summary += f"- [PR #{pr.number}]({pr_url}) (`{pr.head_ref_name}`) - task index `{pr.task_index}` no longer valid\n"
                summary += "\n**To resolve:**\n"
                summary += "1. Review these PRs and verify if they should be closed\n"
                summary += "2. Close any PRs for modified/removed tasks\n"
                summary += "3. ClaudeStep will automatically create new PRs for current tasks\n"
                gh.write_step_summary(summary)

        # Get in-progress tasks
        in_progress_hashes = task_service.get_in_progress_tasks(label, detected_project)

        if in_progress_hashes:
            print(f"Found in-progress tasks: {sorted(in_progress_hashes)}")

        result = task_service.find_next_available_task(spec, in_progress_hashes)

        if not result:
            gh.write_output("has_task", "false")
            gh.write_output("all_tasks_done", "true")
            gh.set_notice("No available tasks (all completed or in progress)")
            return 0  # Not an error, just no tasks

        task_index, task, task_hash = result
        print(f"✅ Found task {task_index}: {task}")
        print(f"   Task hash: {task_hash}")

        # === STEP 5: Create Branch ===
        print("\n=== Step 5/6: Creating branch ===")
        # Use standard ClaudeStep branch format: claude-step-{project}-{task_hash}
        branch_name = pr_service.format_branch_name(detected_project, task_hash)

        try:
            run_git_command(["checkout", "-b", branch_name])
            print(f"✅ Created branch: {branch_name}")
        except GitError as e:
            gh.set_error(f"Failed to create branch: {str(e)}")
            return 1

        # === STEP 6: Prepare Claude Prompt ===
        print("\n=== Step 6/6: Preparing Claude prompt ===")

        # Create the prompt using spec content
        claude_prompt = f"""Complete the following task from spec.md:

Task: {task}

Instructions: Read the entire spec.md file below to understand both WHAT to do and HOW to do it. Follow all guidelines and patterns specified in the document.

--- BEGIN spec.md ---
{spec.content}
--- END spec.md ---

Now complete the task '{task}' following all the details and instructions in the spec.md file above. When you're done, use git add and git commit to commit your changes."""

        print(f"✅ Prompt prepared ({len(claude_prompt)} characters)")

        # === Write All Outputs ===
        gh.write_output("project_name", detected_project)
        gh.write_output("project_path", project.base_path)
        gh.write_output("config_path", project.config_path)
        gh.write_output("spec_path", project.spec_path)
        gh.write_output("pr_template_path", project.pr_template_path)
        gh.write_output("base_branch", base_branch)
        gh.write_output("label", label)
        gh.write_output("reviewers_json", json.dumps([{"username": r.username, "maxOpenPRs": r.max_open_prs} for r in config.reviewers]))
        gh.write_output("slack_webhook_url", slack_webhook_url)
        gh.write_output("task", task)
        gh.write_output("task_index", str(task_index))
        gh.write_output("has_task", "true")
        gh.write_output("all_tasks_done", "false")
        gh.write_output("branch_name", branch_name)
        gh.write_output("claude_prompt", claude_prompt)

        print("\n✅ Preparation complete - ready to run Claude Code")
        return 0

    except (FileNotFoundError, ConfigurationError, GitError, GitHubAPIError) as e:
        gh.set_error(f"Preparation failed: {str(e)}")
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in prepare: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
