"""
BigQuery Loader Service for GitHub Archive Phase 3.

Receives Eventarc events when processed files are written to staging bucket,
loads them into BigQuery, and deletes the source files on success.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any

from flask import Flask, request, jsonify
from google.cloud import bigquery, error_reporting
from google.cloud import storage

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ID = os.getenv('PROJECT_ID')
DATASET_ID = os.getenv('DATASET_ID')
TABLE_ID = os.getenv('TABLE_ID')
STAGING_BUCKET = os.getenv('STAGING_BUCKET')
PARTITION_EXPIRATION_DAYS = int(os.getenv('PARTITION_EXPIRATION_DAYS', '366'))

# BigQuery load configuration
LOAD_TIMEOUT_SECONDS = 600  # 10 minutes
WRITE_DISPOSITION = 'WRITE_APPEND'
CREATE_DISPOSITION = 'CREATE_IF_NEEDED'
SOURCE_FORMAT = 'NEWLINE_DELIMITED_JSON'

# Cloud Run configuration
HOST = '0.0.0.0'
PORT = int(os.getenv('PORT', '8080'))

# =============================================================================
# APP INITIALIZATION
# =============================================================================
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('bq-loader')

# Initialize BigQuery client
bq_client = bigquery.Client(project=PROJECT_ID)

# Initialize Storage client
storage_client = storage.Client()

# Error reporting (if available)
error_reporter = None
try:
    error_reporter = error_reporting.Client()
except Exception:
    pass


# =============================================================================
# HEALTH CHECK
# =============================================================================
@app.route('/', methods=['GET'])
@app.route('/health', methods=['GET'])
def health_check() -> tuple[Dict[str, Any], int]:
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'service': 'bq-loader',
        'project': PROJECT_ID,
        'dataset': f'{PROJECT_ID}.{DATASET_ID}',
        'table': TABLE_ID
    }), 200


@app.route('/ready', methods=['GET'])
def readiness_check() -> tuple[Dict[str, Any], int]:
    """Readiness check endpoint."""
    try:
        # Verify BigQuery access
        dataset = bq_client.get_dataset(f'{PROJECT_ID}.{DATASET_ID}')
        dataset.reload()  # Forces API call

        # Verify Storage access
        bucket = storage_client.bucket(STAGING_BUCKET)
        if not bucket.exists():
            raise Exception(f"Bucket {STAGING_BUCKET} not found")

        return jsonify({
            'ready': True,
            'checks': {
                'bigquery': 'ok',
                'storage': 'ok'
            }
        }), 200
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            'ready': False,
            'error': str(e)
        }), 503


# =============================================================================
# MAIN HANDLER (Eventarc trigger)
# =============================================================================
@app.route('/', methods=['POST'])
def load_file() -> tuple[Dict[str, Any], int]:
    """
    Handle Eventarc event for new processed files in staging bucket.

    Expected Cloud Storage event format:
    {
        "bucket": "bucket-name",
        "name": "processed/2026-03-07-1.ndjson.gz",
        "resourceState": "exists",
        "metageneration": "1"
    }
    """
    start_time = datetime.now()

    # Parse event payload
    try:
        event = request.get_json()
        if not event:
            return jsonify({'error': 'No event payload'}), 400
    except Exception as e:
        logger.error(f"Failed to parse event: {e}")
        return jsonify({'error': f'Invalid event payload: {e}'}), 400

    bucket = event.get('bucket')
    file_name = event.get('name')

    logger.info(f"Received Eventarc event: bucket={bucket}, file={file_name}")

    # Path filtering: Only process files in processed/ path
    if not file_name or not file_name.startswith('processed/'):
        logger.info(f"Ignoring file outside processed/ path: {file_name}")
        return jsonify({'status': 'ignored', 'reason': 'path_not_matching'}), 200

    # Extension filtering: Only process .ndjson.gz files
    if not file_name.endswith('.ndjson.gz'):
        logger.info(f"Ignoring non-ndjson.gz file: {file_name}")
        return jsonify({'status': 'ignored', 'reason': 'extension_not_matching'}), 200

    # Extract date partition from filename
    # Expected format: processed/YYYY-MM-DD-H.ndjson.gz
    date_partition = extract_date_partition(file_name)
    if not date_partition:
        return jsonify({'error': f'Could not extract date from filename: {file_name}'}), 400

    # Build GCS URI
    gcs_uri = f"gs://{bucket}/{file_name}"

    # Build full table reference with partition decorator
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}${date_partition}"

    logger.info(f"Loading into BigQuery: table={table_ref}, source={gcs_uri}")

    try:
        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.SOURCE_FORMAT_NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
            compression='GZIP',
            # Schema autodetect for first load, then we can lock it
            # autodetect=True
        )

        # Start load job
        load_job = bq_client.load_table_from_uri(
            gcs_uri,
            table_ref,
            job_config=job_config,
            project=PROJECT_ID
        )

        logger.info(f"Started BigQuery load job: {load_job.job_id}")

        # Wait for completion with timeout
        load_job.result(timeout=LOAD_TIMEOUT_SECONDS)

        # Check result
        if load_job.errors:
            error_msg = f"BigQuery load failed: {load_job.errors}"
            logger.error(error_msg)
            return jsonify({
                'status': 'error',
                'error': error_msg,
                'file_name': file_name
            }), 500

        # Get output statistics
        destination_table = bq_client.get_table(table_ref)
        rows_loaded = destination_table.num_rows

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(f"Load successful: rows={rows_loaded}, duration={duration:.2f}s")

        # Delete source file after successful load
        try:
            delete_source_file(bucket, file_name)
            logger.info(f"Deleted source file: {file_name}")
        except Exception as delete_error:
            logger.warning(f"Failed to delete source file: {delete_error}")
            # Continue despite delete failure

        return jsonify({
            'status': 'success',
            'file_name': file_name,
            'table_ref': table_ref,
            'rows_loaded': rows_loaded,
            'duration_seconds': round(duration, 2),
            'job_id': load_job.job_id
        }), 200

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        error_msg = f"Load processing error: {str(e)}"
        logger.error(error_msg)

        if error_reporter:
            error_reporter.report_exception()

        return jsonify({
            'status': 'error',
            'error': error_msg,
            'file_name': file_name,
            'duration_seconds': round(duration, 2)
        }), 500


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
def extract_date_partition(file_name: str) -> str:
    """
    Extract date partition from filename for BigQuery partition decorator.

    Expected format: processed/YYYY-MM-DD-H.ndjson.gz
    Output format: YYYYMMDD

    Args:
        file_name: GCS file name (e.g., 'processed/2026-03-07-1.ndjson.gz')

    Returns:
        Partition string (e.g., '20260307') or None if format doesn't match
    """
    import re
    from pathlib import Path

    # Extract just the filename from path
    filename = Path(file_name).name  # Gets '2026-03-07-1.ndjson.gz'

    # Parse: YYYY-MM-DD-H.ndjson.gz
    match = re.match(r'(\d{4})-(\d{2})-(\d{2})-\d+\.ndjson\.gz$', filename)
    if match:
        year, month, day = match.groups()
        return f"{year}{month}{day}"

    return None


def delete_source_file(bucket_name: str, file_name: str) -> None:
    """
    Delete a file from GCS after successful BigQuery load.

    Args:
        bucket_name: GCS bucket name
        file_name: GCS file path

    Raises:
        Exception: If deletion fails
    """
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    blob.delete()
    logger.info(f"Deleted: gs://{bucket_name}/{file_name}")


# =============================================================================
# ERROR HANDLERS
# =============================================================================
@app.errorhandler(404)
def not_found(error) -> tuple[Dict[str, Any], int]:
    """Handle 404 errors."""
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error) -> tuple[Dict[str, Any], int]:
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    if error_reporter:
        error_reporter.report_exception()
    return jsonify({'error': 'Internal server error'}), 500


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    logger.info(
        "Starting BigQuery Loader Service",
        project=PROJECT_ID,
        dataset=f'{PROJECT_ID}.{DATASET_ID}',
        table=TABLE_ID,
        staging_bucket=STAGING_BUCKET
    )

    app.run(host=HOST, port=PORT, debug=False)
