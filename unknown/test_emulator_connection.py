#!/usr/bin/env python3
"""Quick test script to verify BigQuery emulator connection."""

import os
import sys
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions


def test_bigquery_emulator():
    """Test connection to BigQuery emulator."""
    emulator_host = os.getenv("BIGQUERY_EMULATOR_HOST", "localhost:9050")

    print(f"Testing BigQuery Emulator at: http://{emulator_host}")
    print("-" * 50)

    # Create client with emulator
    client_options = ClientOptions(api_endpoint=f"http://{emulator_host}")
    client = bigquery.Client(
        project="test-project",
        client_options=client_options,
        credentials=AnonymousCredentials()
    )

    try:
        # Test 1: List datasets
        print("1. Listing datasets...")
        datasets = list(client.list_datasets())
        print(f"   Found {len(datasets)} dataset(s)")
        for dataset in datasets:
            print(f"   - {dataset.dataset_id}")

        # Test 2: Create a test table
        print("\n2. Creating test table...")
        dataset_id = "github_dataset"
        table_id = "test_events"
        table_ref = f"{client.project}.{dataset_id}.{table_id}"

        # Check if dataset exists, create if not
        try:
            dataset = bigquery.Dataset(f"{client.project}.{dataset_id}")
            dataset.location = "US"
            client.create_dataset(dataset, exists_ok=True)
            print(f"   Dataset '{dataset_id}' ready")
        except Exception as e:
            print(f"   Dataset error: {e}")

        # Create table
        schema = [
            bigquery.SchemaField("event_id", "STRING"),
            bigquery.SchemaField("event_type", "STRING"),
            bigquery.SchemaField("created_at", "TIMESTAMP"),
        ]

        table = bigquery.Table(table_ref, schema=schema)
        table = client.create_table(table, exists_ok=True)
        print(f"   Table '{table_id}' created")

        # Test 3: Insert test data
        print("\n3. Inserting test data...")
        rows = [
            {
                "event_id": "test-1",
                "event_type": "PushEvent",
                "created_at": "2025-01-15T14:30:00Z",
            },
            {
                "event_id": "test-2",
                "event_type": "PullRequestEvent",
                "created_at": "2025-01-15T15:45:00Z",
            },
        ]

        errors = client.insert_rows_json(table_ref, rows)
        if errors:
            print(f"   Insert errors: {errors}")
        else:
            print(f"   Inserted {len(rows)} rows successfully")

        # Test 4: Query the data
        print("\n4. Querying test data...")
        query = f"""
            SELECT event_id, event_type, created_at
            FROM `{table_ref}`
            ORDER BY created_at
        """

        result = client.query(query).to_dataframe()
        print(f"   Query returned {len(result)} row(s)")
        for _, row in result.iterrows():
            print(f"   - {row['event_id']}: {row['event_type']} at {row['created_at']}")

        # Test 5: Clean up
        print("\n5. Cleaning up...")
        client.delete_table(table_ref)
        print(f"   Table '{table_id}' deleted")

        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
        return True

    except Exception as e:
        print(f"\nTest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_bigquery_emulator()
    sys.exit(0 if success else 1)
