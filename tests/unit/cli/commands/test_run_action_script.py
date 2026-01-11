"""Unit tests for run_action_script CLI command."""

import os
import stat
from unittest.mock import MagicMock, patch
import pytest

from claudechain.cli.commands.run_action_script import cmd_run_action_script
from claudechain.domain.exceptions import ActionScriptError
from claudechain.domain.models import ActionResult


class TestCmdRunActionScript:
    """Tests for cmd_run_action_script function."""

    def test_pre_action_script_runs_when_exists(self, tmp_path):
        """Pre-action script runs when exists."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Pre-action ran'\n")
        os.chmod(script_path, stat.S_IRWXU)

        gh = MagicMock()

        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=project_path,
            working_directory=str(tmp_path),
        )

        assert result == 0
        gh.set_error.assert_not_called()

    def test_post_action_script_runs_when_exists(self, tmp_path):
        """Post-action script runs when exists."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "post-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Post-action ran'\n")
        os.chmod(script_path, stat.S_IRWXU)

        gh = MagicMock()

        result = cmd_run_action_script(
            gh=gh,
            script_type="post",
            project_path=project_path,
            working_directory=str(tmp_path),
        )

        assert result == 0
        gh.set_error.assert_not_called()

    def test_success_when_script_not_exists(self, tmp_path):
        """Returns success when script doesn't exist (optional)."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        gh = MagicMock()

        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=project_path,
            working_directory=str(tmp_path),
        )

        assert result == 0
        gh.set_error.assert_not_called()

    def test_non_zero_exit_on_script_failure(self, tmp_path):
        """Returns non-zero exit code on script failure."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\nexit 42\n")
        os.chmod(script_path, stat.S_IRWXU)

        gh = MagicMock()

        result = cmd_run_action_script(
            gh=gh,
            script_type="pre",
            project_path=project_path,
            working_directory=str(tmp_path),
        )

        assert result == 42
        gh.set_error.assert_called_once()
        assert "pre-action" in gh.set_error.call_args[0][0]

    def test_sets_error_on_failure(self, tmp_path):
        """Calls gh.set_error on script failure."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "post-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'failure' >&2\nexit 1\n")
        os.chmod(script_path, stat.S_IRWXU)

        gh = MagicMock()

        result = cmd_run_action_script(
            gh=gh,
            script_type="post",
            project_path=project_path,
            working_directory=str(tmp_path),
        )

        assert result == 1
        gh.set_error.assert_called_once()
        error_msg = gh.set_error.call_args[0][0]
        assert "post-action" in error_msg
        assert "failed" in error_msg

    def test_handles_unexpected_exception(self, tmp_path):
        """Handles unexpected exceptions gracefully."""
        gh = MagicMock()

        with patch(
            "claudechain.cli.commands.run_action_script.run_action_script",
            side_effect=Exception("Unexpected error"),
        ):
            result = cmd_run_action_script(
                gh=gh,
                script_type="pre",
                project_path=str(tmp_path),
                working_directory=str(tmp_path),
            )

        assert result == 1
        gh.set_error.assert_called_once()
        assert "Unexpected error" in gh.set_error.call_args[0][0]
