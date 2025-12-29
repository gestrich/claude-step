"""Abstract interface for metadata storage operations

This module defines the MetadataStore abstract interface that all metadata
storage backends must implement. This allows ClaudeStep to switch between
different storage strategies (e.g., GitHub branch-based, local files, etc.)
without changing application logic.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from claudestep.domain.models import HybridProjectMetadata


class MetadataStore(ABC):
    """Abstract interface for metadata storage operations

    This interface defines the contract that all metadata storage backends
    must implement. It provides CRUD operations for project metadata using
    the Hybrid model (schema version 2.0).

    Implementations should handle:
    - Serialization/deserialization of HybridProjectMetadata
    - Concurrency control (optimistic locking, retries)
    - Error handling and logging
    - Storage-specific optimizations

    Example implementations:
    - GitHubMetadataStore: Branch-based storage using GitHub Contents API
    - LocalMetadataStore: File-based storage for testing
    """

    @abstractmethod
    def save_project(self, project: HybridProjectMetadata) -> None:
        """Save or update project metadata

        Args:
            project: HybridProjectMetadata instance to save

        Raises:
            GitHubAPIError: If storage operation fails
            ValueError: If project data is invalid
        """
        pass

    @abstractmethod
    def get_project(self, project_name: str) -> Optional[HybridProjectMetadata]:
        """Get project metadata by name

        Args:
            project_name: Name of the project

        Returns:
            HybridProjectMetadata instance or None if not found

        Raises:
            GitHubAPIError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_all_projects(self) -> List[HybridProjectMetadata]:
        """Get metadata for all projects

        Returns:
            List of HybridProjectMetadata instances (may be empty)

        Raises:
            GitHubAPIError: If storage operation fails
        """
        pass

    @abstractmethod
    def list_project_names(self) -> List[str]:
        """List names of all projects

        This is a lighter-weight operation than get_all_projects() as it
        doesn't require reading and deserializing project metadata.

        Returns:
            List of project names (may be empty)

        Raises:
            GitHubAPIError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_projects_modified_since(self, date: datetime) -> List[HybridProjectMetadata]:
        """Get projects modified after a specific date

        This is used by the statistics command to filter projects by
        activity in a specific time period (e.g., last 7 days, last 30 days).

        Args:
            date: Datetime threshold (projects modified after this date)

        Returns:
            List of HybridProjectMetadata instances (may be empty)

        Raises:
            GitHubAPIError: If storage operation fails
        """
        pass

    @abstractmethod
    def project_exists(self, project_name: str) -> bool:
        """Check if a project exists

        This is a lighter-weight operation than get_project() as it doesn't
        require reading and deserializing project metadata.

        Args:
            project_name: Name of the project

        Returns:
            True if project exists, False otherwise

        Raises:
            GitHubAPIError: If storage operation fails
        """
        pass

    @abstractmethod
    def delete_project(self, project_name: str) -> None:
        """Delete project metadata

        This operation should be used with caution as it permanently removes
        all metadata for a project.

        Args:
            project_name: Name of the project to delete

        Raises:
            GitHubAPIError: If storage operation fails
            ValueError: If project doesn't exist
        """
        pass
