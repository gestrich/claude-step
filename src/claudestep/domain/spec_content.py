"""Domain models for spec.md content parsing"""

import re
from dataclasses import dataclass
from typing import List, Optional

from claudestep.domain.project import Project


@dataclass
class SpecTask:
    """Domain model for a task in spec.md"""

    index: int  # 1-based position in file
    description: str
    is_completed: bool
    raw_line: str  # Original markdown line

    @classmethod
    def from_markdown_line(cls, line: str, index: int) -> Optional['SpecTask']:
        """Parse task from markdown checklist line

        Args:
            line: Markdown line to parse (e.g., "- [ ] Task description")
            index: Task index (1-based)

        Returns:
            SpecTask instance or None if line doesn't match task pattern
        """
        # Pattern: "- [ ]" or "- [x]" or "- [X]"
        match = re.match(r'^\s*- \[([xX ])\]\s*(.+)$', line)
        if not match:
            return None

        checkbox, description = match.groups()
        is_completed = checkbox.lower() == 'x'

        return cls(
            index=index,
            description=description.strip(),
            is_completed=is_completed,
            raw_line=line
        )

    def to_markdown_line(self) -> str:
        """Convert task back to markdown format

        Returns:
            Markdown string like "- [ ] Task description" or "- [x] Task description"
        """
        checkbox = "[x]" if self.is_completed else "[ ]"
        return f"- {checkbox} {self.description}"


class SpecContent:
    """Domain model for parsed spec.md content"""

    def __init__(self, project: Project, content: str):
        """Initialize SpecContent

        Args:
            project: Project domain model
            content: Raw spec.md content
        """
        self.project = project
        self.content = content
        self._tasks: Optional[List[SpecTask]] = None

    @property
    def tasks(self) -> List[SpecTask]:
        """Lazily parse and return all tasks from spec

        Returns:
            List of SpecTask instances
        """
        if self._tasks is None:
            self._tasks = self._parse_tasks()
        return self._tasks

    def _parse_tasks(self) -> List[SpecTask]:
        """Parse all tasks from markdown content

        Returns:
            List of SpecTask instances
        """
        tasks = []
        task_index = 1

        for line in self.content.split('\n'):
            task = SpecTask.from_markdown_line(line, task_index)
            if task:
                tasks.append(task)
                task_index += 1

        return tasks

    @property
    def total_tasks(self) -> int:
        """Count total tasks

        Returns:
            Number of tasks in spec
        """
        return len(self.tasks)

    @property
    def completed_tasks(self) -> int:
        """Count completed tasks

        Returns:
            Number of completed tasks
        """
        return sum(1 for task in self.tasks if task.is_completed)

    @property
    def pending_tasks(self) -> int:
        """Count pending tasks

        Returns:
            Number of uncompleted tasks
        """
        return self.total_tasks - self.completed_tasks

    def get_task_by_index(self, index: int) -> Optional[SpecTask]:
        """Get task by 1-based index

        Args:
            index: Task index (1-based)

        Returns:
            SpecTask instance or None if index out of range
        """
        return self.tasks[index - 1] if 0 < index <= len(self.tasks) else None

    def get_next_available_task(self, skip_indices: Optional[set] = None) -> Optional[SpecTask]:
        """Find the next uncompleted task

        Args:
            skip_indices: Optional set of task indices to skip (1-based)

        Returns:
            Next available SpecTask or None if all tasks completed
        """
        skip_indices = skip_indices or set()

        for task in self.tasks:
            if not task.is_completed and task.index not in skip_indices:
                return task

        return None

    def get_pending_task_indices(self, skip_indices: Optional[set] = None) -> List[int]:
        """Get indices of all pending tasks

        Args:
            skip_indices: Optional set of task indices to skip (1-based)

        Returns:
            List of task indices (1-based)
        """
        skip_indices = skip_indices or set()
        return [
            task.index
            for task in self.tasks
            if not task.is_completed and task.index not in skip_indices
        ]

    def to_markdown(self) -> str:
        """Convert all tasks back to markdown format

        Returns:
            Markdown string with all tasks
        """
        return "\n".join(task.to_markdown_line() for task in self.tasks)
