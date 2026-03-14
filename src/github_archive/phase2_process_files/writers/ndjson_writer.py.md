## 1. Overview

`ndjson_writer.py` writes a Pandas DataFrame to GCS as gzip-compressed newline-delimited JSON (`.ndjson.gz`). It uses the GCS blob streaming upload API (`blob.open('wb')`) to avoid buffering the entire output in memory. Each row is serialised to a JSON string and written line by line through a `GzipFile` wrapper.

The module exposes a single public function `write_dataframe_to_gcs()`.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `pandas`, `google-cloud-storage` (via `requirements.txt`)
- **IAM**: The caller must pass a `storage.Client` whose service account has `storage.objects.create` on the target bucket.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **`processors/file_processor.py`** | Calls `write_dataframe_to_gcs(transform_result.df, blob_name, storage_client, staging_bucket)` for each non-empty chunk. |
| Downstream | **GCS staging bucket** | Output files land at `gs://{bucket}/{blob_name}` (e.g., `gs://staging-bucket/processed/2026-03-05-12-chunk-001.ndjson.gz`). |
| Downstream | **Phase 3 BigQuery loader** | Reads the `.ndjson.gz` files from the staging bucket and loads them into BigQuery. |

## 4. IAM & Service Accounts

| Identity | Format | Purpose |
|----------|--------|---------|
| **Processor SA** | `{env}-github-archive-processor@{project}.iam.gserviceaccount.com` | The `storage_client` passed into `write_dataframe_to_gcs()` is created by `file_processor.py` under the Cloud Run service account. |

**Required roles/permissions:**
- `roles/storage.objectCreator` on the **staging bucket** -- needed for `blob.open('wb')` streaming upload of `.ndjson.gz` files.

**IAM propagation notes:**
- If the `objectCreator` binding on the staging bucket is newly created or modified, there can be a propagation delay of up to 60 seconds. During this window, `blob.open('wb')` will raise `403 Forbidden`.
- Stale SA issues: since the `storage_client` is passed in from `file_processor`, any cached credentials from a deleted-and-recreated SA will persist until the Cloud Run revision is redeployed.

## 5. Code Walkthrough

1. **`write_dataframe_to_gcs()` (lines 20-68)**: Main function.
   - **Parameters**: `df` (DataFrame to write), `blob_name` (GCS object path), `storage_client` (reused client from `file_processor`), `bucket_name`, `compress` (default `True`), `chunk_size` (upload chunk size, default 10 MB).
   - **Blob path** (lines 43-45): Appends `.gz` suffix if `compress=True` and the path does not already end with `.gz`.
   - **Streaming upload** (lines 47-66): Opens the blob in binary write mode with `blob.open('wb', chunk_size=...)`. If compressing, wraps the file object with `gzip.GzipFile`. Iterates `df.to_dict(orient='records')`, serialises each record with `json.dumps()` using a custom default serialiser, and writes the encoded line. The gzip file is closed in a `finally` block to flush the compressed stream.
   - **Return value** (line 68): Returns the full GCS path `gs://{bucket_name}/{blob_path}`.

2. **`_json_serializer(obj)` (lines 71-75)**: Custom JSON serialiser for `json.dumps(default=...)`. Converts `pandas.NA` and other NA-like values to `None` (JSON `null`). Falls back to `str(obj)` for any other non-serialisable type.
