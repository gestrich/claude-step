"""Integration tests for run_action_script CLI command.

Tests the full flow of the action script functionality including
script execution, error handling, and integration with the CLI.
"""

import os
import stat
import subprocess
import sys
from unittest.mock import MagicMock
import pytest


class TestActionScriptIntegration:
    """Integration tests for action script execution."""

    def test_full_pre_action_flow(self, tmp_path):
        """Full flow: pre-action script runs and creates a file."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        output_file = tmp_path / "pre_action_output.txt"

        script_path = project_path / "pre-action.sh"
        script_path.write_text(f"""#!/bin/bash
echo "Pre-action executed" > {output_file}
echo "Environment setup complete"
exit 0
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert result == 0
        assert output_file.exists()
        assert "Pre-action executed" in output_file.read_text()

    def test_full_post_action_flow(self, tmp_path):
        """Full flow: post-action script validates changes."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        validation_marker = tmp_path / "validated.txt"

        script_path = project_path / "post-action.sh"
        script_path.write_text(f"""#!/bin/bash
echo "Validation passed" > {validation_marker}
echo "Post-action validation complete"
exit 0
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="post",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert result == 0
        assert validation_marker.exists()

    def test_pre_action_failure_stops_execution(self, tmp_path):
        """Pre-action failure returns non-zero exit code."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        script_path = project_path / "pre-action.sh"
        script_path.write_text("""#!/bin/bash
echo "Setup failed: missing dependency" >&2
exit 1
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert result == 1
        gh.set_error.assert_called_once()

    def test_post_action_failure_prevents_pr(self, tmp_path):
        """Post-action failure returns non-zero exit code."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        script_path = project_path / "post-action.sh"
        script_path.write_text("""#!/bin/bash
echo "Tests failed: 3 failures" >&2
exit 1
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="post",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert result == 1
        gh.set_error.assert_called_once()

    def test_missing_scripts_do_not_cause_failures(self, tmp_path):
        """Missing scripts don't cause failures."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()

        pre_result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        post_result = cmd_run_action_script(
            gh=gh,
            script_type="post",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert pre_result == 0
        assert post_result == 0
        gh.set_error.assert_not_called()

    def test_script_can_access_working_directory(self, tmp_path):
        """Script can access files in working directory."""
        project_path = tmp_path / "project"
        project_path.mkdir()
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        source_file = work_dir / "source.txt"
        source_file.write_text("original content")

        script_path = project_path / "pre-action.sh"
        script_path.write_text(f"""#!/bin/bash
if [ -f "source.txt" ]; then
    echo "Found source file"
    exit 0
else
    echo "Source file not found" >&2
    exit 1
fi
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=str(project_path),
            working_directory=str(work_dir),
        )

        assert result == 0

    def test_script_environment_variables(self, tmp_path):
        """Script has access to environment variables."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        env_output = tmp_path / "env_output.txt"

        script_path = project_path / "pre-action.sh"
        script_path.write_text(f"""#!/bin/bash
echo "PATH exists: ${{PATH:+yes}}" > {env_output}
echo "HOME: $HOME" >> {env_output}
exit 0
""")
        os.chmod(str(script_path), stat.S_IRWXU)

        from claudechain.cli.commands.run_action_script import cmd_run_action_script

        gh = MagicMock()
        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=str(project_path),
            working_directory=str(tmp_path),
        )

        assert result == 0
        output = env_output.read_text()
        assert "PATH exists: yes" in output


class TestCLIInvocation:
    """Tests for invoking run-action-script via CLI."""

    @pytest.fixture
    def project_root(self):
        """Get the project root directory."""
        return os.path.dirname(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(
                        os.path.dirname(os.path.abspath(__file__))
                    )
                )
            )
        )

    def test_cli_invocation_with_missing_args(self, project_root):
        """CLI requires --type and --project-path arguments."""
        result = subprocess.run(
            [sys.executable, "-m", "claudechain", "run-action-script"],
            cwd=project_root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": os.path.join(project_root, "src")},
        )

        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "error" in result.stderr.lower()

    def test_cli_invocation_with_valid_args(self, tmp_path, project_root):
        """CLI runs successfully with valid arguments."""
        project_path = tmp_path / "project"
        project_path.mkdir()

        script_path = project_path / "pre-action.sh"
        script_path.write_text("#!/bin/bash\necho 'Success'\n")
        os.chmod(str(script_path), stat.S_IRWXU)

        result = subprocess.run(
            [
                sys.executable, "-m", "claudechain", "run-action-script",
                "--type", "pre",
                "--project-path", str(project_path),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": os.path.join(project_root, "src")},
        )

        assert result.returncode == 0
