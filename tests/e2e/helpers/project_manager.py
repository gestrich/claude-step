"""Test project manager for E2E tests.

This module provides a helper class for creating and managing test projects
during E2E tests, including cleanup of test artifacts.
"""

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Optional


class TestProjectManager:
    """Manager for creating and cleaning up test projects in E2E tests."""

    def __init__(self, repo_root: Optional[Path] = None):
        """Initialize test project manager.

        Args:
            repo_root: Root of the repository. Defaults to current git repo root.
        """
        if repo_root is None:
            # Get git repo root
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True
            )
            repo_root = Path(result.stdout.strip())

        self.repo_root = repo_root
        self.projects_dir = repo_root / "claude-step"

    def create_test_project(
        self,
        project_id: Optional[str] = None,
        spec_content: Optional[str] = None,
        config_content: Optional[str] = None,
        pr_template_content: Optional[str] = None
    ) -> str:
        """Create a test project with spec.md and configuration files.

        Args:
            project_id: Unique project ID. If None, generates a random ID.
            spec_content: Content for spec.md. If None, uses a default spec.
            config_content: Content for configuration.yml. If None, uses default.
            pr_template_content: Content for pr-template.md. If None, uses default.

        Returns:
            Project name (e.g., "test-project-abc123")
        """
        if project_id is None:
            project_id = uuid.uuid4().hex[:8]

        project_name = f"test-project-{project_id}"
        project_path = self.projects_dir / project_name

        # Create project directory
        project_path.mkdir(parents=True, exist_ok=True)

        # Create spec.md
        if spec_content is None:
            spec_content = self._default_spec_content()
        (project_path / "spec.md").write_text(spec_content)

        # Create configuration.yml
        if config_content is None:
            config_content = self._default_config_content()
        (project_path / "configuration.yml").write_text(config_content)

        # Create pr-template.md
        if pr_template_content is None:
            pr_template_content = self._default_pr_template_content()
        (project_path / "pr-template.md").write_text(pr_template_content)

        return project_name

    def delete_test_project(self, project_name: str) -> None:
        """Delete a test project from the filesystem.

        Args:
            project_name: Name of the project to delete (e.g., "test-project-abc123")
        """
        project_path = self.projects_dir / project_name

        # Safety check: only delete test projects
        if not project_name.startswith("test-project-"):
            raise ValueError(
                f"Refusing to delete non-test project: {project_name}"
            )

        if project_path.exists():
            shutil.rmtree(project_path)

    def commit_and_push_project(
        self,
        project_name: str,
        branch: str = "main"
    ) -> None:
        """Commit and push a test project to the repository.

        Args:
            project_name: Name of the project to commit
            branch: Branch to commit to
        """
        project_path = self.projects_dir / project_name

        # Add project to git (force add to override .gitignore)
        subprocess.run(
            ["git", "add", "-f", str(project_path)],
            cwd=self.repo_root,
            check=True
        )

        # Commit
        commit_msg = f"Add test project: {project_name}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=self.repo_root,
            check=True
        )

        # Push
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=self.repo_root,
            check=True
        )

    def remove_and_commit_project(
        self,
        project_name: str,
        branch: str = "main"
    ) -> None:
        """Remove a test project and commit the removal.

        Args:
            project_name: Name of the project to remove
            branch: Branch to commit to
        """
        project_path = self.projects_dir / project_name

        # Safety check
        if not project_name.startswith("test-project-"):
            raise ValueError(
                f"Refusing to remove non-test project: {project_name}"
            )

        if not project_path.exists():
            return  # Already removed

        # Remove from git (using -f to handle gitignored files)
        result = subprocess.run(
            ["git", "rm", "-rf", "-f", str(project_path)],
            cwd=self.repo_root,
            capture_output=True,
            text=True
        )

        # If git rm fails (e.g., file not tracked), just remove it from filesystem
        if result.returncode != 0:
            import shutil
            shutil.rmtree(project_path)

        # Commit
        commit_msg = f"Remove test project: {project_name}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=self.repo_root,
            check=True
        )

        # Push
        subprocess.run(
            ["git", "push", "origin", branch],
            cwd=self.repo_root,
            check=True
        )

    @staticmethod
    def _default_spec_content() -> str:
        """Generate default spec.md content for testing."""
        return """# Test Project Spec

## Tasks

- [ ] Task 1: Add hello world function - Create a simple hello world function in a new file.
- [ ] Task 2: Add tests - Add tests for the hello world function.
"""

    @staticmethod
    def _default_config_content() -> str:
        """Generate default configuration.yml content for testing."""
        return """reviewers:
  - username: octocat
    maxOpenPRs: 2
"""

    @staticmethod
    def _default_pr_template_content() -> str:
        """Generate default pr-template.md content for testing."""
        return """## Changes

{changes}

## Testing

Manual testing performed.
"""
