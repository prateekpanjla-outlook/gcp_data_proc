"""
Cloud Run Service entry point for GitHub Archive Phase 2 processing.

Receives Eventarc events when files land in the landing bucket,
validates, transforms, and writes them to the staging bucket.
"""

import os
import json
import time
from typing import Dict, Any

from flask import Flask, request, jsonify
from google.cloud import error_reporting

from processors.file_processor import GitHubArchiveFileProcessor
from utils.logger import get_logger


# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ID = os.getenv('PROJECT_ID')
LANDING_BUCKET = os.getenv('LANDING_BUCKET')
STAGING_BUCKET = os.getenv('STAGING_BUCKET')
FILE_SIZE_THRESHOLD_MB = int(os.getenv('FILE_SIZE_THRESHOLD_MB', '500'))
CHUNKSIZE = int(os.getenv('CHUNKSIZE', '100000'))

# Cloud Run requires 0.0.0.0 binding
HOST = '0.0.0.0'
PORT = int(os.getenv('PORT', '8080'))

# =============================================================================
# APP INITIALIZATION
# =============================================================================
app = Flask(__name__)

# Initialize logger
logger = get_logger('phase2-processor')

# Initialize processor
processor = GitHubArchiveFileProcessor(
    project_id=PROJECT_ID,
    landing_bucket=LANDING_BUCKET,
    staging_bucket=STAGING_BUCKET,
    chunksize=CHUNKSIZE,
    file_size_threshold_mb=FILE_SIZE_THRESHOLD_MB,
    logger=logger
)

# Error reporting
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
        'service': 'github-archive-processor',
        'project': PROJECT_ID,
        'landing_bucket': LANDING_BUCKET,
        'staging_bucket': STAGING_BUCKET
    }), 200


# =============================================================================
# READINESS PROBE
# =============================================================================
@app.route('/ready', methods=['GET'])
def readiness_check() -> tuple[Dict[str, Any], int]:
    """Readiness check endpoint."""
    checks = {
        'config_valid': all([
            PROJECT_ID,
            LANDING_BUCKET,
            STAGING_BUCKET
        ])
    }

    ready = all(checks.values())

    status_code = 200 if ready else 503
    return jsonify({
        'ready': ready,
        'checks': checks
    }), status_code


