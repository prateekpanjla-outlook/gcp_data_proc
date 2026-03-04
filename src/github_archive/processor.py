"""GitHub Archive event processor for Cloud Storage → Cloud Run → BigQuery pipeline."""

import datetime
import gzip
import io
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Optional

from src.shared.bigquery_client import BigQueryClient
from src.shared.config import get_config
from src.shared.storage_client import StorageClient

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result of processing a file."""
    source_file: str
    total_events: int = 0
    processed_events: int = 0
    failed_events: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def add_error(self, error: str):
        """Add an error to the result."""
        self.errors.append(error)


class GitHubArchiveProcessor:
    """
    Processor for GitHub Archive JSON files.

    Handles decompression, parsing, and loading of GitHub timeline events
    from GitHub Archive (https://data.gharchive.org/) into BigQuery.
    """

    def __init__(
        self,
        storage_client: Optional[StorageClient] = None,
        bq_client: Optional[BigQueryClient] = None,
        config=None
    ):
        """
        Initialize the GitHub Archive processor.

        Args:
            storage_client: StorageClient instance (created if not provided)
            bq_client: BigQueryClient instance (created if not provided)
            config: Pipeline configuration (created if not provided)
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
            event_data: Event data from Eventarc containing bucket and file info

        Returns:
            ProcessingResult with statistics and any errors
        """
        bucket = event_data.get("bucket")
        file_name = event_data.get("name")

        if not bucket or not file_name:
            result = ProcessingResult(source_file="unknown")
            result.add_error("Missing bucket or file name in event data")
            return result

        logger.info(f"Processing GitHub Archive file: {file_name}")

        try:
            return self.process_file(file_name)
        except Exception as e:
            logger.error(f"Error processing file {file_name}: {e}")
            result = ProcessingResult(source_file=file_name)
            result.add_error(str(e))
            return result

    def process_file(self, file_path: str) -> ProcessingResult:
        """
        Process a GitHub Archive file from Cloud Storage.

        Args:
            file_path: Path to the file in Cloud Storage

        Returns:
            ProcessingResult with statistics and any errors
        """
        result = ProcessingResult(source_file=file_path)
        batch = []
        is_compressed = file_path.endswith('.gz')

        try:
            # Read and parse events from the file
            for event in self.storage.read_jsonl_file(file_path, compressed=is_compressed):
                result.total_events += 1

                try:
                    processed = self.parse_event(event)
                    if processed:
                        batch.append(processed)
                        result.processed_events += 1
                    else:
                        result.failed_events += 1
                except Exception as e:
                    logger.warning(f"Failed to parse event: {e}")
                    result.failed_events += 1

                # Insert in batches
                if len(batch) >= self.config.batch_size:
                    self._insert_batch(batch)
                    batch = []

            # Insert remaining events
            if batch:
                self._insert_batch(batch)

            # Move processed file
            if result.processed_events > 0:
                processed_path = self.config.storage.get_processed_path(
                    "github-archive",
                    file_path.split('/')[-1]
                )
                self.storage.move_file(file_path, processed_path)
                logger.info(f"Moved processed file to {processed_path}")

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            result.add_error(str(e))

            # Move to error directory if processing failed
            error_path = self.config.storage.get_error_path(
                "github-archive",
                file_path.split('/')[-1]
            )
            try:
                self.storage.move_file(file_path, error_path)
            except Exception as move_error:
                result.add_error(f"Failed to move to error directory: {move_error}")

        return result

    def parse_event(self, raw_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Parse a raw GitHub event into a BigQuery-compatible format.

        Args:
            raw_event: Raw event from GitHub Archive

        Returns:
            Dictionary ready for BigQuery insertion, or None if invalid
        """
        # Validate required fields
        event_id = raw_event.get("id")
        event_type = raw_event.get("type")
        created_at = raw_event.get("created_at")

        if not all([event_id, event_type, created_at]):
            logger.warning(f"Event missing required fields: {event_id}")
            return None

        # Parse timestamp
        try:
            created_at_ts = datetime.datetime.fromisoformat(
                created_at.replace('Z', '+00:00')
            )
        except ValueError:
            logger.warning(f"Invalid timestamp format: {created_at}")
            return None

        # Extract actor information
        actor = raw_event.get("actor", {})
        actor_id = actor.get("id")
        actor_login = actor.get("login")
        actor_display_login = actor.get("display_login")
        actor_gravatar_id = actor.get("gravatar_id")
        actor_url = actor.get("url")
        actor_avatar_url = actor.get("avatar_url")

        # Extract repository information
        repo = raw_event.get("repo", {})
        repo_id = repo.get("id")
        repo_name = repo.get("name")
        repo_url = repo.get("url")

        # Extract organization information
        org = raw_event.get("org", {})
        org_id = org.get("id")
        org_login = org.get("login")
        org_url = org.get("url")

        # Get payload
        payload = raw_event.get("payload", {})

        # Build base record
        record = {
            "event_id": str(event_id),
            "event_type": event_type,
            "created_at": created_at_ts,
            "actor_id": actor_id,
            "actor_login": actor_login,
            "actor_display_login": actor_display_login,
            "actor_gravatar_id": actor_gravatar_id,
            "actor_url": actor_url,
            "actor_avatar_url": actor_avatar_url,
            "repo_id": repo_id,
            "repo_name": repo_name,
            "repo_url": repo_url,
            "org_id": org_id,
            "org_login": org_login,
            "org_url": org_url,
            "payload": payload,
            "public": raw_event.get("public"),
            "ingestion_timestamp": datetime.datetime.utcnow(),
            "processed_at": datetime.datetime.utcnow(),
        }

        # Extract common payload fields
        record.update(self._extract_common_payload_fields(event_type, payload))

        return record

    def _extract_common_payload_fields(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract event-type-specific fields from payload."""
        fields = {
            "action": None,
            "ref": None,
            "ref_type": None,
            "master_branch": None,
            "description": None,
            "pusher_type": None,
            "push_size": None,
            "push_distinct_size": None,
            "push_head": None,
            "push_before": None,
            "pr_number": None,
            "pr_state": None,
            "pr_title": None,
            "pr_body": None,
            "pr_merged": None,
            "pr_merge_commit_sha": None,
            "issue_number": None,
            "issue_state": None,
            "issue_title": None,
            "issue_body": None,
            "release_tag_name": None,
            "release_name": None,
            "release_draft": None,
            "release_prerelease": None,
        }

        # Common fields
        fields["action"] = payload.get("action")
        fields["ref"] = payload.get("ref")
        fields["ref_type"] = payload.get("ref_type")
        fields["master_branch"] = payload.get("master_branch")
        fields["description"] = payload.get("description")

        # PushEvent specific
        if event_type == "PushEvent":
            fields["push_size"] = payload.get("size")
            fields["push_distinct_size"] = payload.get("distinct_size")
            fields["push_head"] = payload.get("head")
            fields["push_before"] = payload.get("before")

        # PullRequestEvent specific
        elif event_type == "PullRequestEvent":
            pr = payload.get("pull_request", {})
            fields["pr_number"] = pr.get("number")
            fields["pr_state"] = pr.get("state")
            fields["pr_title"] = pr.get("title")
            fields["pr_body"] = pr.get("body")
            fields["pr_merged"] = pr.get("merged")
            fields["pr_merge_commit_sha"] = pr.get("merge_commit_sha")

        # IssuesEvent specific
        elif event_type == "IssuesEvent":
            issue = payload.get("issue", {})
            fields["issue_number"] = issue.get("number")
            fields["issue_state"] = issue.get("state")
            fields["issue_title"] = issue.get("title")
            fields["issue_body"] = issue.get("body")

        # ReleaseEvent specific
        elif event_type == "ReleaseEvent":
            release = payload.get("release", {})
            fields["release_tag_name"] = release.get("tag_name")
            fields["release_name"] = release.get("name")
            fields["release_draft"] = release.get("draft")
            fields["release_prerelease"] = release.get("prerelease")

        return fields

    def _insert_batch(self, batch: List[Dict[str, Any]]) -> None:
        """Insert a batch of events into BigQuery."""
        errors = self.bq.insert_rows(
            dataset_id=self.config.bigquery.dataset_id,
            table_id=self.config.bigquery.table_id,
            rows=batch
        )

        if errors:
            logger.error(f"BigQuery insert errors: {errors}")
            raise Exception(f"Failed to insert {len(errors)} rows")


def create_bigquery_table(
    project_id: str,
    dataset_id: str,
    table_id: str = "events"
) -> None:
    """
    Create the BigQuery table for GitHub events if it doesn't exist.

    Args:
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        table_id: Table ID (default: "events")
    """
    from src.github_archive.schemas import get_github_events_schema

    bq_client = BigQueryClient(project_id=project_id)

    if not bq_client.table_exists(dataset_id, table_id):
        bq_client.create_table(
            dataset_id=dataset_id,
            table_id=table_id,
            schema=get_github_events_schema(),
            partitioning_field="created_at",
            clustering_fields=["event_type", "repo_id"],
            partition_expiration_days=400
        )
        logger.info(f"Created table {dataset_id}.{table_id}")
    else:
        logger.info(f"Table {dataset_id}.{table_id} already exists")
