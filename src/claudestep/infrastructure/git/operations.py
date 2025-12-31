"""Git command operations"""

import subprocess
from typing import List, Optional

from claudestep.domain.exceptions import GitError


def run_command(cmd: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
    """Run a shell command and return the result

    Args:
        cmd: Command and arguments as list
        check: Whether to raise exception on non-zero exit
        capture_output: Whether to capture stdout/stderr

    Returns:
        CompletedProcess instance

    Raises:
        subprocess.CalledProcessError: If command fails and check=True
    """
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture_output,
        text=True
    )


def run_git_command(args: List[str]) -> str:
    """Run a git command and return stdout

    Args:
        args: Git command arguments (without 'git' prefix)

    Returns:
        Command stdout as string

    Raises:
        GitError: If git command fails
    """
    try:
        result = run_command(["git"] + args)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise GitError(f"Git command failed: {' '.join(args)}\n{e.stderr}")


def detect_changed_files(ref_before: str, ref_after: str, pattern: str) -> List[str]:
    """Detect added or modified files between two git references

    Args:
        ref_before: Git reference for the before state (e.g., commit SHA)
        ref_after: Git reference for the after state (e.g., commit SHA)
        pattern: File pattern to filter (e.g., "claude-step/*/spec.md")

    Returns:
        List of file paths that were added or modified

    Raises:
        GitError: If git command fails
    """
    output = run_git_command([
        "diff",
        "--name-only",
        "--diff-filter=AM",
        ref_before,
        ref_after,
        "--",
        pattern
    ])

    if not output:
        return []

    return [line.strip() for line in output.split("\n") if line.strip()]


def detect_deleted_files(ref_before: str, ref_after: str, pattern: str) -> List[str]:
    """Detect deleted files between two git references

    Args:
        ref_before: Git reference for the before state (e.g., commit SHA)
        ref_after: Git reference for the after state (e.g., commit SHA)
        pattern: File pattern to filter (e.g., "claude-step/*/spec.md")

    Returns:
        List of file paths that were deleted

    Raises:
        GitError: If git command fails
    """
    output = run_git_command([
        "diff",
        "--name-only",
        "--diff-filter=D",
        ref_before,
        ref_after,
        "--",
        pattern
    ])

    if not output:
        return []

    return [line.strip() for line in output.split("\n") if line.strip()]


def parse_spec_path_to_project(path: str) -> Optional[str]:
    """Extract project name from a spec.md file path

    Expected path format: claude-step/{project_name}/spec.md

    Args:
        path: File path to parse

    Returns:
        Project name if path matches expected format, None otherwise

    Examples:
        >>> parse_spec_path_to_project("claude-step/my-project/spec.md")
        'my-project'
        >>> parse_spec_path_to_project("claude-step/another/spec.md")
        'another'
        >>> parse_spec_path_to_project("invalid/path/spec.md")
        None
    """
    parts = path.split("/")

    # Expected format: claude-step/{project_name}/spec.md
    if len(parts) != 3:
        return None

    if parts[0] != "claude-step" or parts[2] != "spec.md":
        return None

    return parts[1]
