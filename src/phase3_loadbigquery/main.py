"""
BigQuery Loader Cloud Function (2nd gen)

Triggered by Cloud Storage events when files are finalized in the staging bucket.
Loads .ndjson.gz files to BigQuery and optionally deletes the source file.
"""

import os
import logging
from google.cloud import bigquery
from google.cloud import storage

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET_ID = os.environ.get("DATASET_ID", "github_archive")
TABLE_ID = os.environ.get("TABLE_ID", "github_events")
DELETE_AFTER_LOAD = os.environ.get("DELETE_AFTER_LOAD", "true").lower() == "true"

# Clients
bq_client = bigquery.Client(project=PROJECT_ID)
storage_client = storage.Client(project=PROJECT_ID)


def load_to_bigquery(data, context):
    """
    Cloud Function entry point.

    Triggered by GCS object finalized event via Eventarc.
    Uses background event format (data, context).

    Args:
        data: The event data containing bucket and file info
        context: The event context (event_id, timestamp, etc.)

    Returns:
        dict with status and message
    """
    # Log context for debugging
    logger.info(f"Event ID: {context.event_id}, Type: {context.event_type}")

    bucket_name = data.get("bucket")
    file_name = data.get("name")
    file_size = data.get("size", "unknown")

    logger.info(f"Processing event: bucket={bucket_name}, file={file_name}, size={file_size}")

    # Validate file extension
    if not file_name.endswith(".ndjson.gz"):
        logger.info(f"Skipping {file_name} - not a .ndjson.gz file")
        return {"status": "skipped", "reason": "invalid_extension"}

    # Only process files in processed/ prefix
    if not file_name.startswith("processed/"):
        logger.info(f"Skipping {file_name} - not in processed/ prefix")
        return {"status": "skipped", "reason": "invalid_prefix"}

    # Construct URIs
    gcs_uri = f"gs://{bucket_name}/{file_name}"
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    logger.info(f"Loading {gcs_uri} to {table_ref}")

    try:
        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            ignore_unknown_values=True,  # Skip fields not in table schema
            # Schema already exists in table - no autodetect needed
            # BigQuery automatically handles gzip compression
        )

        # Start load job
        load_job = bq_client.load_table_from_uri(
            gcs_uri,
            table_ref,
            job_config=job_config,
        )

        # Wait for completion
        result = load_job.result()

        logger.info(f"Load job completed: {load_job.job_id}")
        logger.info(f"Loaded {result.output_rows} rows")

        # Delete source file after successful load
        if DELETE_AFTER_LOAD:
            try:
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(file_name)
                blob.delete()
                logger.info(f"Deleted source file: {file_name}")
            except Exception as delete_error:
                logger.warning(f"Failed to delete source file: {delete_error}")
                # Don't fail the function if delete fails

        return {
            "status": "success",
            "job_id": load_job.job_id,
            "rows_loaded": result.output_rows,
            "source_file": file_name,
        }

    except Exception as e:
        logger.error(f"Failed to load {gcs_uri}: {e}")
        raise  # Re-raise to trigger retry policy
