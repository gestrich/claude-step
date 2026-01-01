"""Manager for ephemeral E2E test branch lifecycle."""

import subprocess
from pathlib import Path
from typing import Optional

# Import using try/except to support both package import and direct import
try:
    from ..constants import E2E_TEST_BRANCH
except ImportError:
    # When run directly (not as a package), use absolute import
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from constants import E2E_TEST_BRANCH


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
        self.test_branch = E2E_TEST_BRANCH

    def delete_remote_branch(self) -> None:
        """Delete test branch from remote if it exists."""
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
        """Create fresh test branch from current main."""
        # Fetch main branch (needed for GitHub Actions where only trigger branch is cloned)
        subprocess.run(
            ["git", "fetch", "origin", "main:main"],
            cwd=self.repo_root, check=True
        )
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
        # Only commit if there are staged changes (directory may already exist)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=self.repo_root, capture_output=True
        )
        if result.returncode != 0:  # There are staged changes
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
        """Complete setup: delete old branch, create fresh one with test workspace."""
        print("Setting up ephemeral E2E test branch...")
        self.delete_remote_branch()
        self.create_fresh_branch()
        self.create_test_workspace()
        self.push_test_branch()
        print(f"✓ Test branch '{self.test_branch}' ready for testing")

    def cleanup_test_branch(self) -> None:
        """Delete the test branch after tests complete."""
        # Fetch main branch (needed for GitHub Actions where only trigger branch is cloned)
        subprocess.run(
            ["git", "fetch", "origin", "main:main"],
            cwd=self.repo_root, capture_output=True
        )
        subprocess.run(["git", "checkout", "main"], cwd=self.repo_root, check=True)
        self.delete_remote_branch()
        subprocess.run(
            ["git", "branch", "-D", self.test_branch],
            cwd=self.repo_root, capture_output=True
        )
        print(f"✓ Cleaned up test branch '{self.test_branch}'")
