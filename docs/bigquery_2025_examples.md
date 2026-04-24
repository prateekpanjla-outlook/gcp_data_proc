# BigQuery Python Examples and Best Practices (2025)

This guide covers modern BigQuery Python patterns, emulator testing, and 2025 best practices.

## Table of Contents

- [Quick Start with Emulator](#quick-start-with-emulator)
- [Python Client Setup](#python-client-setup)
- [Connection Patterns](#connection-patterns)
- [Data Operations](#data-operations)
- [Query Best Practices](#query-best-practices)
- [Testing with Emulator](#testing-with-emulator)
- [Performance Optimization](#performance-optimization)
- [Cost Control](#cost-control)

## Quick Start with Emulator

### Start the BigQuery Emulator

```bash
# Using Docker Compose
docker compose -f docker-compose.test.yml up -d bigquery

# Or with Docker directly
docker run -d -p 9050:9050 -p 9060:9060 \
  ghcr.io/goccy/bigquery-emulator:latest \
  --project test-project \
  --dataset github_dataset \
  --dataset hacker_news
```

### Connect from Python

```python
import os
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions

# For emulator
emulator_host = os.getenv("BIGQUERY_EMULATOR_HOST", "localhost:9050")
client_options = ClientOptions(api_endpoint=f"http://{emulator_host}")

client = bigquery.Client(
    project="test-project",
    client_options=client_options,
    credentials=AnonymousCredentials()
)

# For production (uses ADC)
# client = bigquery.Client()
```

## Python Client Setup

### Installation (2025)

```bash
# Create virtual environment (required for Ubuntu 24.04+)
python3 -m venv .venv
source .venv/bin/activate

# Install packages
pip install google-cloud-bigquery pandas google-auth
```

### Project Configuration

```pyproject.toml>
[tool.poetry.dependencies]
python = "^3.11"
google-cloud-bigquery = "^3.25.0"
pandas-gbq = "^0.23.0"
google-auth = "^2.29.0"
```

## Connection Patterns

### Pattern 1: Service Account (Production)

```python
import os
from google.cloud import bigquery
from google.oauth2 import service_account

# Use environment variable for credentials path
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
credentials = service_account.Credentials.from_service_account_file(
    credentials_path,
    scopes=["https://www.googleapis.com/auth/cloud-platform"]
)

client = bigquery.Client(
    project="your-project-id",
    credentials=credentials
)
```

### Pattern 2: Application Default Credentials (Development)

```python
from google.cloud import bigquery

# Uses gcloud auth application-default login
client = bigquery.Client(project="your-project-id")
```

### Pattern 3: Anonymous Credentials (Emulator/Testing)

```python
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions

client_options = ClientOptions(api_endpoint="http://localhost:9050")
client = bigquery.Client(
    project="test-project",
    client_options=client_options,
    credentials=AnonymousCredentials()
)
```

### Pattern 4: With Custom Timeout and Retry

```python
from google.cloud import bigquery
from google.api_core.retry import Retry
from datetime import timedelta

client = bigquery.Client(project="your-project-id")
client.default_query_job_config.timeout = timedelta(minutes=5)
client.default_query_job_config.retry = Retry(deadline=60)
```

## Data Operations

### Creating Tables with Schema

```python
from google.cloud import bigquery

# Define schema
schema = [
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_type", "STRING"),
    bigquery.SchemaField("created_at", "TIMESTAMP"),
    bigquery.SchemaField("actor_login", "STRING"),
    bigquery.SchemaField("repo_name", "STRING"),
    bigquery.SchemaField("payload", "JSON"),
    bigquery.SchemaField("ingestion_timestamp", "TIMESTAMP"),
]

# Create table with partitioning
table_ref = f"{project}.{dataset_id}.{table_id}"
table = bigquery.Table(table_ref, schema=schema)

# Add partitioning (2025 best practice)
table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY,
    field="created_at",
    expiration_ms=7776000000  # 90 days
)

# Add clustering for better query performance
table.clustering = bigquery.Clustering(fields=["event_type", "actor_login"])

table = client.create_table(table, exists_ok=True)
print(f"Created table {table.table_id}")
```

### Loading Data from GCS

```python
from google.cloud import bigquery

# Configure load job
job_config = bigquery.LoadJobConfig(
    schema=schema,
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
    time_partitioning=bigquery.TimePartitioning(
        type_=bigquery.TimePartitioningType.DAY,
        field="created_at"
    ),
    clustering=bigquery.Clustering(fields=["event_type"]),
    # Allow field additions for schema evolution
    schema_update_options=[
        bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
    ]
)

# Load from GCS
load_job = client.load_table_from_uri(
    f"gs://{bucket_name}/github-archive/raw/*.json.gz",
    table_ref,
    job_config=job_config
)

load_job.result()  # Wait for completion
print(f"Loaded {load_job.output_rows} rows")
```

### Streaming Insert (Individual Rows)

```python
# For single-row inserts or low-volume streaming
rows_to_insert = [
    {
        "event_id": "12345",
        "event_type": "PushEvent",
        "created_at": "2025-03-02T14:30:00Z",
        "actor_login": "user123",
        "repo_name": "org/repo",
    }
]

errors = client.insert_rows_json(table_ref, rows_to_insert)
if errors:
    print(f"Errors: {errors}")
```

### Batch Insert with Query API

```python
# For bulk inserts, use INSERT via query
query = f"""
    INSERT INTO `{table_ref}` (event_id, event_type, created_at, actor_login)
    VALUES
        ('12345', 'PushEvent', TIMESTAMP('2025-03-02T14:30:00Z'), 'user1'),
        ('12346', 'PullRequestEvent', TIMESTAMP('2025-03-02T14:31:00Z'), 'user2')
"""

job = client.query(query)
job.result()  # Wait for completion
print(f"Inserted {job.num_dml_updates} rows")
```

## Query Best Practices

### Parameterized Queries (Security)

```python
from google.cloud import bigquery

query = """
    SELECT event_id, event_type, actor_login
    FROM `project.dataset.events`
    WHERE event_type = @event_type
      AND created_at >= @start_time
      AND created_at < @end_time
    LIMIT @limit
"""

job_config = bigquery.QueryJobConfig(
    query_parameters=[
        bigquery.ScalarQueryParameter("event_type", "STRING", "PushEvent"),
        bigquery.ScalarQueryParameter("start_time", "TIMESTAMP", "2025-01-01T00:00:00Z"),
        bigquery.ScalarQueryParameter("end_time", "TIMESTAMP", "2025-02-01T00:00:00Z"),
        bigquery.ScalarQueryParameter("limit", "INT64", 1000),
    ]
)

results = client.query(query, job_config=job_config)
df = results.to_dataframe()
```

### Query with Dry Run (Cost Estimation)

```python
job_config = bigquery.QueryJobConfig()
job_config.dry_run = True
job_config.use_query_cache = False

job = client.query(query, job_config=job_config)

print(f"This query will process {job.total_bytes_processed} bytes")
print(f"Estimated cost: ${job.total_bytes_processed / 10**12 * 5:.2f}")
```

### Query with Result Caching Control

```python
job_config = bigquery.QueryJobConfig()
# Disable cache for fresh data
job_config.use_query_cache = False
# Or set maximum cache age (24 hours default)
job_config.maximum_bytes_billed = 1_000_000_000  # 1 GB limit

results = client.query(query, job_config=job_config)
```

### Efficient Query Patterns (2025)

```sql
-- Good: Specific columns with early filtering
SELECT
    event_id,
    event_type,
    actor_login
FROM `project.dataset.events`
WHERE created_at >= TIMESTAMP('2025-01-01')
  AND event_type IN ('PushEvent', 'PullRequestEvent')
ORDER BY created_at DESC
LIMIT 1000

-- Bad: SELECT * with no filtering
SELECT * FROM `project.dataset.events`

-- Good: Use EXCEPT to exclude specific columns
SELECT * EXCEPT (payload_raw, raw_metadata)
FROM `project.dataset.events`

-- Good: Approximate aggregations
SELECT
    event_type,
    APPROX_COUNT_DISTINCT(actor_login) as unique_users,
    COUNT(*) as event_count
FROM `project.dataset.events`
GROUP BY event_type

-- Good: Window functions instead of self-joins
SELECT
    event_id,
    event_type,
    created_at,
    LAG(created_at) OVER (PARTITION BY actor_login ORDER BY created_at) as prev_event
FROM `project.dataset.events`
```

## Testing with Emulator

### Setup Test Fixtures

```python
import pytest
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions

@pytest.fixture
def bq_client():
    """BigQuery client for emulator testing."""
    emulator_host = "localhost:9050"
    client_options = ClientOptions(api_endpoint=f"http://{emulator_host}")
    return bigquery.Client(
        project="test-project",
        client_options=client_options,
        credentials=AnonymousCredentials()
    )

@pytest.fixture
def test_table(bq_client):
    """Create and cleanup test table."""
    table_ref = "test-project.test_dataset.test_table"
    schema = [
        bigquery.SchemaField("id", "INTEGER"),
        bigquery.SchemaField("name", "STRING"),
    ]
    table = bigquery.Table(table_ref, schema=schema)
    bq_client.create_table(table, exists_ok=True)

    yield table_ref

    # Cleanup
    bq_client.delete_table(table_ref)

def test_insert_and_query(bq_client, test_table):
    """Test basic CRUD operations."""
    # Insert data
    rows = [{"id": 1, "name": "Test"}]
    errors = bq_client.insert_rows_json(test_table, rows)
    assert len(errors) == 0

    # Query data
    results = bq_client.query(f"SELECT * FROM `{test_table}`").to_dataframe()
    assert len(results) == 1
    assert results.iloc[0]["name"] == "Test"
```

### Run Tests

```bash
# Start emulator
docker compose -f docker-compose.test.yml up -d bigquery

# Run tests
BIGQUERY_EMULATOR_HOST=http://localhost:9050 pytest tests/ -v
```

## Performance Optimization

### Partitioning Best Practices

```python
# Date partitioning (most common)
table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY,
    field="created_at",
    expiration_ms=7776000000  # 90 days
)

# Ingestion-time partitioning (no field needed)
table.time_partitioning = bigquery.TimePartitioning(
    type_=bigquery.TimePartitioningType.DAY
)
```

### Clustering Best Practices

```python
# Cluster by most-filtered columns
table.clustering = bigquery.Clustering(fields=[
    "event_type",   # High cardinality, often filtered
    "actor_login"   # Often used in joins
])

# Cluster order matters: most filtered first
# Good: event_type, actor_login
# Bad: actor_login, event_type (if you filter by type more often)
```

### Materialized Views (2025)

```python
# Create materialized view for frequent aggregations
mv_query = """
CREATE MATERIALIZED VIEW `project.dataset.daily_event_stats`
AS
SELECT
    DATE(created_at) as event_date,
    event_type,
    COUNT(*) as event_count,
    APPROX_COUNT_DISTINCT(actor_login) as unique_users
FROM `project.dataset.events`
GROUP BY 1, 2
"""

job = client.query(mv_query)
job.result()

# Query materialized view automatically used by optimizer
results = client.query("""
    SELECT event_date, event_type, event_count
    FROM `project.dataset.daily_event_stats`
    WHERE event_date >= '2025-01-01'
""").to_dataframe()
```

### Query Performance Tips

```python
# Use query caching
job_config = bigquery.QueryJobConfig(use_query_cache=True)

# Set maximum bytes billed to prevent runaway queries
job_config = bigquery.QueryJobConfig(
    maximum_bytes_billed=1_000_000_000  # 1 GB = $0.005
)

# Use destination table for large results
job_config = bigquery.QueryJobConfig(
    destination=f"temp_project.temp_dataset.results_{int(time.time())}",
    write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
)
```

## Cost Control

### Cost Monitoring

```python
def estimate_query_cost(client, query):
    """Estimate query cost before running."""
    job_config = bigquery.QueryJobConfig(dry_run=True)
    job = client.query(query, job_config=job_config)

    bytes_processed = job.total_bytes_processed
    gb_processed = bytes_processed / 10**9
    on_demand_cost = gb_processed * 5  # $5 per TB

    return {
        "bytes_processed": bytes_processed,
        "gb_processed": gb_processed,
        "estimated_cost_usd": on_demand_cost
    }

# Usage
cost_info = estimate_query_cost(client, query)
print(f"Estimated cost: ${cost_info['estimated_cost_usd']:.4f}")
```

### Slot Reservation Recommendations (2025)

```python
# For production workloads, consider reservations:
# - Standard Edition: Up to 1600 slots
# - Enterprise Edition: Enhanced security + ML
# - Enterprise Plus: Highest elasticity + disaster recovery

# 57% discount with 1-year commitment
# 70% discount with 3-year commitment
```

### Cost Optimization Checklist

- [ ] Use partitioned tables for time-series data
- [ ] Use clustering on high-cardinality columns
- [ ] Avoid SELECT * - specify columns
- [ ] Use approximate functions (APPROX_COUNT_DISTINCT)
- [ ] Set maximum_bytes_billed on all queries
- [ ] Use query dry-run before expensive operations
- [ ] Schedule batch jobs during off-peak hours
- [ ] Use materialized views for frequent aggregations
- [ ] Monitor slot usage with INFORMATION_SCHEMA

## Sources

- [BigQuery Python Client Documentation](https://cloud.google.com/python/docs/reference/bigquery/latest)
- [goccy/bigquery-emulator GitHub](https://github.com/goccy/bigquery-emulator)
- [BigQuery Best Practices for Costs](https://cloud.google.com/bigquery/docs/best-practices-costs)
- [BigQuery Performance Optimization](https://www.linkedin.com/posts/lakshmi-gangireddygari185_bigquery-dataengineering-sql-activity-7424854984753627136-0ewG)
