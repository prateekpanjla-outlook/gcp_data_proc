"""BigQuery schema definitions for Hacker News data."""

from typing import List

from google.cloud import bigquery


def get_stories_schema() -> List[bigquery.SchemaField]:
    """Return the BigQuery schema for Hacker News stories table."""

    return [
        bigquery.SchemaField("story_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("by", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("type", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("url", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("domain", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("score", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("descendants", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("kids", "INTEGER", mode="REPEATED"),
        bigquery.SchemaField("parts", "INTEGER", mode="REPEATED"),
        bigquery.SchemaField("poll_id", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("is_dead", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("is_deleted", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("processed_at", "TIMESTAMP", mode="REQUIRED"),
    ]


def get_comments_schema() -> List[bigquery.SchemaField]:
    """Return the BigQuery schema for Hacker News comments table."""

    return [
        bigquery.SchemaField("comment_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("parent_id", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("story_id", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("by", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("kids", "INTEGER", mode="REPEATED"),
        bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("is_dead", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("is_deleted", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("depth", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("parent_author", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("processed_at", "TIMESTAMP", mode="REQUIRED"),
    ]


def get_users_schema() -> List[bigquery.SchemaField]:
    """Return the BigQuery schema for Hacker News users table."""

    return [
        bigquery.SchemaField("username", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("created", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("karma", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("about", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("submitted", "INTEGER", mode="REPEATED"),
        bigquery.SchemaField("submitted_count", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("last_updated", "TIMESTAMP", mode="REQUIRED"),
    ]


# Type constants
STORY_TYPES = ["story", "job", "poll", "pollopt"]
COMMENT_TYPES = ["comment"]
USER_TYPES = ["user"]
