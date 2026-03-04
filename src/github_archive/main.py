"""Main entry point for GitHub Archive Cloud Run service."""

import os
import logging

from flask import Flask, request, jsonify

from src.github_archive.processor import GitHubArchiveProcessor, create_bigquery_table
from src.shared.config import get_config
from src.shared.storage_client import StorageClient
from src.shared.bigquery_client import BigQueryClient

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Get configuration
config = get_config()

# Initialize processor
storage_client = StorageClient(
    bucket_name=config.storage.bucket_name,
    project_id=config.bigquery.project_id
)
bq_client = BigQueryClient(project_id=config.bigquery.project_id)
processor = GitHubArchiveProcessor(
    storage_client=storage_client,
    bq_client=bq_client,
    config=config
)


@app.route("/", methods=["POST"])
def handle_event():
    """
    Handle incoming Eventarc events from Cloud Storage.

    Expected payload format (from Eventarc):
    {
        "bucket": "bucket-name",
        "name": "path/to/file.json.gz"
    }
    """
    # Handle Pub/Sub push format
    if request.is_json:
        envelope = request.get_json()

        # Check if this is a Pub/Sub envelope
        if "message" in envelope:
            import json
            import base64

            message = envelope["message"]
            data_str = base64.b64decode(message.get("data", "")).decode("utf-8")
            event_data = json.loads(data_str) if data_str else {}
        else:
            # Direct JSON payload
            event_data = envelope
    else:
        return jsonify({"error": "Invalid content type"}), 400

    logger.info(f"Received event: {event_data}")

    # Validate required fields
    bucket = event_data.get("bucket")
    file_name = event_data.get("name")

    if not bucket or not file_name:
        logger.error("Missing bucket or file name in event data")
        return jsonify({"error": "Missing bucket or file name"}), 400

    # Only process GitHub Archive files
    if "github-archive" not in file_name.lower():
        logger.info(f"Skipping non-GitHub Archive file: {file_name}")
        return jsonify({"message": "File skipped"}), 200

    # Process the file
    result = processor.process_gcs_event(event_data)

    response = {
        "source_file": result.source_file,
        "total_events": result.total_events,
        "processed_events": result.processed_events,
        "failed_events": result.failed_events,
        "success": result.failed_events == 0
    }

    if result.errors:
        response["errors"] = result.errors

    status_code = 200 if result.failed_events == 0 else 207

    return jsonify(response), status_code


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "github-archive-processor",
        "configuration": config.cloud_run.configuration
    }), 200


@app.route("/tasks/create-table", methods=["POST"])
def create_table():
    """Create BigQuery table (one-time setup)."""
    try:
        create_bigquery_table(
            project_id=config.bigquery.project_id,
            dataset_id=config.bigquery.dataset_id,
            table_id=config.bigquery.table_id
        )
        return jsonify({"message": "Table created successfully"}), 200
    except Exception as e:
        logger.error(f"Failed to create table: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/tasks/download", methods=["GET", "POST"])
def download_github_archive():
    """
    Download latest GitHub Archive file (for scheduled execution).

    Query parameters:
        hours_ago: Number of hours ago to download (default: 1)
    """
    from urllib.request import urlopen
    import gzip
    from datetime import datetime, timedelta

    hours_ago = int(request.args.get("hours_ago", 1))
    target_time = datetime.utcnow() - timedelta(hours=hours_ago)
    filename = target_time.strftime("%Y-%m-%d-%-H.json.gz")  # Note: %-H is non-zero padded

    # URL format: https://data.gharchive.org/2025-01-15-14.json.gz
    url = f"https://data.gharchive.org/{filename}"

    logger.info(f"Downloading GitHub Archive from {url}")

    try:
        with urlopen(url, timeout=300) as response:
            compressed_data = response.read()

        # Verify it's valid gzip data
        try:
            gzip.decompress(compressed_data)
        except gzip.BadGzipFile:
            logger.error(f"Downloaded file is not valid gzip: {url}")
            return jsonify({"error": "Invalid gzip data"}), 400

        # Upload to Cloud Storage
        blob_name = f"github-archive/raw/{filename}"
        blob = storage_client.bucket.blob(blob_name)
        blob.upload_from_string(compressed_data, content_type="application/gzip")

        logger.info(f"Successfully uploaded {blob_name}")

        return jsonify({
            "message": "File downloaded and uploaded",
            "filename": filename,
            "size": len(compressed_data),
            "url": url
        }), 200

    except Exception as e:
        logger.error(f"Failed to download GitHub Archive: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
