#!/usr/bin/env python3
"""Script to create BigQuery datasets and tables for the pipeline."""

import argparse
import logging

from google.cloud import bigquery

from src.github_archive.schemas import (
    get_github_events_schema,
    get_repositories_schema,
    get_users_schema
)
from src.hacker_news.schemas import (
    get_stories_schema,
    get_comments_schema,
    get_users_schema as get_hn_users_schema
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_dataset(client: bigquery.Client, dataset_id: str, location: str = "US"):
    """Create a BigQuery dataset if it doesn't exist."""
    dataset_ref = f"{client.project}.{dataset_id}"
    dataset = bigquery.Dataset(dataset_ref)
    dataset.location = location

    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        logger.info(f"Dataset {dataset_id} created or already exists")
    except Exception as e:
        logger.error(f"Failed to create dataset {dataset_id}: {e}")
        raise


def create_table(
    client: bigquery.Client,
    dataset_id: str,
    table_id: str,
    schema,
    partitioning_field: str = None,
    clustering_fields: list = None
):
    """Create a BigQuery table if it doesn't exist."""
    table_ref = f"{client.project}.{dataset_id}.{table_id}"
    table = bigquery.Table(table_ref, schema=schema)

    if partitioning_field:
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partitioning_field
        )

    if clustering_fields:
        table.clustering_fields = clustering_fields

    try:
        table = client.create_table(table, exists_ok=True)
        logger.info(f"Table {dataset_id}.{table_id} created or already exists")
    except Exception as e:
        logger.error(f"Failed to create table {table_id}: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Create BigQuery datasets and tables")
    parser.add_argument("--project_id", required=True, help="GCP project ID")
    parser.add_argument("--location", default="US", help="BigQuery location")
    parser.add_argument("--github", action="store_true", help="Create GitHub Archive tables")
    parser.add_argument("--hackernews", action="store_true", help="Create Hacker News tables")
    parser.add_argument("--all", action="store_true", help="Create all tables")

    args = parser.parse_args()

    if not any([args.github, args.hackernews, args.all]):
        args.all = True

    client = bigquery.Client(project=args.project_id)

    if args.github or args.all:
        logger.info("Creating GitHub Archive dataset and tables...")
        create_dataset(client, "github_dataset", args.location)

        create_table(
            client,
            "github_dataset",
            "events",
            get_github_events_schema(),
            partitioning_field="created_at",
            clustering_fields=["event_type", "repo_id"]
        )

        create_table(
            client,
            "github_dataset",
            "repositories",
            get_repositories_schema()
        )

        create_table(
            client,
            "github_dataset",
            "users",
            get_users_schema()
        )

    if args.hackernews or args.all:
        logger.info("Creating Hacker News dataset and tables...")
        create_dataset(client, "hacker_news", args.location)

        create_table(
            client,
            "hacker_news",
            "stories",
            get_stories_schema(),
            partitioning_field="timestamp",
            clustering_fields=["by", "score"]
        )

        create_table(
            client,
            "hacker_news",
            "comments",
            get_comments_schema(),
            partitioning_field="timestamp",
            clustering_fields=["story_id", "by"]
        )

        create_table(
            client,
            "hacker_news",
            "users",
            get_hn_users_schema()
        )

    logger.info("All datasets and tables created successfully")


if __name__ == "__main__":
    main()
