## 1. Overview

`file_processor.py` contains the core processing logic for Phase 2. It downloads a `.json.gz` file from GCS, decompresses it, reads it in chunks using `pd.read_json(..., chunksize=...)`, validates each chunk, flattens the nested JSON schema, and streams each chunk as a gzip-compressed NDJSON file to the GCS staging bucket.

The module exposes a single public function `process_file()` and a `FileProcessingResult` dataclass that captures success/failure status, record counts, error counts, output file paths, and duration.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `pandas`, `google-cloud-storage`, `google-api-core` (via `requirements.txt`)
- **IAM**: The Cloud Run service account needs `storage.objects.get` / `storage.objects.create` on both landing and staging buckets.
- **Disk**: Temporary disk space for the downloaded `.json.gz` and decompressed `.json` file (Cloud Run `/tmp` is an in-memory tmpfs by default).

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **`main.py`** | Calls `process_file(input_gcs_path, project_id, staging_bucket, chunksize)`. |
| Downstream | **`validators/file_validator.py`** | `validate_file()` validates the file name format; `validate_chunk()` validates each DataFrame chunk. |
| Downstream | **`processors/transformer.py`** | `transform_chunk()` flattens nested JSON fields (actor, repo, payload) into the staging schema. |
| Downstream | **`writers/ndjson_writer.py`** | `write_dataframe_to_gcs()` streams each processed chunk to GCS as `.ndjson.gz`. |
| Downstream | **GCS staging bucket** | Output destination; files are written as `processed/{date_prefix}-chunk-NNN.ndjson.gz`. |

## 4. IAM & Service Accounts

| Identity | Format | Purpose |
|----------|--------|---------|
| **Processor SA** | `{env}-github-archive-processor@{project}.iam.gserviceaccount.com` | Cloud Run service identity inherited from `main.py`. The `storage.Client` created in this module uses Application Default Credentials, which resolve to this SA. |

**Required roles/permissions:**
- `roles/storage.objectViewer` on the **landing bucket** -- needed for `blob.reload()` (metadata fetch) and `blob.download_to_filename()` (file download).
- `roles/storage.objectCreator` on the **staging bucket** -- needed to write processed `.ndjson.gz` chunks via `ndjson_writer`.
- `roles/storage.objectViewer` on the **staging bucket** -- needed for the post-upload `blob.reload()` verification in `ndjson_writer`.

**IAM propagation notes:**
- If the processor SA's storage bindings are updated in Terraform (Layer 01 static), the change may take up to 60 seconds to propagate. During this window, `blob.reload()` or `blob.download_to_filename()` calls will raise `google.api_core.exceptions.Forbidden`.
- Stale SA issues: if a SA is deleted and recreated with the same email, existing Cloud Run revisions may still hold a cached identity token for the old SA. A new Cloud Run revision deployment is required to pick up the fresh credentials.

## 5. Code Walkthrough

1. **`FileProcessingResult` dataclass (lines 33-44)**: Captures all processing metrics: `success`, `input_file`, `output_file` (first chunk), `output_files` (all chunks), `records_in`, `records_out`, `errors`, `warnings`, `duration_seconds`, and an optional `error_message`.

2. **`process_file()` (lines 50-151)**: Public entry point.
   - Creates a single `storage.Client` per file invocation and reuses it for both download and all chunk uploads. The docstring explains why: creating a client per chunk risks HTTP 429 throttling from the metadata server.
   - Parses the `gs://` path to extract bucket name and blob path.
   - Fetches blob metadata with `blob.reload()`; returns a failed result on `Forbidden` or `NotFound`.
   - Calls `validate_file()` to check the file name matches `YYYY-MM-DD-H.json.gz`.
   - Delegates to `_process_with_pandas()` for the actual chunked processing.

3. **`_process_with_pandas()` (lines 154-263)**: Internal chunked processing.
   - Downloads the blob to a temp file, decompresses from `.json.gz` to `.json`.
   - Iterates over the decompressed file with `pd.read_json(lines=True, chunksize=chunksize)`.
   - For each chunk: validates with `validate_chunk()`, transforms with `transform_chunk()`, and writes non-empty results with `write_dataframe_to_gcs()`.
   - Output blobs are named `processed/{date_prefix}-chunk-001.ndjson.gz`, `...-chunk-002.ndjson.gz`, etc.
   - Cleans up temp files in a `finally` block.
   - Determines overall success: at least one output record and error rate below 10%.

4. **Memory note (lines 194-202)**: A TODO comment documents that each chunk currently creates ~4 DataFrame copies (~400 MB at 100K rows) and suggests optimizations to reduce to ~2 copies.
