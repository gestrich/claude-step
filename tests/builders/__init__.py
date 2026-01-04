"""Test data builders for ClaudeChain tests

This module provides builder pattern helpers for creating complex test data.
Builders simplify test setup and improve readability by providing fluent interfaces
with sensible defaults.

Example usage:
    config = ConfigBuilder()
        .with_assignee("alice")
        .build()
"""

from tests.builders.config_builder import ConfigBuilder
from tests.builders.pr_data_builder import PRDataBuilder
from tests.builders.artifact_builder import (
    ArtifactBuilder,
    TaskMetadataBuilder,
    TaskMetadata,
    ProjectArtifact,
)
from tests.builders.spec_file_builder import SpecFileBuilder

__all__ = [
    "ConfigBuilder",
    "PRDataBuilder",
    "ArtifactBuilder",
    "TaskMetadataBuilder",
    "TaskMetadata",
    "ProjectArtifact",
    "SpecFileBuilder",
]
