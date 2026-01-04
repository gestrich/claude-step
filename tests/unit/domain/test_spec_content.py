"""Unit tests for SpecContent and SpecTask domain models"""

import pytest

from claudechain.domain.project import Project
from claudechain.domain.spec_content import SpecTask, SpecContent, generate_task_hash


class TestSpecTaskFromMarkdownLine:
    """Test suite for SpecTask.from_markdown_line factory method"""

    def test_from_markdown_line_with_uncompleted_task(self):
        """Should parse uncompleted task from markdown"""
        # Arrange
        line = "- [ ] Implement feature X"
        index = 1

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.index == 1
        assert task.description == "Implement feature X"
        assert task.is_completed is False
        assert task.raw_line == line
        assert task.task_hash == generate_task_hash("Implement feature X")

    def test_from_markdown_line_with_completed_task_lowercase_x(self):
        """Should parse completed task with lowercase [x]"""
        # Arrange
        line = "- [x] Fix bug Y"
        index = 2

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.index == 2
        assert task.description == "Fix bug Y"
        assert task.is_completed is True
        assert task.raw_line == line

    def test_from_markdown_line_with_completed_task_uppercase_x(self):
        """Should parse completed task with uppercase [X]"""
        # Arrange
        line = "- [X] Add tests"
        index = 3

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.index == 3
        assert task.description == "Add tests"
        assert task.is_completed is True

    def test_from_markdown_line_with_leading_whitespace(self):
        """Should handle task with leading whitespace"""
        # Arrange
        line = "  - [ ] Task with indent"
        index = 1

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.description == "Task with indent"
        assert task.is_completed is False

    def test_from_markdown_line_with_extra_spaces_in_description(self):
        """Should trim whitespace from description"""
        # Arrange
        line = "- [ ]   Task with extra spaces   "
        index = 1

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.description == "Task with extra spaces"

    def test_from_markdown_line_returns_none_for_invalid_format(self):
        """Should return None for non-task lines"""
        # Arrange
        invalid_lines = [
            "# Heading",
            "Regular paragraph text",
            "- Not a checkbox",
            "* [ ] Wrong bullet",
            "[ ] No bullet",
            "",
            "- [?] Invalid checkbox",
        ]

        # Act & Assert
        for line in invalid_lines:
            task = SpecTask.from_markdown_line(line, 1)
            assert task is None, f"Should return None for: {line}"

    def test_from_markdown_line_with_complex_description(self):
        """Should handle complex task descriptions"""
        # Arrange
        line = "- [ ] Update API endpoint `/users/{id}` to support PATCH"
        index = 1

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.description == "Update API endpoint `/users/{id}` to support PATCH"

    def test_from_markdown_line_preserves_markdown_in_description(self):
        """Should preserve markdown formatting in description"""
        # Arrange
        line = "- [ ] Add **bold** and _italic_ text support"
        index = 1

        # Act
        task = SpecTask.from_markdown_line(line, index)

        # Assert
        assert task is not None
        assert task.description == "Add **bold** and _italic_ text support"


class TestSpecTaskToMarkdownLine:
    """Test suite for SpecTask.to_markdown_line method"""

    def test_to_markdown_line_for_uncompleted_task(self):
        """Should convert uncompleted task to markdown"""
        # Arrange
        task = SpecTask(
            index=1,
            description="My task",
            is_completed=False,
            raw_line="original",
            task_hash=generate_task_hash("My task")
        )

        # Act
        markdown = task.to_markdown_line()

        # Assert
        assert markdown == "- [ ] My task"

    def test_to_markdown_line_for_completed_task(self):
        """Should convert completed task to markdown"""
        # Arrange
        task = SpecTask(
            index=1,
            description="My task",
            is_completed=True,
            raw_line="original",
            task_hash=generate_task_hash("My task")
        )

        # Act
        markdown = task.to_markdown_line()

        # Assert
        assert markdown == "- [x] My task"

    def test_to_markdown_line_roundtrip(self):
        """Should be able to roundtrip through markdown conversion"""
        # Arrange
        original_line = "- [ ] Implement feature"
        task = SpecTask.from_markdown_line(original_line, 1)

        # Act
        converted = task.to_markdown_line()
        restored = SpecTask.from_markdown_line(converted, 1)

        # Assert
        assert restored.description == task.description
        assert restored.is_completed == task.is_completed


