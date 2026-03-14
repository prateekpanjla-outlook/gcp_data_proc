## 1. Overview

`main.py` is the Flask application entry point for the Phase 2 Cloud Run Service. It receives Eventarc notifications when new `.json.gz` files land in the GCS landing bucket, performs path filtering and file-size checks, then delegates the actual processing to `file_processor.process_file()`. It returns structured JSON responses with processing statistics (records in/out, errors, warnings, output file paths).

Key behaviors:
- Listens on `0.0.0.0:8080` (Cloud Run requirement).
- Filters events to only process files matching `github-archive/raw/*.json.gz`.
- Rejects files exceeding `FILE_SIZE_THRESHOLD_MB` (default 50 MB) with HTTP 413.
- Returns HTTP 200 on success, 207 on partial success (errors < 10%), and 500 on failure.

## 2. Prerequisites

- **Python** >= 3.11
- **Packages**: `flask`, `google-cloud-storage`, `google-api-core` (installed via `requirements.txt`)
- **Environment variables** (set by Cloud Run / Terraform):
  - `PROJECT_ID` -- GCP project ID
  - `LANDING_BUCKET` -- source bucket name (Eventarc watches this bucket)
  - `STAGING_BUCKET` -- destination bucket for processed NDJSON files
  - `FILE_SIZE_THRESHOLD_MB` -- max allowed file size in MB (default `50`)
  - `CHUNKSIZE` -- rows per processing chunk (default `100000`)
  - `PORT` -- HTTP port (default `8080`)
- **IAM**: Cloud Run service account needs `storage.objects.get` on the landing bucket and permissions delegated through `file_processor`.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **Eventarc trigger** | Sends HTTP POST with Cloud Storage event payload (`bucket`, `name`) when a file is created in the landing bucket. |
| Upstream | **GCS landing bucket** | Source of `.json.gz` files deposited by Phase 1 ingestion. |
| Downstream | **`processors/file_processor.py`** | `process_file()` is called with the GCS path, project ID, staging bucket, and chunk size. |
| Downstream | **GCS staging bucket** | Receives processed `.ndjson.gz` chunks written by the file processor. |
| Downstream | **Phase 3 BigQuery loader** | Picks up `.ndjson.gz` files from the staging bucket and loads them into BigQuery. |

## 4. Code Walkthrough

1. **Module-level configuration (lines 20-30)**: Reads environment variables for project ID, bucket names, file size threshold, chunk size, and port. Initialises a `storage.Client` at module scope so it is reused across requests.

2. **Health check -- `GET /` and `GET /health` (lines 47-57)**: Returns a JSON object with service status, project, and bucket names. Used by Cloud Run health checks and the Dockerfile `HEALTHCHECK` directive.

3. **Event handler -- `POST /` `process_file_event()` (lines 64-155)**:
   - **Payload parsing** (lines 78-85): Extracts JSON body from the Eventarc request; returns 400 if missing or malformed.
   - **Path filtering** (lines 94-104): Skips files that do not match `github-archive/raw/*.json.gz` by checking prefix, extension, and subdirectory. Returns 200 with `status: ignored`.
   - **File size check** (lines 110-123): Calls `blob.reload()` to fetch metadata, compares size against `FILE_SIZE_THRESHOLD_MB`, and returns 413 if too large.
   - **Processing** (lines 126-155): Calls `process_file()` from `file_processor`. On success, returns a response with `input_file`, `output_files`, `records_in`, `records_out`, `errors`, and `warnings`. On exception, returns 500.

4. **Application startup (lines 162-165)**: When run directly (`__main__`), starts the Flask development server. In production, Gunicorn launches the `app` object (see `Dockerfile.processor`).
