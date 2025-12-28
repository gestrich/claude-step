"""Manager for ephemeral E2E test branch lifecycle."""

import subprocess
from pathlib import Path
from typing import Optional


class TestBranchManager:
    """Manages creation and cleanup of ephemeral test branch."""

    def __init__(self, repo_root: Optional[Path] = None):
        if repo_root is None:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True
            )
            repo_root = Path(result.stdout.strip())
        self.repo_root = repo_root
        self.test_branch = "e2e-test"

    def delete_remote_branch(self) -> None:
        """Delete e2e-test branch from remote if it exists."""
        # Check if branch exists on remote
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", self.test_branch],
            capture_output=True, text=True, cwd=self.repo_root
        )

        if result.stdout.strip():
            # Branch exists, delete it
            subprocess.run(
                ["git", "push", "origin", "--delete", self.test_branch],
                cwd=self.repo_root, check=True
            )

    def create_fresh_branch(self) -> None:
        """Create fresh e2e-test branch from current main."""
        # Ensure we're on main and up to date
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "pull", "origin", "main"], cwd=self.repo_root, check=True)

        # Delete local branch if exists
        subprocess.run(
            ["git", "branch", "-D", self.test_branch],
            cwd=self.repo_root, capture_output=True
        )

        # Create new branch
        subprocess.run(
            ["git", "checkout", "-b", self.test_branch],
            cwd=self.repo_root, check=True
        )

    def create_test_workflows(self) -> None:
        """Write test-specific workflows to the test branch."""
        workflows_dir = self.repo_root / ".github" / "workflows"

        # Create claudestep-test.yml
        claudestep_test = workflows_dir / "claudestep-test.yml"
        claudestep_test.write_text(self._get_claudestep_test_workflow())

        # Commit the workflows
        subprocess.run(
            ["git", "add", ".github/workflows/"],
            cwd=self.repo_root, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add test-specific workflows for E2E testing"],
            cwd=self.repo_root, check=True
        )

    def create_test_workspace(self) -> None:
        """Create claude-step/ directory for test projects."""
        workspace = self.repo_root / "claude-step"
        workspace.mkdir(exist_ok=True)

        readme = workspace / "README.md"
        readme.write_text("""# E2E Test Workspace

This directory is used exclusively for E2E testing on ephemeral test branches.
Test projects are created here during test runs and cleaned up afterwards.

**This branch is ephemeral** - it's deleted and recreated for each test run.
""")

        subprocess.run(
            ["git", "add", "claude-step/"],
            cwd=self.repo_root, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Create test workspace directory"],
            cwd=self.repo_root, check=True
        )

    def push_test_branch(self) -> None:
        """Push the test branch to remote."""
        subprocess.run(
            ["git", "push", "-u", "origin", self.test_branch],
            cwd=self.repo_root, check=True
        )

    def setup_test_branch(self) -> None:
        """Complete setup: delete old branch, create fresh one with workflows."""
        print("Setting up ephemeral E2E test branch...")
        self.delete_remote_branch()
        self.create_fresh_branch()
        self.create_test_workflows()
        self.create_test_workspace()
        self.push_test_branch()
        print(f"✓ Test branch '{self.test_branch}' ready for testing")

    def cleanup_test_branch(self) -> None:
        """Delete the test branch after tests complete."""
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True)
        self.delete_remote_branch()
        subprocess.run(
            ["git", "branch", "-D", self.test_branch],
            cwd=self.repo_root, capture_output=True
        )
        print(f"✓ Cleaned up test branch '{self.test_branch}'")

    def _get_claudestep_test_workflow(self) -> str:
        """Return claudestep-test.yml workflow content."""
        return """name: ClaudeStep Test

on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name in claude-step directory'
        required: true
      base_branch:
        description: 'Base branch for pull requests'
        required: false
        default: 'e2e-test'

jobs:
  run-claudestep:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          ref: e2e-test

      - name: Run ClaudeStep action
        uses: ./
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          github_token: ${{ secrets.GITHUB_TOKEN }}
          project_name: ${{ github.event.inputs.project_name }}
          base_branch: ${{ github.event.inputs.base_branch || 'e2e-test' }}
          claude_model: 'claude-3-haiku-20240307'
"""
