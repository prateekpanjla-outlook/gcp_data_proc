"""Hacker News data processor for Cloud Storage → Cloud Run → BigQuery pipeline."""

import datetime
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.shared.bigquery_client import BigQueryClient
from src.shared.config import get_config
from src.shared.storage_client import StorageClient

logger = logging.getLogger(__name__)


class ProcessingResult:
    """Result of processing a file."""

    def __init__(self, source_file: str):
        self.source_file = source_file
        self.total_items = 0
        self.processed_stories = 0
        self.processed_comments = 0
        self.failed_items = 0
        self.errors = []

    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)


class HNProcessor:
    """
    Processor for Hacker News data.

    Handles parsing and loading of Hacker News stories and comments
    into BigQuery.
    """

    def __init__(
        self,
        storage_client: Optional[StorageClient] = None,
        bq_client: Optional[BigQueryClient] = None,
        config=None
    ):
        """
        Initialize the HN processor.

        Args:
            storage_client: StorageClient instance
            bq_client: BigQueryClient instance
            config: Pipeline configuration
        """
        self.config = config or get_config()

        if storage_client is None:
            storage_client = StorageClient(
                bucket_name=self.config.storage.bucket_name,
                project_id=self.config.bigquery.project_id
            )
        self.storage = storage_client

        if bq_client is None:
            bq_client = BigQueryClient(
                project_id=self.config.bigquery.project_id
            )
        self.bq = bq_client

    def process_gcs_event(self, event_data: Dict[str, Any]) -> ProcessingResult:
        """
        Process a Cloud Storage event (triggered by Eventarc).

        Args:
            event_data: Event data containing bucket and file info

        Returns:
            ProcessingResult with statistics
        """
        bucket = event_data.get("bucket")
        file_name = event_data.get("name")

        if not bucket or not file_name:
            result = ProcessingResult(source_file="unknown")
            result.add_error("Missing bucket or file name in event data")
            return result

        logger.info(f"Processing HN file: {file_name}")

        try:
            return self.process_file(file_name)
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            result = ProcessingResult(source_file=file_name)
            result.add_error(str(e))
            return result

    def process_file(self, file_path: str) -> ProcessingResult:
        """
        Process a Hacker News data file from Cloud Storage.

        Args:
            file_path: Path to the file in Cloud Storage

        Returns:
            ProcessingResult with statistics
        """
        result = ProcessingResult(source_file=file_path)
        is_compressed = file_path.endswith('.gz')

        try:
            data = self.storage.read_json_file(file_path, compressed=is_compressed)

            stories_batch = []
            comments_batch = []

            # Process stories
            for story in data.get("stories", []):
                result.total_items += 1
                try:
                    story_record = self.parse_story(story)
                    if story_record:
                        stories_batch.append(story_record)
                        result.processed_stories += 1
                except Exception as e:
                    logger.warning(f"Failed to parse story: {e}")
                    result.failed_items += 1

                if len(stories_batch) >= self.config.batch_size:
                    self._insert_stories_batch(stories_batch)
                    stories_batch = []

            # Process comments
            for comment in data.get("comments", []):
                result.total_items += 1
                try:
                    comment_record = self.parse_comment(comment)
                    if comment_record:
                        comments_batch.append(comment_record)
                        result.processed_comments += 1
                except Exception as e:
                    logger.warning(f"Failed to parse comment: {e}")
                    result.failed_items += 1

                if len(comments_batch) >= self.config.batch_size:
                    self._insert_comments_batch(comments_batch)
                    comments_batch = []

            # Insert remaining records
            if stories_batch:
                self._insert_stories_batch(stories_batch)
            if comments_batch:
                self._insert_comments_batch(comments_batch)

            # Move processed file
            if result.processed_stories > 0 or result.processed_comments > 0:
                processed_path = self.config.storage.get_processed_path(
                    "hacker-news",
                    file_path.split('/')[-1]
                )
                self.storage.move_file(file_path, processed_path)
                logger.info(f"Moved processed file to {processed_path}")

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            result.add_error(str(e))

            # Move to error directory
            error_path = self.config.storage.get_error_path(
                "hacker-news",
                file_path.split('/')[-1]
            )
            try:
                self.storage.move_file(file_path, error_path)
            except Exception as move_error:
                result.add_error(f"Failed to move to error directory: {move_error}")

        return result

    def parse_story(self, raw_story: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a raw Hacker News story into BigQuery format.

        Args:
            raw_story: Raw story from HN API

        Returns:
            Dictionary ready for BigQuery insertion
        """
        story_id = raw_story.get("id")
        if not story_id:
            return None

        # Convert Unix timestamp to datetime
        timestamp_ts = self._convert_timestamp(raw_story.get("time"))

        # Extract domain from URL
        url = raw_story.get("url")
        domain = self._extract_domain(url)

        return {
            "story_id": story_id,
            "by": raw_story.get("by"),
            "timestamp": timestamp_ts,
            "type": raw_story.get("type"),
            "title": raw_story.get("title"),
            "url": url,
            "domain": domain,
            "score": raw_story.get("score"),
            "descendants": raw_story.get("descendants"),
            "text": raw_story.get("text"),
            "kids": raw_story.get("kids", []),
            "parts": raw_story.get("parts", []),
            "poll_id": raw_story.get("poll_id"),
            "fetched_at": datetime.datetime.utcnow(),
            "is_dead": raw_story.get("dead"),
            "is_deleted": raw_story.get("deleted"),
            "ingestion_timestamp": datetime.datetime.utcnow(),
            "processed_at": datetime.datetime.utcnow(),
        }

    def parse_comment(self, raw_comment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a raw Hacker News comment into BigQuery format.

        Args:
            raw_comment: Raw comment from HN API

        Returns:
            Dictionary ready for BigQuery insertion
        """
        comment_id = raw_comment.get("id")
        if not comment_id:
            return None

        timestamp_ts = self._convert_timestamp(raw_comment.get("time"))
        parent_id = raw_comment.get("parent")

        return {
            "comment_id": comment_id,
            "parent_id": parent_id,
            "story_id": self._extract_story_id(raw_comment),
            "by": raw_comment.get("by"),
            "timestamp": timestamp_ts,
            "text": raw_comment.get("text"),
            "kids": raw_comment.get("kids", []),
            "fetched_at": datetime.datetime.utcnow(),
            "is_dead": raw_comment.get("dead"),
            "is_deleted": raw_comment.get("deleted"),
            "depth": None,  # Will be calculated separately
            "parent_author": None,  # Will be populated separately
            "ingestion_timestamp": datetime.datetime.utcnow(),
            "processed_at": datetime.datetime.utcnow(),
        }

    def _convert_timestamp(self, unix_timestamp: Optional[int]) -> Optional[datetime.datetime]:
        """Convert Unix timestamp to datetime."""
        if unix_timestamp is None:
            return None
        try:
            return datetime.datetime.fromtimestamp(unix_timestamp, tz=datetime.timezone.utc)
        except (ValueError, OSError):
            return None

    def _extract_domain(self, url: Optional[str]) -> Optional[str]:
        """Extract domain from URL."""
        if not url:
            return None
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    def _extract_story_id(self, comment: Dict[str, Any]) -> Optional[int]:
        """
        Extract the root story ID from a comment.

        This is a simplified version - in practice you'd need to
        traverse the parent chain to find the root story.
        """
        # For now, return None - this would be populated by a separate process
        # that builds the comment tree
        return None

    def _insert_stories_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Insert a batch of stories into BigQuery."""
        errors = self.bq.insert_rows(
            dataset_id=self.config.bigquery.dataset_id,
            table_id="stories",
            rows=batch
        )

        if errors:
            logger.error(f"BigQuery insert errors for stories: {errors}")
            raise Exception(f"Failed to insert {len(errors)} story rows")

    def _insert_comments_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Insert a batch of comments into BigQuery."""
        errors = self.bq.insert_rows(
            dataset_id=self.config.bigquery.dataset_id,
            table_id="comments",
            rows=batch
        )

        if errors:
            logger.error(f"BigQuery insert errors for comments: {errors}")
            raise Exception(f"Failed to insert {len(errors)} comment rows")


def create_bigquery_tables(
    project_id: str,
    dataset_id: str
) -> None:
    """
    Create BigQuery tables for Hacker News data if they don't exist.

    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
    """
    from src.hacker_news.schemas import get_stories_schema, get_comments_schema, get_users_schema

    bq_client = BigQueryClient(project_id=project_id)

    # Create stories table
    if not bq_client.table_exists(dataset_id, "stories"):
        bq_client.create_table(
            dataset_id=dataset_id,
            table_id="stories",
            schema=get_stories_schema(),
            partitioning_field="timestamp",
            clustering_fields=["by", "score"],
            partition_expiration_days=400
        )
        logger.info(f"Created table {dataset_id}.stories")
    else:
        logger.info(f"Table {dataset_id}.stories already exists")

    # Create comments table
    if not bq_client.table_exists(dataset_id, "comments"):
        bq_client.create_table(
            dataset_id=dataset_id,
            table_id="comments",
            schema=get_comments_schema(),
            partitioning_field="timestamp",
            clustering_fields=["story_id", "by"],
            partition_expiration_days=400
        )
        logger.info(f"Created table {dataset_id}.comments")
    else:
        logger.info(f"Table {dataset_id}.comments already exists")

    # Create users table (not partitioned)
    if not bq_client.table_exists(dataset_id, "users"):
        bq_client.create_table(
            dataset_id=dataset_id,
            table_id="users",
            schema=get_users_schema()
        )
        logger.info(f"Created table {dataset_id}.users")
    else:
        logger.info(f"Table {dataset_id}.users already exists")
