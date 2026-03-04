#!/usr/bin/env python3
import os
import sys

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
sys.path.insert(0, '.')

print("Step 1: Imports", flush=True)
from src.shared.bigquery_emulator_client import BigQueryEmulatorAwareClient
print("  OK", flush=True)

from google.cloud import bigquery
print("  OK", flush=True)

print("Step 2: Create client", flush=True)
client = BigQueryEmulatorAwareClient('test-project')
print(f"  EMULATOR={client.is_emulator}", flush=True)

print("Step 3: Call create_dataset", flush=True)
client.create_dataset('test_dataset')
print("  OK", flush=True)

print("Step 4: Call create_table (overwrite=True)", flush=True)
schema = [bigquery.SchemaField('id', 'STRING'), bigquery.SchemaField('value', 'STRING')]
client.create_table(
    dataset_id='test_dataset',
    table_id='test_verify_table',
    schema=schema,
    overwrite=True
)
print("  OK", flush=True)

print("All steps passed!", flush=True)
