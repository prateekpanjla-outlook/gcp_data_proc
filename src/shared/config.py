"""Shared configuration management for the pipeline."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BigQueryConfig:
    """BigQuery configuration."""
    project_id: str = field(default_factory=lambda: os.getenv("PROJECT_ID", ""))
    dataset_id: str = field(default_factory=lambda: os.getenv("DATASET_ID", ""))
    table_id: str = field(default_factory=lambda: os.getenv("TABLE_ID", ""))
    location: str = "US"

    @property
    def full_table_path(self) -> str:
        """Returns the full table path in format project.dataset.table."""
        return f"{self.project_id}.{self.dataset_id}.{self.table_id}"


@dataclass
class StorageConfig:
    """Cloud Storage configuration."""
    bucket_name: str = field(default_factory=lambda: os.getenv("BUCKET_NAME", ""))
    project_id: str = field(default_factory=lambda: os.getenv("PROJECT_ID", ""))
    raw_prefix: str = "raw"
    processed_prefix: str = "processed"
    error_prefix: str = "errors"

    def get_raw_path(self, source: str, filename: str) -> str:
        """Get the full path for raw files."""
        return f"{source}/{self.raw_prefix}/{filename}"

    def get_processed_path(self, source: str, filename: str) -> str:
        """Get the full path for processed files."""
        return f"{source}/{self.processed_prefix}/{filename}"

    def get_error_path(self, source: str, filename: str) -> str:
        """Get the full path for error files."""
        return f"{source}/{self.error_prefix}/{filename}"


@dataclass
class CloudRunConfig:
    """Cloud Run configuration."""
    service_name: str = field(default_factory=lambda: os.getenv("K_SERVICE", "unknown"))
    revision: str = field(default_factory=lambda: os.getenv("K_REVISION", "unknown"))
    configuration: str = field(default_factory=lambda: os.getenv("K_CONFIGURATION", "unknown"))

    @property
    def is_cloud_run(self) -> bool:
        """Check if running in Cloud Run."""
        return bool(self.service_name and self.service_name != "unknown")


@dataclass
class PipelineConfig:
    """Main pipeline configuration combining all configs."""

    def __init__(self):
        """Initialize all configurations from environment variables."""
        self.bigquery = BigQueryConfig()
        self.storage = StorageConfig()
        self.cloud_run = CloudRunConfig()

        # Processing settings
        self.batch_size = int(os.getenv("BATCH_SIZE", "500"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.log_level = os.getenv("LOG_LEVEL", "INFO")

        # Source-specific settings
        self.source = os.getenv("DATA_SOURCE", "unknown")  # github-archive or hacker-news


def get_config() -> PipelineConfig:
    """Get the current pipeline configuration."""
    return PipelineConfig()
