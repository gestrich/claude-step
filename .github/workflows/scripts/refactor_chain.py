#!/usr/bin/env python3
"""
Refactor Chain - GitHub Actions Helper Script

This script handles all operations for the automated refactoring chain workflow.
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
class RefactorChainError(Exception):
    """Base exception for refactor chain operations"""
    pass


class ConfigurationError(RefactorChainError):
    """Configuration file issues"""
    pass


class FileNotFoundError(RefactorChainError):
    """Missing required files"""
    pass


class GitError(RefactorChainError):
    """Git operation failures"""
    pass


class GitHubAPIError(RefactorChainError):
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


def find_unchecked_task(plan_file: str) -> Optional[str]:
    """Find first unchecked task in markdown checklist

    Args:
        plan_file: Path to plan.md file

    Returns:
        First unchecked task text, or None if none found

    Raises:
        FileNotFoundError: If plan file doesn't exist
    """
    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Plan file not found: {plan_file}")

    with open(plan_file, "r") as f:
        for line in f:
            # Match markdown checkbox: - [ ] or   - [ ]
            match = re.match(r'^\s*- \[ \] (.+)$', line)
            if match:
                return match.group(1).strip()

    return None


def mark_task_complete(plan_file: str, task: str) -> None:
    """Mark a task as complete in the plan file

    Args:
        plan_file: Path to plan.md file
        task: Task description to mark complete

    Raises:
        FileNotFoundError: If plan file doesn't exist
    """
    if not os.path.exists(plan_file):
        raise FileNotFoundError(f"Plan file not found: {plan_file}")

    with open(plan_file, "r") as f:
        content = f.read()

    # Replace the unchecked task with checked version
    # Match the task with surrounding whitespace preserved
    pattern = r'(\s*)- \[ \] ' + re.escape(task)
    replacement = r'\1- [x] ' + task
    updated_content = re.sub(pattern, replacement, content, count=1)

    with open(plan_file, "w") as f:
        f.write(updated_content)


def find_available_reviewer(reviewers: List[Dict[str, Any]], label: str) -> Optional[str]:
    """Find first reviewer with capacity

    Args:
        reviewers: List of reviewer dicts with 'username' and 'maxOpenPRs'
        label: GitHub label to filter PRs

    Returns:
        Username of available reviewer, or None if all at capacity

    Raises:
        GitHubAPIError: If GitHub CLI command fails
    """
    for reviewer in reviewers:
        username = reviewer["username"]
        max_prs = reviewer["maxOpenPRs"]

        # Query GitHub for open PRs assigned to this reviewer with the label
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        try:
            output = run_gh_command([
                "pr", "list",
                "--repo", repo,
                "--label", label,
                "--assignee", username,
                "--state", "open",
                "--json", "number",
                "--jq", "length"
            ])
            open_prs = int(output) if output else 0
        except (ValueError, GitHubAPIError) as e:
            print(f"Error checking PRs for {username}: {e}")
            continue

        print(f"Reviewer {username}: {open_prs} open PRs (max: {max_prs})")

        if open_prs < max_prs:
            print(f"Selected reviewer: {username}")
            return username

    return None


# Command Handlers
def cmd_setup(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'setup' subcommand - load configuration

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        project = args.project
        project_path = f"refactor/{project}"
        config_file = f"{project_path}/configuration.json"

        # Load and validate configuration
        config = load_json(config_file)

        # Extract required fields
        label = config.get("label")
        branch_prefix = config.get("branchPrefix")
        reviewers = config.get("reviewers")

        if not label or not branch_prefix or not reviewers:
            raise ConfigurationError("Missing required fields: label, branchPrefix, or reviewers")

        # Convert reviewers to JSON string for passing to next job
        reviewers_json = json.dumps(reviewers)

        # Write outputs
        gh.write_output("label", label)
        gh.write_output("branch_prefix", branch_prefix)
        gh.write_output("reviewers_json", reviewers_json)
        gh.write_output("project_path", project_path)

        # Write step summary
        gh.write_step_summary("### Configuration")
        gh.write_step_summary(f"- Project: {project}")
        gh.write_step_summary(f"- Label: {label}")
        gh.write_step_summary(f"- Branch prefix: {branch_prefix}")

        return 0

    except (FileNotFoundError, ConfigurationError) as e:
        gh.set_error(str(e))
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in setup: {str(e)}")
        return 1


def cmd_check_capacity(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'check-capacity' subcommand - find reviewer with capacity

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get environment variables
        label = os.environ.get("LABEL", "")
        reviewers_json = os.environ.get("REVIEWERS_JSON", "")

        if not label or not reviewers_json:
            raise ConfigurationError("Missing required environment variables: LABEL, REVIEWERS_JSON")

        # Parse reviewers
        reviewers = json.loads(reviewers_json)

        print("Checking reviewer capacity...")

        # Find available reviewer
        selected_reviewer = find_available_reviewer(reviewers, label)

        if selected_reviewer:
            gh.write_output("reviewer", selected_reviewer)
            gh.write_output("has_capacity", "true")
        else:
            gh.write_output("reviewer", "")
            gh.write_output("has_capacity", "false")
            gh.set_notice("All reviewers at capacity, skipping PR creation")

        return 0

    except (ConfigurationError, GitHubAPIError) as e:
        gh.set_error(str(e))
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in check-capacity: {str(e)}")
        return 1


def cmd_find_task(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'find-task' subcommand - find next unchecked task

    Args:
        args: Parsed command-line arguments
        gh: GitHub Actions helper instance

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    try:
        # Get project path from environment
        project_path = os.environ.get("PROJECT_PATH", "")

        if not project_path:
            raise ConfigurationError("Missing required environment variable: PROJECT_PATH")

        plan_file = f"{project_path}/plan.md"

        # Find unchecked task
        task = find_unchecked_task(plan_file)

        if task:
            # Generate task ID
            task_id = generate_task_id(task)

            gh.write_output("task", task)
            gh.write_output("task_id", task_id)
            gh.write_output("has_task", "true")

            gh.write_step_summary("### Next Task")
            gh.write_step_summary(task)
        else:
            gh.write_output("task", "")
            gh.write_output("task_id", "")
            gh.write_output("has_task", "false")
            gh.set_notice("No unchecked tasks found in plan")

        return 0

    except (FileNotFoundError, ConfigurationError) as e:
        gh.set_error(str(e))
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in find-task: {str(e)}")
        return 1


def cmd_create_pr(args: argparse.Namespace, gh: GitHubActionsHelper) -> int:
    """Handle 'create-pr' subcommand - push branch and create PR

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
        reviewer = os.environ.get("REVIEWER", "")
        label = os.environ.get("LABEL", "")
        project_path = os.environ.get("PROJECT_PATH", "")
        gh_token = os.environ.get("GH_TOKEN", "")
        github_repository = os.environ.get("GITHUB_REPOSITORY", "")

        if not all([branch_name, task, reviewer, label, project_path, gh_token, github_repository]):
            raise ConfigurationError("Missing required environment variables")

        # Check if there are commits to push
        try:
            commits_ahead = run_git_command(["rev-list", "--count", "origin/main..HEAD"])
            commits_count = int(commits_ahead) if commits_ahead else 0
        except (GitError, ValueError):
            commits_count = 0

        if commits_count == 0:
            gh.set_warning("No changes made by Claude, skipping PR creation")
            return 0

        print(f"Found {commits_count} commit(s) to push")

        # Reconfigure git auth (Claude Code action may have changed it)
        remote_url = f"https://x-access-token:{gh_token}@github.com/{github_repository}.git"
        run_git_command(["remote", "set-url", "origin", remote_url])

        # Mark task as complete in plan.md before pushing
        plan_file = f"{project_path}/plan.md"
        try:
            mark_task_complete(plan_file, task)
            print(f"Marked task complete in {plan_file}")

            # Add the updated plan to the same commit
            run_git_command(["add", plan_file])

            # Check if there are changes to commit
            try:
                status_output = run_git_command(["status", "--porcelain"])
                if status_output.strip():
                    # Amend the last commit to include the plan update
                    run_git_command(["commit", "--amend", "--no-edit"])
                    print("Added plan.md update to commit")
            except GitError:
                # If amending fails, create a new commit
                run_git_command(["commit", "-m", f"Mark task complete: {task}"])
                print("Created separate commit for plan.md update")
        except (GitError, FileNotFoundError) as e:
            gh.set_warning(f"Failed to mark task complete in plan: {str(e)}")

        # Push the branch with all changes
        run_git_command(["push", "-u", "origin", branch_name, "--force-with-lease"])

        # Load PR template and substitute
        pr_template_file = f"{project_path}/pr-template.md"
        if os.path.exists(pr_template_file):
            with open(pr_template_file, "r") as f:
                pr_body = substitute_template(f.read(), TASK_DESCRIPTION=task)
        else:
            pr_body = f"## Task\n{task}"

        # Create PR
        run_gh_command([
            "pr", "create",
            "--title", f"Refactor: {task}",
            "--body", pr_body,
            "--label", label,
            "--assignee", reviewer,
            "--head", branch_name
        ])

        # Write summary
        gh.write_step_summary("### PR Created")
        gh.write_step_summary(f"- Branch: {branch_name}")
        gh.write_step_summary(f"- Reviewer: {reviewer}")
        gh.write_step_summary(f"- Task: {task}")

        return 0

    except (GitError, GitHubAPIError, ConfigurationError) as e:
        gh.set_error(str(e))
        return 1
    except Exception as e:
        gh.set_error(f"Unexpected error in create-pr: {str(e)}")
        return 1


def main():
    """Main entry point for the script"""
    parser = argparse.ArgumentParser(
        description="Refactor Chain - GitHub Actions Helper Script"
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    # Setup subcommand
    parser_setup = subparsers.add_parser("setup", help="Load configuration and write outputs")
    parser_setup.add_argument("project", help="Refactor project folder name")

    # Check-capacity subcommand
    parser_check = subparsers.add_parser("check-capacity", help="Find reviewer with capacity")

    # Find-task subcommand
    parser_find = subparsers.add_parser("find-task", help="Find next unchecked task")

    # Create-PR subcommand
    parser_create = subparsers.add_parser("create-pr", help="Push branch and create PR")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Initialize GitHub Actions helper
    gh = GitHubActionsHelper()

    # Route to appropriate command handler
    if args.command == "setup":
        return cmd_setup(args, gh)
    elif args.command == "check-capacity":
        return cmd_check_capacity(args, gh)
    elif args.command == "find-task":
        return cmd_find_task(args, gh)
    elif args.command == "create-pr":
        return cmd_create_pr(args, gh)
    else:
        gh.set_error(f"Unknown command: {args.command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
