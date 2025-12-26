"""Project detection logic"""

import glob
import json
import os
from typing import Optional, Tuple

from claudestep.config import load_json
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
        # Branch format: YYYY-MM-{project}-{index}
        # Example: 2025-12-test-project-d324087d-1 -> test-project-d324087d
        parts = branch_name.split("-")
        if len(parts) >= 4:
            # Remove YYYY, MM, and index (last part)
            # Join the remaining parts to get the project name
            project = "-".join(parts[2:-1])
            print(f"✅ Extracted project from branch name: {project}")

            # Verify the project exists
            config_path = f"refactor/{project}/configuration.json"
            if os.path.exists(config_path):
                return project
            else:
                print(f"Warning: Project config not found at {config_path}")
                return None
        else:
            print(f"Branch name '{branch_name}' doesn't match expected format")
            return None

    except Exception as e:
        print(f"Failed to detect project from PR: {str(e)}")
        return None


def detect_project_paths(project_name: str, config_path_input: str = "",
                        spec_path_input: str = "", pr_template_path_input: str = "") -> Tuple[str, str, str, str]:
    """Determine project paths from project name and optional overrides

    Args:
        project_name: Name of the project
        config_path_input: Optional override for config path
        spec_path_input: Optional override for spec path
        pr_template_path_input: Optional override for PR template path

    Returns:
        Tuple of (config_path, spec_path, pr_template_path, project_path)
    """
    config_path = config_path_input or f"refactor/{project_name}/configuration.json"
    spec_path = spec_path_input or f"refactor/{project_name}/spec.md"
    pr_template_path = pr_template_path_input or f"refactor/{project_name}/pr-template.md"
    project_path = f"refactor/{project_name}"

    print(f"Configuration paths:")
    print(f"  Project: {project_name}")
    print(f"  Config: {config_path}")
    print(f"  Spec: {spec_path}")
    print(f"  PR Template: {pr_template_path}")

    return config_path, spec_path, pr_template_path, project_path
