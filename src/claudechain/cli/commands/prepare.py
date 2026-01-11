"""CLI command for prepare workflow.

Orchestrates Service Layer classes to coordinate preparation workflow.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import argparse
import os
from typing import Optional

from claudechain.domain.claude_schemas import get_main_task_schema_json
from claudechain.domain.config import validate_spec_format_from_string
from claudechain.domain.constants import DEFAULT_BASE_BRANCH
from claudechain.domain.exceptions import ConfigurationError, FileNotFoundError, GitError, GitHubAPIError
from claudechain.domain.project import Project
from claudechain.infrastructure.git.operations import run_git_command
from claudechain.infrastructure.github.actions import GitHubActionsHelper
from claudechain.infrastructure.github.operations import add_label_to_pr, ensure_label_exists
from claudechain.infrastructure.repositories.project_repository import ProjectRepository
from claudechain.services.core.pr_service import PRService
from claudechain.services.core.assignee_service import AssigneeService
from claudechain.services.core.task_service import TaskService


def cmd_prepare(args: argparse.Namespace, gh: GitHubActionsHelper, default_allowed_tools: str) -> int:
    """Orchestrate preparation workflow using Service Layer classes.

    This command instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern
    where CLI acts as thin orchestration layer.

    Workflow: detect-project, setup, check-capacity, find-task, create-branch, prepare-prompt

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance
        default_allowed_tools: Default allowed tools from workflow (can be overridden by project config)

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
        task_service = TaskService(repo, pr_service)
        assignee_service = AssigneeService(repo, pr_service)

        # === STEP 1: Detect Project ===
        print("=== Step 1/6: Detecting project ===")
        project_name = os.environ.get("PROJECT_NAME", "")
        merged_pr_number = os.environ.get("MERGED_PR_NUMBER", "")

        # project_name is always provided by parse_event (for PR merges) or workflow input (for manual triggers)
        if not project_name:
            gh.set_error("PROJECT_NAME must be provided (set by parse_event or workflow_dispatch input)")
            return 1

        if merged_pr_number:
            print(f"Processing merged PR #{merged_pr_number} for project '{project_name}'")
            print("Proceeding to prepare next task...")
        else:
            print(f"Using provided project name: {project_name}")

        # Create Project domain model
        project = Project(project_name)

        # Get default base branch from environment (workflow provides this)
        # Use env var if set and non-empty, otherwise fall back to constant
        env_base_branch = os.environ.get("BASE_BRANCH", "")
        default_base_branch = env_base_branch if env_base_branch else DEFAULT_BASE_BRANCH

        # === STEP 2: Load Configuration and Resolve Base Branch ===
        print("\n=== Step 2/6: Loading configuration ===")

        # Load configuration from local filesystem (after checkout)
        # This is more efficient than GitHub API and works for all trigger types
        config = project_repository.load_local_configuration(project)

        # Resolve actual base branch (config override or default)
        base_branch = config.get_base_branch(default_base_branch)
        if base_branch != default_base_branch:
            print(f"Base branch: {base_branch} (overridden from default: {default_base_branch})")
        else:
            print(f"Base branch: {base_branch}")

        # Validate base branch matches expected target
        merge_target_branch = os.environ.get("MERGE_TARGET_BRANCH", "")
        if merge_target_branch:
            # PR merge event
            result = _validate_base_branch_for_pr_merge(
                gh, project_name, base_branch, merge_target_branch
            )
            if result is not None:
                return result
        else:
            # workflow_dispatch event
            result = _validate_base_branch_for_workflow_dispatch(
                gh, project_name, config.base_branch, default_base_branch
            )
            if result is not None:
                return result

        # Resolve allowed tools (config override or default)
        allowed_tools = config.get_allowed_tools(default_allowed_tools)
        if allowed_tools != default_allowed_tools:
            print(f"Allowed tools: {allowed_tools} (overridden from default)")
        else:
            print(f"Allowed tools: {allowed_tools}")

        slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")  # From action input
        label = os.environ.get("PR_LABEL", "claudechain")  # From action input, defaults to "claudechain"

        # Ensure label exists
        ensure_label_exists(label, gh)

        # Load spec from local filesystem (after checkout)
        print(f"Loading spec from local filesystem...")
        spec = project_repository.load_local_spec(project)

        if not spec:
            error_msg = f"""Error: spec.md not found at '{project.spec_path}'
Required file:
  - {project.spec_path}

Please ensure your spec.md file exists and the checkout was successful."""
            gh.set_error(error_msg)
            return 1

        print(f"✅ spec.md loaded from local filesystem")

        validate_spec_format_from_string(spec.content, project.spec_path)

        if config.assignee:
            print(f"✅ Configuration loaded: label={label}, assignee={config.assignee}")
        else:
            print(f"✅ Configuration loaded: label={label}, no assignee configured")

        # === STEP 3: Check Capacity ===
        print("\n=== Step 3/6: Checking capacity ===")

        capacity_result = assignee_service.check_capacity(config, label, project_name)

        summary = capacity_result.format_summary()
        gh.write_step_summary(summary)
        print("\n" + summary)

        # Check capacity
        if not capacity_result.has_capacity:
            gh.write_output("has_capacity", "false")
            gh.write_output("assignee", "")
            gh.set_notice("Project at capacity (1 open PR limit), skipping PR creation")
            return 0  # Not an error, just no capacity

        gh.write_output("has_capacity", "true")
        gh.write_output("assignee", capacity_result.assignee or "")  # Empty string if no assignee
        if capacity_result.assignee:
            print(f"✅ Capacity available - assignee: {capacity_result.assignee}")
        else:
            print("✅ Capacity available (no assignee configured)")

        # === STEP 4: Find Next Task ===
        print("\n=== Step 4/6: Finding next task ===")

        # Detect orphaned PRs (PRs for tasks that have been modified or removed)
        orphaned_prs = task_service.detect_orphaned_prs(label, project_name, spec)
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
            print("  3. ClaudeChain will automatically create new PRs for current tasks")
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
                summary += "3. ClaudeChain will automatically create new PRs for current tasks\n"
                gh.write_step_summary(summary)

        # Get in-progress tasks
        in_progress_hashes = task_service.get_in_progress_tasks(label, project_name)

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
        # Use standard ClaudeChain branch format: claude-chain-{project}-{task_hash}
        branch_name = pr_service.format_branch_name(project_name, task_hash)

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

