#!/usr/bin/env python3
import os
import sys

os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
sys.path.insert(0, '.')

from google.api_core.client_options import ClientOptions
from google.auth.credentials import AnonymousCredentials
from google.cloud import bigquery

print("Step 1: Create client", flush=True)
client_options = ClientOptions(api_endpoint="http://0.0.0.0:9050")
client = bigquery.Client("test-project", client_options=client_options, credentials=AnonymousCredentials())
print("  OK", flush=True)

print("Step 2: Create dataset", flush=True)
dataset = bigquery.Dataset("test-project.test_dataset")
dataset.location = "US"
client.create_dataset(dataset, exists_ok=True)
print("  OK", flush=True)

print("Step 3: Create table", flush=True)
schema = [bigquery.SchemaField("id", "STRING"), bigquery.SchemaField("value", "STRING")]
table = bigquery.Table("test-project.test_dataset.test_verify_table", schema=schema)
client.create_table(table, exists_ok=True)
print("  OK", flush=True)

print("All steps passed!", flush=True)
