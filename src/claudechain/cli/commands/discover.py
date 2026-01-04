"""Discover all refactor projects in the repository"""

import json
import os
from pathlib import Path
from typing import List

from claudechain.domain.project import Project
from claudechain.infrastructure.github.actions import GitHubActionsHelper


def find_all_projects(base_dir: str = None) -> List[str]:
    """Find all project directories with configuration.yml

    Args:
        base_dir: Base directory to search for projects (default: auto-detect from environment or use 'claude-chain')

    Returns:
        List of project names
    """
    # Auto-detect base directory from environment or use default
    if base_dir is None:
        base_dir = os.environ.get("CLAUDECHAIN_PROJECT_DIR", "claude-chain")

    # Check if base directory exists
    if not os.path.exists(base_dir):
        print(f"Base directory '{base_dir}' not found")
        return []

    # Use Project domain model's find_all factory method
    projects = Project.find_all(base_dir)

    # Log found projects
    for project in projects:
        print(f"Found project: {project.name}")

    # Return just the names for backward compatibility
    return [project.name for project in projects]


def main():
    """Discover all projects and output as JSON array"""
    print("Discovering refactor projects...")

    projects = find_all_projects()

    if not projects:
        print("No projects found")
        projects_json = "[]"
    else:
        print(f"\nFound {len(projects)} project(s):")
        for project in projects:
            print(f"  - {project}")
        projects_json = json.dumps(projects)

    # Output for GitHub Actions
    gh = GitHubActionsHelper()
    gh.write_output("projects", projects_json)
    gh.write_output("project_count", str(len(projects)))

    print(f"\nProjects JSON: {projects_json}")


if __name__ == "__main__":
    main()