class TestSpecContentInitialization:
    """Test suite for SpecContent initialization"""

    def test_create_spec_content_with_project_and_content(self):
        """Should create SpecContent with project and content"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [ ] Task 2"

        # Act
        spec = SpecContent(project, content)

        # Assert
        assert spec.project == project
        assert spec.content == content

    def test_tasks_are_lazily_loaded(self):
        """Should not parse tasks until accessed"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1"
        spec = SpecContent(project, content)

        # Assert - Internal cache should be None before access
        assert spec._tasks is None

        # Act - Access tasks property
        tasks = spec.tasks

        # Assert - Cache should now be populated
        assert spec._tasks is not None
        assert len(tasks) == 1


class TestSpecContentTaskParsing:
    """Test suite for SpecContent task parsing"""

    def test_parse_single_task(self):
        """Should parse single task from content"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Implement feature X"
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert len(tasks) == 1
        assert tasks[0].description == "Implement feature X"
        assert tasks[0].is_completed is False

    def test_parse_multiple_tasks(self):
        """Should parse multiple tasks from content"""
        # Arrange
        project = Project("my-project")
        content = """- [ ] Task 1
- [ ] Task 2
- [x] Task 3
- [ ] Task 4"""
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert len(tasks) == 4
        assert tasks[0].description == "Task 1"
        assert tasks[1].description == "Task 2"
        assert tasks[2].description == "Task 3"
        assert tasks[2].is_completed is True
        assert tasks[3].description == "Task 4"

    def test_parse_tasks_with_non_task_content(self):
        """Should parse only tasks and ignore other content"""
        # Arrange
        project = Project("my-project")
        content = """# Project Spec

This is a description.

- [ ] Task 1
- [ ] Task 2

Some more text here.

- [x] Task 3

## Notes
Additional information."""
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert len(tasks) == 3
        assert tasks[0].description == "Task 1"
        assert tasks[1].description == "Task 2"
        assert tasks[2].description == "Task 3"

    def test_parse_empty_content(self):
        """Should handle empty content"""
        # Arrange
        project = Project("my-project")
        content = ""
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert tasks == []

    def test_parse_content_with_no_tasks(self):
        """Should handle content with no tasks"""
        # Arrange
        project = Project("my-project")
        content = """# Header
Some text
More text"""
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert tasks == []

    def test_task_indices_are_sequential(self):
        """Should assign sequential indices to tasks"""
        # Arrange
        project = Project("my-project")
        content = """# Header
