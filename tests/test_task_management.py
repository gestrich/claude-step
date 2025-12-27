"""Unit tests for task finding and management"""

import os
import tempfile
from pathlib import Path

import pytest

from claudestep.domain.exceptions import FileNotFoundError
from claudestep.application.services.task_management import (
    find_next_available_task,
    generate_task_id,
    mark_task_complete,
)


class TestFindNextAvailableTask:
    """Tests for find_next_available_task function"""

    def test_find_first_unchecked_task(self, tmp_path):
        """Should find the first unchecked task"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        result = find_next_available_task(str(spec_file))
        assert result is not None
        task_index, task_text = result
        assert task_index == 1
        assert task_text == "Task 1"

    def test_find_next_task_after_completed(self, tmp_path):
        """Should find the next unchecked task after completed tasks"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [x] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        result = find_next_available_task(str(spec_file))
        assert result is not None
        task_index, task_text = result
        assert task_index == 2
        assert task_text == "Task 2"

    def test_find_next_task_with_multiple_completed(self, tmp_path):
        """Should correctly index tasks when multiple are completed"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [x] Task 1
- [x] Task 2
- [ ] Task 3
- [ ] Task 4
""")

        result = find_next_available_task(str(spec_file))
        assert result is not None
        task_index, task_text = result
        assert task_index == 3
        assert task_text == "Task 3"

    def test_skip_in_progress_tasks(self, tmp_path):
        """Should skip tasks that are already in progress"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
""")

        # Skip task 1 (it's in progress)
        result = find_next_available_task(str(spec_file), skip_indices={1})
        assert result is not None
        task_index, task_text = result
        assert task_index == 2
        assert task_text == "Task 2"

    def test_skip_multiple_in_progress_tasks(self, tmp_path):
        """Should skip multiple in-progress tasks"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [ ] Task 1
- [ ] Task 2
- [ ] Task 3
- [ ] Task 4
""")

        # Skip tasks 1 and 2 (they're in progress)
        result = find_next_available_task(str(spec_file), skip_indices={1, 2})
        assert result is not None
        task_index, task_text = result
        assert task_index == 3
        assert task_text == "Task 3"

    def test_return_none_when_all_tasks_complete(self, tmp_path):
        """Should return None when all tasks are completed"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [x] Task 1
- [x] Task 2
- [x] Task 3
""")

        result = find_next_available_task(str(spec_file))
        assert result is None

    def test_return_none_when_no_tasks(self, tmp_path):
        """Should return None when there are no tasks"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

This project has no tasks yet.
""")

        result = find_next_available_task(str(spec_file))
        assert result is None

    def test_handle_capital_x_in_completed_tasks(self, tmp_path):
        """Should recognize both [x] and [X] as completed"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [X] Task 1
- [x] Task 2
- [ ] Task 3
""")

        result = find_next_available_task(str(spec_file))
        assert result is not None
        task_index, task_text = result
        assert task_index == 3
        assert task_text == "Task 3"

    def test_handle_indented_tasks(self, tmp_path):
        """Should handle tasks with various indentation levels"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

  - [x] Task 1
    - [ ] Task 2
- [ ] Task 3
""")

        result = find_next_available_task(str(spec_file))
        assert result is not None
        task_index, task_text = result
        assert task_index == 2
        assert task_text == "Task 2"

    def test_raise_error_when_file_not_found(self):
        """Should raise FileNotFoundError when spec file doesn't exist"""
        with pytest.raises(FileNotFoundError):
            find_next_available_task("/nonexistent/path/spec.md")

    def test_complex_scenario_merge_trigger(self, tmp_path):
        """
        Simulate merge trigger scenario:
        - Task 1 is completed (just merged)
        - Task 2 is in progress (open PR)
        - Should find Task 3 as the next available task
        """
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [x] Task 1
- [ ] Task 2
- [ ] Task 3
- [ ] Task 4
""")

        # Task 2 is in progress (has an open PR)
        result = find_next_available_task(str(spec_file), skip_indices={2})
        assert result is not None
        task_index, task_text = result
        assert task_index == 3
        assert task_text == "Task 3"


class TestMarkTaskComplete:
    """Tests for mark_task_complete function"""

    def test_mark_task_complete(self, tmp_path):
        """Should mark an unchecked task as complete"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

- [ ] Task 1
- [ ] Task 2
""")

        mark_task_complete(str(spec_file), "Task 1")

        updated_content = spec_file.read_text()
        assert "- [x] Task 1" in updated_content
        assert "- [ ] Task 2" in updated_content

    def test_preserve_indentation(self, tmp_path):
        """Should preserve task indentation when marking complete"""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text("""# Test Project

## Tasks

  - [ ] Task 1
    - [ ] Task 2
""")

        mark_task_complete(str(spec_file), "Task 2")

        updated_content = spec_file.read_text()
        assert "  - [ ] Task 1" in updated_content
        assert "    - [x] Task 2" in updated_content

    def test_raise_error_when_file_not_found(self):
        """Should raise FileNotFoundError when spec file doesn't exist"""
        with pytest.raises(FileNotFoundError):
            mark_task_complete("/nonexistent/path/spec.md", "Task 1")


class TestGenerateTaskId:
    """Tests for generate_task_id function"""

    def test_generate_basic_task_id(self):
        """Should generate sanitized task ID"""
        task = "Create test file"
        result = generate_task_id(task)
        assert result == "create-test-file"

    def test_handle_special_characters(self):
        """Should replace special characters with dashes"""
        task = "Update config.yml file!"
        result = generate_task_id(task)
        assert result == "update-config-yml-file"

    def test_truncate_long_ids(self):
        """Should truncate IDs to max length"""
        task = "This is a very long task description that exceeds the maximum length"
        result = generate_task_id(task, max_length=20)
        assert len(result) <= 20
        assert result == "this-is-a-very-long"

    def test_remove_leading_trailing_dashes(self):
        """Should remove leading and trailing dashes"""
        task = "!!! Important task !!!"
        result = generate_task_id(task)
        assert result == "important-task"
