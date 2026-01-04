"""Repository for loading project data from GitHub or local filesystem"""

import os
from typing import Optional, Tuple

from claudechain.domain.project import Project
from claudechain.domain.project_configuration import ProjectConfiguration
from claudechain.domain.spec_content import SpecContent


class ProjectRepository:
    """Infrastructure repository for loading project data from GitHub or local filesystem"""

    def __init__(self, repo: str):
        """Initialize repository

        Args:
            repo: GitHub repository in format 'owner/name'
        """
        self.repo = repo

    # ============================================================
    # Local Filesystem Methods (post-checkout)
    # ============================================================

    def load_local_configuration(self, project: Project) -> ProjectConfiguration:
        """Load and parse project configuration from local filesystem.

        Use this method after checkout when the project files are available locally.
        This is more efficient than making GitHub API calls and is preferred for
        merge event handling.

        If configuration.yml doesn't exist, returns default configuration
        (no assignee, no base branch override). This allows projects to work
        with sensible defaults without requiring a configuration file.

        Args:
            project: Project domain model

        Returns:
            Parsed ProjectConfiguration or default configuration if not found

        Raises:
            ConfigurationError: If configuration file exists but is invalid
        """
        if not os.path.exists(project.config_path):
            return ProjectConfiguration.default(project)

        with open(project.config_path, 'r', encoding='utf-8') as f:
            config_content = f.read()

        return ProjectConfiguration.from_yaml_string(project, config_content)

    def load_local_spec(self, project: Project) -> Optional[SpecContent]:
        """Load and parse spec.md from local filesystem.

        Use this method after checkout when the project files are available locally.

        Args:
            project: Project domain model

        Returns:
            Parsed SpecContent or None if not found
        """
        if not os.path.exists(project.spec_path):
            return None

        with open(project.spec_path, 'r', encoding='utf-8') as f:
            spec_content = f.read()

        if not spec_content:
            return None

        return SpecContent(project, spec_content)

    # ============================================================
    # GitHub API Methods (remote fetch)
    # ============================================================

    def load_configuration(
        self, project: Project, base_branch: str = "main"
    ) -> ProjectConfiguration:
        """Load and parse project configuration from GitHub

        If configuration.yml doesn't exist, returns default configuration
        (no assignee, no base branch override). This allows projects to work
        with sensible defaults without requiring a configuration file.

        Args:
            project: Project domain model
            base_branch: Branch to fetch from

        Returns:
            Parsed ProjectConfiguration or default configuration if not found

        Raises:
            GitHubAPIError: If GitHub API fails
            ConfigurationError: If configuration is invalid
        """
        from claudechain.infrastructure.github.operations import get_file_from_branch

        config_content = get_file_from_branch(self.repo, base_branch, project.config_path)
        if not config_content:
            return ProjectConfiguration.default(project)

        return ProjectConfiguration.from_yaml_string(project, config_content)

    def load_configuration_if_exists(
        self, project: Project, base_branch: str = "main"
    ) -> Optional[ProjectConfiguration]:
        """Load configuration only if it exists, returning None otherwise.

        Use this method when you need to distinguish between projects with
        and without configuration files.

        Args:
            project: Project domain model
            base_branch: Branch to fetch from

        Returns:
            Parsed ProjectConfiguration or None if file doesn't exist

        Raises:
            GitHubAPIError: If GitHub API fails
            ConfigurationError: If configuration is invalid
        """
        from claudechain.infrastructure.github.operations import get_file_from_branch

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
        from claudechain.infrastructure.github.operations import get_file_from_branch

        spec_content = get_file_from_branch(self.repo, base_branch, project.spec_path)
        if not spec_content:
            return None

        return SpecContent(project, spec_content)

    def load_project_full(
        self, project_name: str, base_branch: str = "main"
    ) -> Optional[Tuple[Project, ProjectConfiguration, SpecContent]]:
        """Load complete project data (config + spec)

        Configuration is optional - if not found, uses default configuration.
        Spec is required - if not found, returns None.

        Args:
            project_name: Name of the project
            base_branch: Branch to fetch from

        Returns:
            Tuple of (Project, ProjectConfiguration, SpecContent) or None if spec not found
        """
        project = Project(project_name)

        # Spec is required for a valid project
        spec = self.load_spec(project, base_branch)
        if not spec:
            return None

        # Config is optional - uses defaults if not found
        config = self.load_configuration(project, base_branch)

        return project, config, spec
