"""CLI command for running pre/post action scripts.

This command runs the action scripts as part of the GitHub Actions workflow.
"""

import os
from typing import Literal

from claudechain.domain.exceptions import ActionScriptError
from claudechain.infrastructure.actions.script_runner import run_action_script
from claudechain.infrastructure.github.actions import GitHubActionsHelper


def cmd_run_action_script(
    gh: GitHubActionsHelper,
    script_type: Literal["pre", "post"],
    project_path: str,
    working_directory: str,
) -> int:
    """Run a pre or post action script.

    Args:
        gh: GitHub Actions helper instance
        script_type: Type of script to run ("pre" or "post")
        project_path: Path to the project directory
        working_directory: Directory to run the script from

    Returns:
        Exit code (0 for success or script not found, non-zero for failure)
    """
    print(f"=== Running {script_type}-action script ===")
    print(f"Project path: {project_path}")
    print(f"Working directory: {working_directory}")

    try:
        result = run_action_script(
            project_path=project_path,
            script_type=script_type,
            working_directory=working_directory,
        )

        if not result.script_exists:
            print(f"No {script_type}-action.sh script found, continuing")
            return 0

        print(f"✅ {script_type}-action.sh completed successfully")
        return 0

    except ActionScriptError as e:
        gh.set_error(f"{script_type}-action script failed: {str(e)}")
        if e.stdout:
            print(f"stdout: {e.stdout}")
        if e.stderr:
            print(f"stderr: {e.stderr}")
        return e.exit_code

    except Exception as e:
        gh.set_error(f"Unexpected error running {script_type}-action script: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
