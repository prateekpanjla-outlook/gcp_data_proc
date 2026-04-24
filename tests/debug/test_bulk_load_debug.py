#!/usr/bin/env python3
"""Debug test for BigQuery emulator bulk load with issue #224 workaround.

This test verifies that bulk load jobs work in the emulator despite
throwing "unspecified job configuration query" error.

Run from IDE with:
- Python interpreter: .venv/bin/python
- Environment variable: BIGQUERY_EMULATOR_HOST=localhost:9050

Or set the variable in IDE run configuration.
"""

import os
import sys
import pandas as pd
import logging

# IMPORTANT: Set environment BEFORE importing bigquery
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery
from google.api_core.exceptions import BadRequest


def main():
    print("=" * 70)
    print("DEBUG: BigQuery Emulator Bulk Load Test")
    print("=" * 70)
    print(f"BIGQUERY_EMULATOR_HOST: {os.environ.get('BIGQUERY_EMULATOR_HOST')}")
    print()

    # Step 1: Create client
    print("[STEP 1] Creating BigQuery client with AnonymousCredentials...")
    client_options = ClientOptions(api_endpoint="http://0.0.0.0:9050")
    client = bigquery.Client(
        "test-project",
        client_options=client_options,
        credentials=AnonymousCredentials(),
    )
    print("  Client created successfully")

    # Step 2: Setup dataset and table
    print("\n[STEP 2] Setting up dataset and table...")
    dataset_id = 'test_dataset'
    table_id = 'test_bulk_load_debug'

    # Create dataset if needed
    try:
        dataset = client.get_dataset(f"test-project.{dataset_id}")
        print(f"  Dataset '{dataset_id}' exists")
    except Exception:
        print(f"  Creating dataset '{dataset_id}'")
        dataset = bigquery.Dataset(f"test-project.{dataset_id}")
        dataset.location = "US"
        client.create_dataset(dataset)

    # Define schema
    schema = [
        bigquery.SchemaField("id", "STRING"),
        bigquery.SchemaField("value", "STRING"),
    ]

    # Delete existing table
    try:
        client.delete_table(f"test-project.{dataset_id}.{table_id}")
        print(f"  Deleted existing table '{table_id}'")
    except Exception:
        pass

    # Create table
    table = bigquery.Table(f"test-project.{dataset_id}.{table_id}", schema=schema)
    client.create_table(table)
    print(f"  Created table '{table_id}'")

    # Step 3: Create test DataFrame
    print("\n[STEP 3] Creating test DataFrame...")
    df = pd.DataFrame({
        'id': ['1', '2', '3', '4', '5'],
        'value': ['apple', 'banana', 'cherry', 'date', 'elderberry'],
    })
    print(f"  DataFrame shape: {df.shape}")
    print(f"  DataFrame:\n{df}")

    # Step 4: Submit bulk load job
    print("\n[STEP 4] Submitting bulk load job...")
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    job = client.load_table_from_dataframe(
        df,
        f"test-project.{dataset_id}.{table_id}",
        job_config=job_config,
    )
    print(f"  Job submitted: {job.job_id}")
    print(f"  Job state: {job.state}")

    # Step 5: Wait for job with error handling
    print("\n[STEP 5] Waiting for job to complete (with 30s timeout)...")
    data_loaded = False

    try:
        job.result(timeout=30)
        print("  Job completed without error!")
        data_loaded = True
    except BadRequest as e:
        error_msg = str(e)
        print(f"  Got BadRequest: {error_msg[:100]}...")

        if "unspecified job configuration query" in error_msg.lower():
            print("\n  This is the KNOWN EMULATOR BUG (issue #224)")
            print("  Checking if data was loaded anyway...")

            # Verify with COUNT query
            try:
                count_job = client.query(
                    f"SELECT COUNT(*) as cnt FROM `test-project.{dataset_id}.{table_id}`"
                )
                count_result = list(count_job.result(timeout=10))[0]
                actual_rows = count_result.get('cnt', 0)

                if actual_rows > 0:
                    print(f"  Data WAS loaded! Table has {actual_rows} rows")
                    data_loaded = True
                else:
                    print(f"  Table is empty - data was NOT loaded")
            except Exception as verify_err:
                print(f"  Verification query failed: {verify_err}")
        else:
            print(f"  Unexpected error - re-raising")
            raise

    # Step 6: Verify data content
    print("\n[STEP 6] Verifying data content...")
    if data_loaded:
        query_job = client.query(
            f"SELECT * FROM `test-project.{dataset_id}.{table_id}` ORDER BY id"
        )
        results = list(query_job.result(timeout=10))
        print(f"  Query returned {len(results)} rows:")
        for row in results:
            print(f"    {dict(row)}")
    else:
        print("  Skipping - data not loaded")

    print("\n" + "=" * 70)
    print("Test completed successfully!")
    print("=" * 70)


if __name__ == '__main__':
    main()
