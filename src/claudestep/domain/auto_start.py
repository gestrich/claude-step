"""Domain models for auto-start detection"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ProjectChangeType(Enum):
    """Type of change detected for a project spec file"""

    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class AutoStartProject:
    """Domain model representing a project detected for potential auto-start

    Attributes:
        name: Project name extracted from spec path
        change_type: Type of change (added, modified, deleted)
        spec_path: Path to the spec.md file (e.g., claude-step/project-name/spec.md)
    """

    name: str
    change_type: ProjectChangeType
    spec_path: str

    def __repr__(self) -> str:
        """String representation for debugging"""
        return f"AutoStartProject(name='{self.name}', change_type={self.change_type.value}, spec_path='{self.spec_path}')"


@dataclass
class AutoStartDecision:
    """Domain model representing a decision about whether to auto-trigger a project

    Attributes:
        project: The project being evaluated
        should_trigger: Whether the workflow should be triggered for this project
        reason: Human-readable reason for the decision
    """

    project: AutoStartProject
    should_trigger: bool
    reason: str

    def __repr__(self) -> str:
        """String representation for debugging"""
        action = "TRIGGER" if self.should_trigger else "SKIP"
        return f"AutoStartDecision({action}: {self.project.name} - {self.reason})"
