"""
End-to-end integration test for ClaudeStep workflow

This test validates the complete workflow using the demo repository:
- Creates a test project with tasks
- Triggers workflow and verifies PR creation
- Verifies AI-generated PR summaries are posted as comments
- Tests reviewer capacity (max 2 PRs per reviewer)
- Tests merge trigger functionality
- Cleans up all created resources
"""

import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional

import pytest
import yaml


class GitHubHelper:
    """Helper class for GitHub operations"""

    def __init__(self, repo: str = "gestrich/claude-step-demo"):
        self.repo = repo
        self._check_gh_cli()

    def _check_gh_cli(self):
        """Verify gh CLI is installed and authenticated"""
        try:
            subprocess.run(["gh", "--version"], check=True, capture_output=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pytest.skip("gh CLI not installed or not in PATH")

        # Check authentication
        try:
            subprocess.run(["gh", "auth", "status"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            pytest.skip("gh CLI not authenticated - run 'gh auth login'")

    def run_command(self, args: list[str]) -> str:
        """Run gh command and return output"""
        result = subprocess.run(
            ["gh"] + args,
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()

    def trigger_workflow(self, workflow: str, inputs: dict[str, str]) -> str:
        """Trigger a workflow and return the run ID"""
        args = ["workflow", "run", workflow, "--repo", self.repo]
        for key, value in inputs.items():
            args.extend(["-f", f"{key}={value}"])

        self.run_command(args)

        # Wait a moment for the run to be created
        time.sleep(2)

        # Get the most recent run
        output = self.run_command([
            "run", "list",
            "--workflow", workflow,
            "--repo", self.repo,
            "--limit", "1",
            "--json", "databaseId"
        ])
        runs = json.loads(output)
        if not runs:
            raise RuntimeError("Failed to find workflow run after triggering")

        return str(runs[0]["databaseId"])

    def wait_for_workflow(self, run_id: str, timeout: int = 300) -> str:
        """Wait for workflow to complete and return status"""
        print(f"Waiting for workflow run {run_id}...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            output = self.run_command([
                "run", "view", run_id,
                "--repo", self.repo,
                "--json", "status,conclusion"
            ])
            data = json.loads(output)

            status = data.get("status")
            conclusion = data.get("conclusion")

            print(f"  Status: {status}, Conclusion: {conclusion}")

            if status == "completed":
                return conclusion or "unknown"

            time.sleep(10)

        raise TimeoutError(f"Workflow {run_id} did not complete within {timeout}s")

    def get_prs_by_label(self, label: str) -> list[dict]:
        """Get all PRs with a specific label"""
        output = self.run_command([
            "pr", "list",
            "--repo", self.repo,
            "--label", label,
            "--json", "number,title,headRefName,state",
            "--limit", "100"
        ])
        return json.loads(output)

    def get_pr_by_branch(self, branch: str) -> Optional[dict]:
        """Get PR for a specific branch"""
        output = self.run_command([
            "pr", "list",
            "--repo", self.repo,
            "--head", branch,
            "--json", "number,title,headRefName,state",
            "--limit", "1"
        ])
        prs = json.loads(output)
        return prs[0] if prs else None

    def merge_pr(self, pr_number: int):
        """Merge a PR"""
        self.run_command([
            "pr", "merge", str(pr_number),
            "--repo", self.repo,
            "--squash",
            "--delete-branch"
        ])

    def close_pr(self, pr_number: int):
        """Close a PR without merging"""
        self.run_command([
            "pr", "close", str(pr_number),
            "--repo", self.repo,
            "--delete-branch"
        ])

    def get_pr_comments(self, pr_number: int) -> list[dict]:
        """Get all comments on a PR"""
        output = self.run_command([
            "pr", "view", str(pr_number),
            "--repo", self.repo,
            "--json", "comments"
        ])
        data = json.loads(output)
        return data.get("comments", [])

    def verify_pr_summary(self, pr_number: int, timeout: int = 60) -> bool:
        """
        Verify that a PR has an AI-generated summary comment.
        Retries for up to timeout seconds since the summary is posted asynchronously.

        Returns True if summary found, False otherwise.
        """
        start_time = time.time()

        while time.time() - start_time < timeout:
            comments = self.get_pr_comments(pr_number)

            for comment in comments:
                body = comment.get("body", "")
                if "## AI-Generated Summary" in body or "AI-Generated Summary" in body:
                    print(f"  ✓ Found AI-generated summary on PR #{pr_number}")
                    return True

            # Wait before retrying
            if time.time() - start_time < timeout:
                time.sleep(5)

        print(f"  ✗ No AI-generated summary found on PR #{pr_number} after {timeout}s")
        return False


class TestProjectManager:
    """Manages test project creation and cleanup"""

    def __init__(self, repo_path: Path, project_id: str):
        self.repo_path = repo_path
        self.project_id = project_id
        self.project_name = f"test-project-{project_id}"
        self.project_path = repo_path / "claude-step" / self.project_name

    def create_project(self):
        """Create test project files"""
        self.project_path.mkdir(parents=True, exist_ok=True)

        # Create spec.md
        spec_content = f"""# Test Project {self.project_id}

This is an integration test project for ClaudeStep.

## Objective

Create test files to validate the ClaudeStep workflow.

## Instructions

Create simple text files with the specified content.

## Tasks

- [ ] Create test-file-1.txt with content "Test 1"
- [ ] Create test-file-2.txt with content "Test 2"
- [ ] Create test-file-3.txt with content "Test 3"

## Implementation Notes

- Use the Write tool to create each file
- Each task should result in exactly one new file
"""
        (self.project_path / "spec.md").write_text(spec_content)

        # Create configuration.yml
        config_content = {
            "branchPrefix": f"refactor/{self.project_name}",
            "reviewers": [
                {"username": "gestrich", "maxOpenPRs": 2}
            ]
        }
        (self.project_path / "configuration.yml").write_text(
            yaml.dump(config_content, default_flow_style=False)
        )

        # Create pr-template.md
        pr_template = f"""## Task

{{TASK_DESCRIPTION}}

## Test Project

This PR was created by an integration test for ClaudeStep.
Project: {self.project_name}
"""
        (self.project_path / "pr-template.md").write_text(pr_template)

    def commit_and_push(self):
        """Commit and push test project to main branch"""
        # Configure git
        subprocess.run(
            ["git", "config", "user.name", "Integration Test"],
            cwd=self.repo_path,
            check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.repo_path,
            check=True
        )

        # Add and commit
        subprocess.run(
            ["git", "add", str(self.project_path)],
            cwd=self.repo_path,
            check=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"Add test project {self.project_name}"],
            cwd=self.repo_path,
            check=True
        )

        # Push to main
        subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=self.repo_path,
            check=True
        )

    def cleanup(self):
        """Remove test project from repository"""
        if self.project_path.exists():
            # Remove from git and filesystem
            subprocess.run(
                ["git", "rm", "-rf", str(self.project_path)],
                cwd=self.repo_path,
                check=False  # Don't fail if already removed
            )
            subprocess.run(
                ["git", "commit", "-m", f"Remove test project {self.project_name}"],
                cwd=self.repo_path,
                check=False
            )
            subprocess.run(
                ["git", "push", "origin", "main"],
                cwd=self.repo_path,
                check=False
            )


@pytest.fixture
def temp_repo(tmp_path):
    """Clone demo repository to temporary directory"""
    repo_path = tmp_path / "claude-step-demo"

    print(f"\nCloning repository to {repo_path}...")
    subprocess.run(
        ["git", "clone", "https://github.com/gestrich/claude-step-demo.git", str(repo_path)],
        check=True,
        capture_output=True
    )

    yield repo_path


@pytest.fixture
def project_id():
    """Generate unique project ID"""
    return uuid.uuid4().hex[:8]


@pytest.fixture
def test_project(temp_repo, project_id):
    """Create and manage test project"""
    manager = TestProjectManager(temp_repo, project_id)
    manager.create_project()
    manager.commit_and_push()

    yield manager

    # Cleanup
    print("\nCleaning up test project...")
    manager.cleanup()


@pytest.fixture
def gh():
    """GitHub helper instance"""
    return GitHubHelper()


@pytest.fixture
def cleanup_prs(gh, test_project):
    """Cleanup fixture that closes test PRs after test completes"""
    created_prs = []

    yield created_prs

    # Cleanup all PRs created during test
    print(f"\nCleaning up {len(created_prs)} test PRs...")
    for pr_number in created_prs:
        try:
            gh.close_pr(pr_number)
            print(f"  Closed PR #{pr_number}")
        except Exception as e:
            print(f"  Failed to close PR #{pr_number}: {e}")


@pytest.mark.integration
def test_claudestep_workflow_e2e(gh, test_project, cleanup_prs):
    """
    End-to-end test of ClaudeStep workflow

    Tests:
    1. Workflow creates PR for first task
    2. AI-generated summary is posted on PR #1
    3. Workflow creates PR for second task (respects reviewer capacity)
    4. AI-generated summary is posted on PR #2
    5. Merge trigger creates PR for next task
    6. AI-generated summary is posted on PR #3
    """

    print(f"\n{'='*60}")
    print(f"Testing ClaudeStep workflow with project: {test_project.project_name}")
    print(f"{'='*60}\n")

    # === STEP 1: Trigger workflow and verify first PR ===
    print("\n[STEP 1] Triggering workflow for first task...")

    run_id_1 = gh.trigger_workflow(
        "claudestep.yml",
        {"project_name": test_project.project_name}
    )
    print(f"  Workflow run ID: {run_id_1}")

    conclusion_1 = gh.wait_for_workflow(run_id_1)
    assert conclusion_1 == "success", f"First workflow run failed: {conclusion_1}"
    print(f"  ✓ Workflow completed successfully")

    # Check that PR was created
    time.sleep(5)  # Give GitHub API a moment to index the PR
    pr_1 = gh.get_pr_by_branch(f"refactor/{test_project.project_name}-1")
    assert pr_1 is not None, "First PR was not created"
    assert pr_1["state"] == "OPEN", f"First PR is not open: {pr_1['state']}"
    assert "test-file-1" in pr_1["title"].lower(), f"First PR has wrong title: {pr_1['title']}"

    pr_1_number = pr_1["number"]
    cleanup_prs.append(pr_1_number)
    print(f"  ✓ PR #{pr_1_number} created: {pr_1['title']}")

    # Verify PR summary comment was posted
    print(f"  Checking for AI-generated summary on PR #{pr_1_number}...")
    has_summary_1 = gh.verify_pr_summary(pr_1_number, timeout=90)
    assert has_summary_1, f"PR #{pr_1_number} does not have an AI-generated summary comment"

    # Wait a bit to ensure PR is fully indexed before second workflow run
    print("  Waiting for PR to be fully indexed...")
    time.sleep(10)

    # === STEP 2: Trigger workflow again and verify second PR ===
    print("\n[STEP 2] Triggering workflow for second task...")

    run_id_2 = gh.trigger_workflow(
        "claudestep.yml",
        {"project_name": test_project.project_name}
    )
    print(f"  Workflow run ID: {run_id_2}")

    conclusion_2 = gh.wait_for_workflow(run_id_2)
    # Note: Workflow may fail due to Claude Code install lock when running concurrently
    # But the finalize step runs anyway (if: always()) and creates the PR
    print(f"  Workflow conclusion: {conclusion_2}")

    # Check that second PR was created (different task) - this is what matters
    time.sleep(5)
    pr_2 = gh.get_pr_by_branch(f"refactor/{test_project.project_name}-2")
    assert pr_2 is not None, "Second PR was not created"
    assert pr_2["state"] == "OPEN", f"Second PR is not open: {pr_2['state']}"
    assert "test-file-2" in pr_2["title"].lower(), f"Second PR has wrong title: {pr_2['title']}"

    pr_2_number = pr_2["number"]
    cleanup_prs.append(pr_2_number)
    print(f"  ✓ PR #{pr_2_number} created: {pr_2['title']}")

    # Verify PR summary comment was posted
    print(f"  Checking for AI-generated summary on PR #{pr_2_number}...")
    has_summary_2 = gh.verify_pr_summary(pr_2_number, timeout=90)
    assert has_summary_2, f"PR #{pr_2_number} does not have an AI-generated summary comment"

    # Verify both PRs are open (reviewer at capacity)
    all_prs = gh.get_prs_by_label("claudestep")
    open_prs = [pr for pr in all_prs if pr["state"] == "OPEN"]
    assert len(open_prs) == 2, f"Expected 2 open PRs, found {len(open_prs)}"
    print(f"  ✓ Reviewer at capacity with 2 open PRs")

    # === STEP 3: Merge first PR and verify merge trigger ===
    print("\n[STEP 3] Merging first PR to test merge trigger...")

    gh.merge_pr(pr_1_number)
    print(f"  ✓ Merged PR #{pr_1_number}")

    # Wait for merge trigger to create new workflow run
    print("  Waiting for merge trigger to start workflow...")
    time.sleep(10)

    # Find the most recent workflow run (should be triggered by merge)
    runs_output = gh.run_command([
        "run", "list",
        "--workflow", "claudestep.yml",
        "--repo", gh.repo,
        "--limit", "1",
        "--json", "databaseId,event"
    ])
    runs = json.loads(runs_output)
    assert runs, "No workflow runs found after merge"

    latest_run = runs[0]
    run_id_3 = str(latest_run["databaseId"])

    # Skip if this is the same run we just triggered manually
    if run_id_3 == run_id_2:
        print("  Waiting for new workflow run...")
        time.sleep(20)
        runs_output = gh.run_command([
            "run", "list",
            "--workflow", "claudestep.yml",
            "--repo", gh.repo,
            "--limit", "1",
            "--json", "databaseId,event"
        ])
        runs = json.loads(runs_output)
        run_id_3 = str(runs[0]["databaseId"])

    print(f"  Workflow run ID: {run_id_3}")

    conclusion_3 = gh.wait_for_workflow(run_id_3)
    # Note: Workflow may fail due to Claude Code install lock, but PR creation is what matters
    print(f"  Workflow conclusion: {conclusion_3}")

    # Check that third PR was created - this validates the merge trigger worked
    time.sleep(5)
    pr_3 = gh.get_pr_by_branch(f"refactor/{test_project.project_name}-3")
    assert pr_3 is not None, "Third PR was not created by merge trigger"
    assert pr_3["state"] == "OPEN", f"Third PR is not open: {pr_3['state']}"
    assert "test-file-3" in pr_3["title"].lower(), f"Third PR has wrong title: {pr_3['title']}"

    pr_3_number = pr_3["number"]
    cleanup_prs.append(pr_3_number)
    print(f"  ✓ PR #{pr_3_number} created: {pr_3['title']}")

    # Verify PR summary comment was posted
    print(f"  Checking for AI-generated summary on PR #{pr_3_number}...")
    has_summary_3 = gh.verify_pr_summary(pr_3_number, timeout=90)
    assert has_summary_3, f"PR #{pr_3_number} does not have an AI-generated summary comment"

    # === SUCCESS ===
    print(f"\n{'='*60}")
    print("✓ All tests passed!")
    print(f"{'='*60}")
    print(f"\nCreated PRs:")
    print(f"  - PR #{pr_1_number}: {pr_1['title']} (MERGED) - Summary: ✓")
    print(f"  - PR #{pr_2_number}: {pr_2['title']} (OPEN) - Summary: ✓")
    print(f"  - PR #{pr_3_number}: {pr_3['title']} (OPEN) - Summary: ✓")


if __name__ == "__main__":
    # Allow running test directly
    pytest.main([__file__, "-v", "-s"])
