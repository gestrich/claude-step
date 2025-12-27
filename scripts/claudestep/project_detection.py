"""Project detection logic"""

import glob
import json
import os
from typing import Optional, Tuple

from claudestep.github_operations import run_gh_command


def detect_project_from_pr(pr_number: str, repo: str) -> Optional[str]:
    """Detect project from merged PR branch name

    Args:
        pr_number: PR number to check
        repo: GitHub repository (owner/name)

    Returns:
        Detected project name or None if not found
    """
    print(f"Detecting project from merged PR #{pr_number}...")
    try:
        # Get the branch name from the PR
        pr_output = run_gh_command([
            "pr", "view", pr_number,
            "--repo", repo,
            "--json", "headRefName"
        ])
        pr_data = json.loads(pr_output)
        branch_name = pr_data.get("headRefName")

        if not branch_name:
            print(f"Failed to get branch name for PR #{pr_number}")
            return None

        print(f"PR branch: {branch_name}")

        # Extract project name from branch name
        # Branch formats:
        # 1. Default: YYYY-MM-{project}-{index} (e.g., 2025-12-test-project-d324087d-1)
        # 2. Custom prefix: {branchPrefix}-{index} (e.g., refactor/swift-migration-1)

        # Strategy: Find all existing project directories and check which one matches the branch
        project_dirs = glob.glob("claude-step/*/")
        project_names = [os.path.basename(os.path.dirname(p)) for p in project_dirs]

        print(f"Found {len(project_names)} project(s): {project_names}")

        # Check each project to see if its branch prefix matches
        for project in project_names:
            # Check for config file to get branchPrefix
            config_path = f"claude-step/{project}/configuration.yml"

            if os.path.exists(config_path):
                from claudestep.config import load_config
                config = load_config(config_path)
                branch_prefix = config.get("branchPrefix")

                # Check if branch matches this project's pattern
                if branch_prefix:
                    # Custom prefix format: {branchPrefix}-{index}
                    # Branch should start with the prefix
                    if branch_name.startswith(f"{branch_prefix}-"):
                        print(f"✅ Matched project '{project}' with branchPrefix '{branch_prefix}'")
                        return project
                else:
                    # Default format: YYYY-MM-{project}-{index}
                    # Extract using the old logic
                    parts = branch_name.split("-")
                    if len(parts) >= 4:
                        extracted_project = "-".join(parts[2:-1])
                        if extracted_project == project:
                            print(f"✅ Matched project '{project}' using default format")
                            return project

        print(f"Could not match branch '{branch_name}' to any existing project")
        return None

    except Exception as e:
        print(f"Failed to detect project from PR: {str(e)}")
        return None


def detect_project_paths(project_name: str) -> Tuple[str, str, str, str]:
    """Determine project paths from project name

    Projects must be located in the claude-step/ directory with standard file names.

    Args:
        project_name: Name of the project

    Returns:
        Tuple of (config_path, spec_path, pr_template_path, project_path)
    """
    config_path = f"claude-step/{project_name}/configuration.yml"
    spec_path = f"claude-step/{project_name}/spec.md"
    pr_template_path = f"claude-step/{project_name}/pr-template.md"
    project_path = f"claude-step/{project_name}"

    print(f"Configuration paths:")
    print(f"  Project: {project_name}")
    print(f"  Config: {config_path}")
    print(f"  Spec: {spec_path}")
    print(f"  PR Template: {pr_template_path}")

    return config_path, spec_path, pr_template_path, project_path
