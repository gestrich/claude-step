"""Builder for creating test artifact and metadata data"""

from typing import Optional
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class TaskMetadata:
    """Test version of TaskMetadata for builder pattern"""
    task_index: int
    task_description: str
    project: str
    branch_name: str
    assignee: str
    created_at: datetime
    workflow_run_id: int
    pr_number: int
    main_task_cost_usd: float = 0.0
    pr_summary_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


@dataclass
class ProjectArtifact:
    """Test version of ProjectArtifact for builder pattern"""
    artifact_id: int
    artifact_name: str
    workflow_run_id: int
    metadata: Optional[TaskMetadata] = None

    @property
    def task_index(self) -> Optional[int]:
        """Convenience accessor for task index"""
        if self.metadata:
            return self.metadata.task_index
        # Fallback: parse from name
        import re
        match = re.search(r'-(\d+)\.json$', self.artifact_name)
        return int(match.group(1)) if match else None


class TaskMetadataBuilder:
    """Fluent interface for creating TaskMetadata objects

    Example:
        metadata = TaskMetadataBuilder()
            .with_task(3, "Implement feature")
            .with_project("my-project")
            .with_assignee("alice")
            .build()
    """

    def __init__(self):
        """Initialize builder with default values"""
        self._task_index: int = 1
        self._task_description: str = "Default task"
        self._project: str = "sample-project"
        self._branch_name: str = "claude-chain-sample-project-1"
        self._assignee: str = "alice"
        self._created_at: datetime = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        self._workflow_run_id: int = 123456789
        self._pr_number: int = 100
        self._main_task_cost_usd: float = 0.0
        self._pr_summary_cost_usd: float = 0.0
        self._total_cost_usd: float = 0.0

    def with_task(self, index: int, description: str) -> "TaskMetadataBuilder":
        """Set task index and description

        Automatically updates branch name to match.

        Args:
            index: Task index (1-based)
            description: Task description

        Returns:
            Self for method chaining
        """
        self._task_index = index
        self._task_description = description
        self._branch_name = f"claude-chain-{self._project}-{index}"
        return self

    def with_project(self, project: str) -> "TaskMetadataBuilder":
        """Set project name

        Automatically updates branch name to match.

        Args:
            project: Project name

        Returns:
            Self for method chaining
        """
        self._project = project
        self._branch_name = f"claude-chain-{project}-{self._task_index}"
        return self

    def with_assignee(self, assignee: str) -> "TaskMetadataBuilder":
        """Set assignee username

        Args:
            assignee: Assignee username

        Returns:
            Self for method chaining
        """
        self._assignee = assignee
        return self

    def with_branch_name(self, branch_name: str) -> "TaskMetadataBuilder":
        """Set branch name (overrides auto-generated name)

        Args:
            branch_name: Custom branch name

        Returns:
            Self for method chaining
        """
        self._branch_name = branch_name
        return self

    def with_pr_number(self, pr_number: int) -> "TaskMetadataBuilder":
        """Set PR number

        Args:
            pr_number: PR number

        Returns:
            Self for method chaining
        """
        self._pr_number = pr_number
        return self

    def with_workflow_run_id(self, run_id: int) -> "TaskMetadataBuilder":
        """Set workflow run ID

        Args:
            run_id: GitHub Actions workflow run ID

        Returns:
            Self for method chaining
        """
        self._workflow_run_id = run_id
        return self

    def with_costs(
        self,
        main_task: float = 0.0,
        pr_summary: float = 0.0
    ) -> "TaskMetadataBuilder":
        """Set cost information

        Args:
            main_task: Main task cost in USD
            pr_summary: PR summary cost in USD

        Returns:
            Self for method chaining
        """
        self._main_task_cost_usd = main_task
        self._pr_summary_cost_usd = pr_summary
        self._total_cost_usd = main_task + pr_summary
        return self

    def with_created_at(self, created_at: datetime) -> "TaskMetadataBuilder":
        """Set creation timestamp

        Args:
            created_at: Creation datetime

        Returns:
            Self for method chaining
        """
        self._created_at = created_at
        return self

    def build(self) -> TaskMetadata:
        """Build and return the TaskMetadata object

        Returns:
            Complete TaskMetadata object
        """
        return TaskMetadata(
            task_index=self._task_index,
            task_description=self._task_description,
            project=self._project,
            branch_name=self._branch_name,
            assignee=self._assignee,
            created_at=self._created_at,
            workflow_run_id=self._workflow_run_id,
            pr_number=self._pr_number,
            main_task_cost_usd=self._main_task_cost_usd,
            pr_summary_cost_usd=self._pr_summary_cost_usd,
            total_cost_usd=self._total_cost_usd
        )


