"""CLI command for discovering ready projects.

Orchestrates Service Layer classes to coordinate project discovery workflow.
This command instantiates services and coordinates their operations but
does not implement business logic directly.
"""

import json
import os

from claudestep.cli.commands.discover import find_all_projects
from claudestep.domain.config import validate_spec_format
from claudestep.domain.project import Project
from claudestep.infrastructure.github.actions import GitHubActionsHelper
from claudestep.services.core.reviewer_service import ReviewerService
from claudestep.services.core.task_service import TaskService


def check_project_ready(project_name: str, repo: str) -> bool:
    """Orchestrate project readiness check using Service Layer classes.

    This function instantiates services and coordinates their operations but
    does not implement business logic directly. Follows Service Layer pattern.

    A project is ready if:
    1. spec.md exists (required)
    2. Spec format is valid (contains checklist items)
    3. Has capacity (reviewer capacity OR project-level capacity if no reviewers)
    4. Has available tasks

    Configuration is optional - projects without configuration.yml use default settings.

    Args:
        project_name: Name of the project to check
        repo: GitHub repository (owner/name)

    Returns:
        True if project is ready for work, False otherwise
    """
    try:
        # Create Project domain model
        project = Project(project_name)

        # Check if spec.md exists (required)
        if not os.path.exists(project.spec_path):
            print(f"  ⏭️  No spec.md found")
            return False

        # Validate spec format
        try:
            validate_spec_format(project.spec_path)
        except Exception as e:
            print(f"  ⏭️  Invalid spec format: {str(e)}")
            return False

        # Use single 'claudestep' label for all projects
        label = "claudestep"

        # Load configuration (optional - uses defaults if not found)
        from claudestep.domain.project_configuration import ProjectConfiguration
        if os.path.exists(project.config_path):
            with open(project.config_path, 'r') as f:
                config_content = f.read()
            project_config = ProjectConfiguration.from_yaml_string(project, config_content)
        else:
            project_config = ProjectConfiguration.default(project)

        # Initialize services
        from claudestep.services.core.pr_service import PRService
        pr_service = PRService(repo)
        reviewer_service = ReviewerService(repo, pr_service)
        task_service = TaskService(repo, pr_service)

        # Check capacity (reviewer capacity OR project-level capacity if no reviewers)
        _, capacity_result = reviewer_service.find_available_reviewer(
            project_config, label, project_name
        )

        if capacity_result.all_at_capacity:
            if project_config.reviewers:
                print(f"  ⏭️  No reviewer capacity")
            else:
                print(f"  ⏭️  Project at capacity (1 open PR limit)")
            return False

        # Load spec and check for available tasks
        with open(project.spec_path, 'r') as f:
            spec_content = f.read()
        from claudestep.domain.spec_content import SpecContent
        spec = SpecContent(project, spec_content)

        # Get in-progress tasks
        in_progress_hashes = task_service.get_in_progress_tasks(label, project_name)
        next_task = task_service.find_next_available_task(spec, in_progress_hashes)

        if not next_task:
            print(f"  ⏭️  No available tasks")
            return False

        # Get stats for logging
        uncompleted = spec.pending_tasks

        # Get capacity info from result
        open_prs = sum(r['open_count'] for r in capacity_result.reviewers_status)
        max_prs = sum(r['max_prs'] for r in capacity_result.reviewers_status)

        if project_config.reviewers:
            print(f"  ✅ Ready for work ({open_prs}/{max_prs} PRs, {uncompleted} tasks remaining)")
        else:
            print(f"  ✅ Ready for work (no reviewers, {uncompleted} tasks remaining)")
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