Now complete the task '{task}' following all the details and instructions in the spec.md file above."""

        print(f"✅ Prompt prepared ({len(claude_prompt)} characters)")

        # === Add label to merged PR (Phase 6) ===
        # This helps statistics discover all ClaudeChain-related PRs
        if merged_pr_number:
            if add_label_to_pr(repo, int(merged_pr_number), label):
                print(f"✅ Added '{label}' label to merged PR #{merged_pr_number}")

        # === Write All Outputs ===
        gh.write_output("project_name", project_name)
        gh.write_output("project_path", project.base_path)
        gh.write_output("config_path", project.config_path)
        gh.write_output("spec_path", project.spec_path)
        gh.write_output("pr_template_path", project.pr_template_path)
        gh.write_output("base_branch", base_branch)
        gh.write_output("allowed_tools", allowed_tools)
        gh.write_output("label", label)
        gh.write_output("slack_webhook_url", slack_webhook_url)
        gh.write_output("task_description", task)
        gh.write_output("task_index", str(task_index))
        gh.write_output("task_hash", task_hash)
        gh.write_output("has_task", "true")
        gh.write_output("all_tasks_done", "false")
        gh.write_output("branch_name", branch_name)
        gh.write_output("claude_prompt", claude_prompt)
        gh.write_output("json_schema", get_main_task_schema_json())

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


# --- Private helper functions ---


def _validate_base_branch_for_pr_merge(
    gh: GitHubActionsHelper,
    project_name: str,
    expected_base_branch: str,
    merge_target_branch: str,
) -> Optional[int]:
    """Validate base branch for PR merge events.

    For PR merges, we SKIP (not error) if the merge target doesn't match
    the expected base branch. This is normal - the PR just merged to a
    different branch than this project uses.

    Args:
        gh: GitHub Actions helper for outputs
        project_name: Name of the project being processed
        expected_base_branch: Base branch from project config (or default)
        merge_target_branch: Branch the PR was merged INTO

    Returns:
        0 to skip processing, None to continue
    """
    if merge_target_branch != expected_base_branch:
        skip_msg = (
            f"Skipping: Project '{project_name}' expects base branch "
            f"'{expected_base_branch}' but PR merged into '{merge_target_branch}'"
        )
        print(f"\n⏭️  {skip_msg}")
        gh.set_notice(skip_msg)
        gh.write_output("has_capacity", "false")
        gh.write_output("has_task", "false")
        gh.write_output("base_branch_mismatch", "true")
        return 0  # Skip, not error

    return None  # Continue processing


def _validate_base_branch_for_workflow_dispatch(
    gh: GitHubActionsHelper,
    project_name: str,
    config_base_branch: Optional[str],
    provided_base_branch: str,
) -> Optional[int]:
    """Validate base branch for workflow_dispatch events.

    For manual triggers, we ERROR (not skip) if the provided base branch
    doesn't match the project's configured baseBranch. This catches user
    errors where they selected the wrong branch in the GitHub UI.

    Args:
        gh: GitHub Actions helper for errors
        project_name: Name of the project being processed
        config_base_branch: baseBranch from project config (None if not set)
        provided_base_branch: base_branch input from workflow_dispatch

    Returns:
        1 to error, None to continue
    """
    if config_base_branch and config_base_branch != provided_base_branch:
        error_msg = (
            f"Base branch mismatch: project '{project_name}' expects "
            f"'{config_base_branch}' but workflow was triggered with '{provided_base_branch}'"
        )
        print(f"\n❌ {error_msg}")
        gh.set_error(error_msg)
        return 1  # Error, not skip

    return None  # Continue processing