- [ ] First task
Some text
- [ ] Second task
- [x] Third task"""
        spec = SpecContent(project, content)

        # Act
        tasks = spec.tasks

        # Assert
        assert tasks[0].index == 1
        assert tasks[1].index == 2
        assert tasks[2].index == 3


class TestSpecContentTaskCounts:
    """Test suite for SpecContent task counting properties"""

    def test_total_tasks_with_multiple_tasks(self):
        """Should count total tasks correctly"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3"
        spec = SpecContent(project, content)

        # Act
        total = spec.total_tasks

        # Assert
        assert total == 3

    def test_total_tasks_with_no_tasks(self):
        """Should return 0 for empty spec"""
        # Arrange
        project = Project("my-project")
        content = "# No tasks here"
        spec = SpecContent(project, content)

        # Act
        total = spec.total_tasks

        # Assert
        assert total == 0

    def test_completed_tasks_count(self):
        """Should count completed tasks correctly"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [x] Task 2\n- [x] Task 3\n- [ ] Task 4"
        spec = SpecContent(project, content)

        # Act
        completed = spec.completed_tasks

        # Assert
        assert completed == 2

    def test_completed_tasks_with_none_completed(self):
        """Should return 0 when no tasks completed"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [ ] Task 2"
        spec = SpecContent(project, content)

        # Act
        completed = spec.completed_tasks

        # Assert
        assert completed == 0

    def test_completed_tasks_with_all_completed(self):
        """Should count all tasks when all completed"""
        # Arrange
        project = Project("my-project")
        content = "- [x] Task 1\n- [x] Task 2\n- [x] Task 3"
        spec = SpecContent(project, content)

        # Act
        completed = spec.completed_tasks

        # Assert
        assert completed == 3

    def test_pending_tasks_count(self):
        """Should calculate pending tasks correctly"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3\n- [ ] Task 4"
        spec = SpecContent(project, content)

        # Act
        pending = spec.pending_tasks

        # Assert
        assert pending == 3

    def test_pending_tasks_with_all_completed(self):
        """Should return 0 when all tasks completed"""
        # Arrange
        project = Project("my-project")
        content = "- [x] Task 1\n- [x] Task 2"
        spec = SpecContent(project, content)

        # Act
        pending = spec.pending_tasks

        # Assert
        assert pending == 0


class TestSpecContentGetTaskByIndex:
    """Test suite for SpecContent.get_task_by_index method"""

    def test_get_task_by_index_first_task(self):
        """Should get first task with index 1"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(1)

        # Assert
        assert task is not None
        assert task.description == "First"
        assert task.index == 1

    def test_get_task_by_index_middle_task(self):
        """Should get middle task correctly"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(2)

        # Assert
        assert task is not None
        assert task.description == "Second"
        assert task.index == 2

    def test_get_task_by_index_last_task(self):
        """Should get last task correctly"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(3)

        # Assert
        assert task is not None
        assert task.description == "Third"
        assert task.index == 3

    def test_get_task_by_index_returns_none_for_zero(self):
        """Should return None for index 0"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(0)

        # Assert
        assert task is None

    def test_get_task_by_index_returns_none_for_negative(self):
        """Should return None for negative index"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(-1)

        # Assert
        assert task is None

    def test_get_task_by_index_returns_none_for_out_of_range(self):
        """Should return None for index beyond task count"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_task_by_index(5)

        # Assert
        assert task is None


class TestSpecContentGetNextAvailableTask:
    """Test suite for SpecContent.get_next_available_task method"""

    def test_get_next_available_task_returns_first_uncompleted(self):
        """Should return first uncompleted task"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_next_available_task()

        # Assert
        assert task is not None
        assert task.description == "First"
        assert task.index == 1

    def test_get_next_available_task_skips_completed(self):
        """Should skip completed tasks"""
        # Arrange
        project = Project("my-project")
        content = "- [x] First\n- [x] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_next_available_task()

        # Assert
        assert task is not None
        assert task.description == "Third"
        assert task.index == 3



    def test_get_next_available_task_returns_none_when_all_completed(self):
        """Should return None when all tasks completed"""
        # Arrange
        project = Project("my-project")
        content = "- [x] First\n- [x] Second\n- [x] Third"
        spec = SpecContent(project, content)

        # Act
        task = spec.get_next_available_task()

        # Assert
        assert task is None


    def test_get_next_available_task_with_empty_spec(self):
        """Should return None for empty spec"""
        # Arrange
        project = Project("my-project")
        content = ""
        spec = SpecContent(project, content)

        # Act
        task = spec.get_next_available_task()

        # Assert
        assert task is None

    def test_get_next_available_task_with_skip_hashes(self):
        """Should skip tasks by hash"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third\n- [ ] Fourth"
        spec = SpecContent(project, content)

        # Get hash of first task to skip it
        first_task_hash = spec.tasks[0].task_hash

        # Act
        task = spec.get_next_available_task(skip_hashes={first_task_hash})

        # Assert
        assert task is not None
        assert task.description == "Second"
        assert task.index == 2


    def test_get_next_available_task_with_multiple_skip_hashes(self):
        """Should skip multiple tasks by hash"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [ ] Second\n- [ ] Third\n- [ ] Fourth"
        spec = SpecContent(project, content)

        # Get hashes to skip
        first_hash = spec.tasks[0].task_hash
        second_hash = spec.tasks[1].task_hash
        third_hash = spec.tasks[2].task_hash

        # Act
        task = spec.get_next_available_task(skip_hashes={first_hash, second_hash, third_hash})

        # Assert
        assert task is not None
        assert task.description == "Fourth"
        assert task.index == 4


