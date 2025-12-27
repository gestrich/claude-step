"""Project detection logic"""

import json
from typing import Optional, Tuple

from claudestep.infrastructure.github.operations import run_gh_command
from claudestep.application.services.pr_operations import parse_branch_name


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

        # Extract project name from branch name using standard format
        # Expected format: claude-step-{project}-{index}
        result = parse_branch_name(branch_name)

        if result:
            project_name, _ = result
            print(f"✅ Detected project '{project_name}' from branch '{branch_name}'")
            return project_name
        else:
            print(f"Could not parse branch '{branch_name}' - not in expected format claude-step-{{project}}-{{index}}")
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
