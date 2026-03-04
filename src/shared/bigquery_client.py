"""BigQuery client wrapper with error handling and retry logic."""

import logging
from typing import Any, Dict, List, Optional

import google.auth.exceptions
from google.cloud import bigquery
from google.cloud.bigquery import DatasetReference, Table, TableReference
from google.api_core import exceptions as gcp_exceptions
from google.api_core.retry import Retry

logger = logging.getLogger(__name__)


class BigQueryClient:
    """Wrapper around Google Cloud BigQuery client with enhanced functionality."""

    def __init__(
        self,
        project_id: str,
        location: str = "US",
        retry_attempts: int = 3
    ):
        """
        Initialize BigQuery client.

        Args:
            project_id: GCP project ID
            location: BigQuery dataset location
            retry_attempts: Number of retry attempts for transient failures
        """
        self.project_id = project_id
        self.location = location
        self.retry_attempts = retry_attempts

        try:
            self.client = bigquery.Client(project=project_id)
            logger.info(f"BigQuery client initialized for project: {project_id}")
        except google.auth.exceptions.DefaultCredentialsError as e:
            logger.error(f"Failed to initialize BigQuery client: {e}")
            raise

    def table_exists(self, dataset_id: str, table_id: str) -> bool:
        """Check if a table exists."""
        try:
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            self.client.get_table(table_ref)
            return True
        except gcp_exceptions.NotFound:
            return False
        except gcp_exceptions.ClientError as e:
            logger.error(f"Error checking table existence: {e}")
            raise

    def create_table(
        self,
        dataset_id: str,
        table_id: str,
        schema: List[bigquery.SchemaField],
        partitioning_field: Optional[str] = None,
        clustering_fields: Optional[List[str]] = None,
        partition_expiration_days: Optional[int] = None
    ) -> Table:
        """
        Create a BigQuery table with optional partitioning and clustering.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            schema: List of SchemaField objects
            partitioning_field: Field to partition by (typically a timestamp)
            clustering_fields: Fields to cluster by
            partition_expiration_days: Days before partitions expire

        Returns:
            Created Table object
        """
        table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
        table = Table(table_ref, schema=schema)

        if partitioning_field:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field=partitioning_field
            )

        if clustering_fields:
            table.clustering_fields = clustering_fields

        if partition_expiration_days:
            table.partition_expiration_days = partition_expiration_days

        try:
            table = self.client.create_table(table, exists_ok=True)
            logger.info(f"Table {table_ref} created successfully")
            return table
        except gcp_exceptions.ClientError as e:
            logger.error(f"Failed to create table {table_ref}: {e}")
            raise

    def insert_rows(
        self,
        dataset_id: str,
        table_id: str,
        rows: List[Dict[str, Any]],
        retry_on_failure: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Insert rows into a BigQuery table.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            rows: List of row dictionaries
            retry_on_failure: Whether to retry on transient failures

        Returns:
            List of errors (empty if successful)
        """
        if not rows:
            logger.warning("No rows to insert")
            return []

        table_ref = f"{self.project_id}.{dataset_id}.{table_id}"

        # Convert all values to BigQuery-compatible types
        converted_rows = []
        for row in rows:
            converted_row = self._convert_row_types(row)
            converted_rows.append(converted_row)

        errors = []
        attempt = 0

        while attempt <= self.retry_attempts if retry_on_failure else True:
            try:
                errors = self.client.insert_rows_json(table_ref, converted_rows, retry=None)

                if not errors:
                    logger.info(f"Successfully inserted {len(rows)} rows into {table_ref}")
                    return []
                else:
                    logger.warning(f"Insert errors: {len(errors)} rows failed")
                    return errors

            except gcp_exceptions.ServerError as e:
                attempt += 1
                if attempt > self.retry_attempts or not retry_on_failure:
                    logger.error(f"Server error after {attempt} attempts: {e}")
                    raise
                logger.warning(f"Retry {attempt}/{self.retry_attempts} after server error")

            except gcp_exceptions.ClientError as e:
                logger.error(f"Client error inserting rows: {e}")
                raise

        return errors

    def _convert_row_types(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Python types to BigQuery-compatible types."""
        converted = {}
        for key, value in row.items():
            if value is None:
                converted[key] = None
            elif isinstance(value, (str, int, float, bool)):
                converted[key] = value
            elif isinstance(value, list):
                # Convert lists to JSON for REPEATED fields or JSON type
                converted[key] = value
            elif isinstance(value, dict):
                # Convert dicts to JSON string for JSON fields
                import json
                converted[key] = json.dumps(value)
            else:
                # String fallback
                converted[key] = str(value)
        return converted

    def query(self, sql: str) -> bigquery.job.QueryJob:
        """
        Execute a SQL query.

        Args:
            sql: SQL query string

        Returns:
            QueryJob object
        """
        try:
            query_job = self.client.query(sql)
            logger.info(f"Query job {query_job.job_id} started")
            return query_job
        except gcp_exceptions.ClientError as e:
            logger.error(f"Query failed: {e}")
            raise

    def get_table_info(self, dataset_id: str, table_id: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a table.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID

        Returns:
            Dictionary with table information or None if not found
        """
        try:
            table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
            table = self.client.get_table(table_ref)
            return {
                "table_id": table.table_id,
                "num_rows": table.num_rows,
                "num_bytes": table.num_bytes,
                "created": table.created,
                "modified": table.modified,
                "partitioning": table.time_partitioning,
                "clustering": table.clustering_fields,
            }
        except gcp_exceptions.NotFound:
            logger.warning(f"Table {dataset_id}.{table_id} not found")
            return None
        except gcp_exceptions.ClientError as e:
            logger.error(f"Error getting table info: {e}")
            raise
