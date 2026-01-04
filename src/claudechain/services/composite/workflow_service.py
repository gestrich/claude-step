"""Composite service for GitHub workflow triggering.

Provides workflow dispatch capabilities for triggering ClaudeChain workflows
programmatically. This service wraps the GitHub CLI workflow run command and
provides error handling for batch workflow triggering.
"""

from typing import List, Tuple

from claudechain.domain.exceptions import GitHubAPIError
from claudechain.infrastructure.github.operations import run_gh_command


class WorkflowService:
    """Composite service for triggering GitHub workflows.

    This service provides workflow dispatch capabilities for the ClaudeChain
    auto-start workflow and other use cases that need to trigger workflows
    programmatically.

    Example:
        >>> service = WorkflowService()
        >>> service.trigger_claudechain_workflow("test-project", "main", "main")
        >>> # Or batch trigger
        >>> results = service.batch_trigger_claudechain_workflows(
        ...     ["project1", "project2"],
        ...     "main",
        ...     "main"
        ... )
    """

    def trigger_claudechain_workflow(
        self,
        project_name: str,
        base_branch: str,
        checkout_ref: str
    ) -> None:
        """Trigger the ClaudeChain workflow for a single project.

        Args:
            project_name: Name of the project to process
            base_branch: Base branch to fetch specs from
            checkout_ref: Git ref to checkout

        Raises:
            GitHubAPIError: If workflow trigger fails

        Example:
            >>> service = WorkflowService()
            >>> service.trigger_claudechain_workflow(
            ...     "my-refactor",
            ...     "main",
            ...     "main"
            ... )
        """
        try:
            run_gh_command([
                "workflow", "run", "claudechain.yml",
                "-f", f"project_name={project_name}",
                "-f", f"base_branch={base_branch}",
                "-f", f"checkout_ref={checkout_ref}"
            ])
        except GitHubAPIError as e:
            raise GitHubAPIError(
                f"Failed to trigger workflow for project '{project_name}': {e}"
            )

    def batch_trigger_claudechain_workflows(
        self,
        projects: List[str],
        base_branch: str,
        checkout_ref: str
    ) -> Tuple[List[str], List[str]]:
        """Trigger ClaudeChain workflow for multiple projects.

        Attempts to trigger workflows for all projects, collecting both
        successes and failures. Does not raise on individual failures,
        allowing batch processing to continue.

        Args:
            projects: List of project names to trigger
            base_branch: Base branch to fetch specs from
            checkout_ref: Git ref to checkout

        Returns:
            Tuple of (successful_projects, failed_projects)

        Example:
            >>> service = WorkflowService()
            >>> success, failed = service.batch_trigger_claudechain_workflows(
            ...     ["project1", "project2", "project3"],
            ...     "main",
            ...     "main"
            ... )
            >>> print(f"Triggered: {len(success)}, Failed: {len(failed)}")
        """
        successful = []
        failed = []

        for project in projects:
            try:
                self.trigger_claudechain_workflow(project, base_branch, checkout_ref)
                successful.append(project)
                print(f"  ✅ Successfully triggered workflow for project: {project}")
            except GitHubAPIError as e:
                failed.append(project)
                print(f"  ⚠️  Failed to trigger workflow for project '{project}': {e}")

        return successful, failed