# =============================================================================
# MAIN PROCESSING HANDLER (Eventarc trigger)
# =============================================================================
@app.route('/', methods=['POST'])
def process_file_event() -> tuple[Dict[str, Any], int]:
    """
    Handle Eventarc event for new files in landing bucket.

    Expected Cloud Storage event format:
    {
        "bucket": "bucket-name",
        "name": "path/to/file.json.gz",
        "resourceState": "exists",
        "metageneration": "1"
    }
    """
    start_time = time.time()

    # Parse event payload
    try:
        event = request.get_json()
        if not event:
            return jsonify({'error': 'No event payload'}), 400

    except Exception as e:
        logger.error(f"Failed to parse event: {e}")
        return jsonify({'error': f'Invalid event payload: {e}'}), 400

    # Extract event data
    bucket = event.get('bucket')
    file_name = event.get('name')

    logger.info(f"Received Eventarc event: bucket={bucket}, file={file_name}")

    # Path filtering: Only process files in github-archive/raw/ or github-archive/chunks/
    # Eventarc triggers don't support 'name' attribute filtering for Cloud Storage events
    if not file_name or not file_name.startswith('github-archive/'):
        logger.info(f"Ignoring file outside github-archive/ path: {file_name}")
        return jsonify({'status': 'ignored', 'reason': 'path_not_matching'}), 200

    if not file_name.endswith('.json.gz'):
        logger.info(f"Ignoring non-.json.gz file: {file_name}")
        return jsonify({'status': 'ignored', 'reason': 'extension_not_matching'}), 200

    # Validate path patterns: raw/ or chunks/ subdirectories
    if not ('/raw/' in file_name or '/chunks/' in file_name):
        logger.info(f"Ignoring file not in raw/ or chunks/ path: {file_name}")
        return jsonify({'status': 'ignored', 'reason': 'subdirectory_not_matching'}), 200

    # Build full GCS path
    input_gcs_path = f"gs://{bucket}/{file_name}"

    # Process the file
    try:
        result = processor.process_file(input_gcs_path)

        duration = time.time() - start_time

        # Handle file split required case
        if result.error_message == 'FILE_SPLIT_REQUIRED':
            # Trigger file splitter job
            from google.cloud import run_v2
            from processors.file_splitter import run_splitter_job

            logger.info(f"Triggering file splitter for: {file_name}")

            try:
                # Execute file splitter job
                # Note: In production, you might want to use Cloud Tasks or Pub/Sub
                # to trigger this asynchronously
                split_result = run_splitter_job(
                    input_file=input_gcs_path,
                    project_id=PROJECT_ID,
                    landing_bucket=LANDING_BUCKET
                )

                response_data = {
                    'status': 'split',
                    'action': 'file_splitter_executed',
                    'input_file': input_gcs_path,
                    'chunk_count': split_result['chunk_count'],
                    'total_records': split_result['total_records'],
                    'output_files': split_result['output_files'],
                    'duration_seconds': round(duration, 2)
                }

                logger.info(f"File split completed: {split_result['chunk_count']} chunks created")

                return jsonify(response_data), 200

            except Exception as split_error:
                logger.error(f"File splitter failed: {split_error}")
                return jsonify({
                    'status': 'error',
                    'error': f'File splitter failed: {str(split_error)}',
                    'input_file': input_gcs_path
                }), 500

        # Normal processing response
        response_data = {
            'status': 'success' if result.success else 'failed',
            'input_file': result.input_file,
            'output_file': result.output_file,
            'output_files': result.output_files or [],
            'output_count': result.output_count,
            'records_in': result.records_in,
            'records_out': result.records_out,
            'errors': result.errors,
            'warnings': result.warnings,
            'duration_seconds': round(duration, 2)
        }

        status_code = 200 if result.success else 207  # 207 for partial success

        logger.info(f"Processing {'completed' if result.success else 'failed'}: {file_name}, in={result.records_in}, out={result.records_out}")

        return jsonify(response_data), status_code

    except Exception as e:
        duration = time.time() - start_time
        error_msg = f"Processing error: {str(e)}"

        logger.error(f"{error_msg} file={file_name} duration={round(duration, 2)}s")

        if error_reporter:
            error_reporter.report_exception()

        return jsonify({
            'status': 'error',
            'error': error_msg,
            'duration_seconds': round(duration, 2)
        }), 500


# =============================================================================
# MANUAL TRIGGER (for testing)
# =============================================================================
@app.route('/process', methods=['POST'])
def process_manual() -> tuple[Dict[str, Any], int]:
    """
    Manually trigger processing of a file.

    Request body:
    {
        "file_path": "gs://bucket/path/to/file.json.gz"
    }
    """
    try:
        data = request.get_json()
        file_path = data.get('file_path')

        if not file_path:
            return jsonify({'error': 'file_path is required'}), 400

        # Validate path format
        if not file_path.startswith('gs://'):
            return jsonify({'error': 'file_path must be a gs:// path'}), 400

        logger.info(f"Manual processing request for: {file_path}")

        result = processor.process_file(file_path)

        return jsonify({
            'status': 'success' if result.success else 'failed',
            'input_file': result.input_file,
            'output_file': result.output_file,
            'records_in': result.records_in,
            'records_out': result.records_out,
            'errors': result.errors,
            'warnings': result.warnings,
            'duration_seconds': result.duration_seconds
        }), 200 if result.success else 500

    except Exception as e:
        logger.error(f"Manual processing error: {e}")
        if error_reporter:
            error_reporter.report_exception()
        return jsonify({'error': str(e)}), 500



# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    logger.info(f"Starting GitHub Archive Processor: project={PROJECT_ID}, landing={LANDING_BUCKET}, staging={STAGING_BUCKET}, port={PORT}")

    app.run(host=HOST, port=PORT, debug=False)
