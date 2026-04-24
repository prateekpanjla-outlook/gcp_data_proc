"""Integration tests with BigQuery emulator.

Run with: pytest tests/integration/ -v -m emulator
Requires: BigQuery emulator running on localhost:9050
"""

import os
import pytest

from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials

from src.github_archive.schemas import get_github_events_schema
from src.hacker_news.schemas import get_stories_schema


pytestmark = pytest.mark.emulator


@pytest.fixture(scope="module")
def bq_client():
    """BigQuery client connected to emulator."""
    emulator_host = os.getenv("BIGQUERY_EMULATOR_HOST", "localhost:9050")

    client = bigquery.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
        location="US"
    )
    client.emulator_host = f"http://{emulator_host}"

    return client


@pytest.fixture(scope="module")
def test_datasets(bq_client):
    """Create test datasets."""
    datasets = []

    for dataset_id in ["test_github", "test_hackernews"]:
        dataset_ref = f"{bq_client.project}.{dataset_id}"
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        bq_client.create_dataset(dataset, exists_ok=True)
        datasets.append(dataset_id)

    yield datasets

    # Cleanup
    for dataset_id in datasets:
        dataset_ref = f"{bq_client.project}.{dataset_id}"
        bq_client.delete_dataset(dataset_ref, delete_contents=True)


class TestBigQueryEmulator:
    """Test BigQuery emulator connectivity and operations."""

    def test_list_datasets(self, bq_client):
        """Test listing datasets."""
        datasets = list(bq_client.list_datasets())
        assert len(datasets) > 0

    def test_create_github_events_table(self, bq_client, test_datasets):
        """Test creating GitHub events table."""
        table_id = "events"
        dataset_id = test_datasets[0]
        table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"

        table = bigquery.Table(table_ref, schema=get_github_events_schema())
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="created_at"
        )

        table = bq_client.create_table(table, exists_ok=True)

        assert table.table_id == table_id
        assert len(table.schema) > 0

    def test_insert_and_query_github_events(self, bq_client, test_datasets):
        """Test inserting and querying GitHub events."""
        table_id = "events_test"
        dataset_id = test_datasets[0]
        table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"

        # Create table
        table = bigquery.Table(table_ref, schema=get_github_events_schema())
        bq_client.create_table(table, exists_ok=True)

        # Insert test data
        from datetime import datetime
        rows = [
            {
                "event_id": "test-1",
                "event_type": "PushEvent",
                "created_at": datetime(2025, 1, 15, 14, 30, 0),
                "actor_login": "testuser",
                "repo_name": "test/repo",
                "ingestion_timestamp": datetime.utcnow(),
                "processed_at": datetime.utcnow(),
            }
        ]

        errors = bq_client.insert_rows_json(table_ref, rows)
        assert len(errors) == 0

        # Query the data
        query = f"""
            SELECT event_type, actor_login, repo_name
            FROM `{table_ref}`
            WHERE event_id = 'test-1'
        """

        result = bq_client.query(query).to_dataframe()
        assert len(result) == 1
        assert result.iloc[0]["event_type"] == "PushEvent"

    def test_create_hn_stories_table(self, bq_client, test_datasets):
        """Test creating HN stories table."""
        table_id = "stories"
        dataset_id = test_datasets[1]
        table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"

        table = bigquery.Table(table_ref, schema=get_stories_schema())
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field="timestamp"
        )

        table = bq_client.create_table(table, exists_ok=True)

        assert table.table_id == table_id
        assert len(table.schema) > 0

    def test_insert_and_query_hn_stories(self, bq_client, test_datasets):
        """Test inserting and querying HN stories."""
        table_id = "stories_test"
        dataset_id = test_datasets[1]
        table_ref = f"{bq_client.project}.{dataset_id}.{table_id}"

        # Create table
        table = bigquery.Table(table_ref, schema=get_stories_schema())
        bq_client.create_table(table, exists_ok=True)

        # Insert test data
        from datetime import datetime, timezone
        rows = [
            {
                "story_id": 12345,
                "by": "testuser",
                "timestamp": datetime(2025, 1, 15, 14, 30, 0, tzinfo=timezone.utc),
                "type": "story",
                "title": "Test Story",
                "url": "https://example.com",
                "domain": "example.com",
                "score": 42,
                "descendants": 10,
                "kids": [12346, 12347],
                "fetched_at": datetime.utcnow(),
                "is_dead": False,
                "is_deleted": False,
                "ingestion_timestamp": datetime.utcnow(),
                "processed_at": datetime.utcnow(),
            }
        ]

        errors = bq_client.insert_rows_json(table_ref, rows)
        assert len(errors) == 0

        # Query the data
        query = f"""
            SELECT story_id, by, title, score
            FROM `{table_ref}`
            WHERE story_id = 12345
        """

        result = bq_client.query(query).to_dataframe()
        assert len(result) == 1
        assert result.iloc[0]["title"] == "Test Story"
        assert result.iloc[0]["score"] == 42
