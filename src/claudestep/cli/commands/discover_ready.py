"""CLI command for discovering ready projects.

Orchestrates Service Layer classes to coordinate project discovery workflow.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import json
import os

from claudestep.cli.commands.discover import find_all_projects
from claudestep.domain.config import load_config, validate_spec_format
from claudestep.domain.project import Project
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.infrastructure.repositories.project_repository import ProjectRepository
from claudestep.services.project_detection_service import ProjectDetectionService
from claudestep.services.reviewer_management_service import ReviewerManagementService
from claudestep.services.task_management_service import TaskManagementService


def check_project_ready(project_name: str, repo: str) -> bool:
    """Orchestrate project readiness check using Service Layer classes.

    This function instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern.

    Args:
        project_name: Name of the project to check
        repo: GitHub repository (owner/name)

    Returns:
        True if project is ready for work, False otherwise
    """
    try:
        # Create Project domain model
        project = Project(project_name)

        # Check if files exist
        if not os.path.exists(project.config_path):
            print(f"  ⏭️  No configuration file found")
            return False

        if not os.path.exists(project.spec_path):
            print(f"  ⏭️  No spec.md found")
            return False

        # Initialize infrastructure
        project_repository = ProjectRepository(repo)

        # Load and validate configuration
        config = load_config(project.config_path)
        reviewers = config.get("reviewers", [])

        if not reviewers:
            print(f"  ⏭️  No reviewers configured")
            return False

        # Validate spec format
        try:
            validate_spec_format(project.spec_path)
        except Exception as e:
            print(f"  ⏭️  Invalid spec format: {str(e)}")
            return False

        # Use single 'claudestep' label for all projects
        label = "claudestep"

        # Load configuration using repository (for type-safe access)
        from claudestep.domain.config import load_config_from_string
        with open(project.config_path, 'r') as f:
            config_content = f.read()
        from claudestep.domain.project_configuration import ProjectConfiguration
        project_config = ProjectConfiguration.from_yaml_string(project, config_content)

        # Initialize services
        reviewer_service = ReviewerManagementService(repo)
        task_service = TaskManagementService(repo)

        # Check reviewer capacity
        selected_reviewer, capacity_result = reviewer_service.find_available_reviewer(project_config, label, project_name)

        if not selected_reviewer:
            print(f"  ⏭️  No reviewer capacity")
            return False

        # Load spec and check for available tasks
        with open(project.spec_path, 'r') as f:
            spec_content = f.read()
        from claudestep.domain.spec_content import SpecContent
        spec = SpecContent(project, spec_content)

        in_progress_indices = task_service.get_in_progress_task_indices(label, project_name)
        next_task = task_service.find_next_available_task(spec, in_progress_indices)

        if not next_task:
            print(f"  ⏭️  No available tasks")
            return False

        # Get stats for logging
        uncompleted = spec.pending_tasks

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
