#!/usr/bin/env python3
"""
ClaudeStep - GitHub Actions Helper Script

This script handles all operations for the automated refactoring workflow.
It replaces bash scripts with a more maintainable Python implementation.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


# Custom Exceptions
class ContinuousRefactoringError(Exception):
    """Base exception for continuous refactoring operations"""
    pass


class ConfigurationError(ContinuousRefactoringError):
    """Configuration file issues"""
    pass


class FileNotFoundError(ContinuousRefactoringError):
    """Missing required files"""
    pass


class GitError(ContinuousRefactoringError):
    """Git operation failures"""
    pass


class GitHubAPIError(ContinuousRefactoringError):
    """GitHub API call failures"""
    pass


# GitHub Actions Helper
class GitHubActionsHelper:
    """Handle GitHub Actions environment interactions"""

    def __init__(self):
        self.github_output_file = os.environ.get("GITHUB_OUTPUT")
        self.github_step_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")

    def write_output(self, name: str, value: str) -> None:
        """Write to $GITHUB_OUTPUT for subsequent steps

        Args:
            name: Output variable name
            value: Output variable value
        """
        if not self.github_output_file:
            print(f"{name}={value}")
            return

        with open(self.github_output_file, "a") as f:
            f.write(f"{name}={value}\n")

    def write_step_summary(self, text: str) -> None:
        """Write to $GITHUB_STEP_SUMMARY for workflow summary

        Args:
            text: Markdown text to append to summary
        """
        if not self.github_step_summary_file:
            print(f"SUMMARY: {text}")
            return

        with open(self.github_step_summary_file, "a") as f:
            f.write(f"{text}\n")

    def set_error(self, message: str) -> None:
        """Set error annotation in workflow

        Args:
            message: Error message to display
        """
        print(f"::error::{message}")

    def set_notice(self, message: str) -> None:
        """Set notice annotation in workflow

        Args:
            message: Notice message to display
        """
        print(f"::notice::{message}")

    def set_warning(self, message: str) -> None:
        """Set warning annotation in workflow

        Args:
            message: Warning message to display
        """
        print(f"::warning::{message}")


# Utility Functions
def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file and return parsed content

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        ConfigurationError: If file is invalid JSON
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in {file_path}: {str(e)}")


def run_command(cmd: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result

    Args:
        cmd: Command and arguments as list
        check: Whether to raise exception on non-zero exit
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
    """
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True
    )


def run_git_command(args: List[str]) -> str:
    """Run a git command and return stdout

    Args:
        args: Git command arguments (without 'git' prefix)

    Returns:
        Command stdout as string

    Raises:
        GitError: If git command fails
    """
    try:
        result = run_command(["git"] + args)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {' '.join(args)}\n{e.stderr}")


def run_gh_command(args: List[str]) -> str:
    """Run a GitHub CLI command and return stdout

    Args:
        args: gh command arguments (without 'gh' prefix)

    Returns:
        Command stdout as string

    Raises:
        GitHubAPIError: If gh command fails
    """
    try:
        result = run_command(["gh"] + args)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitHubAPIError(f"GitHub CLI command failed: {' '.join(args)}\n{e.stderr}")


def gh_api_call(endpoint: str, method: str = "GET") -> Dict[str, Any]:
    """Call GitHub REST API using gh CLI

    Args:
        endpoint: API endpoint path (e.g., "/repos/owner/repo/actions/runs")
        method: HTTP method (GET, POST, etc.)

    Returns:
        Parsed JSON response

    Raises:
        GitHubAPIError: If API call fails
    """
    try:
        output = run_gh_command(["api", endpoint, "--method", method])
        return json.loads(output) if output else {}
    except json.JSONDecodeError as e:
        raise GitHubAPIError(f"Invalid JSON from API: {str(e)}")


def generate_task_id(task: str, max_length: int = 30) -> str:
    """Generate sanitized task ID from task description

    Args:
        task: Task description text
        max_length: Maximum length for the ID

    Returns:
        Sanitized task ID (lowercase, alphanumeric + dashes, truncated)
    """
    # Convert to lowercase and replace non-alphanumeric with dashes
    sanitized = re.sub(r"[^a-z0-9]+", "-", task.lower())
    # Remove leading/trailing dashes
    sanitized = sanitized.strip("-")
    # Truncate to max length and remove trailing dash if present
    sanitized = sanitized[:max_length].rstrip("-")
    return sanitized