class ArtifactBuilder:
    """Fluent interface for creating ProjectArtifact objects

    Example:
        artifact = ArtifactBuilder()
            .with_id(123)
            .with_task(3, "Implement feature", "my-project")
            .with_metadata()
            .build()
    """

    def __init__(self):
        """Initialize builder with default values"""
        self._artifact_id: int = 12345
        self._artifact_name: str = "task-metadata-sample-project-1.json"
        self._workflow_run_id: int = 123456789
        self._metadata: Optional[TaskMetadata] = None
        self._metadata_builder: Optional[TaskMetadataBuilder] = None

    def with_id(self, artifact_id: int) -> "ArtifactBuilder":
        """Set artifact ID

        Args:
            artifact_id: Artifact ID

        Returns:
            Self for method chaining
        """
        self._artifact_id = artifact_id
        return self

    def with_name(self, name: str) -> "ArtifactBuilder":
        """Set artifact name

        Args:
            name: Artifact name (e.g., "task-metadata-project-3.json")

        Returns:
            Self for method chaining
        """
        self._artifact_name = name
        return self

    def with_task(
        self,
        task_index: int,
        description: str = None,
        project: str = "sample-project"
    ) -> "ArtifactBuilder":
        """Set artifact name based on task information

        Args:
            task_index: Task index (1-based)
            description: Task description (optional, only affects metadata)
            project: Project name

        Returns:
            Self for method chaining
        """
        self._artifact_name = f"task-metadata-{project}-{task_index}.json"

        # Also prepare metadata builder if we'll create metadata
        if self._metadata_builder is None:
            self._metadata_builder = TaskMetadataBuilder()

        self._metadata_builder.with_task(
            task_index,
            description or f"Task {task_index}"
        ).with_project(project)

        return self

    def with_workflow_run_id(self, run_id: int) -> "ArtifactBuilder":
        """Set workflow run ID

        Args:
            run_id: GitHub Actions workflow run ID

        Returns:
            Self for method chaining
        """
        self._workflow_run_id = run_id
        return self

    def with_metadata(self, metadata: Optional[TaskMetadata] = None) -> "ArtifactBuilder":
        """Add metadata to the artifact

        If metadata is None, builds metadata from the current metadata builder state.

        Args:
            metadata: TaskMetadata object (or None to auto-build)

        Returns:
            Self for method chaining
        """
        if metadata is not None:
            self._metadata = metadata
        else:
            # Build from metadata builder if available
            if self._metadata_builder is None:
                self._metadata_builder = TaskMetadataBuilder()

            # Make sure workflow_run_id matches
            self._metadata_builder.with_workflow_run_id(self._workflow_run_id)
            self._metadata = self._metadata_builder.build()

        return self

    def build(self) -> ProjectArtifact:
        """Build and return the ProjectArtifact object

        Returns:
            Complete ProjectArtifact object
        """
        return ProjectArtifact(
            artifact_id=self._artifact_id,
            artifact_name=self._artifact_name,
            workflow_run_id=self._workflow_run_id,
            metadata=self._metadata
        )

    @staticmethod
    def simple(artifact_id: int = 12345, task_index: int = 1) -> ProjectArtifact:
        """Quick helper for creating a simple artifact without metadata

        Args:
            artifact_id: Artifact ID
            task_index: Task index for naming

        Returns:
            ProjectArtifact without metadata
        """
        return (ArtifactBuilder()
                .with_id(artifact_id)
                .with_task(task_index)
                .build())

    @staticmethod
    def with_full_metadata(
        artifact_id: int = 12345,
        task_index: int = 1,
        project: str = "sample-project"
    ) -> ProjectArtifact:
        """Quick helper for creating an artifact with complete metadata

        Args:
            artifact_id: Artifact ID
            task_index: Task index
            project: Project name

        Returns:
            ProjectArtifact with full metadata
        """
        return (ArtifactBuilder()
                .with_id(artifact_id)
                .with_task(task_index, f"Task {task_index}", project)
                .with_metadata()
                .build())
