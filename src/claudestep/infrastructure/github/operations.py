"""GitHub CLI and API operations"""

import base64
import json
import os
import re
import subprocess
import tempfile
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.domain.github_models import GitHubPullRequest, PRComment, WorkflowRun
from claudestep.infrastructure.git.operations import run_command
from claudestep.infrastructure.github.actions import GitHubActionsHelper


def run_gh_command(args: List[str]) -> str:
    """Run a GitHub CLI command and return stdout

    Args:
        args: gh command arguments (without 'gh' prefix)

    Returns:
        Command stdout as string

    Raises:
        GitHubAPIError: If gh command fails
    """
    try:
        result = run_command(["gh"] + args)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitHubAPIError(f"GitHub CLI command failed: {' '.join(args)}\n{e.stderr}")


def gh_api_call(endpoint: str, method: str = "GET") -> Dict[str, Any]:
    """Call GitHub REST API using gh CLI

    Args:
        endpoint: API endpoint path (e.g., "/repos/owner/repo/actions/runs")
        method: HTTP method (GET, POST, etc.)

    Returns:
        Parsed JSON response

    Raises:
        GitHubAPIError: If API call fails
    """
    try:
        output = run_gh_command(["api", endpoint, "--method", method])
        return json.loads(output) if output else {}
    except json.JSONDecodeError as e:
        raise GitHubAPIError(f"Invalid JSON from API: {str(e)}")


def compare_commits(repo: str, base: str, head: str) -> List[str]:
    """Get list of changed files between two commits via GitHub API.

    Uses the GitHub Compare API: GET /repos/{owner}/{repo}/compare/{base}...{head}

    Args:
        repo: GitHub repository (owner/name)
        base: Base commit SHA or branch name
        head: Head commit SHA or branch name

    Returns:
        List of file paths that were added, modified, or removed

    Raises:
        GitHubAPIError: If API call fails

    Example:
        >>> # Compare two commits
        >>> changed_files = compare_commits("owner/repo", "abc123", "def456")
        >>> for file_path in changed_files:
        ...     print(f"Changed: {file_path}")
        >>> # Compare branches
        >>> changed_files = compare_commits("owner/repo", "main", "feature-branch")
    """
    endpoint = f"/repos/{repo}/compare/{base}...{head}"
    response = gh_api_call(endpoint, method="GET")

    files = response.get("files", [])
    return [f["filename"] for f in files]


def detect_project_from_diff(changed_files: List[str]) -> Optional[str]:
    """Extract project name from changed spec files.

    Looks for files matching pattern: claude-step/{project}/spec.md

    Args:
        changed_files: List of file paths from compare_commits

    Returns:
        Project name if exactly one spec.md was changed, None otherwise

    Raises:
        ValueError: If multiple different spec.md files were changed

    Example:
        >>> # Single project changed
        >>> files = ["claude-step/my-project/spec.md", "README.md"]
        >>> detect_project_from_diff(files)
        'my-project'
        >>> # No spec files changed
        >>> files = ["src/main.py", "README.md"]
        >>> detect_project_from_diff(files)
        None
        >>> # Multiple projects changed (raises error)
        >>> files = ["claude-step/project-a/spec.md", "claude-step/project-b/spec.md"]
        >>> detect_project_from_diff(files)  # Raises ValueError
    """
    spec_pattern = re.compile(r"^claude-step/([^/]+)/spec\.md$")
    projects = set()

    for file_path in changed_files:
        match = spec_pattern.match(file_path)
        if match:
            projects.add(match.group(1))

    if len(projects) == 0:
        return None
    elif len(projects) == 1:
        return projects.pop()
    else:
        raise ValueError(
            f"Multiple projects modified in single push: {sorted(projects)}. "
            "Push changes to one project at a time."
        )


