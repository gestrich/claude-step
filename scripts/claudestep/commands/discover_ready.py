"""Discover all refactor projects that have reviewer capacity and available tasks"""

import json
import os

from claudestep.commands.discover import find_all_projects
from claudestep.config import load_config, validate_spec_format
from claudestep.github_actions import GitHubActionsHelper
from claudestep.project_detection import detect_project_paths
from claudestep.reviewer_management import find_available_reviewer
from claudestep.task_management import find_next_available_task, get_in_progress_task_indices


def check_project_ready(project_name: str, repo: str) -> bool:
    """Check if a project has capacity and available tasks

    Args:
        project_name: Name of the project to check
        repo: GitHub repository (owner/name)

    Returns:
        True if project is ready for work, False otherwise
    """
    try:
        # Get project paths
        config_path, spec_path, pr_template_path, project_path = detect_project_paths(project_name)

        # Check if files exist
        if not os.path.exists(config_path):
            print(f"  ⏭️  No configuration file found")
            return False

        if not os.path.exists(spec_path):
            print(f"  ⏭️  No spec.md found")
            return False

        # Load and validate configuration
        config = load_config(config_path)
        reviewers = config.get("reviewers", [])

        if not reviewers:
            print(f"  ⏭️  No reviewers configured")
            return False

        # Validate spec format
        try:
            validate_spec_format(spec_path)
        except Exception as e:
            print(f"  ⏭️  Invalid spec format: {str(e)}")
            return False

        # Use single 'claudestep' label for all projects
        label = "claudestep"

        # Check reviewer capacity
        selected_reviewer, capacity_result = find_available_reviewer(reviewers, label, project_name)

        if not selected_reviewer:
            print(f"  ⏭️  No reviewer capacity")
            return False

        # Check for available tasks
        in_progress_indices = get_in_progress_task_indices(repo, label, project_name)
        next_task = find_next_available_task(spec_path, in_progress_indices)

        if not next_task:
            print(f"  ⏭️  No available tasks")
            return False

        # Count stats for logging
        with open(spec_path, 'r') as f:
            spec_content = f.read()
            uncompleted = spec_content.count('- [ ]')

        # Get capacity info
        summary = capacity_result.format_summary()
        # Extract open PRs count from summary (it's in the format)
        open_prs = sum(r['openPRs'] for r in capacity_result.reviewer_status)
        max_prs = sum(r['maxPRs'] for r in capacity_result.reviewer_status)

        print(f"  ✅ Ready for work ({open_prs}/{max_prs} PRs, {uncompleted} tasks remaining)")
        return True

    except Exception as e:
        print(f"  ❌ Error checking project: {str(e)}")
        return False


def main():
    """Discover all projects ready for work and output as JSON array"""
    print("========================================================================")
    print("ClaudeStep Discovery Mode")
    print("========================================================================")
    print("")
    print("🔍 Finding all projects with capacity and available tasks...")
    print("")

    # Initialize GitHub Actions helper
    gh = GitHubActionsHelper()

    # Get repository from environment
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not repo:
        print("Error: GITHUB_REPOSITORY environment variable not set")
        gh.write_output("projects", "[]")
        gh.write_output("project_count", "0")
        return 1

    # Discover all projects
    all_projects = find_all_projects()

    if not all_projects:
        print("No refactor projects found")
        print("")
        gh.write_output("projects", "[]")
        gh.write_output("project_count", "0")
        return 0

    # Check each project for capacity and tasks
    ready_projects = []

    for project in all_projects:
        print(f"Checking project: {project}")
        if check_project_ready(project, repo):
            ready_projects.append(project)

    # Output results
    if not ready_projects:
        print("")
        print("No projects have available capacity and tasks")
        print("")
        projects_json = "[]"
    else:
        print("")
        print("========================================================================")
        print(f"Found {len(ready_projects)} project(s) ready for work:")
        for project in ready_projects:
            print(f"  - {project}")
        print("========================================================================")
        print("")
        projects_json = json.dumps(ready_projects)

    gh.write_output("projects", projects_json)
    gh.write_output("project_count", str(len(ready_projects)))

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
