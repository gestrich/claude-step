"""Service Layer class for auto-start orchestration.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for detecting and determining which projects should be auto-triggered when
their spec.md files change.
"""

from typing import List

from claudestep.domain.auto_start import AutoStartProject, AutoStartDecision, ProjectChangeType
from claudestep.infrastructure.git.operations import (
    detect_changed_files,
    detect_deleted_files,
    parse_spec_path_to_project
)
from claudestep.services.core.pr_service import PRService


class AutoStartService:
    """Service Layer class for auto-start orchestration.

    Coordinates auto-start workflow by orchestrating git diff operations and
    GitHub PR queries. Implements business logic for ClaudeStep's auto-start
    detection and decision workflows.
    """

    def __init__(self, repo: str, pr_service: PRService):
        """Initialize the auto-start service

        Args:
            repo: GitHub repository (owner/name)
            pr_service: PRService instance for PR operations
        """
        self.repo = repo
        self.pr_service = pr_service

    # Public API methods

    def detect_changed_projects(
        self, ref_before: str, ref_after: str, spec_pattern: str = "claude-step/*/spec.md"
    ) -> List[AutoStartProject]:
        """Identify projects with spec.md changes between two git references

        Args:
            ref_before: Git reference for the before state (e.g., commit SHA)
            ref_after: Git reference for the after state (e.g., commit SHA)
            spec_pattern: File pattern to match spec files (default: "claude-step/*/spec.md")

        Returns:
            List of AutoStartProject domain models representing changed projects

        Examples:
            >>> service = AutoStartService("owner/repo", pr_service)
            >>> projects = service.detect_changed_projects("abc123", "def456")
            >>> projects[0].name
            'my-project'
            >>> projects[0].change_type
            ProjectChangeType.ADDED
        """
        changed_projects = []

        # Detect added or modified spec files
        changed_files = detect_changed_files(ref_before, ref_after, spec_pattern)
        for file_path in changed_files:
            project_name = parse_spec_path_to_project(file_path)
            if project_name:
                # Determine if this is a new file (added) or modified
                # For now, we'll treat all changes as MODIFIED and rely on
                # determine_new_projects() to check if the project is truly new
                changed_projects.append(
                    AutoStartProject(
                        name=project_name,
                        change_type=ProjectChangeType.MODIFIED,
                        spec_path=file_path
                    )
                )

        # Detect deleted spec files
        deleted_files = detect_deleted_files(ref_before, ref_after, spec_pattern)
        for file_path in deleted_files:
            project_name = parse_spec_path_to_project(file_path)
            if project_name:
                changed_projects.append(
                    AutoStartProject(
                        name=project_name,
                        change_type=ProjectChangeType.DELETED,
                        spec_path=file_path
                    )
                )

        return changed_projects

    def determine_new_projects(self, projects: List[AutoStartProject]) -> List[AutoStartProject]:
        """Check which projects have no existing PRs (are truly new)

        Args:
            projects: List of AutoStartProject instances to check

        Returns:
            List of projects that have no existing PRs (new projects)

        Examples:
            >>> service = AutoStartService("owner/repo", pr_service)
            >>> changed = [AutoStartProject("proj1", ProjectChangeType.MODIFIED, "path")]
            >>> new_projects = service.determine_new_projects(changed)
            >>> len(new_projects)
            1
        """
        new_projects = []

        for project in projects:
            # Skip deleted projects
            if project.change_type == ProjectChangeType.DELETED:
                continue

            try:
                # Use PRService to get all PRs for this project
                prs = self.pr_service.get_project_prs(project.name, state="all")

                # If no PRs exist, this is a new project
                if len(prs) == 0:
                    new_projects.append(project)
                    print(f"  ✓ {project.name} is a new project (no existing PRs)")
                else:
                    print(f"  ✗ {project.name} has {len(prs)} existing PR(s), skipping")

            except Exception as e:
                # Log warning, skip project on API failure
                print(f"⚠️  Error querying GitHub API for {project.name}: {e}")
                continue

        return new_projects

    def should_auto_trigger(self, project: AutoStartProject) -> AutoStartDecision:
        """Determine whether to auto-trigger a project based on business logic

        Args:
            project: AutoStartProject to evaluate

        Returns:
            AutoStartDecision with trigger decision and reason

        Examples:
            >>> service = AutoStartService("owner/repo", pr_service)
            >>> project = AutoStartProject("proj1", ProjectChangeType.MODIFIED, "path")
            >>> decision = service.should_auto_trigger(project)
            >>> decision.should_trigger
            True
            >>> decision.reason
            'New project detected'
        """
        # Deleted projects should never be triggered
        if project.change_type == ProjectChangeType.DELETED:
            return AutoStartDecision(
                project=project,
                should_trigger=False,
                reason="Project spec was deleted"
            )

        # Check if project has existing PRs
        try:
            prs = self.pr_service.get_project_prs(project.name, state="all")

            if len(prs) == 0:
                # New project - should trigger
                return AutoStartDecision(
                    project=project,
                    should_trigger=True,
                    reason="New project detected"
                )
            else:
                # Existing project - should not trigger
                return AutoStartDecision(
                    project=project,
                    should_trigger=False,
                    reason=f"Project has {len(prs)} existing PR(s)"
                )

        except Exception as e:
            # On error, default to not triggering
            return AutoStartDecision(
                project=project,
                should_trigger=False,
                reason=f"Error checking PRs: {e}"
            )
