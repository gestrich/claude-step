"""GitHub API helper for E2E tests.

This module provides a helper class for interacting with GitHub API during E2E tests,
including triggering workflows, checking workflow status, and managing PRs.
"""

import time
import logging
from typing import Optional, Dict, Any, List, Callable

from claudestep.domain.constants import DEFAULT_PR_LABEL
from claudestep.domain.exceptions import GitHubAPIError
from claudestep.domain.github_models import WorkflowRun, GitHubPullRequest, PRComment
from claudestep.infrastructure.github.operations import (
    list_pull_requests_for_project as _list_prs_for_project,
    list_pull_requests as _list_pull_requests,
    trigger_workflow as _trigger_workflow,
    list_workflow_runs as _list_workflow_runs,
    get_pull_request_by_branch as _get_pull_request_by_branch,
    get_pull_request_comments as _get_pull_request_comments,
    close_pull_request as _close_pull_request,
    delete_branch as _delete_branch,
    list_branches as _list_branches,
)

# Configure logger for E2E test diagnostics
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


class GitHubHelper:
    """Helper class for GitHub operations in E2E tests."""

    def __init__(self, repo: str = "gestrich/claude-step"):
        """Initialize GitHub helper.

        Args:
            repo: Repository in format "owner/name". Defaults to claude-step repo.
        """
        self.repo = repo

    def wait_for_condition(
        self,
        check_fn: Callable[[], bool],
        timeout: int = 30,
        poll_interval: float = 1.0,
        condition_name: str = "condition"
    ) -> None:
        """Wait for a condition to become true.

        Args:
            check_fn: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds
            condition_name: Description of condition for logging

        Raises:
            TimeoutError: If condition not met within timeout
        """
        logger.debug(f"Waiting for {condition_name} (timeout={timeout}s, interval={poll_interval}s)")
        start_time = time.time()
        poll_count = 0

        while time.time() - start_time < timeout:
            poll_count += 1
            elapsed = time.time() - start_time

            if check_fn():
                logger.debug(f"Condition '{condition_name}' met after {elapsed:.1f}s ({poll_count} polls)")
                return

            logger.debug(f"[Poll {poll_count}, {elapsed:.1f}s] Condition '{condition_name}' not yet met")
            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        logger.error(f"Condition '{condition_name}' not met after {elapsed:.1f}s ({poll_count} polls)")
        raise TimeoutError(f"Condition '{condition_name}' not met within {timeout} seconds")

    def wait_for_workflow_to_start(
        self,
        workflow_name: str,
        timeout: int = 30,
        poll_interval: float = 2.0,
        branch: str = "e2e-test"
    ) -> Dict[str, Any]:
        """Wait for a workflow run to appear after triggering.

        This replaces fixed sleeps after workflow triggers with smart polling
        that waits for the workflow run to actually appear in the API.

        Args:
            workflow_name: Name of the workflow file
            timeout: Maximum time to wait in seconds
            poll_interval: Time between checks in seconds
            branch: Branch to filter runs by

        Returns:
            The workflow run that was found

        Raises:
            TimeoutError: If workflow doesn't appear within timeout
        """
        logger.info(f"Waiting for workflow '{workflow_name}' to start on branch '{branch}'")
        start_time = time.time()
        initial_run_id = None
        poll_count = 0

        # Get current latest run ID to detect new runs
        existing_run = self.get_latest_workflow_run(workflow_name, branch=branch)
        if existing_run:
            initial_run_id = existing_run.get("databaseId")
            logger.debug(f"Current latest run ID: {initial_run_id}")

        while time.time() - start_time < timeout:
            poll_count += 1
            elapsed = time.time() - start_time

            run = self.get_latest_workflow_run(workflow_name, branch=branch)
            if run:
                run_id = run.get("databaseId")
                # If we have a new run (different from initial), workflow has started
                if initial_run_id is None or run_id != initial_run_id:
                    run_url = run.get("url", f"https://github.com/{self.repo}/actions/runs/{run_id}")
                    logger.info(f"Workflow started after {elapsed:.1f}s - Run ID: {run_id}")
                    logger.info(f"Workflow URL: {run_url}")
                    return run

            logger.debug(f"[Poll {poll_count}, {elapsed:.1f}s] Workflow not started yet")
            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        logger.error(f"Workflow '{workflow_name}' did not start within {timeout}s")
        raise TimeoutError(f"Workflow '{workflow_name}' did not start within {timeout} seconds")

    def trigger_workflow(
        self,
        workflow_name: str,
        inputs: Dict[str, str],
        ref: str = "e2e-test"
    ) -> None:
        """Trigger a GitHub workflow manually.

        Args:
            workflow_name: Name of the workflow file (e.g., "claudestep.yml")
            inputs: Dictionary of workflow inputs
            ref: Git ref to run workflow on (branch/tag/SHA)
        """
        logger.info(f"Triggering workflow '{workflow_name}' on ref '{ref}' with inputs: {inputs}")
        start_time = time.time()

        try:
            _trigger_workflow(
                repo=self.repo,
                workflow_name=workflow_name,
                inputs=inputs,
                ref=ref
            )
            elapsed = time.time() - start_time
            logger.info(f"Successfully triggered workflow in {elapsed:.2f}s")
        except GitHubAPIError as e:
            elapsed = time.time() - start_time
            logger.error(f"Failed to trigger workflow after {elapsed:.2f}s: {e}")
            raise RuntimeError(f"Failed to trigger workflow: {e}")

    def get_latest_workflow_run(
        self,
        workflow_name: str,
        branch: str = "e2e-test"
    ) -> Optional[WorkflowRun]:
        """Get the latest workflow run for a given workflow.

        Args:
            workflow_name: Name of the workflow file
            branch: Branch to filter runs by

        Returns:
            WorkflowRun domain model, or None if no runs found
        """
        try:
            runs = _list_workflow_runs(
                repo=self.repo,
                workflow_name=workflow_name,
                branch=branch,
                limit=1
            )

            if runs:
                run = runs[0]
                logger.debug(f"Found workflow run: ID={run.database_id}, status={run.status}, conclusion={run.conclusion}")
                return run
            else:
                logger.debug(f"No workflow runs found for '{workflow_name}' on branch '{branch}'")
                return None

        except GitHubAPIError as e:
            logger.error(f"Failed to get workflow runs: {e}")
            raise RuntimeError(f"Failed to get workflow runs: {e}")

    def wait_for_workflow_completion(
        self,
        workflow_name: str,
        timeout: int = 600,
        poll_interval: int = 10,
        branch: str = "e2e-test"
    ) -> WorkflowRun:
        """Wait for a workflow to complete.

        Args:
            workflow_name: Name of the workflow file
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
            branch: Branch to filter runs by (defaults to "e2e-test")

        Returns:
            WorkflowRun domain model for the completed workflow

        Raises:
            TimeoutError: If workflow doesn't complete within timeout
            RuntimeError: If workflow fails
        """
        logger.info(f"Waiting for workflow '{workflow_name}' to complete (timeout={timeout}s, poll_interval={poll_interval}s)")
        start_time = time.time()
        last_status = None
        poll_count = 0

        while time.time() - start_time < timeout:
            elapsed = time.time() - start_time
            poll_count += 1

            run = self.get_latest_workflow_run(workflow_name, branch=branch)
            if not run:
                logger.warning(f"[Poll {poll_count}, {elapsed:.1f}s] No workflow run found yet, waiting...")
                time.sleep(poll_interval)
                continue

            # Log status changes
            if run.status != last_status:
                logger.info(f"[Poll {poll_count}, {elapsed:.1f}s] Workflow status: {run.status} (conclusion: {run.conclusion})")
                logger.info(f"View workflow run: {run.url}")
                last_status = run.status
            else:
                logger.debug(f"[Poll {poll_count}, {elapsed:.1f}s] Still {run.status}...")

            if run.status == "completed":
                total_time = time.time() - start_time
                if run.conclusion == "success":
                    logger.info(f"Workflow completed successfully in {total_time:.1f}s")
                    logger.info(f"Workflow URL: {run.url}")
                    return run
                else:
                    logger.error(f"Workflow failed with conclusion '{run.conclusion}' after {total_time:.1f}s")
                    logger.error(f"View failed workflow: {run.url}")
                    raise RuntimeError(
                        f"Workflow failed with conclusion: {run.conclusion}. View details at: {run.url}"
                    )

            time.sleep(poll_interval)

        elapsed = time.time() - start_time
        logger.error(f"Workflow timed out after {elapsed:.1f}s (limit: {timeout}s)")
        if run:
            logger.error(f"Last known status: {run.status} - View workflow: {run.url}")
            raise TimeoutError(
                f"Workflow did not complete within {timeout} seconds. "
                f"Last status: {run.status}. View at: {run.url}"
            )
        else:
            raise TimeoutError(f"Workflow did not complete within {timeout} seconds (no run found)")

    def get_pull_request(self, branch: str) -> Optional[GitHubPullRequest]:
        """Get PR for a given branch.

        Args:
            branch: Branch name to find PR for

        Returns:
            GitHubPullRequest domain model, or None if no PR found
        """
        logger.info(f"Looking for PR on branch '{branch}'")

        try:
            pr = _get_pull_request_by_branch(repo=self.repo, branch=branch)

            if pr:
                logger.info(f"Found PR #{pr.number}: {pr.title} ({pr.state})")
                return pr
            else:
                logger.warning(f"No PR found for branch '{branch}'")
                return None

        except GitHubAPIError as e:
            logger.warning(f"Failed to get PR for branch '{branch}': {e}")
            return None

    def get_pull_requests_for_project(self, project_name: str, label: str = DEFAULT_PR_LABEL):
        """Get all PRs for a given project using infrastructure layer.

        Args:
            project_name: Project name to filter PRs by
            label: Label to filter PRs by (default: DEFAULT_PR_LABEL)

        Returns:
            List of GitHubPullRequest domain models
        """
        logger.info(f"Looking for PRs for project '{project_name}' with label '{label}'")

        # Use infrastructure layer function
        prs = _list_prs_for_project(
            repo=self.repo,
            project_name=project_name,
            label=label,
            state="all",
            limit=100
        )

        logger.info(f"Found {len(prs)} PR(s) for project '{project_name}'")
        return prs

    def get_pr_comments(self, pr_number: int) -> List[PRComment]:
        """Get comments on a PR.

        Args:
            pr_number: PR number

        Returns:
            List of PRComment domain models
        """
        logger.info(f"Fetching comments for PR #{pr_number}")

        try:
            comments = _get_pull_request_comments(repo=self.repo, pr_number=pr_number)

            logger.info(f"Found {len(comments)} comment(s) on PR #{pr_number}")

            # Log summary of comments for diagnostics
            for i, comment in enumerate(comments):
                body_preview = comment.body[:100].replace("\n", " ")
                logger.debug(f"  Comment {i+1}: {body_preview}...")

            return comments

        except GitHubAPIError as e:
            logger.warning(f"Failed to get comments for PR #{pr_number}: {e}")
            return []

    def close_pull_request(self, pr_number: int) -> None:
        """Close a pull request.

        Args:
            pr_number: PR number to close
        """
        logger.info(f"Closing PR #{pr_number}")

        try:
            _close_pull_request(repo=self.repo, pr_number=pr_number)
            logger.info(f"Successfully closed PR #{pr_number}")
        except GitHubAPIError as e:
            logger.warning(f"Failed to close PR #{pr_number}: {e}")
            raise RuntimeError(f"Failed to close PR #{pr_number}: {e}")

    def delete_branch(self, branch: str) -> None:
        """Delete a remote branch.

        Args:
            branch: Branch name to delete
        """
        logger.info(f"Deleting branch '{branch}'")

        try:
            _delete_branch(repo=self.repo, branch=branch)
            logger.info(f"Successfully deleted branch '{branch}'")
        except GitHubAPIError as e:
            logger.warning(f"Failed to delete branch '{branch}': {e}")

    def cleanup_test_branches(self, pattern_prefix: str = "claude-step-test-") -> None:
        """Clean up test branches from previous failed runs.

        This is idempotent and can be run before tests to ensure clean state.

        Args:
            pattern_prefix: Prefix of branch names to clean up
        """
        logger.info(f"Cleaning up test branches with prefix '{pattern_prefix}'")

        try:
            # List all branches with the prefix
            branches = _list_branches(repo=self.repo, prefix=pattern_prefix)
            cleanup_count = 0

            for branch_name in branches:
                try:
                    self.delete_branch(branch_name)
                    cleanup_count += 1
                except Exception as e:
                    logger.warning(f"Failed to delete branch '{branch_name}': {e}")

            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} test branch(es)")
            else:
                logger.debug("No test branches to clean up")

        except GitHubAPIError as e:
            logger.warning(f"Failed to list branches: {e}")

    def cleanup_test_prs(self, title_prefix: str = "ClaudeStep") -> None:
        """Clean up open test PRs from previous failed runs.

        This is idempotent and can be run before tests to ensure clean state.

        Args:
            title_prefix: Prefix of PR titles to clean up
        """
        logger.info(f"Cleaning up test PRs with title prefix '{title_prefix}'")

        try:
            # List all open PRs
            prs = _list_pull_requests(repo=self.repo, state="open", limit=100)
            cleanup_count = 0

            for pr in prs:
                # Only clean up PRs that look like test PRs
                if pr.title.startswith(title_prefix) and "test-project-" in pr.title.lower():
                    try:
                        self.close_pull_request(pr.number)
                        cleanup_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to close PR #{pr.number}: {e}")

            if cleanup_count > 0:
                logger.info(f"Cleaned up {cleanup_count} test PR(s)")
            else:
                logger.debug("No test PRs to clean up")

        except GitHubAPIError as e:
            logger.warning(f"Failed to list PRs: {e}")
