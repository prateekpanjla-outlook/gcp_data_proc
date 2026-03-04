#!/usr/bin/env python3
import os
import sys
import pandas as pd

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
sys.path.insert(0, '.')

from src.shared.bigquery_emulator_client import BigQueryEmulatorAwareClient
from google.cloud import bigquery

print('Creating client...', flush=True)
client = BigQueryEmulatorAwareClient('test-project')
print(f'Client mode: EMULATOR={client.is_emulator}', flush=True)

dataset_id = 'test_dataset'
table_id = 'test_verify_table'
schema = [bigquery.SchemaField('id', 'STRING'), bigquery.SchemaField('value', 'STRING')]

client.create_dataset(dataset_id)
print('Calling create_table with overwrite=True...', flush=True)
client.create_table(dataset_id=dataset_id, table_id=table_id, schema=schema, overwrite=True)
print('Table created!', flush=True)

df = pd.DataFrame({'id': ['x', 'y', 'z'], 'value': ['a', 'b', 'c']})

print('Testing load_dataframe...', flush=True)
result = client.load_dataframe(dataset_id, table_id, df, schema=schema)
print(f"Method: {result.get('method')}", flush=True)
print(f"State: {result.get('state')}", flush=True)
print(f"Num rows: {result.get('num_rows')}", flush=True)
print(f"Note: {result.get('note')}", flush=True)

# Verify
count_result = client.query(f'SELECT COUNT(*) as cnt FROM `test-project.{dataset_id}.{table_id}`')
count_row = count_result[0]
print(f'Actual rows in table: {count_row["cnt"]}', flush=True)
print('SUCCESS!', flush=True)
