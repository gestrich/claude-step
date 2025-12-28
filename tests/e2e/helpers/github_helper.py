"""GitHub API helper for E2E tests.

This module provides a helper class for interacting with GitHub API during E2E tests,
including triggering workflows, checking workflow status, and managing PRs.
"""

import subprocess
import time
import json
from typing import Optional, Dict, Any, List


class GitHubHelper:
    """Helper class for GitHub operations in E2E tests."""

    def __init__(self, repo: str = "gestrich/claude-step"):
        """Initialize GitHub helper.

        Args:
            repo: Repository in format "owner/name". Defaults to claude-step repo.
        """
        self.repo = repo

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
        cmd = ["gh", "workflow", "run", workflow_name, "--repo", self.repo, "--ref", ref]
        for key, value in inputs.items():
            cmd.extend(["-f", f"{key}={value}"])

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to trigger workflow: {result.stderr}")

    def get_latest_workflow_run(
        self,
        workflow_name: str,
        branch: str = "e2e-test"
    ) -> Optional[Dict[str, Any]]:
        """Get the latest workflow run for a given workflow.

        Args:
            workflow_name: Name of the workflow file
            branch: Branch to filter runs by

        Returns:
            Dictionary with workflow run info, or None if no runs found
        """
        cmd = [
            "gh", "run", "list",
            "--workflow", workflow_name,
            "--branch", branch,
            "--repo", self.repo,
            "--json", "databaseId,status,conclusion,createdAt",
            "--limit", "1"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Failed to get workflow runs: {result.stderr}")

        runs = json.loads(result.stdout)
        return runs[0] if runs else None

    def wait_for_workflow_completion(
        self,
        workflow_name: str,
        timeout: int = 600,
        poll_interval: int = 10,
        branch: str = "e2e-test"
    ) -> Dict[str, Any]:
        """Wait for a workflow to complete.

        Args:
            workflow_name: Name of the workflow file
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
            branch: Branch to filter runs by (defaults to "e2e-test")

        Returns:
            Final workflow run info

        Raises:
            TimeoutError: If workflow doesn't complete within timeout
            RuntimeError: If workflow fails
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            run = self.get_latest_workflow_run(workflow_name, branch=branch)
            if not run:
                time.sleep(poll_interval)
                continue

            status = run.get("status")
            conclusion = run.get("conclusion")

            if status == "completed":
                if conclusion == "success":
                    return run
                else:
                    raise RuntimeError(
                        f"Workflow failed with conclusion: {conclusion}"
                    )

            time.sleep(poll_interval)

        raise TimeoutError(f"Workflow did not complete within {timeout} seconds")

    def get_pull_request(self, branch: str) -> Optional[Dict[str, Any]]:
        """Get PR for a given branch.

        Args:
            branch: Branch name to find PR for

        Returns:
            Dictionary with PR info, or None if no PR found
        """
        cmd = [
            "gh", "pr", "list",
            "--repo", self.repo,
            "--head", branch,
            "--json", "number,title,body,state",
            "--limit", "1"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return None

        prs = json.loads(result.stdout)
        return prs[0] if prs else None

    def get_pr_comments(self, pr_number: int) -> List[Dict[str, Any]]:
        """Get comments on a PR.

        Args:
            pr_number: PR number

        Returns:
            List of comment dictionaries
        """
        cmd = [
            "gh", "pr", "view", str(pr_number),
            "--repo", self.repo,
            "--json", "comments"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        return data.get("comments", [])

    def close_pull_request(self, pr_number: int) -> None:
        """Close a pull request.

        Args:
            pr_number: PR number to close
        """
        cmd = ["gh", "pr", "close", str(pr_number), "--repo", self.repo]
        subprocess.run(cmd, capture_output=True, text=True, check=True)

    def delete_branch(self, branch: str) -> None:
        """Delete a remote branch.

        Args:
            branch: Branch name to delete
        """
        cmd = ["gh", "api", f"repos/{self.repo}/git/refs/heads/{branch}", "-X", "DELETE"]
        subprocess.run(cmd, capture_output=True, text=True)
