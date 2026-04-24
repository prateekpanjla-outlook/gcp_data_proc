#!/usr/bin/env python3
"""Test BigQuery emulator with standard client library.

This uses the google-cloud-bigquery library with AnonymousCredentials
to connect to the emulator, which allows using load_table_from_dataframe().
"""

import os
import sys
import pandas as pd

# Set emulator environment
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

# Add src to path
sys.path.insert(0, '/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project')

from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

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
    print("Testing BigQuery Emulator with Standard Client Library")
    print("=" * 60)

    # Create client with AnonymousCredentials
    client_options = ClientOptions(api_endpoint="http://0.0.0.0:9050")
    client = bigquery.Client(
        "test-project",
        client_options=client_options,
        credentials=AnonymousCredentials(),
    )

    print("\nClient created successfully with AnonymousCredentials")

    # Setup dataset and table
    dataset_id = 'test_dataset'
    table_id = 'test_bulk_load_table'
    dataset_ref = client.dataset(dataset_id)
    table_ref = dataset_ref.table(table_id)

    # Create dataset if not exists
    try:
        dataset = client.get_dataset(dataset_ref)
        print(f"\nDataset '{dataset_id}' already exists")
    except Exception:
        print(f"\nCreating dataset '{dataset_id}'")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"
        dataset = client.create_dataset(dataset)

    # Define schema
    schema = [
        bigquery.SchemaField("event_id", "STRING"),
        bigquery.SchemaField("event_type", "STRING"),
        bigquery.SchemaField("actor_login", "STRING"),
        bigquery.SchemaField("repo_name", "STRING"),
        bigquery.SchemaField("created_at", "TIMESTAMP"),
        bigquery.SchemaField("public", "BOOLEAN"),
    ]

    # Create table
    try:
        client.delete_table(table_ref)
        print(f"Deleted existing table '{table_id}'")
    except Exception:
        pass

    print(f"Creating table '{table_id}'")
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table)

    # Create test DataFrame
    print(f"\nCreating test DataFrame with 100 rows...")
    df = create_test_dataframe(100)
    print(f"DataFrame shape: {df.shape}")

    # Test 1: Streaming insert (insertAll)
    print("\n" + "=" * 60)
    print("Test 1: Streaming Insert (insert_rows_json)")
    print("=" * 60)

    rows_to_insert = df.to_dict('records')
    # Convert timestamps to ISO format
    for row in rows_to_insert:
        if pd.notna(row.get('created_at')):
            row['created_at'] = row['created_at'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')

    errors = client.insert_rows_json(table_ref, rows_to_insert)
    print(f"Streaming insert result: {len(errors)} errors")

    if errors:
        print("Errors:")
        for err in errors[:5]:
            print(f"  - {err}")

    # Test 2: Bulk load job (load_table_from_dataframe)
    print("\n" + "=" * 60)
    print("Test 2: Bulk Load Job (load_table_from_dataframe)")
    print("=" * 60)

    # Clear the table first
    client.delete_table(table_ref)
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table)

    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    print(f"Submitting load job...")

    job = client.load_table_from_dataframe(
        df,
        f"{dataset_id}.{table_id}",
        job_config=job_config,
    )

    print(f"Job submitted: {job.job_id}")

    # Wait for job to complete - catch known emulator bug
    from google.api_core.exceptions import BadRequest
    data_loaded = False

    try:
        job.result(timeout=30)
        print(f"Load job completed without error!")
        data_loaded = True
    except BadRequest as e:
        error_msg = str(e)
        if "unspecified job configuration query" in error_msg.lower():
            print(f"\n⚠️  Got expected error: {e}")
            print(f"   (This is a known emulator bug - see issue #224)")
            print(f"   Checking if data was loaded anyway...")
            # Verify data was loaded using COUNT query
            try:
                count_job = client.query(f"SELECT COUNT(*) as cnt FROM `{dataset_id}.{table_id}`")
                count_result = list(count_job.result())[0]
                actual_rows = count_result.get('cnt', 0)
                if actual_rows > 0:
                    print(f"   ✅ Data WAS loaded! Table has {actual_rows} rows")
                    data_loaded = True
                else:
                    print(f"   ❌ Table is empty - data was NOT loaded")
            except Exception as verify_err:
                print(f"   Could not verify: {verify_err}")
        else:
            print(f"Load job failed with unexpected error: {e}")
            raise

    # Verify data with query
    print("\n" + "=" * 60)
    print("Verifying data with query...")
    print("=" * 60)

    query = f"SELECT event_type, COUNT(*) as count FROM `{dataset_id}.{table_id}` GROUP BY event_type"
    query_job = client.query(query)

    results = list(query_job.result())
    print(f"\nQuery results ({len(results)} rows):")
    for row in results:
        print(f"  {dict(row)}")

    print("\n" + "=" * 60)
    print("Test completed!")
    print("=" * 60)

if __name__ == '__main__':
    main()
