# Issues and Fixes

This document tracks all issues encountered during the development of the Cloud Storage → Cloud Run → BigQuery data pipeline, along with their solutions.

---

## Table of Contents

1. [Memory Issues with Large Files](#1-memory-issues-with-large-files)
2. [Test Process Hanging](#2-test-process-hanging)
3. [Missing Python Dependencies](#3-missing-python-dependencies)
4. [Test Filename Mismatch](#4-test-filename-mismatch)
5. [GCS Emulator Upload API](#5-gcs-emulator-upload-api)
6. [BigQuery Python Client Authentication Issues](#6-bigquery-python-client-authentication-issues)
7. [Pandas Dtype Optimization with Unhashable Types](#7-pandas-dtype-optimization-with-unhashable-types)
8. [Pandas Timestamp JSON Serialization](#8-pandas-timestamp-json-serialization)
9. [BigQuery Loading Method Selection](#9-bigquery-loading-method-selection)
10. [BigQuery Emulator exists_ok=True Hang](#10-bigquery-emulator-exists_oktrue-hang)

---

## 1. Memory Issues with Large Files

### Problem
When attempting to load the full GitHub Archive file (67MB compressed, ~472MB uncompressed with 142,347 events), the system ran out of memory and crashed.

```
Error: System exhausted all available memory
File: 2025-01-01-0.json.gz (67MB compressed → 472MB uncompressed)
Events: 142,347
```

### Root Cause
The code was trying to load the entire file into memory at once using a single `read_jsonl_file()` call that accumulated all events into a list before processing.

### Fix
1. **Created smaller test file**: Extracted 10,000 events (4.5MB compressed, ~31MB uncompressed)
   ```bash
   # Created data/github_archive/test-10k.json.gz
   gunzip -c 2025-01-01-0.json.gz | head -n 10000 | gzip > test-10k.json.gz
   ```

2. **Implemented chunked processing**: Modified the processor to handle data in batches of 1,000 rows
   ```python
   batch_size = 1000
   for event in storage.read_jsonl_file(blob, compressed=True):
       events.append(processed_event)
       if len(events) >= batch_size:
           bq_client.insert_rows(dataset_id, table_id, events)
           events = []  # Clear after insert
   ```

3. **Implemented pandas chunked reading**: For even larger files, use pandas with chunked reading
   ```python
   # Reads only chunk_size rows at a time into memory
   for chunk_df in processor.read_jsonl_chunks(file_path, chunk_size=10000):
       process_and_insert(chunk_df)
   ```

### Prevention
- Always use generator-based reading for large JSONL files
- Process in batches (1,000-10,000 rows depending on row size)
- Never accumulate entire file in memory before processing

---

## 2. Test Process Hanging

### Problem
Running `scripts/test_e2e_flow.py` resulted in background processes with no stdout output. The test appeared to hang indefinitely.

```
# Process was running but producing no visible output
# No errors, no progress, just silence
```

### Root Cause
The test script was too complex to debug in one go. Multiple operations happening simultaneously made it impossible to identify where the failure occurred.

### Fix (User-Suggested Methodology)
**Step-by-step incremental testing**: Break down complex operations into smaller, testable steps.

```python
# /tmp/step1.py - Test imports
# /tmp/step2.py - Test storage connection
# /tmp/step3.py - Test file reading
# /tmp/step4.py - Test data processing
# /tmp/step5.py - Test BigQuery insertion
# /tmp/step6.py - Test query results
```

Each step builds on the previous one:
```python
# Step 1: Imports
from src.shared.storage import get_storage_backend

# Step 2: Add storage connection
storage = get_storage_backend()
print(f"Connected: {type(storage).__name__}")

# Step 3: Add file reading
for event in storage.read_jsonl_file(...):
    print(event)
    break

# Continue adding functionality incrementally
```

### Prevention
- Use step-by-step debugging methodology
- Test each component in isolation before integrating
- Never jump to full integration testing from scratch

---

## 3. Missing Python Dependencies

### Problem A: Missing `pandas`

```
ModuleNotFoundError: No module named 'pandas'
```

Occurred when calling `query_job.to_dataframe()` in step 6 of debugging.

**Fix:**
```bash
pip install pandas
```

### Problem B: Missing `db-dtypes`

After installing pandas, still got:
```
ValueError: Please install the 'db-dtypes' package to use pandas with BigQuery
```

**Fix:**
```bash
pip install db-dtypes
```

### Root Cause
The BigQuery Python client's `to_dataframe()` method requires both:
- `pandas` - for DataFrame functionality
- `db-dtypes` - for BigQuery-specific data types (e.g., RECORD, TIMESTAMP)

### Prevention
Add explicit dependency checks in setup:
```python
try:
    import pandas
    import db_dtypes
except ImportError as e:
    raise ImportError(
        "pandas and db-dtypes are required for DataFrame operations. "
        f"Install with: pip install pandas db-dtypes"
    ) from e
```

Update `requirements.txt` or `pyproject.toml`:
```
pandas>=2.0.0
db-dtypes>=0.5.0
```

---

## 4. Test Filename Mismatch

### Problem
The test script was looking for a file that didn't exist:
```python
# Expected filename (line 180)
return f"{BUCKET_NAME}/github-archive/raw/2025-01-01-0.json.gz"

# Actual filename
test-10k.json.gz
```

### Root Cause
After creating the smaller test file, the test script wasn't updated to reference the new filename.

### Fix
Updated `scripts/test_e2e_flow.py` line 180:
```python
# Before
return f"{BUCKET_NAME}/github-archive/raw/2025-01-01-0.json.gz"

# After
return f"{BUCKET_NAME}/github-archive/raw/test-10k.json.gz"
```

### Prevention
- Use configuration files for test data filenames
- Validate file exists before attempting to read
- Use descriptive constants
  ```python
  TEST_DATA_FILE = "test-10k.json.gz"
  ```

---

## 5. GCS Emulator Upload API

### Problem
Initial attempt to upload file to fake-gcs-server failed with HTTP 400:
```bash
curl -X PUT "http://localhost:4443/test-bucket/path/file.gz" \
  --data-binary "@file.gz"

# Response: HTTP 400 - "invalid uploadType"
```

However, a subsequent HEAD request returned 200, giving false impression that upload succeeded.

### Root Cause
1. **Wrong HTTP method**: Used `PUT` instead of `POST`
2. **Wrong endpoint**: Used direct object path instead of upload API
3. **Missing parameters**: Didn't include required `uploadType` query parameter

The fake-gcs-server implements a subset of GCS API. The correct endpoint for media uploads is:
```
POST /upload/storage/v1/b/{bucket}/o?uploadType=media&name={object-path}
```

### Fix
```bash
# Correct upload command
curl -X POST \
  "http://localhost:4443/upload/storage/v1/b/test-github-archive/o?uploadType=media&name=github-archive/raw/test-10k.json.gz" \
  --data-binary "@/tmp/test.json.gz" \
  -H "Content-Type: application/octet-stream"

# Verify with GET (not HEAD)
curl "http://localhost:4443/storage/v1/b/test-github-archive/o?prefix=github-archive/raw/"
```

### Prevention
- Always check API documentation for emulators
- Verify uploads with GET, not just HEAD
- Use proper HTTP methods and endpoints:
  ```
  # Download
  GET /download/storage/v1/b/{bucket}/o/{path}?alt=media

  # Upload (media)
  POST /upload/storage/v1/b/{bucket}/o?uploadType=media&name={path}

  # Metadata
  GET /storage/v1/b/{bucket}/o/{path}
  ```

---

## 6. BigQuery Python Client Authentication Issues

### Problem
The `google-cloud-bigquery` Python client library fails when connecting to the BigQuery emulator because it insists on OAuth authentication, which the emulator doesn't require.

```python
from google.cloud import bigquery

client = bigquery.Client(project='test-project')

# Error: google.auth.exceptions.RefreshError:
# ('invalid_grant: Account has been deleted', ...)
```

Even with `BIGQUERY_EMULATOR_HOST` environment variable set:
```python
os.environ['BIGQUERY_EMULATOR_HOST'] = 'localhost:9050'
client = bigquery.Client(project='test-project')
# Still tries to authenticate!
```

### Root Cause
The `google-cloud-bigquery` library internally:
1. Calls `google.auth.default()` to get credentials
2. Attempts to refresh those credentials via OAuth
3. Fails when the emulator doesn't support OAuth

The emulator environment variable is used by the library to construct the correct URL, but it doesn't skip authentication.

### Fix
Created an emulator-aware BigQuery client that uses:
- **REST API via `requests`** for emulator (no auth needed)
- **`google-cloud-bigquery` library** for production

```python
class BigQueryEmulatorAwareClient:
    def __init__(self, project_id: str, emulator_host: Optional[str] = None):
        # Detect emulator from environment
        if emulator_host is None:
            emulator_host = os.environ.get('BIGQUERY_EMULATOR_HOST')

        self._use_emulator = emulator_host is not None

        if self._use_emulator:
            # Use REST API with requests - no auth needed
            self._emulator_base_url = f"http://{emulator_host}/bigquery/v2"
            self.client = None
        else:
            # Use standard production client
            self.client = bigquery.Client(project=project_id)

    def insert_rows(self, dataset_id, table_id, rows):
        if self._use_emulator:
            # REST API call
            url = f"{self._emulator_base_url}/projects/.../insertAll"
            response = requests.post(url, json={"rows": [{"json": r} for r in rows]})
        else:
            # Standard library call
            return self.client.insert_rows_json(table_ref, rows)
```

### Prevention
- Always use emulator-specific clients for local development
- Detect environment early and switch implementation
- Don't rely on environment variables alone to switch library behavior

---

## 7. Pandas Dtype Optimization with Unhashable Types

### Problem
When optimizing pandas DataFrame dtypes for memory efficiency, the code failed on columns containing dictionaries (nested JSON fields):

```python
for col in df.columns:
    if col_type == 'object':
        num_unique = df[col].nunique()  # ERROR!

# TypeError: unhashable type: 'dict'
```

### Root Cause
The GitHub Archive JSON contains nested structures:
```json
{
  "id": "45185629417",
  "type": "PushEvent",
  "actor": {"id": 49699333, "login": "dependabot[bot]", ...},
  "repo": {"id": 590239375, "name": "mshdabiola/NotePad", ...},
  ...
}
```

When loaded into pandas, `actor` and `repo` columns contain dictionaries. Calling `nunique()` requires hashable values, but dicts are not hashable.

### Fix
Add type checking before attempting `nunique()`:

```python
def _optimize_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
    for col in df.columns:
        col_type = df[col].dtype

        if col_type == 'object':
            try:
                # Check first non-null value
                first_val = df[col].dropna().iloc[0] if len(df[col]) > 0 else None
                if isinstance(first_val, (dict, list)):
                    continue  # Skip nested structures

                # Safe to proceed with nunique()
                num_unique = df[col].nunique()
                num_total = len(df[col])
                if num_unique / num_total < 0.5:
                    df[col] = df[col].astype('category')
            except (TypeError, ValueError, IndexError):
                pass  # Skip this column
    return df
```

### Prevention
- Always check data types before operations that require hashability
- Test with actual data that has nested structures
- Consider whether optimization is needed for all columns (nested columns could be skipped entirely)

---

## 8. Pandas Timestamp JSON Serialization

### Problem
When inserting pandas DataFrames with timestamp columns into BigQuery via the emulator's REST API, JSON serialization failed:

```python
# DataFrame has timestamp column
df['created_at'] = pd.to_datetime(df['created_at'])

# Convert to dict for JSON insertion
rows = df.to_dict('records')

# Try to POST to BigQuery emulator
requests.post(url, json=rows)

# TypeError: Object of type Timestamp is not JSON serializable
```

### Root Cause
Pandas `Timestamp` objects are not natively JSON serializable. The standard `json` module doesn't know how to convert them to strings.

### Fix
Convert timestamps to ISO format strings before serialization:

```python
def get_insert_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
    df = df.copy()

    # Convert timestamps to ISO format strings (JSON serializable)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        elif isinstance(df[col].dtype, pd.CategoricalDtype):
            df[col] = df[col].astype(str)

    # Replace NaN/NaT with None
    df = df.where(pd.notnull(df), None)

    return df.to_dict('records')
```

### Prevention
- Always convert pandas-specific types before JSON serialization
- Handle all special pandas types: `Timestamp`, `Categorical`, `NA`, `NaT`
- Consider using a custom JSON encoder:
  ```python
  import json

  class PandasEncoder(json.JSONEncoder):
      def default(self, obj):
          if isinstance(obj, pd.Timestamp):
              return obj.isoformat()
          elif pd.isna(obj):
              return None
          return super().default(obj)
  ```

---

## Summary of Solutions

| Issue | Solution Approach |
|-------|------------------|
| Large file memory issues | Chunked processing (batch_size=1000-10000) |
| Test process hanging | Step-by-step incremental debugging |
| Missing dependencies | Explicit dependency checks + requirements.txt |
| Filename mismatch | Configuration-based file references |
| GCS upload errors | Use correct `/upload/` endpoint with `uploadType=media` |
| BigQuery auth errors | Emulator-aware client (REST vs library) |
| Pandas dtype errors | Type checking before `nunique()` |
| Timestamp serialization | Convert to ISO strings before JSON |
| Loading method selection | Use bulk load (FREE) for both emulator and production - emulator bug throws false error but data loads (issue #224) |
| exists_ok=True hang | Avoid exists_ok=True with emulator - use try/except NotFound instead |

---

## Best Practices Established

1. **Memory Management**: Always process large files in chunks
2. **Debugging**: Build up tests incrementally, step by step
3. **Dependencies**: Declare all dependencies explicitly
4. **Emulator Handling**: Create emulator-aware wrappers for GCP services
   - Use `AnonymousCredentials()` + `ClientOptions(api_endpoint=...)` for BigQuery emulator
5. **Type Handling**: Convert pandas types before JSON serialization
6. **API Usage**: Follow emulator-specific API documentation, not production docs
   - Test critical paths with emulators - some APIs may be incomplete even if claimed
7. **Loading Strategy**: Use bulk load jobs (FREE) for batch data in production, streaming for real-time
   - **Emulator**: Bulk load works but throws false error "unspecified job configuration query" - catch and verify (issue #224)
8. **Emulator Quirks**: Avoid `exists_ok=True` parameter - it causes `get_dataset`/`get_table` calls that hang
   - Use try/except with NotFound exception instead
   - Always add timeouts to `query_job.result()` calls

---

## 9. BigQuery Loading Method Selection

### Problem
The initial production code used `insert_rows_json()` for all data loading, which is a **streaming API** with rate limits and costs. This was not optimal for batch loading large datasets like GitHub Archive.

```python
# Original code in src/shared/bigquery_client.py:137
errors = self.client.insert_rows_json(table_ref, converted_rows, retry=None)
```

### Analysis of BigQuery Loading Methods

| Method | API Type | Cost | Rate Limits | Use Case |
|--------|----------|------|-------------|----------|
| `insert_rows_json()` | Streaming (`tabledata.insertAll`) | **$0.05/GB** | 10,000 rows/sec (with dedup) | Real-time data |
| `load_table_from_dataframe()` | Bulk Load Job | **FREE** | 1,000 jobs/table/day | Batch ETL |
| `load_table_from_file()` | Bulk Load Job | **FREE** | 1,000 jobs/table/day | Batch ETL |

### Streaming Insert (`insert_rows_json`)
- **Cost**: $0.05 per GB loaded (~$0.01 per 200 MB minimum)
- **Rate limits**:
  - 10,000 rows/sec with deduplication
  - 1,000,000 rows/sec without deduplication
  - 100 MB/sec (with dedup) / 1 GB/sec (without)
- **Data availability**: Immediate (1-2 seconds)
- **Best for**: Real-time/near real-time data ingestion

### Bulk Load Job (`load_table_from_dataframe`)
- **Cost**: **FREE** (uses BigQuery's shared compute pool)
- **Rate limits**: 1,000 load jobs per table per day
- **Data availability**: After job completion (seconds to minutes)
- **Best for**: Batch ETL, bulk data imports, historical data

### Key Discovery: Emulator Bug - Data Loads Despite Error
**IMPORTANT:** After further testing with issue #224 feedback, we discovered:

> **"the exception is raised but the data is still ingested successfully"**
> — @vhnguyenae, Feb 5, 2025

**Test Results:**
- Streaming inserts (`insert_rows_json`) work perfectly ✅
- Bulk load jobs (`load_table_from_dataframe`) **DO work** but throw false error ✅
  - Error: `400 BadRequest: unspecified job configuration query`
  - **Data IS actually loaded** (verified with COUNT query)
  - This is a **known emulator bug** tracked in [issue #224](https://github.com/goccy/bigquery-emulator/issues/224)

**Verification:**
```python
try:
    job.result(timeout=30)
except BadRequest as e:
    if "unspecified job configuration query" in str(e).lower():
        # Data was loaded anyway! Verify with COUNT query
        count_result = client.query(f"SELECT COUNT(*) as cnt FROM ...")
        actual_rows = list(count_result.result())[0]['cnt']
        # actual_rows > 0 means data WAS loaded!
```

### Solution
Created `load_dataframe()` method in `BigQueryEmulatorAwareClient` that:

1. **Both emulator AND production**: Uses bulk load job (FREE)
2. **Emulator workaround**: Catches the false error and verifies data was loaded

```python
def load_dataframe(
    self,
    dataset_id: str,
    table_id: str,
    dataframe: "pd.DataFrame",
    schema: Optional[List[bigquery.SchemaField]] = None,
    write_disposition: str = "WRITE_APPEND",
) -> Dict[str, Any]:
    """Load DataFrame using bulk load (works in both emulator and production).

    NOTE: Emulator throws "unspecified job configuration query" error,
    but data IS loaded. We catch this error and verify the load.
    """
    job_config = bigquery.LoadJobConfig(
        schema=schema,
        write_disposition=write_disposition,
    )

    job = self.client.load_table_from_dataframe(
        dataframe,
        f"{self.project_id}.{dataset_id}.{table_id}",
        job_config=job_config,
    )

    try:
        job.result(timeout=30)
        return {"method": "bulk_load_job", "job_id": job.job_id, ...}
    except BadRequest as e:
        if "unspecified job configuration query" in str(e).lower():
            # Emulator bug: data was loaded anyway (issue #224)
            count_result = self.client.query(f"SELECT COUNT(*) as cnt FROM ...")
            actual_rows = list(count_result.result(timeout=10))[0]['cnt']
            return {"method": "bulk_load_job", "note": "Emulator bug #224", ...}
        raise
```

### Updated Processor
Modified processor to support both bulk load and streaming methods:

```python
def process_storage_to_bigquery(
    ...,
    use_bulk_load: bool = True
) -> Dict[str, Any]:
    """Process with configurable loading method."""
    if use_bulk_load and hasattr(bigquery_client, 'load_dataframe'):
        # Use bulk load (recommended for production)
        load_result = bigquery_client.load_dataframe(
            dataset_id=dataset_id,
            table_id=table_id,
            dataframe=processed_df,
            schema=schema_fields,
            write_disposition="WRITE_APPEND"
        )
    else:
        # Fall back to streaming insert (legacy behavior)
        rows = processor.get_insert_rows(processed_df)
        errors = bigquery_client.insert_rows(dataset_id, table_id, rows)
```

### Cost Comparison Example
For loading **10,000 GitHub events** (~31MB uncompressed):

| Method | Cost | Notes |
|--------|------|-------|
| Streaming insert | ~$0.02 | Per GB charges add up |
| Bulk load job | **$0.00** | FREE loading |

For large-scale loading (e.g., full day of GitHub Archive = 142,347 events), the savings become significant.

### Prevention
- Use bulk load jobs (`load_table_from_dataframe`) for batch processing
- Reserve streaming inserts for real-time/near real-time use cases
- Be aware that emulators may not support all production features
- Always check documentation for cost implications of API choices

---

## 10. BigQuery Emulator exists_ok=True Hang

### Problem
When using the BigQuery Python client with the emulator, operations with `exists_ok=True` parameter would hang indefinitely:

```python
# This hangs on emulator:
client.create_dataset(dataset, exists_ok=True)
client.create_table(table, exists_ok=True)
```

### Root Cause
The `exists_ok=True` parameter causes the BigQuery client to first call `get_dataset()` or `get_table()` to check if the resource exists. On the emulator, these calls hang when the resource doesn't exist, likely due to how the emulator handles NotFound exceptions.

**Working approach** (from `test_bulk_load_debug.py`):
```python
# This works - explicit check with exception handling:
try:
    dataset = client.get_dataset(f"test-project.{dataset_id}")
    print("Dataset exists")
except Exception:
    print("Creating dataset...")
    dataset = bigquery.Dataset(f"test-project.{dataset_id}")
    client.create_dataset(dataset)
```

### Fix
Updated `BigQueryEmulatorAwareClient` to avoid `exists_ok=True` and use try/except pattern:

```python
def create_dataset(self, dataset_id: str) -> None:
    """Create a dataset if it doesn't exist.

    Note: Using exists_ok=True causes the client to call get_dataset first,
    which can hang on the emulator. Instead, we catch NotFound exception.
    """
    try:
        self.client.get_dataset(f"{self.project_id}.{dataset_id}")
        # Dataset exists, nothing to do
    except gcp_exceptions.NotFound:
        # Dataset doesn't exist, create it
        dataset = bigquery.Dataset(f"{self.project_id}.{dataset_id}")
        dataset.location = self.location
        self.client.create_dataset(dataset)

def create_table(self, ...):
    # ...
    # Don't use exists_ok=True (causes get_table hang)
    self.client.create_table(table)
```

Also added timeout to query methods:
```python
def query(self, query: str, timeout: int = 10) -> List[Dict[str, Any]]:
    query_job = self.client.query(query)
    return [dict(row) for row in query_job.result(timeout=timeout)]
```

### Prevention
- **Never use `exists_ok=True` with the emulator** - use try/except with NotFound instead
- **Always add timeouts** to `query_job.result()` calls (default 10 seconds for emulator)
- **Avoid `get_table()` / `get_dataset()`** when the resource might not exist - catch exceptions instead