def download_artifact_json(repo: str, artifact_id: int) -> Optional[Dict[str, Any]]:
    """Download and parse artifact JSON using GitHub API

    Args:
        repo: GitHub repository (owner/name)
        artifact_id: Artifact ID to download

    Returns:
        Parsed JSON content or None if download fails
    """
    try:
        # Get artifact download URL (returns a redirect)
        download_endpoint = f"/repos/{repo}/actions/artifacts/{artifact_id}/zip"

        # Create temp file for the zip
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
            tmp_zip_path = tmp_file.name

        try:
            # Download the zip file using gh api
            # The endpoint returns a redirect which gh api should follow
            subprocess.run(
                ["gh", "api", download_endpoint, "--method", "GET"],
                stdout=open(tmp_zip_path, 'wb'),
                stderr=subprocess.PIPE,
                check=True
            )

            # Extract and parse the JSON from the zip
            with zipfile.ZipFile(tmp_zip_path, 'r') as zip_ref:
                # Get the first JSON file in the zip
                json_files = [f for f in zip_ref.namelist() if f.endswith('.json')]
                if json_files:
                    with zip_ref.open(json_files[0]) as json_file:
                        return json.load(json_file)
                else:
                    print(f"Warning: No JSON file found in artifact {artifact_id}")
                    return None

        finally:
            # Clean up temp file
            if os.path.exists(tmp_zip_path):
                os.remove(tmp_zip_path)

    except Exception as e:
        print(f"Warning: Failed to download/parse artifact {artifact_id}: {e}")
        return None


def ensure_label_exists(label: str, gh: GitHubActionsHelper) -> None:
    """Ensure a GitHub label exists in the repository, create if it doesn't

    Args:
        label: Label name to ensure exists
        gh: GitHub Actions helper instance for logging
    """
    try:
        # Try to create the label
        # If it already exists, gh will return an error which we'll catch
        run_gh_command([
            "label", "create", label,
            "--description", "ClaudeStep automated refactoring",
            "--color", "0E8A16"  # Green color for refactor labels
        ])
        gh.write_step_summary(f"- Label '{label}': ✅ Created")
        gh.set_notice(f"Created label '{label}'")
    except GitHubAPIError as e:
        # Check if error is because label already exists
        if "already exists" in str(e).lower():
            gh.write_step_summary(f"- Label '{label}': ✅ Already exists")
        else:
            # Re-raise if it's a different error
            raise


def get_file_from_branch(repo: str, branch: str, file_path: str) -> Optional[str]:
    """Fetch file content from a specific branch via GitHub API

    Args:
        repo: GitHub repository in format "owner/repo"
        branch: Branch name to fetch from
        file_path: Path to file within repository

    Returns:
        File content as string, or None if file not found

    Raises:
        GitHubAPIError: If API call fails for reasons other than file not found
    """
    endpoint = f"/repos/{repo}/contents/{file_path}?ref={branch}"

    try:
        response = gh_api_call(endpoint, method="GET")

        # GitHub API returns content as Base64 encoded
        if "content" in response:
            # Remove newlines that GitHub adds to the base64 string
            encoded_content = response["content"].replace("\n", "")
            decoded_content = base64.b64decode(encoded_content).decode("utf-8")
            return decoded_content
        else:
            return None

    except GitHubAPIError as e:
        # If it's a 404 (file not found), return None
        if "404" in str(e) or "Not Found" in str(e):
            return None
        # Re-raise other errors
        raise


def file_exists_in_branch(repo: str, branch: str, file_path: str) -> bool:
    """Check if a file exists in a specific branch

    Args:
        repo: GitHub repository in format "owner/repo"
        branch: Branch name to check
        file_path: Path to file within repository

    Returns:
        True if file exists, False otherwise
    """
    content = get_file_from_branch(repo, branch, file_path)
    return content is not None


