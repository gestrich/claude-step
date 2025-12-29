"""GitHub branch-based metadata storage implementation

This module implements the MetadataStore interface using GitHub's Contents API
to store project metadata in a dedicated branch (claudestep-metadata).

Design:
- One JSON file per project: projects/{project-name}.json
- Uses GitHub Contents API for read/write operations
- Implements optimistic locking via SHA-based conditional updates
- Automatic retry logic for transient failures
- No checkout required - all operations via API
"""

import base64
import json
import logging
import time
from datetime import datetime
from typing import List, Optional

from claudestep.domain.exceptions import GitHubAPIError
from claudestep.domain.models import HybridProjectMetadata
from claudestep.infrastructure.github.operations import gh_api_call, run_gh_command
from claudestep.infrastructure.metadata.operations import MetadataStore

logger = logging.getLogger(__name__)


class GitHubMetadataStore(MetadataStore):
    """GitHub branch-based metadata storage

    Stores project metadata as JSON files in the claudestep-metadata branch.
    Uses GitHub Contents API for all operations without requiring checkout.

    File structure:
        claudestep-metadata/
        ├── projects/
        │   ├── project1.json
        │   ├── project2.json
        │   └── project3.json
        └── README.md

    Key features:
    - Optimistic locking via SHA-based updates
    - Automatic retry for transient failures
    - Branch created on first write if not exists
    - All operations via GitHub API (no git checkout)
    """

    def __init__(self, repo: str, branch: str = "claudestep-metadata", max_retries: int = 3):
        """Initialize GitHub metadata store

        Args:
            repo: GitHub repository in owner/repo format
            branch: Branch name for metadata storage
            max_retries: Maximum retry attempts for API failures
        """
        self.repo = repo
        self.branch = branch
        self.max_retries = max_retries
        self.base_path = "projects"

    def _get_file_path(self, project_name: str) -> str:
        """Get file path for a project

        Args:
            project_name: Name of the project

        Returns:
            File path in the format: projects/{project-name}.json
        """
        return f"{self.base_path}/{project_name}.json"

    def _ensure_branch_exists(self) -> None:
        """Ensure the metadata branch exists, create if needed

        This method:
        1. Checks if the branch exists
        2. If not, creates it from the default branch
        3. Adds a README.md to explain the branch purpose

        Raises:
            GitHubAPIError: If branch operations fail
        """
        try:
            # Check if branch exists by trying to get its ref
            try:
                gh_api_call(f"/repos/{self.repo}/git/ref/heads/{self.branch}", method="GET")
                logger.debug(f"Branch {self.branch} already exists")
                return
            except GitHubAPIError as e:
                # Branch doesn't exist if we get 404
                if "404" not in str(e):
                    raise

            logger.info(f"Creating branch {self.branch}")

            # Get the default branch SHA
            repo_info = gh_api_call(f"/repos/{self.repo}", method="GET")
            default_branch = repo_info.get("default_branch", "main")
            default_ref = gh_api_call(f"/repos/{self.repo}/git/ref/heads/{default_branch}", method="GET")
            base_sha = default_ref["object"]["sha"]

            # Create new branch from default branch
            run_gh_command([
                "api",
                f"/repos/{self.repo}/git/refs",
                "--method", "POST",
                "-f", f"ref=refs/heads/{self.branch}",
                "-f", f"sha={base_sha}"
            ])

            # Create README.md to explain the branch
            readme_content = """# ClaudeStep Metadata Branch

This branch stores metadata for ClaudeStep automated refactoring projects.

## Purpose

ClaudeStep uses this branch to track:
- Project progress and task status
- Pull request history and reviewer assignments
- AI operation costs and statistics

## Structure

```
claudestep-metadata/
├── projects/
│   ├── project1.json
│   ├── project2.json
│   └── ...
└── README.md
```

Each project JSON contains:
- Task definitions and status
- Pull request execution details
- AI operation metadata (costs, tokens, duration)

## Inspecting Metadata

You can view metadata using GitHub CLI:

```bash
# List all projects
gh api repos/{repo}/contents/projects --jq '.[].name'

# View specific project
gh api repos/{repo}/contents/projects/my-project.json --jq '.content' | base64 -d | jq .
```

Or by checking out this branch:

```bash
git fetch origin {branch}
git checkout {branch}
cat projects/my-project.json | jq .
```

## Privacy & Security

This metadata contains:
- Task descriptions from your spec.md files
- PR numbers and reviewer usernames
- AI cost and token usage statistics

It does NOT contain:
- API keys or secrets
- Code changes or diffs
- Sensitive application data

---
*This branch is automatically managed by ClaudeStep. Manual edits may be overwritten.*
""".replace("{repo}", self.repo).replace("{branch}", self.branch)

            # Write README to the branch
            readme_b64 = base64.b64encode(readme_content.encode()).decode()
            run_gh_command([
                "api",
                f"/repos/{self.repo}/contents/README.md",
                "--method", "PUT",
                "-f", f"message=Initialize {self.branch} branch with README",
                "-f", f"content={readme_b64}",
                "-f", f"branch={self.branch}"
            ])

            logger.info(f"Successfully created branch {self.branch}")

        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Failed to ensure branch exists: {str(e)}")

    def _read_file(self, file_path: str) -> tuple[Optional[dict], Optional[str]]:
        """Read file from GitHub using Contents API

        Args:
            file_path: Path to file in the repository

        Returns:
            Tuple of (content_dict, sha) where:
            - content_dict: Parsed JSON content or None if file doesn't exist
            - sha: Current file SHA for optimistic locking, or None if file doesn't exist

        Raises:
            GitHubAPIError: If API call fails (except 404)
        """
        try:
            response = gh_api_call(
                f"/repos/{self.repo}/contents/{file_path}?ref={self.branch}",
                method="GET"
            )

            # Decode base64 content
            content_b64 = response.get("content", "")
            content_str = base64.b64decode(content_b64).decode("utf-8")
            content_dict = json.loads(content_str)

            sha = response.get("sha")

            logger.debug(f"Read file {file_path} (SHA: {sha})")
            return content_dict, sha

        except GitHubAPIError as e:
            # 404 means file doesn't exist (not an error)
            if "404" in str(e):
                logger.debug(f"File {file_path} does not exist")
                return None, None
            raise
        except (json.JSONDecodeError, KeyError) as e:
            raise GitHubAPIError(f"Failed to parse file {file_path}: {str(e)}")

    def _write_file(self, file_path: str, content: dict, sha: Optional[str] = None, commit_message: str = None) -> str:
        """Write file to GitHub using Contents API with retry logic

        Args:
            file_path: Path to file in the repository
            content: Dictionary to serialize as JSON
            sha: Current file SHA (required for updates, None for creates)
            commit_message: Git commit message

        Returns:
            New SHA of the written file

        Raises:
            GitHubAPIError: If write fails after all retries
        """
        if commit_message is None:
            action = "Update" if sha else "Create"
            commit_message = f"{action} metadata for {file_path}"

        # Serialize and encode content
        content_str = json.dumps(content, indent=2)
        content_b64 = base64.b64encode(content_str.encode()).decode()

        # Retry loop for transient failures
        for attempt in range(self.max_retries):
            try:
                # Build API call arguments
                api_args = [
                    "api",
                    f"/repos/{self.repo}/contents/{file_path}",
                    "--method", "PUT",
                    "-f", f"message={commit_message}",
                    "-f", f"content={content_b64}",
                    "-f", f"branch={self.branch}"
                ]

                # Add SHA for updates (optimistic locking)
                if sha:
                    api_args.extend(["-f", f"sha={sha}"])

                # Execute API call
                result = run_gh_command(api_args)
                response = json.loads(result)

                new_sha = response.get("content", {}).get("sha")
                logger.info(f"Wrote file {file_path} (attempt {attempt + 1}/{self.max_retries}, SHA: {new_sha})")

                return new_sha

            except GitHubAPIError as e:
                # Check for conflict (SHA mismatch)
                if "409" in str(e) or "does not match" in str(e).lower():
                    if attempt < self.max_retries - 1:
                        logger.warning(f"SHA conflict on {file_path}, retrying (attempt {attempt + 1}/{self.max_retries})")
                        time.sleep(1)  # Brief delay before retry

                        # Re-read file to get new SHA
                        _, sha = self._read_file(file_path)
                        continue
                    else:
                        raise GitHubAPIError(f"SHA conflict on {file_path} after {self.max_retries} retries")

                # For other errors, retry with exponential backoff
                if attempt < self.max_retries - 1:
                    backoff = 2 ** attempt
                    logger.warning(f"API error on {file_path}, retrying in {backoff}s (attempt {attempt + 1}/{self.max_retries}): {str(e)}")
                    time.sleep(backoff)
                    continue
                else:
                    raise
            except Exception as e:
                raise GitHubAPIError(f"Failed to write file {file_path}: {str(e)}")

        raise GitHubAPIError(f"Failed to write {file_path} after {self.max_retries} retries")

    def _list_project_files(self) -> List[str]:
        """List all project JSON files in the metadata branch

        Uses Git Tree API to recursively list files in the projects/ directory.

        Returns:
            List of project names (without .json extension)

        Raises:
            GitHubAPIError: If API call fails
        """
        try:
            # Get branch reference to find tree SHA
            ref_response = gh_api_call(f"/repos/{self.repo}/git/ref/heads/{self.branch}", method="GET")
            commit_sha = ref_response["object"]["sha"]

            # Get commit to find tree SHA
            commit_response = gh_api_call(f"/repos/{self.repo}/git/commits/{commit_sha}", method="GET")
            tree_sha = commit_response["tree"]["sha"]

            # Get tree recursively
            tree_response = gh_api_call(f"/repos/{self.repo}/git/trees/{tree_sha}?recursive=1", method="GET")

            # Filter for project JSON files
            project_names = []
            for item in tree_response.get("tree", []):
                path = item.get("path", "")
                if path.startswith(f"{self.base_path}/") and path.endswith(".json"):
                    # Extract project name (remove "projects/" prefix and ".json" suffix)
                    project_name = path[len(f"{self.base_path}/"):-5]
                    project_names.append(project_name)

            logger.debug(f"Found {len(project_names)} projects in {self.branch}")
            return project_names

        except GitHubAPIError as e:
            # If branch doesn't exist, return empty list
            if "404" in str(e):
                logger.debug(f"Branch {self.branch} does not exist yet")
                return []
            raise

    def save_project(self, project: HybridProjectMetadata) -> None:
        """Save or update project metadata

        Args:
            project: HybridProjectMetadata instance to save

        Raises:
            GitHubAPIError: If save operation fails
            ValueError: If project data is invalid
        """
        if not project.project:
            raise ValueError("Project name cannot be empty")

        # Ensure branch exists
        self._ensure_branch_exists()

        # Update last_updated timestamp
        project.last_updated = datetime.utcnow()

        # Get current file SHA (for optimistic locking)
        file_path = self._get_file_path(project.project)
        _, current_sha = self._read_file(file_path)

        # Serialize project to dict
        content = project.to_dict()

        # Write file with retry logic
        commit_message = f"Update metadata for project '{project.project}'"
        self._write_file(file_path, content, sha=current_sha, commit_message=commit_message)

        logger.info(f"Saved project metadata: {project.project}")

    def get_project(self, project_name: str) -> Optional[HybridProjectMetadata]:
        """Get project metadata by name

        Args:
            project_name: Name of the project

        Returns:
            HybridProjectMetadata instance or None if not found

        Raises:
            GitHubAPIError: If API call fails
        """
        file_path = self._get_file_path(project_name)
        content, _ = self._read_file(file_path)

        if content is None:
            logger.debug(f"Project not found: {project_name}")
            return None

        try:
            project = HybridProjectMetadata.from_dict(content)
            logger.debug(f"Loaded project: {project_name}")
            return project
        except Exception as e:
            raise GitHubAPIError(f"Failed to deserialize project {project_name}: {str(e)}")

    def get_all_projects(self) -> List[HybridProjectMetadata]:
        """Get metadata for all projects

        Returns:
            List of HybridProjectMetadata instances (may be empty)

        Raises:
            GitHubAPIError: If API calls fail
        """
        project_names = self._list_project_files()

        projects = []
        for project_name in project_names:
            project = self.get_project(project_name)
            if project:
                projects.append(project)

        logger.info(f"Loaded {len(projects)} projects")
        return projects

    def list_project_names(self) -> List[str]:
        """List names of all projects

        Returns:
            List of project names (may be empty)

        Raises:
            GitHubAPIError: If API call fails
        """
        return self._list_project_files()

    def get_projects_modified_since(self, date: datetime) -> List[HybridProjectMetadata]:
        """Get projects modified after a specific date

        This implementation reads all projects and filters by last_updated timestamp.
        For typical usage (5-20 projects), this is fast enough (<2 seconds).

        Args:
            date: Datetime threshold (projects modified after this date)

        Returns:
            List of HybridProjectMetadata instances (may be empty)

        Raises:
            GitHubAPIError: If API calls fail
        """
        all_projects = self.get_all_projects()

        # Filter by last_updated timestamp
        filtered = [
            project for project in all_projects
            if project.last_updated >= date
        ]

        logger.info(f"Found {len(filtered)} projects modified since {date.isoformat()}")
        return filtered

    def project_exists(self, project_name: str) -> bool:
        """Check if a project exists

        Args:
            project_name: Name of the project

        Returns:
            True if project exists, False otherwise

        Raises:
            GitHubAPIError: If API call fails
        """
        file_path = self._get_file_path(project_name)
        content, _ = self._read_file(file_path)
        return content is not None

    def delete_project(self, project_name: str) -> None:
        """Delete project metadata

        Args:
            project_name: Name of the project to delete

        Raises:
            GitHubAPIError: If delete operation fails
            ValueError: If project doesn't exist
        """
        file_path = self._get_file_path(project_name)

        # Get current SHA (required for deletion)
        _, sha = self._read_file(file_path)

        if sha is None:
            raise ValueError(f"Project '{project_name}' does not exist")

        # Delete file via API
        try:
            run_gh_command([
                "api",
                f"/repos/{self.repo}/contents/{file_path}",
                "--method", "DELETE",
                "-f", f"message=Delete metadata for project '{project_name}'",
                "-f", f"sha={sha}",
                "-f", f"branch={self.branch}"
            ])
            logger.info(f"Deleted project metadata: {project_name}")
        except Exception as e:
            raise GitHubAPIError(f"Failed to delete project {project_name}: {str(e)}")
