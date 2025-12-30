"""Domain model representing a ClaudeStep project"""

import os
import re
from typing import List, Optional


class Project:
    """Domain model representing a ClaudeStep project with its paths and metadata"""

    def __init__(self, name: str, base_path: Optional[str] = None):
        """Initialize a Project

        Args:
            name: Project name
            base_path: Optional custom base path. Defaults to claude-step/{name}
        """
        self.name = name
        self.base_path = base_path or f"claude-step/{name}"

    @property
    def config_path(self) -> str:
        """Path to configuration.yml file"""
        return f"{self.base_path}/configuration.yml"

    @property
    def spec_path(self) -> str:
        """Path to spec.md file"""
        return f"{self.base_path}/spec.md"

    @property
    def pr_template_path(self) -> str:
        """Path to pr-template.md file"""
        return f"{self.base_path}/pr-template.md"

    @property
    def metadata_file_path(self) -> str:
        """Path to metadata JSON file in claudestep-metadata branch"""
        return f"{self.name}.json"

    def get_branch_name(self, task_index: int) -> str:
        """Generate branch name for a task

        Args:
            task_index: Task index (1-based)

        Returns:
            Branch name in format: claude-step-{project}-{index}
        """
        return f"claude-step-{self.name}-{task_index}"

    @classmethod
    def from_config_path(cls, config_path: str) -> 'Project':
        """Factory: Extract project from config path

        Args:
            config_path: Path like 'claude-step/my-project/configuration.yml'

        Returns:
            Project instance
        """
        project_name = os.path.basename(os.path.dirname(config_path))
        return cls(project_name)

    @classmethod
    def from_branch_name(cls, branch_name: str) -> Optional['Project']:
        """Factory: Parse project from branch name

        Args:
            branch_name: Branch name like 'claude-step-{project}-{index}'

        Returns:
            Project instance or None if branch name doesn't match pattern
        """
        pattern = r"^claude-step-(.+)-(\d+)$"
        match = re.match(pattern, branch_name)
        if match:
            return cls(match.group(1))
        return None

    @classmethod
    def find_all(cls, base_dir: str = "claude-step") -> List['Project']:
        """Factory: Discover all projects in a directory

        Args:
            base_dir: Directory to scan for projects. Defaults to 'claude-step'

        Returns:
            List of Project instances, sorted by name
        """
        projects = []
        if not os.path.exists(base_dir):
            return projects

        for entry in os.listdir(base_dir):
            project_path = os.path.join(base_dir, entry)
            if os.path.isdir(project_path):
                config_yml = os.path.join(project_path, "configuration.yml")
                if os.path.exists(config_yml):
                    projects.append(cls(entry))

        return sorted(projects, key=lambda p: p.name)

    def __eq__(self, other) -> bool:
        """Check equality based on name and base_path"""
        if not isinstance(other, Project):
            return False
        return self.name == other.name and self.base_path == other.base_path

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"Project(name='{self.name}', base_path='{self.base_path}')"

    def __hash__(self) -> int:
        """Hash based on name and base_path for use in sets/dicts"""
        return hash((self.name, self.base_path))
