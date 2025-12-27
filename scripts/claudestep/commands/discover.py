"""Discover all refactor projects in the repository"""

import json
import os
from pathlib import Path
from typing import List

from claudestep.infrastructure.github.actions import GitHubActionsHelper


def find_all_projects(base_dir: str = None) -> List[str]:
    """Find all project directories with configuration.yml

    Args:
        base_dir: Base directory to search for projects (default: auto-detect from environment or use 'claude-step')

    Returns:
        List of project names
    """
    # Auto-detect base directory from environment or use default
    if base_dir is None:
        base_dir = os.environ.get("CLAUDESTEP_PROJECT_DIR", "claude-step")
    projects = []

    if not os.path.exists(base_dir):
        print(f"Base directory '{base_dir}' not found")
        return projects

    # Walk through the base directory
    for entry in os.listdir(base_dir):
        project_path = os.path.join(base_dir, entry)

        # Check if it's a directory with a configuration file
        if os.path.isdir(project_path):
            config_yml = os.path.join(project_path, "configuration.yml")
            if os.path.exists(config_yml):
                projects.append(entry)
                print(f"Found project: {entry}")

    return sorted(projects)


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
