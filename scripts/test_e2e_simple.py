#!/usr/bin/env python3
"""
Simplified End-to-End Test: Local -> BigQuery
Tests reading local file and loading to BigQuery emulator
"""

import os
import sys
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# BigQuery imports
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions

# Configuration
BQ_EMULATOR_HOST = os.getenv("BIGQUERY_EMULATOR_HOST", "localhost:9050")
PROJECT_ID = "test-project"
DATASET_ID = "github_dataset"
TABLE_ID = "events"
TEST_FILE = "data/github_archive/test-10k.json.gz"

def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def main():
    print_section("END-TO-END TEST: Local File -> BigQuery")
    print(f"\nConfiguration:")
    print(f"  BigQuery Emulator: http://{BQ_EMULATOR_HOST}")
    print(f"  Project:           {PROJECT_ID}")
    print(f"  Dataset:           {DATASET_ID}")
    print(f"  Table:             {TABLE_ID}")
    print(f"  Test file:         {TEST_FILE}")

    # Step 1: Read local file
    print_section("STEP 1: Reading Local File")

    file_path = Path(TEST_FILE)
    if not file_path.exists():
        print(f"  ERROR: File not found: {file_path}")
        return 1

    print(f"  File: {file_path}")
    print(f"  Size: {file_path.stat().st_size:,} bytes")

    # Read and parse events (limited count for testing)
    print(f"  Reading events...")
    events = []
    max_events = 100  # Limit for faster testing

    with gzip.open(file_path, 'rt') as f:
        for line in f:
            if line.strip():
                try:
                    event = json.loads(line)
                    events.append(event)
                    if len(events) >= max_events:
                        break
                except json.JSONDecodeError:
                    continue

    print(f"  Parsed {len(events)} events")

    # Show sample
    print(f"\n  Sample events:")
    for i, event in enumerate(events[:5]):
        event_type = event.get("type", "Unknown")
        actor = event.get("actor", {}).get("login", "unknown")
        print(f"    [{i+1}] {event_type} by {actor}")

    # Step 2: Load to BigQuery
    print_section("STEP 2: Loading to BigQuery Emulator")

    # Connect to BigQuery emulator
    client_options = ClientOptions(api_endpoint=f"http://{BQ_EMULATOR_HOST}")
    client = bigquery.Client(
        project=PROJECT_ID,
        client_options=client_options,
        credentials=AnonymousCredentials()
    )

    # Create dataset
    dataset_ref = f"{PROJECT_ID}.{DATASET_ID}"
    try:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        client.create_dataset(dataset, exists_ok=True)
        print(f"  Dataset '{DATASET_ID}' ready")
    except Exception as e:
        print(f"  Dataset setup: {e}")

    # Create table
    table_ref = f"{dataset_ref}.{TABLE_ID}"

    schema = [
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("event_type", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("actor_login", "STRING"),
        bigquery.SchemaField("repo_name", "STRING"),
    ]

    try:
        # Drop existing table
        try:
            client.delete_table(table_ref)
        except:
            pass

        table = bigquery.Table(table_ref, schema=schema)
        client.create_table(table)
        print(f"  Table '{TABLE_ID}' created")
    except Exception as e:
        print(f"  Table error: {e}")
        return 1

    # Transform and insert
    print(f"  Transforming {len(events)} events...")

    rows_to_insert = []
    for event in events:
        row = {
            "event_id": event.get("id", f"unknown-{event.get('type')}"),
            "event_type": event.get("type", "Unknown"),
            "created_at": event.get("created_at", datetime.now(timezone.utc).isoformat()),
            "actor_login": event.get("actor", {}).get("login", ""),
            "repo_name": event.get("repo", {}).get("name", ""),
        }
        rows_to_insert.append(row)

    # Insert in one batch
    print(f"  Inserting {len(rows_to_insert)} rows...")
    errors = client.insert_rows_json(table_ref, rows_to_insert)

    if errors:
        print(f"  Errors: {errors}")
        return 1

    print(f"  Inserted {len(rows_to_insert)} rows successfully")

    # Query back
    print_section("STEP 3: Verifying Data")

    query = f"""
        SELECT
            event_type,
            COUNT(*) as count
        FROM `{table_ref}`
        GROUP BY event_type
        ORDER BY count DESC
    """

    try:
        result = client.query(query).to_dataframe()
        print(f"\n  Event Summary:")
        for _, row in result.iterrows():
            print(f"    {row['event_type']}: {row['count']} events")
    except Exception as e:
        print(f"  Query error: {e}")
        return 1

    # Summary
    print_section("TEST SUMMARY")
    print(f"  File:         {TEST_FILE}")
    print(f"  Events read:  {len(events)}")
    print(f"  Rows inserted: {len(rows_to_insert)}")
    print(f"\n  End-to-end test: PASSED")
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())
