"""Unit tests for action script runner."""

import os
import stat
import tempfile
from unittest.mock import patch, MagicMock
import pytest

from claudechain.domain.exceptions import ActionScriptError
from claudechain.domain.models import ActionResult
from claudechain.infrastructure.actions.script_runner import run_action_script, _ensure_executable


class TestRunActionScript:
    """Tests for run_action_script function."""

    def test_script_not_found_returns_success(self, tmp_path):
        """Script doesn't exist → returns success (optional)."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        result = run_action_script(
            project_path=project_path,
            script_type="pre",
            working_directory=str(tmp_path),
        )

        assert result.success is True
        assert result.script_exists is False
        assert result.exit_code is None

    def test_script_exists_and_succeeds(self, tmp_path):
        """Script exists and succeeds → returns success with stdout."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Hello from pre-action'\n")
        os.chmod(script_path, stat.S_IRWXU)

        result = run_action_script(
            project_path=project_path,
            script_type="pre",
            working_directory=str(tmp_path),
        )

        assert result.success is True
        assert result.script_exists is True
        assert result.exit_code == 0
        assert "Hello from pre-action" in result.stdout

    def test_script_exists_and_fails(self, tmp_path):
        """Script exists and fails → raises ActionScriptError."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "post-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Error message' >&2\nexit 1\n")
        os.chmod(script_path, stat.S_IRWXU)

        with pytest.raises(ActionScriptError) as exc_info:
            run_action_script(
                project_path=project_path,
                script_type="post",
                working_directory=str(tmp_path),
            )

        assert exc_info.value.exit_code == 1
        assert "Error message" in exc_info.value.stderr

    def test_script_with_non_executable_permissions(self, tmp_path):
        """Script with non-executable permissions → makes executable and runs."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Made executable'\n")
        # Create without execute permission
        os.chmod(script_path, stat.S_IRUSR | stat.S_IWUSR)

        result = run_action_script(
            project_path=project_path,
            script_type="pre",
            working_directory=str(tmp_path),
        )

        assert result.success is True
        assert "Made executable" in result.stdout

    def test_script_produces_stderr(self, tmp_path):
        """Script produces stderr → captured in result."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'stdout' && echo 'stderr' >&2\n")
        os.chmod(script_path, stat.S_IRWXU)

        result = run_action_script(
            project_path=project_path,
            script_type="pre",
            working_directory=str(tmp_path),
        )

        assert result.success is True
        assert "stdout" in result.stdout
        assert "stderr" in result.stderr

    def test_post_action_script(self, tmp_path):
        """Post-action script runs correctly."""
        project_path = str(tmp_path / "project")
        os.makedirs(project_path)

        script_path = os.path.join(project_path, "post-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\necho 'Post action complete'\n")
        os.chmod(script_path, stat.S_IRWXU)

        result = run_action_script(
            project_path=project_path,
            script_type="post",
            working_directory=str(tmp_path),
        )

        assert result.success is True
        assert "Post action complete" in result.stdout

    def test_script_runs_in_working_directory(self, tmp_path):
        """Script runs from working_directory, not project_path."""
        project_path = str(tmp_path / "project")
        work_dir = str(tmp_path / "work")
        os.makedirs(project_path)
        os.makedirs(work_dir)

        script_path = os.path.join(project_path, "pre-action.sh")
        with open(script_path, "w") as f:
            f.write("#!/bin/bash\npwd\n")
        os.chmod(script_path, stat.S_IRWXU)

        result = run_action_script(
            project_path=project_path,
            script_type="pre",
            working_directory=work_dir,
        )

        assert result.success is True
        assert work_dir in result.stdout


class TestEnsureExecutable:
    """Tests for _ensure_executable function."""

    def test_adds_execute_permission(self, tmp_path):
        """Adds user execute permission if not present."""
        script_path = tmp_path / "script.sh"
        script_path.write_text("#!/bin/bash\necho 'test'\n")
        os.chmod(str(script_path), stat.S_IRUSR | stat.S_IWUSR)

        _ensure_executable(str(script_path))

        mode = os.stat(str(script_path)).st_mode
        assert mode & stat.S_IXUSR

    def test_preserves_existing_permissions(self, tmp_path):
        """Preserves existing permissions when adding execute."""
        script_path = tmp_path / "script.sh"
        script_path.write_text("#!/bin/bash\necho 'test'\n")
        os.chmod(str(script_path), stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP)

        _ensure_executable(str(script_path))

        mode = os.stat(str(script_path)).st_mode
        assert mode & stat.S_IXUSR
        assert mode & stat.S_IRGRP  # Group read still present


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_script_not_found_factory(self):
        """Test script_not_found factory method."""
        result = ActionResult.script_not_found("/path/to/script.sh")

        assert result.success is True
        assert result.script_exists is False
        assert result.exit_code is None
        assert result.script_path == "/path/to/script.sh"
        assert result.stdout == ""
        assert result.stderr == ""

    def test_from_execution_success(self):
        """Test from_execution with successful exit code."""
        result = ActionResult.from_execution(
            script_path="/path/to/script.sh",
            exit_code=0,
            stdout="output",
            stderr="",
        )

        assert result.success is True
        assert result.script_exists is True
        assert result.exit_code == 0
        assert result.stdout == "output"

    def test_from_execution_failure(self):
        """Test from_execution with failed exit code."""
        result = ActionResult.from_execution(
            script_path="/path/to/script.sh",
            exit_code=1,
            stdout="",
            stderr="error",
        )

        assert result.success is False
        assert result.script_exists is True
        assert result.exit_code == 1
        assert result.stderr == "error"


class TestActionScriptError:
    """Tests for ActionScriptError exception."""

    def test_error_message_format(self):
        """Test error message formatting."""
        error = ActionScriptError(
            script_path="/path/to/script.sh",
            exit_code=1,
            stdout="",
            stderr="Something went wrong",
        )

        assert "script.sh" in str(error)
        assert "exit code 1" in str(error)
        assert "Something went wrong" in str(error)

    def test_error_without_stderr(self):
        """Test error without stderr."""
        error = ActionScriptError(
            script_path="/path/to/script.sh",
            exit_code=2,
            stdout="",
            stderr="",
        )

        assert "exit code 2" in str(error)
        assert error.exit_code == 2

    def test_long_stderr_truncated(self):
        """Test that long stderr is truncated in message."""
        long_stderr = "x" * 1000
        error = ActionScriptError(
            script_path="/path/to/script.sh",
            exit_code=1,
            stdout="",
            stderr=long_stderr,
        )

        # Message should be truncated to first 500 chars of stderr
        assert len(str(error)) < 600
