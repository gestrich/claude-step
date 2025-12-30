"""Repository for loading project data from GitHub"""

from typing import Optional, Tuple

from claudestep.domain.project import Project
from claudestep.domain.project_configuration import ProjectConfiguration
from claudestep.domain.spec_content import SpecContent


class ProjectRepository:
    """Infrastructure repository for loading project data from GitHub"""

    def __init__(self, repo: str):
        """Initialize repository

        Args:
            repo: GitHub repository in format 'owner/name'
        """
        self.repo = repo

    def load_configuration(
        self, project: Project, base_branch: str = "main"
    ) -> Optional[ProjectConfiguration]:
        """Load and parse project configuration from GitHub

        Args:
            project: Project domain model
            base_branch: Branch to fetch from

        Returns:
            Parsed ProjectConfiguration or None if not found

        Raises:
            GitHubAPIError: If GitHub API fails
            ConfigurationError: If configuration is invalid
        """
        from claudestep.infrastructure.github.operations import get_file_from_branch

        config_content = get_file_from_branch(self.repo, base_branch, project.config_path)
        if not config_content:
            return None

        return ProjectConfiguration.from_yaml_string(project, config_content)

    def load_spec(
        self, project: Project, base_branch: str = "main"
    ) -> Optional[SpecContent]:
        """Load and parse spec.md from GitHub

        Args:
            project: Project domain model
            base_branch: Branch to fetch from

        Returns:
            Parsed SpecContent or None if not found

        Raises:
            GitHubAPIError: If GitHub API fails
        """
        from claudestep.infrastructure.github.operations import get_file_from_branch

        spec_content = get_file_from_branch(self.repo, base_branch, project.spec_path)
        if not spec_content:
            return None

        return SpecContent(project, spec_content)

    def load_project_full(
        self, project_name: str, base_branch: str = "main"
    ) -> Optional[Tuple[Project, ProjectConfiguration, SpecContent]]:
        """Load complete project data (config + spec)

        Args:
            project_name: Name of the project
            base_branch: Branch to fetch from

        Returns:
            Tuple of (Project, ProjectConfiguration, SpecContent) or None if not found
        """
        project = Project(project_name)

        config = self.load_configuration(project, base_branch)
        if not config:
            return None

        spec = self.load_spec(project, base_branch)
        if not spec:
            return None

        return project, config, spec