def substitute_template(template: str, **kwargs) -> str:
    """Substitute {{VARIABLE}} placeholders in template

    Args:
        template: Template string with {{VAR}} placeholders
        **kwargs: Variables to substitute

    Returns:
        Template with substitutions applied
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def find_next_available_task(plan_file: str, skip_indices: Optional[set] = None) -> Optional[tuple]:
    """Find first unchecked task not in skip_indices

    Args:
        plan_file: Path to spec.md file
        skip_indices: Set of task indices to skip (in-progress tasks)

    Returns:
        Tuple of (task_index, task_text) or None if no available task found
        task_index is 1-based position in spec.md

    Raises:
        FileNotFoundError: If spec file doesn't exist
    """
    if skip_indices is None:
        skip_indices = set()

    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Spec file not found: {plan_file}")

    with open(plan_file, "r") as f:
        task_index = 1
        for line in f:
            # Check for unchecked task
            match = re.match(r'^\s*- \[ \] (.+)$', line)
            if match:
                if task_index not in skip_indices:
                    return (task_index, match.group(1).strip())
                else:
                    print(f"Skipping task {task_index} (already in progress)")
                task_index += 1
            # Also count completed tasks to maintain correct indices
            elif re.match(r'^\s*- \[[xX]\] ', line):
                task_index += 1

    return None


def mark_task_complete(plan_file: str, task: str) -> None:
    """Mark a task as complete in the spec file

    Args:
        plan_file: Path to spec.md file
        task: Task description to mark complete

    Raises:
        FileNotFoundError: If spec file doesn't exist
    """
    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Spec file not found: {plan_file}")

    with open(plan_file, "r") as f:
        content = f.read()

    # Replace the unchecked task with checked version
    # Match the task with surrounding whitespace preserved
    pattern = r'(\s*)- \[ \] ' + re.escape(task)
    replacement = r'\1- [x] ' + task
    updated_content = re.sub(pattern, replacement, content, count=1)

    with open(plan_file, "w") as f:
        f.write(updated_content)


def validate_spec_format(spec_file: str) -> bool:
    """Validate that spec.md contains checklist items in the correct format

    Args:
        spec_file: Path to spec.md file

    Returns:
        True if valid format (contains at least one checklist item)

    Raises:
        FileNotFoundError: If spec file doesn't exist
        ConfigurationError: If spec file has invalid format
    """
    if not os.path.exists(spec_file):
        raise FileNotFoundError(f"Spec file not found: {spec_file}")

    has_checklist_item = False

    with open(spec_file, "r") as f:
        for line in f:
            # Check for unchecked or checked task items
            if re.match(r'^\s*- \[[xX ]\]', line):
                has_checklist_item = True
                break

    if not has_checklist_item:
        raise ConfigurationError(
            f"Invalid spec.md format: No checklist items found. "
            f"The file must contain at least one '- [ ]' or '- [x]' item."
        )

    return True


def download_artifact_json(repo: str, artifact_id: int) -> Optional[Dict[str, Any]]:
    """Download and parse artifact JSON using GitHub API

    Args:
        repo: GitHub repository (owner/name)
        artifact_id: Artifact ID to download

    Returns:
        Parsed JSON content or None if download fails
    """
    import tempfile
    import zipfile
    import subprocess

    try:
        # Get artifact download URL (returns a redirect)
        download_endpoint = f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"

        # Create temp file for the zip
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            tmp_zip_path = tmp_file.name

        try:
            # Download the zip file using gh api
            # The endpoint returns a redirect which gh api should follow
            subprocess.run(
                ["gh", "api", download_endpoint, "--method", "GET"],
                stdout=open(tmp_zip_path, 'wb'),
                stderr=subprocess.PIPE,
                check=True
            )

            # Extract and parse the JSON from the zip
            with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                # Get the first JSON file in the zip
                json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
                if json_files:
                    with zip_ref.open(json_files[0]) as json_file:
                        return json.load(json_file)
                else:
                    print(f"Warning: No JSON file found in artifact {artifact_id}")
                    return None

        finally:
            # Clean up temp file
            if os.path.exists(tmp_zip_path):
                os.remove(tmp_zip_path)

    except Exception as e:
        print(f"Warning: Failed to download/parse artifact {artifact_id}: {e}")
        return None


class ReviewerCapacityResult:
    """Result of reviewer capacity check with detailed information"""

    def __init__(self):
        self.reviewers_status = []  # List of dicts with reviewer details
        self.selected_reviewer = None
        self.all_at_capacity = False

    def add_reviewer(self, username: str, max_prs: int, open_prs: List[Dict], has_capacity: bool):
        """Add reviewer status information"""
        self.reviewers_status.append({
            "username": username,
            "max_prs": max_prs,
            "open_prs": open_prs,  # List of {pr_number, task_index, task_description}
            "open_count": len(open_prs),
            "has_capacity": has_capacity
        })

    def format_summary(self) -> str:
        """Generate formatted summary for GitHub Actions output"""
        lines = ["## Reviewer Capacity Check", ""]

        for reviewer in self.reviewers_status:
            username = reviewer["username"]
            max_prs = reviewer["max_prs"]
            open_count = reviewer["open_count"]
            open_prs = reviewer["open_prs"]
            has_capacity = reviewer["has_capacity"]

            # Reviewer header with status emoji
            status_emoji = "✅" if has_capacity else "❌"
            lines.append(f"### {status_emoji} **{username}**")
            lines.append("")

            # Capacity info
            lines.append(f"**Max PRs Allowed:** {max_prs}")
            lines.append(f"**Currently Open:** {open_count}/{max_prs}")
            lines.append("")

            # List open PRs with details
            if open_prs:
                lines.append("**Open PRs:**")
                for pr_info in open_prs:
                    pr_num = pr_info.get("pr_number", "?")
                    task_idx = pr_info.get("task_index", "?")
                    task_desc = pr_info.get("task_description", "Unknown task")
                    lines.append(f"- PR #{pr_num}: Task {task_idx} - {task_desc}")
                lines.append("")
            else:
                lines.append("**Open PRs:** None")
                lines.append("")

            # Availability status
            if has_capacity:
                available_slots = max_prs - open_count
                lines.append(f"**Status:** ✅ Available ({available_slots} slot(s) remaining)")
            else:
                lines.append(f"**Status:** ❌ At capacity")

            lines.append("")

        # Final decision
        lines.append("---")
        lines.append("")
        if self.selected_reviewer:
            lines.append(f"**Decision:** ✅ Selected **{self.selected_reviewer}** for next PR")
        else:
            lines.append(f"**Decision:** ❌ All reviewers at capacity - skipping PR creation")

        return "\n".join(lines)


def find_available_reviewer(reviewers: List[Dict[str, Any]], label: str, project: str) -> tuple[Optional[str], ReviewerCapacityResult]:
    """Find first reviewer with capacity based on artifact metadata

    Args:
        reviewers: List of reviewer dicts with 'username' and 'maxOpenPRs'
        label: GitHub label to filter PRs
        project: Project name to match artifacts

    Returns:
        Tuple of (username or None, ReviewerCapacityResult)

    Raises:
        GitHubAPIError: If GitHub CLI command fails
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    result = ReviewerCapacityResult()

    # Initialize reviewer PR lists
    reviewer_prs = {}
    for reviewer in reviewers:
        reviewer_prs[reviewer["username"]] = []

    # Get all open PRs with the label
    try:
        pr_output = run_gh_command([
            "pr", "list",
            "--repo", repo,
            "--label", label,
            "--state", "open",
            "--json", "number,headRefName"
        ])
        prs = json.loads(pr_output) if pr_output else []
    except (GitHubAPIError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to list PRs: {e}")
        prs = []

    print(f"Found {len(prs)} open PR(s) with label '{label}'")

    # Build a map of PR numbers from all open PRs
    pr_numbers = {pr["number"] for pr in prs}

    # Get recent successful workflow runs (they run on default branch, not feature branches)
    # We'll check all recent runs and match artifacts to PRs by PR number in metadata
    try:
        api_response = gh_api_call(
            f"/repos/{repo}/actions/runs?status=completed&per_page=50"
        )
        runs = api_response.get("workflow_runs", [])
    except GitHubAPIError as e:
        print(f"Warning: Failed to get workflow runs: {e}")
        runs = []

    # Check artifacts from recent runs to find reviewer assignments
    for run in runs:
        if run.get("conclusion") != "success":
            continue

        try:
            artifacts_data = gh_api_call(
                f"/repos/{repo}/actions/runs/{run['id']}/artifacts"
            )
            artifacts = artifacts_data.get("artifacts", [])

            for artifact in artifacts:
                name = artifact["name"]
                if name.startswith(f"task-metadata-{project}-"):
                    # Download and parse the artifact JSON
                    artifact_id = artifact["id"]
                    metadata = download_artifact_json(repo, artifact_id)

                    if metadata and "pr_number" in metadata and "reviewer" in metadata:
                        pr_num = metadata["pr_number"]
                        # Only count if this PR is in our open PRs list
                        if pr_num in pr_numbers:
                            assigned_reviewer = metadata["reviewer"]
                            if assigned_reviewer in reviewer_prs:
                                # Store PR details
                                pr_info = {
                                    "pr_number": pr_num,
                                    "task_index": metadata.get("task_index", "?"),
                                    "task_description": metadata.get("task_description", "Unknown task")
                                }
                                reviewer_prs[assigned_reviewer].append(pr_info)
                                print(f"PR #{pr_num}: reviewer={assigned_reviewer} (from artifact)")
                            else:
                                print(f"Warning: PR #{pr_num} has unknown reviewer: {assigned_reviewer}")

        except GitHubAPIError as e:
            print(f"Warning: Failed to get artifacts for run {run['id']}: {e}")
            continue

    # Build result and find first available reviewer
    selected_reviewer = None
    for reviewer in reviewers:
        username = reviewer["username"]
        max_prs = reviewer["maxOpenPRs"]
        open_prs = reviewer_prs[username]
        has_capacity = len(open_prs) < max_prs

        # Add to result
        result.add_reviewer(username, max_prs, open_prs, has_capacity)

        print(f"Reviewer {username}: {len(open_prs)} open PRs (max: {max_prs})")

        # Select first available reviewer
        if has_capacity and selected_reviewer is None:
            selected_reviewer = username
            print(f"Selected reviewer: {username}")

    result.selected_reviewer = selected_reviewer
    result.all_at_capacity = (selected_reviewer is None)

    return selected_reviewer, result


def get_in_progress_task_indices(repo: str, label: str, project: str) -> set:
    """Get set of task indices currently being worked on

    Args:
        repo: GitHub repository (owner/name)
        label: GitHub label to filter PRs
        project: Project name to match artifacts

    Returns:
        Set of task indices that are in progress

    Raises:
        GitHubAPIError: If GitHub API calls fail
    """
    in_progress = set()

    # Use gh CLI to list PRs
    try:
        pr_output = run_gh_command([
            "pr", "list",
            "--repo", repo,
            "--label", label,
            "--state", "open",
            "--json", "number,headRefName"
        ])
        prs = json.loads(pr_output) if pr_output else []
    except (GitHubAPIError, json.JSONDecodeError) as e:
        print(f"Warning: Failed to list PRs: {e}")
        return set()

    print(f"Found {len(prs)} open PR(s) with label '{label}'")

    for pr in prs:
        branch = pr["headRefName"]
        pr_number = pr["number"]

        # Get workflow runs for this branch
        try:
            api_response = gh_api_call(
                f"/repos/{repo}/actions/runs?branch={branch}&status=completed&per_page=10"
            )
            runs = api_response.get("workflow_runs", [])
        except GitHubAPIError as e:
            print(f"Warning: Failed to get runs for PR #{pr_number}: {e}")
            continue

        # Check most recent successful run
        for run in runs:
            if run.get("conclusion") == "success":
                # Get artifacts from this run
                try:
                    artifacts_data = gh_api_call(
                        f"/repos/{repo}/actions/runs/{run['id']}/artifacts"
                    )
                    artifacts = artifacts_data.get("artifacts", [])

                    for artifact in artifacts:
                        # Parse task index from artifact name
                        # Format: task-metadata-{project}-{index}.json
                        name = artifact["name"]
                        if name.startswith(f"task-metadata-{project}-"):
                            try:
                                # Extract index from name
                                suffix = name.replace(f"task-metadata-{project}-", "")
                                index_str = suffix.replace(".json", "")
                                task_index = int(index_str)
                                in_progress.add(task_index)
                                print(f"Found in-progress task {task_index} from PR #{pr_number}")
                            except ValueError:
                                print(f"Warning: Could not parse task index from artifact name: {name}")
                                continue
                except GitHubAPIError as e:
                    print(f"Warning: Failed to get artifacts for run {run['id']}: {e}")
                    continue
                break  # Only check first successful run

    return in_progress


# Command Handlers
def ensure_label_exists(label: str, gh: GitHubActionsHelper) -> None:
    """Ensure a GitHub label exists in the repository, create if it doesn't

    Args:
        label: Label name to ensure exists
        gh: GitHub Actions helper instance for logging
    """
    try:
        # Try to create the label
        # If it already exists, gh will return an error which we'll catch
        run_gh_command([
            "label", "create", label,
            "--description", "ClaudeStep automated refactoring",
            "--color", "0E8A16"  # Green color for refactor labels
        ])
        gh.write_step_summary(f"- Label '{label}': ✅ Created")
        gh.set_notice(f"Created label '{label}'")
    except GitHubAPIError as e:
        # Check if error is because label already exists
        if "already exists" in str(e).lower():
            gh.write_step_summary(f"- Label '{label}': ✅ Already exists")
        else:
            # Re-raise if it's a different error
            raise


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
        from datetime import datetime

        # === STEP 1: Detect Project ===
        print("=== Step 1/6: Detecting project ===")
        project_name = os.environ.get("PROJECT_NAME", "")
        merged_pr_number = os.environ.get("MERGED_PR_NUMBER", "")
        config_path_input = os.environ.get("CONFIG_PATH", "")
        spec_path_input = os.environ.get("SPEC_PATH", "")
        pr_template_path_input = os.environ.get("PR_TEMPLATE_PATH", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "")

        detected_project = None

        # If merged PR number provided, detect project from PR labels
        if merged_pr_number:
            print(f"Detecting project from merged PR #{merged_pr_number}...")
            try:
                pr_output = run_gh_command([
                    "pr", "view", merged_pr_number,
                    "--repo", repo,
                    "--json", "labels"
                ])
                pr_data = json.loads(pr_output)
                pr_labels = [label["name"] for label in pr_data.get("labels", [])]
                print(f"PR labels: {pr_labels}")

                # Search for matching refactor project
                import glob
                for config_file in glob.glob("refactor/*/configuration.json"):
                    if os.path.isfile(config_file):
                        try:
                            config = load_json(config_file)
                            label = config.get("label")
                            if label in pr_labels:
                                detected_project = config_file.split("/")[1]
                                print(f"✅ Found matching project: {detected_project} (label: {label})")
                                break
                        except Exception as e:
                            print(f"Warning: Failed to read {config_file}: {e}")

                if not detected_project:
                    gh.set_error(f"No refactor project found with matching label for PR #{merged_pr_number}")
                    return 1
            except Exception as e:
                gh.set_error(f"Failed to detect project from PR: {str(e)}")
                return 1
        elif project_name:
            detected_project = project_name
            print(f"Using provided project name: {detected_project}")
        else:
            gh.set_error("Either project_name or merged_pr_number must be provided")
            return 1

        # Determine paths
        config_path = config_path_input or f"refactor/{detected_project}/configuration.json"
        spec_path = spec_path_input or f"refactor/{detected_project}/spec.md"
        pr_template_path = pr_template_path_input or f"refactor/{detected_project}/pr-template.md"
        project_path = f"refactor/{detected_project}"

        print(f"Configuration paths:")
        print(f"  Project: {detected_project}")
        print(f"  Config: {config_path}")
        print(f"  Spec: {spec_path}")
        print(f"  PR Template: {pr_template_path}")

        # === STEP 2: Load and Validate Configuration ===
        print("\n=== Step 2/6: Loading configuration ===")
        config = load_json(config_path)
        label = config.get("label")
        branch_prefix = config.get("branchPrefix")
        reviewers = config.get("reviewers")

        if not label or not branch_prefix or not reviewers:
            raise ConfigurationError("Missing required fields: label, branchPrefix, or reviewers")

        # Ensure label exists
        ensure_label_exists(label, gh)

        # Validate spec format
        validate_spec_format(spec_path)

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

        result = find_next_available_task(spec_path, in_progress_indices)

        if not result:
            gh.write_output("has_task", "false")
            gh.write_output("all_tasks_done", "true")
            gh.set_notice("No available tasks (all completed or in progress)")
            return 0  # Not an error, just no tasks

        task_index, task = result
        print(f"✅ Found task {task_index}: {task}")

        # === STEP 5: Create Branch ===
        print("\n=== Step 5/6: Creating branch ===")
        date_prefix = datetime.now().strftime("%Y-%m")
        branch_name = f"{date_prefix}-{detected_project}-{task_index}"

        try:
            run_git_command(["checkout", "-b", branch_name])
            print(f"✅ Created branch: {branch_name}")
        except GitError as e:
            gh.set_error(f"Failed to create branch: {str(e)}")
            return 1

        # === STEP 6: Prepare Claude Prompt ===
        print("\n=== Step 6/6: Preparing Claude prompt ===")

        # Read spec content
        with open(spec_path, "r") as f:
            spec_content = f.read()

        # Create the prompt
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
        gh.write_output("branch_prefix", branch_prefix)
        gh.write_output("reviewers_json", json.dumps(reviewers))
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
        from datetime import datetime

        # Get environment variables
        branch_name = os.environ.get("BRANCH_NAME", "")
        task = os.environ.get("TASK", "")
        task_index = os.environ.get("TASK_INDEX", "")
        reviewer = os.environ.get("REVIEWER", "")
        label = os.environ.get("LABEL", "")
        project = os.environ.get("PROJECT", "")
        spec_path = os.environ.get("SPEC_PATH", "")
        pr_template_path = os.environ.get("PR_TEMPLATE_PATH", "")
        gh_token = os.environ.get("GH_TOKEN", "")
        github_repository = os.environ.get("GITHUB_REPOSITORY", "")
        github_run_id = os.environ.get("GITHUB_RUN_ID", "")
        base_branch = os.environ.get("BASE_BRANCH", "main")
        has_capacity = os.environ.get("HAS_CAPACITY", "")
        has_task = os.environ.get("HAS_TASK", "")

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
        if not all([branch_name, task, task_index, reviewer, label, project, spec_path, gh_token, github_repository]):
            raise ConfigurationError("Missing required environment variables")

        # === STEP 1: Commit Any Uncommitted Changes ===
        print("=== Step 1/3: Committing changes ===")

        # Configure git user for commits
        run_git_command(["config", "user.name", "github-actions[bot]"])
        run_git_command(["config", "user.email", "github-actions[bot]@users.noreply.github.com"])

        # Check for any changes (staged, unstaged, or untracked)
        status_output = run_git_command(["status", "--porcelain"])
        if status_output.strip():
            print("Found uncommitted changes, committing...")
            run_git_command(["add", "-A"])
            run_git_command(["commit", "-m", f"Complete task: {task}"])
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

        # Create PR
        pr_url = run_gh_command([
            "pr", "create",
            "--title", f"ClaudeStep: {task}",
            "--body", pr_body,
            "--label", label,
            "--assignee", reviewer,
            "--head", branch_name,
            "--base", base_branch
        ])

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

        metadata = {
            "task_index": int(task_index),
            "task_description": task,
            "project": project,
            "branch_name": branch_name,
            "reviewer": reviewer,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "workflow_run_id": int(github_run_id) if github_run_id else None,
            "pr_number": pr_number
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


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="ClaudeStep - GitHub Actions Helper Script"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Consolidated commands
    parser_prepare = subparsers.add_parser("prepare", help="Prepare everything for Claude Code execution")
    parser_finalize = subparsers.add_parser("finalize", help="Finalize after Claude Code execution (commit, PR, summary)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize GitHub Actions helper
    gh = GitHubActionsHelper()

    # Route to appropriate command handler
    if args.command == "prepare":
        return cmd_prepare(args, gh)
    elif args.command == "finalize":
        return cmd_finalize(args, gh)
    else:
        gh.set_error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
