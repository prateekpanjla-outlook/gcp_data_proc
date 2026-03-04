"""Main entry point for Hacker News Cloud Run services."""

import os
import logging

from flask import Flask, request, jsonify

from src.hacker_news.processor import HNProcessor, create_bigquery_tables
from src.hacker_news.fetcher import HackerNewsFetcher, HackerNewsAPI
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

# Initialize clients
storage_client = StorageClient(
    bucket_name=config.storage.bucket_name,
    project_id=config.bigquery.project_id
)
bq_client = BigQueryClient(project_id=config.bigquery.project_id)
api = HackerNewsAPI()

# Initialize processors
processor = HNProcessor(
    storage_client=storage_client,
    bq_client=bq_client,
    config=config
)
fetcher = HackerNewsFetcher(storage_client=storage_client, api=api)


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
    import json
    import base64

    # Handle Pub/Sub push format
    if request.is_json:
        envelope = request.get_json()

        if "message" in envelope:
            message = envelope["message"]
            data_str = base64.b64decode(message.get("data", "")).decode("utf-8")
            event_data = json.loads(data_str) if data_str else {}
        else:
            event_data = envelope
    else:
        return jsonify({"error": "Invalid content type"}), 400

    logger.info(f"Received event: {event_data}")

    bucket = event_data.get("bucket")
    file_name = event_data.get("name")

    if not bucket or not file_name:
        logger.error("Missing bucket or file name in event data")
        return jsonify({"error": "Missing bucket or file name"}), 400

    # Only process Hacker News files
    if "hacker-news" not in file_name.lower():
        logger.info(f"Skipping non-HN file: {file_name}")
        return jsonify({"message": "File skipped"}), 200

    # Process the file
    result = processor.process_gcs_event(event_data)

    response = {
        "source_file": result.source_file,
        "total_items": result.total_items,
        "processed_stories": result.processed_stories,
        "processed_comments": result.processed_comments,
        "failed_items": result.failed_items,
        "success": result.failed_items == 0
    }

    if result.errors:
        response["errors"] = result.errors

    status_code = 200 if result.failed_items == 0 else 207

    return jsonify(response), status_code


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "hacker-news-processor",
        "configuration": config.cloud_run.configuration
    }), 200


@app.route("/tasks/create-tables", methods=["POST"])
def create_tables():
    """Create BigQuery tables (one-time setup)."""
    try:
        create_bigquery_tables(
            project_id=config.bigquery.project_id,
            dataset_id=config.bigquery.dataset_id
        )
        return jsonify({"message": "Tables created successfully"}), 200
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/tasks/fetch", methods=["GET", "POST"])
def fetch_hn_data():
    """
    Fetch new stories from Hacker News API (for scheduled execution).

    Query parameters:
        count: Number of stories to fetch (default: 100)
        include_comments: Whether to fetch comments (default: true)
    """
    count = int(request.args.get("count", 100))
    include_comments = request.args.get("include_comments", "true").lower() == "true"

    logger.info(f"Fetching {count} stories from HN API")

    try:
        filename = fetcher.fetch_and_store(
            count=count,
            prefix="hacker-news/raw"
        )

        return jsonify({
            "message": "Data fetched successfully",
            "filename": filename,
            "count": count,
            "include_comments": include_comments
        }), 200

    except Exception as e:
        logger.error(f"Failed to fetch HN data: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/tasks/refresh-users", methods=["GET", "POST"])
def refresh_users():
    """
    Refresh user profiles (for scheduled execution).

    This fetches user profiles for active users from recent stories.
    """
    try:
        # Get recent usernames from the last fetch
        files = storage_client.list_files("hacker-news/raw/", file_extension=".json.gz")
        if not files:
            return jsonify({"error": "No recent data files found"}), 404

        # Get the most recent file
        latest_file = sorted(files)[-1]
        data = storage_client.read_json_file(latest_file, compressed=True)

        # Extract unique usernames
        usernames = set()
        for story in data.get("stories", []):
            if story.get("by"):
                usernames.add(story["by"])
        for comment in data.get("comments", []):
            if comment.get("by"):
                usernames.add(comment["by"])

        logger.info(f"Refreshing {len(usernames)} user profiles")

        filename = fetcher.refresh_users(
            usernames=list(usernames),
            prefix="hacker-news/users"
        )

        return jsonify({
            "message": "Users refreshed successfully",
            "filename": filename,
            "user_count": len(usernames)
        }), 200

    except Exception as e:
        logger.error(f"Failed to refresh users: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