class TestSpecContentGetPendingTaskIndices:
    """Test suite for SpecContent.get_pending_task_indices method"""

    def test_get_pending_task_indices_returns_all_uncompleted(self):
        """Should return indices of all uncompleted tasks"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [x] Second\n- [ ] Third\n- [ ] Fourth"
        spec = SpecContent(project, content)

        # Act
        indices = spec.get_pending_task_indices()

        # Assert
        assert indices == [1, 3, 4]


    def test_get_pending_task_indices_with_all_completed(self):
        """Should return empty list when all completed"""
        # Arrange
        project = Project("my-project")
        content = "- [x] First\n- [x] Second"
        spec = SpecContent(project, content)

        # Act
        indices = spec.get_pending_task_indices()

        # Assert
        assert indices == []

    def test_get_pending_task_indices_with_no_tasks(self):
        """Should return empty list when no tasks"""
        # Arrange
        project = Project("my-project")
        content = "# No tasks"
        spec = SpecContent(project, content)

        # Act
        indices = spec.get_pending_task_indices()

        # Assert
        assert indices == []


class TestSpecContentToMarkdown:
    """Test suite for SpecContent.to_markdown method"""

    def test_to_markdown_converts_all_tasks(self):
        """Should convert all tasks to markdown"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] First\n- [x] Second\n- [ ] Third"
        spec = SpecContent(project, content)

        # Act
        markdown = spec.to_markdown()

        # Assert
        expected = "- [ ] First\n- [x] Second\n- [ ] Third"
        assert markdown == expected

    def test_to_markdown_with_empty_spec(self):
        """Should return empty string for spec with no tasks"""
        # Arrange
        project = Project("my-project")
        content = ""
        spec = SpecContent(project, content)

        # Act
        markdown = spec.to_markdown()

        # Assert
        assert markdown == ""

    def test_to_markdown_with_single_task(self):
        """Should convert single task to markdown"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Only task"
        spec = SpecContent(project, content)

        # Act
        markdown = spec.to_markdown()

        # Assert
        assert markdown == "- [ ] Only task"


class TestSpecContentIntegration:
    """Integration tests for SpecContent with realistic scenarios"""

    def test_full_workflow_with_realistic_spec(self):
        """Should handle realistic spec file content"""
        # Arrange
        project = Project("real-project")
        content = """# Project Specification

This project aims to build a feature-rich application.

## Tasks

- [x] Setup project structure
- [x] Configure CI/CD pipeline
- [ ] Implement authentication
- [ ] Add user management
- [ ] Create API endpoints
- [ ] Write unit tests
- [ ] Deploy to staging

## Notes

Remember to update documentation.
"""
        spec = SpecContent(project, content)

        # Act & Assert - Task counts
        assert spec.total_tasks == 7
        assert spec.completed_tasks == 2
        assert spec.pending_tasks == 5

        # Act & Assert - Get specific task
        task3 = spec.get_task_by_index(3)
        assert task3.description == "Implement authentication"
        assert task3.is_completed is False

        # Act & Assert - Get next available
        next_task = spec.get_next_available_task()
        assert next_task.index == 3
        assert next_task.description == "Implement authentication"

        # Act & Assert - Get pending indices
        pending_indices = spec.get_pending_task_indices()
        assert 3 in pending_indices
        assert 4 in pending_indices
        assert 5 in pending_indices

    def test_updating_task_completion_status(self):
        """Should be able to modify task completion and regenerate markdown"""
        # Arrange
        project = Project("my-project")
        content = "- [ ] Task 1\n- [ ] Task 2\n- [ ] Task 3"
        spec = SpecContent(project, content)

        # Act - Mark second task as completed
        spec.tasks[1].is_completed = True
        markdown = spec.to_markdown()

        # Assert
        expected = "- [ ] Task 1\n- [x] Task 2\n- [ ] Task 3"
        assert markdown == expected
        assert spec.completed_tasks == 1
        assert spec.pending_tasks == 2
