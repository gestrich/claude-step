"""Script runner for pre/post action scripts.

This module provides functionality to run action scripts with proper
error handling, capturing stdout/stderr for logging.
"""

import os
import stat
import subprocess
from typing import Literal

from claudechain.domain.exceptions import ActionScriptError
from claudechain.domain.models import ActionResult


def run_action_script(
    project_path: str,
    script_type: Literal["pre", "post"],
    working_directory: str,
) -> ActionResult:
    """Run an action script if it exists.

    Args:
        project_path: Path to the project directory (e.g., claude-chain/my-project)
        script_type: Type of script to run ("pre" or "post")
        working_directory: Directory to run the script from

    Returns:
        ActionResult with success status, stdout, stderr.
        Returns success=True if script doesn't exist (scripts are optional).

    Raises:
        ActionScriptError: If script exists but fails (non-zero exit code)
    """
    script_name = f"{script_type}-action.sh"
    script_path = os.path.join(project_path, script_name)

    # Check if script exists
    if not os.path.exists(script_path):
        print(f"No {script_name} found at {script_path}, skipping")
        return ActionResult.script_not_found(script_path)

    # Make script executable if needed
    _ensure_executable(script_path)

    print(f"Running {script_name} from {script_path}")

    # Run the script
    try:
        result = subprocess.run(
            [script_path],
            cwd=working_directory,
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
        )
    except subprocess.TimeoutExpired as e:
        # e.stdout can be bytes, str, or None depending on context
        stdout_value = ""
        if e.stdout is not None:
            stdout_value = e.stdout if isinstance(e.stdout, str) else e.stdout.decode("utf-8", errors="replace")
        raise ActionScriptError(
            script_path=script_path,
            exit_code=124,  # Standard timeout exit code
            stdout=stdout_value,
            stderr="Script timed out after 600 seconds",
        )
    except Exception as e:
        raise ActionScriptError(
            script_path=script_path,
            exit_code=1,
            stdout="",
            stderr=str(e),
        )

    # Log output
    if result.stdout:
        print(f"--- {script_name} stdout ---")
        print(result.stdout)
    if result.stderr:
        print(f"--- {script_name} stderr ---")
        print(result.stderr)

    # Check for failure
    if result.returncode != 0:
        raise ActionScriptError(
            script_path=script_path,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    print(f"{script_name} completed successfully")
    return ActionResult.from_execution(
        script_path=script_path,
        exit_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _ensure_executable(script_path: str) -> None:
    """Ensure the script file has executable permissions.

    Args:
        script_path: Path to the script file
    """
    current_mode = os.stat(script_path).st_mode
    if not current_mode & stat.S_IXUSR:
        # Add user execute permission
        os.chmod(script_path, current_mode | stat.S_IXUSR)
        print(f"Made {script_path} executable")