def list_pull_requests(
    repo: str,
    state: str = "all",
    label: Optional[str] = None,
    assignee: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100
) -> List[GitHubPullRequest]:
    """Fetch PRs with filtering, returns domain models

    This function provides GitHub PR querying capabilities for capacity
    checking and other use cases. It encapsulates all GitHub CLI command construction
    and JSON parsing, returning type-safe domain models.

    **Current Usage**:
    - Capacity checking (filter by assignee + state=open)
    - Project detection (filter by label)
    - Statistics collection (filter by label, configurable limit)

    **Design Principles**:
    - Parses GitHub JSON once into GitHubPullRequest domain models
    - Infrastructure layer owns GitHub CLI command construction
    - Type-safe return values for service layer consumption
    - Generic and reusable for any future GitHub PR query needs

    **Pagination Note**:
    The limit parameter controls the maximum number of results returned. For
    repositories with many PRs (>100), callers should increase the limit as needed.
    The GitHub CLI ('gh pr list') handles pagination internally up to the specified
    limit. Current usage in StatisticsService uses limit=500 which is sufficient
    for most ClaudeStep repositories.

    Args:
        repo: GitHub repository (owner/name)
        state: "open", "closed", "merged", or "all"
        label: Optional label filter (e.g., "claudestep" for ClaudeStep PRs)
        assignee: Optional assignee filter (e.g., "username" for specific assignee)
        since: Optional date filter (filters by created_at >= since)
        limit: Max results (default 100, increase for repos with many PRs)

    Returns:
        List of GitHubPullRequest domain models with type-safe properties

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Check capacity
        >>> prs = list_pull_requests("owner/repo", state="open", label="claudestep", assignee="alice")
        >>> print(f"Assignee has {len(prs)} open PRs")
        >>>
        >>> # Statistics for large repos
        >>> all_prs = list_pull_requests("owner/repo", state="all", label="claudestep", limit=500)

    See Also:
        - list_merged_pull_requests(): Convenience wrapper for merged PRs
        - list_open_pull_requests(): Convenience wrapper for open PRs
        - GitHubPullRequest: Domain model with type-safe properties
    """
    # Build gh pr list command
    args = [
        "pr", "list",
        "--repo", repo,
        "--state", state,
        "--limit", str(limit),
        "--json", "number,title,state,createdAt,mergedAt,assignees,labels,headRefName,url"
    ]

    # Add label filter if specified
    if label:
        args.extend(["--label", label])

    # Add assignee filter if specified
    if assignee:
        args.extend(["--assignee", assignee])

    # Execute command and parse JSON
    try:
        output = run_gh_command(args)
        pr_data = json.loads(output) if output else []
    except json.JSONDecodeError as e:
        raise GitHubAPIError(f"Invalid JSON from gh pr list: {str(e)}")

    # Parse into domain models
    prs = [GitHubPullRequest.from_dict(pr) for pr in pr_data]

    # Apply date filter if specified (gh pr list doesn't support --since)
    if since:
        prs = [pr for pr in prs if pr.created_at >= since]

    return prs


def list_merged_pull_requests(
    repo: str,
    since: datetime,
    label: Optional[str] = None,
    limit: int = 100
) -> List[GitHubPullRequest]:
    """Convenience function for fetching merged PRs

    Filters by merged state and date range (merged_at >= since).

    **Current Usage**: Not used in normal operations (statistics use metadata instead)

    **Future Usage**: Useful for:
    - Synchronize command: Backfill recently merged PRs into metadata
    - Audit reports: Verify all merged PRs have corresponding metadata entries
    - Historical analysis: Rebuild metadata from GitHub for specific time periods
    - Drift detection: Compare GitHub merge timestamps with metadata timestamps

    Args:
        repo: GitHub repository (owner/name)
        since: Only include PRs merged on or after this date (filters by merged_at)
        label: Optional label filter (e.g., "claudestep")
        limit: Max results (default 100)

    Returns:
        List of merged GitHubPullRequest domain models

    Example:
        >>> # Future synchronize command: Backfill last 30 days
        >>> from datetime import datetime, timedelta, timezone
        >>> cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        >>> recent_merged = list_merged_pull_requests("owner/repo", since=cutoff, label="claudestep")
        >>> print(f"Found {len(recent_merged)} merged PRs to backfill")

    See Also:
        - list_pull_requests(): Base function with full filtering options
        - docs/specs/archive/2025-12-30-adr-001-metadata-as-source-of-truth.md: ADR on metadata-first architecture
        - docs/specs/archive/2025-12-30-refactor-statistics-service-architecture.md: Details on future synchronization
    """
    # Get merged PRs
    prs = list_pull_requests(repo, state="merged", label=label, limit=limit)

    # Filter by merged_at date (not just created_at)
    # Since gh pr list doesn't support date filtering, we do it post-fetch
    filtered = [pr for pr in prs if pr.merged_at and pr.merged_at >= since]

    return filtered


