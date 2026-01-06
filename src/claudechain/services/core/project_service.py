"""Core service for project detection operations.

Follows Service Layer pattern (Fowler, PoEAA) - encapsulates business logic
for detecting projects from changed files.
"""

import re
from typing import List

from claudechain.domain.project import Project


class ProjectService:
    """Core service for project detection operations.

    Provides static methods for identifying ClaudeChain projects from file changes.
    """

    @staticmethod
    def detect_projects_from_merge(changed_files: List[str]) -> List[Project]:
        """Detect projects from changed spec.md files in a merge.

        This function is used to automatically trigger ClaudeChain when spec files
        are changed, regardless of branch naming conventions or labels. It enables
        the "changed files" triggering model where:
        - Initial spec merge: User creates PR with spec.md, merges it, workflow triggers
        - Subsequent merges: System-created PRs merge, workflow triggers same way

        Args:
            changed_files: List of file paths that changed in the merge

        Returns:
            List of Project objects for projects with changed spec.md files.
            Empty list if no spec files were changed.

        Examples:
            >>> files = ["claude-chain/my-project/spec.md", "README.md"]
            >>> projects = ProjectService.detect_projects_from_merge(files)
            >>> [p.name for p in projects]
            ['my-project']

            >>> files = ["claude-chain/project-a/spec.md", "claude-chain/project-b/spec.md"]
            >>> projects = ProjectService.detect_projects_from_merge(files)
            >>> sorted([p.name for p in projects])
            ['project-a', 'project-b']

            >>> files = ["src/main.py", "README.md"]
            >>> ProjectService.detect_projects_from_merge(files)
            []
        """
        spec_pattern = re.compile(r"^claude-chain/([^/]+)/spec\.md$")
        project_names = set()

        for file_path in changed_files:
            match = spec_pattern.match(file_path)
            if match:
                project_names.add(match.group(1))

        return [Project(name) for name in sorted(project_names)]
