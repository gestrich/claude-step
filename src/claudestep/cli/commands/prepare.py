"""Prepare command - setup before Claude Code execution"""

import argparse
import json
import os

from claudestep.domain.config import load_config, load_config_from_string, validate_spec_format, validate_spec_format_from_string
from claudestep.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError
from claudestep.infrastructure.git.operations import run_git_command
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.infrastructure.github.operations import ensure_label_exists, file_exists_in_branch, get_file_from_branch
from claudestep.infrastructure.metadata.github_metadata_store import GitHubMetadataStore
from claudestep.application.services.metadata_service import MetadataService
from claudestep.application.services.pr_operations import format_branch_name
from claudestep.application.services.project_detection import detect_project_from_pr, detect_project_paths
from claudestep.application.services.reviewer_management import find_available_reviewer
from claudestep.application.services.task_management import find_next_available_task, get_in_progress_task_indices


def cmd_prepare(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'prepare' subcommand - all setup steps before running Claude

    This combines: detect-project, setup, check-capacity, find-task, create-branch, prepare-prompt

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, non-zero for various failure modes)
    """
    try:
        # === STEP 1: Detect Project ===
        print("=== Step 1/6: Detecting project ===")
        project_name = os.environ.get("PROJECT_NAME", "")
        merged_pr_number = os.environ.get("MERGED_PR_NUMBER", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")

        detected_project = None

        # If merged PR number provided, detect project from PR labels
        if merged_pr_number:
            detected_project = detect_project_from_pr(merged_pr_number, repo)
            if not detected_project:
                gh.set_error(f"No refactor project found with matching label for PR #{merged_pr_number}")
                return 1

            # Update metadata to mark PR as merged and task as completed
            print(f"Processing merged PR #{merged_pr_number} for project '{detected_project}'")
            try:
                metadata_store = GitHubMetadataStore(repo)
                metadata_service = MetadataService(metadata_store)

                # Update PR state to "merged"
                metadata_service.update_pr_state(detected_project, int(merged_pr_number), "merged")
                print(f"✅ Updated PR #{merged_pr_number} state to 'merged' in metadata")

                # Note: Task status is automatically synced by save_project() in update_pr_state()
                # The task will be marked as "completed" based on the merged PR

            except Exception as e:
                # Log warning but continue - we still want to create the next PR
                print(f"⚠️  Warning: Failed to update metadata for merged PR: {str(e)}")
                import traceback
                traceback.print_exc()

            print("Proceeding to prepare next task...")

        elif project_name:
            detected_project = project_name
            print(f"Using provided project name: {detected_project}")
        else:
            gh.set_error("project_name must be provided (use discovery action to find projects)")
            return 1

        # Determine paths (always use claude-step/ directory structure)
        config_path, spec_path, pr_template_path, project_path = detect_project_paths(detected_project)

        # Validate spec files exist in base branch before proceeding
        base_branch = os.environ.get("BASE_BRANCH", "main")
        print(f"Validating spec files exist in branch '{base_branch}'...")

        # Check if spec.md exists
        spec_file_path = f"claude-step/{detected_project}/spec.md"
        config_file_path = f"claude-step/{detected_project}/configuration.yml"

        spec_exists = file_exists_in_branch(repo, base_branch, spec_file_path)
        config_exists = file_exists_in_branch(repo, base_branch, config_file_path)

        if not spec_exists or not config_exists:
            missing_files = []
            if not spec_exists:
                missing_files.append(f"  - {spec_file_path}")
            if not config_exists:
                missing_files.append(f"  - {config_file_path}")

            error_msg = f"""Error: Spec files not found in branch '{base_branch}'
Required files:
{chr(10).join(missing_files)}

Please merge your spec files to the '{base_branch}' branch before running ClaudeStep."""
            gh.set_error(error_msg)
            return 1

        print(f"✅ Spec files validated in branch '{base_branch}'")

        # === STEP 2: Load and Validate Configuration ===
        print("\n=== Step 2/6: Loading configuration ===")

        # Fetch configuration from GitHub API
        config_content = get_file_from_branch(repo, base_branch, config_file_path)
        if not config_content:
            gh.set_error(f"Failed to fetch configuration file from branch '{base_branch}'")
            return 1

        config = load_config_from_string(config_content, config_file_path)
        reviewers = config.get("reviewers")
        slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")  # From action input
        label = os.environ.get("PR_LABEL", "claudestep")  # From action input, defaults to "claudestep"

        if not reviewers:
            raise ConfigurationError("Missing required field: reviewers")

        # Ensure label exists
        ensure_label_exists(label, gh)

        # Fetch and validate spec format from GitHub API
        spec_content = get_file_from_branch(repo, base_branch, spec_file_path)
        if not spec_content:
            gh.set_error(f"Failed to fetch spec file from branch '{base_branch}'")
            return 1

        validate_spec_format_from_string(spec_content, spec_file_path)

        print(f"✅ Configuration loaded: label={label}, reviewers={len(reviewers)}")

        # === STEP 3: Check Reviewer Capacity ===
        print("\n=== Step 3/6: Checking reviewer capacity ===")
        selected_reviewer, capacity_result = find_available_reviewer(reviewers, label, detected_project)

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
        in_progress_indices = get_in_progress_task_indices(repo, label, detected_project)

        if in_progress_indices:
            print(f"Found in-progress tasks: {sorted(in_progress_indices)}")

        result = find_next_available_task(spec_content, in_progress_indices)

        if not result:
            gh.write_output("has_task", "false")
            gh.write_output("all_tasks_done", "true")
            gh.set_notice("No available tasks (all completed or in progress)")
            return 0  # Not an error, just no tasks

        task_index, task = result
        print(f"✅ Found task {task_index}: {task}")

        # === STEP 5: Create Branch ===
        print("\n=== Step 5/6: Creating branch ===")
        # Use standard ClaudeStep branch format: claude-step-{project}-{index}
        branch_name = format_branch_name(detected_project, task_index)

        try:
            run_git_command(["checkout", "-b", branch_name])
            print(f"✅ Created branch: {branch_name}")
        except GitError as e:
            gh.set_error(f"Failed to create branch: {str(e)}")
            return 1

        # === STEP 6: Prepare Claude Prompt ===
        print("\n=== Step 6/6: Preparing Claude prompt ===")

        # Create the prompt (spec_content already fetched in Step 2)
        claude_prompt = f"""Complete the following task from spec.md:

Task: {task}

Instructions: Read the entire spec.md file below to understand both WHAT to do and HOW to do it. Follow all guidelines and patterns specified in the document.

--- BEGIN spec.md ---
{spec_content}
--- END spec.md ---

Now complete the task '{task}' following all the details and instructions in the spec.md file above. When you're done, use git add and git commit to commit your changes."""

        print(f"✅ Prompt prepared ({len(claude_prompt)} characters)")

        # === Write All Outputs ===
        gh.write_output("project_name", detected_project)
        gh.write_output("project_path", project_path)
        gh.write_output("config_path", config_path)
        gh.write_output("spec_path", spec_path)
        gh.write_output("pr_template_path", pr_template_path)
        gh.write_output("label", label)
        gh.write_output("reviewers_json", json.dumps(reviewers))
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