def list_open_pull_requests(
    repo: str,
    label: Optional[str] = None,
    assignee: Optional[str] = None,
    limit: int = 100
) -> List[GitHubPullRequest]:
    """Convenience function for fetching open PRs

    **Current Usage**: Capacity checking (filter by assignee)

    **Usage Examples**:
    - Capacity checking: Check how many open PRs an assignee has
    - Stale PR detection: Find open PRs older than expected review time
    - Workload balancing: Cross-check assignee assignments

    Args:
        repo: GitHub repository (owner/name)
        label: Optional label filter (e.g., "claudestep")
        assignee: Optional assignee filter (e.g., "username")
        limit: Max results (default 100)

    Returns:
        List of open GitHubPullRequest domain models

    Example:
        >>> # Check capacity
        >>> open_prs = list_open_pull_requests("owner/repo", label="claudestep", assignee="alice")
        >>> print(f"Assignee has {len(open_prs)} open PRs")

    See Also:
        - list_pull_requests(): Base function with full filtering options
    """
    return list_pull_requests(repo, state="open", label=label, assignee=assignee, limit=limit)


def list_pull_requests_for_project(
    repo: str,
    project_name: str,
    label: str,
    state: str = "all",
    limit: int = 100
) -> List[GitHubPullRequest]:
    """Convenience function for fetching PRs for a specific project

    Filters PRs by label and project name based on branch naming convention
    (claude-step-{project_name}-{hash}).

    **Current Usage**: Test automation and project status queries

    **Usage Examples**:
    - Test automation: Verify workflow created PRs for a project
    - Project status: Check all PRs for a specific refactoring project
    - Cleanup: Find and close all PRs for a project

    Args:
        repo: GitHub repository (owner/name)
        project_name: Project name to filter by (matches branch pattern)
        label: Label filter (use DEFAULT_PR_LABEL from constants)
        state: "open", "closed", "merged", or "all" (default: "all")
        limit: Max results (default 100)

    Returns:
        List of GitHubPullRequest domain models for the project

    Example:
        >>> from claudestep.domain.constants import DEFAULT_PR_LABEL
        >>> # Verify PRs created for a project
        >>> project_prs = list_pull_requests_for_project(
        ...     "owner/repo", "my-project", DEFAULT_PR_LABEL
        ... )
        >>> print(f"Found {len(project_prs)} PRs for project")

    See Also:
        - list_pull_requests(): Base function with full filtering options
    """
    # Get all PRs with the label
    all_prs = list_pull_requests(repo, state=state, label=label, limit=limit)

    # Filter by branch naming convention: claude-step-{project_name}-{hash}
    branch_prefix = f"claude-step-{project_name}-"
    project_prs = [pr for pr in all_prs if pr.head_ref_name.startswith(branch_prefix)]

    return project_prs


# ============================================================================
# Workflow operations
# ============================================================================


