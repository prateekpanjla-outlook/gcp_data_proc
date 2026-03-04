#!/usr/bin/env python3
"""Test BigQuery emulator bulk load job functionality.

This tests the load_dataframe() method with the BigQuery emulator
to verify that bulk load jobs work via REST API.
"""

import os
import sys
import pandas as pd

# Set emulator environment
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

# Add src to path
sys.path.insert(0, '/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project')

from src.shared.bigquery_emulator_client import BigQueryEmulatorAwareClient

def create_test_dataframe(num_rows=100):
    """Create a simple test DataFrame."""
    data = {
        'event_id': [f'event_{i}' for i in range(num_rows)],
        'event_type': ['PushEvent', 'PullRequestEvent', 'IssueCommentEvent'] * (num_rows // 3 + 1),
        'actor_login': [f'user_{i % 10}' for i in range(num_rows)],
        'repo_name': [f'repo_{i % 5}' for i in range(num_rows)],
        'created_at': pd.date_range('2025-01-01', periods=num_rows, freq='1min').tolist(),
        'public': [True] * num_rows,
    }
    # Trim to exact size
    for col in data:
        data[col] = data[col][:num_rows]

    return pd.DataFrame(data)

def main():
    print("=" * 60)
    print("Testing BigQuery Emulator Bulk Load Job")
    print("=" * 60)

    # Create client
    client = BigQueryEmulatorAwareClient(
        project_id='test-project',
        location='US'
    )

    print(f"\nClient mode: {'EMULATOR' if client.is_emulator else 'PRODUCTION'}")

    # Create dataset and table
    dataset_id = 'test_dataset'
    table_id = 'test_bulk_load_table'

    print(f"\nCreating dataset: {dataset_id}")
    client.create_dataset(dataset_id)

    # Create table first
    from google.cloud import bigquery
    schema = [
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("event_type", "STRING"),
        bigquery.SchemaField("actor_login", "STRING"),
        bigquery.SchemaField("repo_name", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("public", "BOOLEAN"),
    ]

    print(f"Creating table: {table_id}")
    client.create_table(
        dataset_id=dataset_id,
        table_id=table_id,
        schema=schema,
        overwrite=True
    )

    # Create test DataFrame
    print(f"\nCreating test DataFrame with 100 rows...")
    df = create_test_dataframe(100)
    print(f"DataFrame shape: {df.shape}")
    print(f"DataFrame dtypes:\n{df.dtypes}")

    # Test bulk load
    print(f"\n" + "-" * 60)
    print("Testing load_dataframe() method...")
    print("-" * 60)

    result = client.load_dataframe(
        dataset_id=dataset_id,
        table_id=table_id,
        dataframe=df,
        schema=schema,
        write_disposition="WRITE_APPEND"
    )

    print(f"\nLoad Result:")
    print(f"  Method: {result.get('method')}")
    print(f"  Job ID: {result.get('job_id')}")
    print(f"  State: {result.get('state')}")
    print(f"  Rows: {result.get('num_rows')}")
    print(f"  Errors: {len(result.get('errors', []))}")

    if result.get('errors'):
        print(f"\nErrors:")
        for err in result['errors']:
            print(f"  - {err}")

    # Verify data with query
    print(f"\n" + "-" * 60)
    print("Verifying data with query...")
    print("-" * 60)

    try:
        query = f"SELECT event_type, COUNT(*) as count FROM `{dataset_id}.{table_id}` GROUP BY event_type"
        rows = client.query(query)

        print(f"\nQuery results:")
        for row in rows:
            print(f"  {row}")
    except Exception as e:
        print(f"Query failed: {e}")

    print(f"\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == '__main__':
    main()
