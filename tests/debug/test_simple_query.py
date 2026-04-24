#!/usr/bin/env python3
import os
import sys

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'

from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

print("Step 1: Create client", flush=True)
client_options = ClientOptions(api_endpoint="http://0.0.0.0:9050")
client = bigquery.Client("test-project", client_options=client_options, credentials=AnonymousCredentials())
print("  OK", flush=True)

print("Step 2: Create table", flush=True)
schema = [bigquery.SchemaField("id", "STRING"), bigquery.SchemaField("value", "STRING")]
try:
    client.delete_table("test-project.test_dataset.test_verify_table")
except: pass
table = bigquery.Table("test-project.test_dataset.test_verify_table", schema=schema)
client.create_table(table)
print("  OK", flush=True)

print("Step 3: Simple query", flush=True)
query_job = client.query("SELECT 1 as test")
result = list(query_job.result(timeout=5))
print(f"  OK: {result}", flush=True)

print("Step 4: COUNT query", flush=True)
count_job = client.query("SELECT COUNT(*) as cnt FROM `test-project.test_dataset.test_verify_table`")
count_result = list(count_job.result(timeout=5))
print(f"  OK: {count_result}", flush=True)

print("All steps passed!", flush=True)