def list_workflow_runs(
    repo: str,
    workflow_name: str,
    branch: str,
    limit: int = 10
) -> List[WorkflowRun]:
    """List workflow runs for a specific workflow and branch

    Fetches workflow runs from GitHub Actions API and returns them as
    domain models. Used for monitoring workflow execution and testing.

    Args:
        repo: GitHub repository (owner/name)
        workflow_name: Name of workflow file (e.g., "ci.yml")
        branch: Branch name to filter runs
        limit: Maximum number of runs to return (default: 10)

    Returns:
        List of WorkflowRun domain models, sorted by creation time (newest first)

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Get recent workflow runs for a branch
        >>> runs = list_workflow_runs("owner/repo", "ci.yml", "main", limit=5)
        >>> for run in runs:
        ...     print(f"Run {run.database_id}: {run.status} - {run.conclusion}")
        >>> # Check latest run status
        >>> latest = runs[0] if runs else None
        >>> if latest and latest.is_success():
        ...     print("Latest run succeeded!")
    """
    # Build gh run list command
    args = [
        "run", "list",
        "--repo", repo,
        "--workflow", workflow_name,
        "--branch", branch,
        "--limit", str(limit),
        "--json", "databaseId,status,conclusion,createdAt,headBranch,url"
    ]

    # Execute command and parse JSON
    try:
        output = run_gh_command(args)
        run_data = json.loads(output) if output else []
    except json.JSONDecodeError as e:
        raise GitHubAPIError(f"Invalid JSON from gh run list: {str(e)}")

    # Parse into domain models
    runs = [WorkflowRun.from_dict(run) for run in run_data]

    return runs


def get_workflow_run_logs(
    repo: str,
    run_id: int
) -> str:
    """Get the full logs for a workflow run.

    Fetches the complete logs for all jobs in a workflow run.
    Useful for debugging workflow failures or validating workflow output.

    Args:
        repo: GitHub repository (owner/name)
        run_id: Workflow run database ID

    Returns:
        Complete workflow run logs as a string

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Get logs for a specific run
        >>> logs = get_workflow_run_logs("owner/repo", 12345)
        >>> if "error" in logs.lower():
        ...     print("Found error in logs!")
    """
    # Build gh run view command
    args = [
        "run", "view", str(run_id),
        "--repo", repo,
        "--log"
    ]

    # Execute command
    try:
        return run_gh_command(args)
    except Exception as e:
        raise GitHubAPIError(f"Failed to get workflow run logs: {str(e)}")


def trigger_workflow(
    repo: str,
    workflow_name: str,
    inputs: Dict[str, str],
    ref: str
) -> None:
    """Trigger a GitHub Actions workflow with inputs

    Dispatches a workflow_dispatch event to trigger a workflow run.
    The workflow must have workflow_dispatch trigger configured.

    Args:
        repo: GitHub repository (owner/name)
        workflow_name: Name of workflow file (e.g., "ci.yml")
        inputs: Workflow inputs as key-value pairs
        ref: Git reference (branch, tag, or SHA) to run workflow on

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Trigger a workflow with inputs
        >>> trigger_workflow(
        ...     repo="owner/repo",
        ...     workflow_name="deploy.yml",
        ...     inputs={"environment": "staging", "version": "v1.2.3"},
        ...     ref="main"
        ... )
        >>> # Trigger with no inputs
        >>> trigger_workflow(
        ...     repo="owner/repo",
        ...     workflow_name="test.yml",
        ...     inputs={},
        ...     ref="feature-branch"
        ... )
    """
    # Build gh workflow run command
    args = [
        "workflow", "run", workflow_name,
        "--repo", repo,
        "--ref", ref
    ]

    # Add inputs as --field arguments
    for key, value in inputs.items():
        args.extend(["--field", f"{key}={value}"])

    # Execute command (no output expected)
    run_gh_command(args)


# ============================================================================
# Pull request operations (extensions)
# ============================================================================


def get_pull_request_by_branch(
    repo: str,
    branch: str
) -> Optional[GitHubPullRequest]:
    """Get pull request for a specific branch

    Searches for an open PR with the given head branch name.

    Args:
        repo: GitHub repository (owner/name)
        branch: Branch name to search for

    Returns:
        GitHubPullRequest if found, None otherwise

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Find PR for a branch
        >>> pr = get_pull_request_by_branch("owner/repo", "feature-branch")
        >>> if pr:
        ...     print(f"Found PR #{pr.number}: {pr.title}")
        >>> else:
        ...     print("No PR found for branch")
    """
    # Get all open PRs and filter by branch
    open_prs = list_open_pull_requests(repo, limit=100)

    # Find PR with matching branch
    for pr in open_prs:
        if pr.head_ref_name == branch:
            return pr

    return None


