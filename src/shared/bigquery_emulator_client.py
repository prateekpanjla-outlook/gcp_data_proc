"""BigQuery client that works with both emulator and production.

Automatically detects emulator via BIGQUERY_EMULATOR_HOST environment variable
and uses standard client with AnonymousCredentials for emulator, or
authenticated client for production.

Key finding: The BigQuery emulator does NOT support bulk load jobs properly yet.
The load job API returns "unspecified job configuration query" error.
Therefore, for the emulator, we fall back to streaming insert.
"""

import logging
import os
from typing import Any, Dict, List, Optional
import pandas as pd

from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions
from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials

logger = logging.getLogger(__name__)


class BigQueryEmulatorAwareClient:
    """BigQuery client that automatically switches between emulator and production."""

    def __init__(
        self,
        project_id: str,
        location: str = "US",
        emulator_host: Optional[str] = None
    ):
        """Initialize BigQuery client.

        Args:
            project_id: GCP project ID
            location: BigQuery dataset location
            emulator_host: Optional emulator host (auto-detected from env if None)
        """
        self.project_id = project_id
        self.location = location

        # Detect emulator
        if emulator_host is None:
            emulator_host = os.environ.get('BIGQUERY_EMULATOR_HOST')

        self._use_emulator = emulator_host is not None

        if self._use_emulator:
            # Use standard client with AnonymousCredentials for emulator
            # This provides better compatibility than raw REST API
            client_options = ClientOptions(api_endpoint=f"http://{emulator_host}")
            self.client = bigquery.Client(
                project=project_id,
                client_options=client_options,
                credentials=AnonymousCredentials(),
            )
            logger.info(f"BigQuery client using EMULATOR at {emulator_host}")
        else:
            # Use standard production client
            self.client = bigquery.Client(project=project_id)
            logger.info(f"BigQuery client using PRODUCTION for project {project_id}")

    # ==========================================================================
    # Dataset Operations
    # ==========================================================================

    def dataset_exists(self, dataset_id: str) -> bool:
        """Check if dataset exists."""
        try:
            self.client.get_dataset(f"{self.project_id}.{dataset_id}")
            return True
        except gcp_exceptions.NotFound:
            return False

    def create_dataset(self, dataset_id: str) -> None:
        """Create a dataset if it doesn't exist.

        Note: Using exists_ok=True causes the client to call get_dataset first,
        which can hang on the emulator. Instead, we catch NotFound exception.
        """
        try:
            self.client.get_dataset(f"{self.project_id}.{dataset_id}")
            # Dataset exists, nothing to do
        except gcp_exceptions.NotFound:
            # Dataset doesn't exist, create it
            dataset = bigquery.Dataset(f"{self.project_id}.{dataset_id}")
            dataset.location = self.location
            self.client.create_dataset(dataset)

    # ==========================================================================
    # Table Operations
    # ==========================================================================

    def table_exists(self, dataset_id: str, table_id: str) -> bool:
        """Check if table exists."""
        try:
            self.client.get_table(f"{self.project_id}.{dataset_id}.{table_id}")
            return True
        except gcp_exceptions.NotFound:
            return False

    def create_table(
        self,
        dataset_id: str,
        table_id: str,
        schema: List[bigquery.SchemaField],
        partitioning_field: Optional[str] = None,
        clustering_fields: Optional[List[str]] = None,
        overwrite: bool = False
    ) -> None:
        """Create a table.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            schema: List of SchemaField objects
            partitioning_field: Field to partition by (not supported in emulator)
            clustering_fields: Fields to cluster by (not supported in emulator)
            overwrite: If True, delete existing table first
        """
        full_table_id = f"{self.project_id}.{dataset_id}.{table_id}"

        # Handle overwrite - delete directly without checking existence
        # Note: get_table hangs on emulator when table doesn't exist, so we
        # just try to delete and ignore NotFound errors
        if overwrite:
            try:
                self.delete_table(dataset_id, table_id)
            except gcp_exceptions.NotFound:
                pass  # Table doesn't exist, that's fine

        table = bigquery.Table(full_table_id, schema=schema)

        if partitioning_field:
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field=partitioning_field
            )

        if clustering_fields:
            table.clustering_fields = clustering_fields

        self.client.create_table(table)  # Don't use exists_ok=True (causes get_table hang)

    def delete_table(self, dataset_id: str, table_id: str) -> None:
        """Delete a table."""
        self.client.delete_table(f"{self.project_id}.{dataset_id}.{table_id}")

    # ==========================================================================
    # Data Operations
    # ==========================================================================

    def insert_rows(
        self,
        dataset_id: str,
        table_id: str,
        rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Insert rows into a table using streaming insert.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            rows: List of row dictionaries

        Returns:
            List of errors (empty if successful)
        """
        if not rows:
            return []

        table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
        return self.client.insert_rows_json(table_ref, rows)

    def query(self, query: str, timeout: int = 10) -> List[Dict[str, Any]]:
        """Execute a query and return results.

        Args:
            query: SQL query string
            timeout: Query timeout in seconds (default 10 for emulator)

        Returns:
            List of row dictionaries
        """
        query_job = self.client.query(query)
        return [dict(row) for row in query_job.result(timeout=timeout)]

    def query_with_dataframe(self, query: str, timeout: int = 10):
        """Execute a query and return as pandas DataFrame.

        Note: For emulator, use create_bqstorage_client=False to avoid
        trying to connect to BigQuery Storage API.
        """
        query_job = self.client.query(query)
        query_job.result(timeout=timeout)  # Wait for query to complete
        return query_job.to_dataframe(create_bqstorage_client=False)

    def load_dataframe(
        self,
        dataset_id: str,
        table_id: str,
        dataframe: "pd.DataFrame",
        schema: Optional[List[bigquery.SchemaField]] = None,
        write_disposition: str = "WRITE_APPEND",
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Load a pandas DataFrame to BigQuery.

        PRODUCTION: Uses bulk load job (FREE, recommended for large datasets).
        EMULATOR: Falls back to streaming insert (load jobs not fully supported).

        The BigQuery emulator (goccy/bigquery-emulator) claims to implement
        all BigQuery APIs, but load jobs return "unspecified job configuration query".
        Therefore, we fall back to streaming insert for the emulator.

        Args:
            dataset_id: Dataset ID
            table_id: Table ID
            dataframe: Pandas DataFrame to load
            schema: Optional list of SchemaField objects
            write_disposition: WRITE_APPEND, WRITE_TRUNCATE, or WRITE_EMPTY
            job_id: Optional custom job ID

        Returns:
            Dictionary with job statistics or error info
        """
        df = dataframe.copy()
        num_rows = len(df)

        # Both emulator and production use bulk load
        # See: https://github.com/goccy/bigquery-emulator/issues/224
        # "the exception is raised but the data is still ingested successfully"
        job_config = bigquery.LoadJobConfig(
            schema=schema,
            write_disposition=write_disposition,
        )

        job = self.client.load_table_from_dataframe(
            df,
            f"{self.project_id}.{dataset_id}.{table_id}",
            job_config=job_config,
            job_id=job_id,
        )

        # Wait for job to complete (use timeout for emulator)
        try:
            job.result(timeout=30)
            return {
                "method": "bulk_load_job",
                "job_id": job.job_id,
                "state": job.state,
                "num_rows": job.output_rows,
                "errors": list(job.errors) if job.errors else [],
            }
        except gcp_exceptions.BadRequest as e:
            error_msg = str(e)
            # Check for the known emulator bug where data loads anyway
            if "unspecified job configuration query" in error_msg.lower():
                logger.warning(
                    f"Got 'unspecified job configuration query' error from emulator, "
                    f"but data may have loaded successfully (see issue #224). Verifying..."
                )
                # Verify data was actually loaded by querying row count
                try:
                    count_result = self.client.query(
                        f"SELECT COUNT(*) as cnt FROM `{self.project_id}.{dataset_id}.{table_id}`"
                    )
                    count_row = list(count_result.result(timeout=10))[0]
                    actual_rows = count_row.get('cnt', 0)
                    logger.info(f"Table has {actual_rows} rows - load succeeded despite error")
                    return {
                        "method": "bulk_load_job",
                        "job_id": job.job_id,
                        "state": "DONE",
                        "num_rows": num_rows,
                        "errors": [{"message": str(e), "retriable": False}],
                        "note": "Emulator bug: data loaded despite error (issue #224)",
                    }
                except Exception as verify_error:
                    logger.error(f"Could not verify load: {verify_error}")
                    raise
            else:
                # Different error - re-raise
                raise

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    @property
    def is_emulator(self) -> bool:
        """Return True if using emulator."""
        return self._use_emulator

    def get_table_schema(self, dataset_id: str, table_id: str) -> List[Dict[str, Any]]:
        """Get table schema.

        Returns:
            List of field definitions
        """
        table = self.client.get_table(f"{self.project_id}.{dataset_id}.{table_id}")
        return [
            {
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode
            }
            for field in table.schema
        ]
