#!/usr/bin/env python3
import os
import sys
import pandas as pd

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
sys.path.insert(0, '.')

from src.shared.bigquery_emulator_client import BigQueryEmulatorAwareClient
from google.cloud import bigquery

print("Step 1: Create client", flush=True)
client = BigQueryEmulatorAwareClient('test-project')
print(f"  EMULATOR={client.is_emulator}", flush=True)

print("Step 2: Delete table directly", flush=True)
try:
    client.client.delete_table("test-project.test_dataset.test_verify_table")
    print("  Deleted existing table", flush=True)
except: pass

print("Step 3: Create table (overwrite=False)", flush=True)
dataset_id = 'test_dataset'
table_id = 'test_verify_table'
schema = [bigquery.SchemaField('id', 'STRING'), bigquery.SchemaField('value', 'STRING')]

client.create_table(dataset_id=dataset_id, table_id=table_id, schema=schema, overwrite=False)
print("  OK", flush=True)

print("Step 4: Test query method", flush=True)
count_result = client.query(f'SELECT COUNT(*) as cnt FROM `test-project.{dataset_id}.{table_id}`')
print(f"  OK: {count_result}", flush=True)

print("Step 5: Test load_dataframe", flush=True)
df = pd.DataFrame({'id': ['x', 'y', 'z'], 'value': ['a', 'b', 'c']})
result = client.load_dataframe(dataset_id, table_id, df, schema=schema)
print(f"  Method: {result.get('method')}", flush=True)
print(f"  State: {result.get('state')}", flush=True)
print(f"  Num rows: {result.get('num_rows')}", flush=True)
print(f"  Note: {result.get('note')}", flush=True)

print("Step 6: Verify data", flush=True)
count_result = client.query(f'SELECT COUNT(*) as cnt FROM `test-project.{dataset_id}.{table_id}`')
count_row = count_result[0]
print(f"  Actual rows: {count_row['cnt']}", flush=True)

print("All steps passed!", flush=True)