def get_pull_request_comments(
    repo: str,
    pr_number: int
) -> List[PRComment]:
    """Get comments on a pull request

    Fetches all comments on a PR and returns them as domain models.

    Args:
        repo: GitHub repository (owner/name)
        pr_number: Pull request number

    Returns:
        List of PRComment domain models

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Get all comments on a PR
        >>> comments = get_pull_request_comments("owner/repo", 123)
        >>> for comment in comments:
        ...     print(f"{comment.author}: {comment.body}")
    """
    # Build gh pr view command to get comments
    args = [
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "comments"
    ]

    # Execute command and parse JSON
    try:
        output = run_gh_command(args)
        data = json.loads(output) if output else {}
    except json.JSONDecodeError as e:
        raise GitHubAPIError(f"Invalid JSON from gh pr view: {str(e)}")

    # Extract comments array
    comments_data = data.get("comments", [])

    # Parse into domain models
    comments = [PRComment.from_dict(comment) for comment in comments_data]

    return comments


def close_pull_request(repo: str, pr_number: int) -> None:
    """Close a pull request without merging

    Args:
        repo: GitHub repository (owner/name)
        pr_number: Pull request number to close

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Close a PR
        >>> close_pull_request("owner/repo", 123)
    """
    # Build gh pr close command
    args = [
        "pr", "close", str(pr_number),
        "--repo", repo
    ]

    # Execute command
    run_gh_command(args)


def merge_pull_request(repo: str, pr_number: int, merge_method: str = "merge") -> None:
    """Merge a pull request

    Args:
        repo: GitHub repository (owner/name)
        pr_number: Pull request number to merge
        merge_method: Merge method to use (merge, squash, or rebase). Default: merge

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Merge a PR
        >>> merge_pull_request("owner/repo", 123)
        >>> # Squash merge a PR
        >>> merge_pull_request("owner/repo", 123, merge_method="squash")
    """
    # Build gh pr merge command
    args = [
        "pr", "merge", str(pr_number),
        "--repo", repo,
        f"--{merge_method}"
    ]

    # Execute command
    run_gh_command(args)


# ============================================================================
# Branch operations
# ============================================================================


def delete_branch(repo: str, branch: str) -> None:
    """Delete a remote branch

    Args:
        repo: GitHub repository (owner/name)
        branch: Branch name to delete

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # Delete a remote branch
        >>> delete_branch("owner/repo", "feature-branch")
    """
    # Use GitHub API to delete the branch
    endpoint = f"/repos/{repo}/git/refs/heads/{branch}"

    try:
        # Use gh api with DELETE method
        run_gh_command(["api", endpoint, "--method", "DELETE"])
    except GitHubAPIError as e:
        # Ignore 404 errors (branch already deleted)
        if "404" not in str(e):
            raise


def list_branches(repo: str, prefix: Optional[str] = None) -> List[str]:
    """List remote branches, optionally filtered by prefix

    Args:
        repo: GitHub repository (owner/name)
        prefix: Optional prefix to filter branches (e.g., "claude-step-")

    Returns:
        List of branch names

    Raises:
        GitHubAPIError: If gh command fails

    Example:
        >>> # List all branches
        >>> branches = list_branches("owner/repo")
        >>> print(f"Found {len(branches)} branches")
        >>> # List branches with prefix
        >>> test_branches = list_branches("owner/repo", prefix="test-")
        >>> for branch in test_branches:
        ...     print(branch)
    """
    # Use GitHub API to list branches
    endpoint = f"/repos/{repo}/branches"
    params = "?per_page=100"  # Get up to 100 branches per page

    try:
        # Get branches from API
        data = gh_api_call(endpoint + params, method="GET")

        # Extract branch names
        if isinstance(data, list):
            branches = [branch["name"] for branch in data]
        else:
            # Handle pagination if needed (unlikely for most repos)
            branches = []

        # Filter by prefix if specified
        if prefix:
            branches = [b for b in branches if b.startswith(prefix)]

        return branches

    except GitHubAPIError:
        # Return empty list on error
        return []
