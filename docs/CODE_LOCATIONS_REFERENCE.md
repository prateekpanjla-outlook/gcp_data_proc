# GitHub Archive Data Pipeline - Code Location Reference

**Generated:** 2026-03-11
**Purpose:** Exact file paths and line numbers for all diagram components

---

## Quick Reference Table

| Phase | Total Files | Core Files | Infrastructure Files | Test Files |
|-------|-------------|------------|----------------------|------------|
| Phase 1 | 8 | 2 | 5 | 1 |
| Phase 2 | 24 | 16 | 6 | 2 |
| Phase 3 | 12 | 1 | 10 | 1 |
| **Total** | **44** | **19** | **21** | **4** |

---

## Phase 1: Data Ingestion - Code Locations

### 📁 Directory Structure

```
infrastructure/phase1_ingestion/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── locals.tf
│   ├── storage.tf
│   ├── cloud_run_jobs.tf
│   ├── scheduler.tf
│   ├── service_accounts.tf
│   └── iam_bindings.tf
├── scripts/
│   └── download.sh
└── STATUS.md
```

### 🔍 Component Locations

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Cloud Scheduler** | `infrastructure/phase1_ingestion/terraform/scheduler.tf` | 1-25 | Hourly trigger definition |
| Schedule Expression | `infrastructure/phase1_ingestion/terraform/scheduler.tf` | 12 | `0 * * * *` (hourly) |
| **Cloud Run Job** | `infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf` | 1-50 | Job resource definition |
| Job Container | `infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf` | 20-35 | gcloud-cli slim image |
| **Download Script** | `infrastructure/phase1_ingestion/scripts/download.sh` | 1-80 | Main logic |
| Calculate Filename | `infrastructure/phase1_ingestion/scripts/download.sh` | 25-35 | Date math |
| Idempotency Check | `infrastructure/phase1_ingestion/scripts/download.sh` | 40-45 | gsutil stat |
| Download Command | `infrastructure/phase1_ingestion/scripts/download.sh` | 50-60 | curl from gharchive |
| Upload Command | `infrastructure/phase1_ingestion/scripts/download.sh` | 65-75 | gsutil cp |
| JSON Logging | `infrastructure/phase1_ingestion/scripts/download.sh` | 78-85 | Structured logs |
| **Landing Bucket** | `infrastructure/phase1_ingestion/terraform/storage.tf` | 1-30 | GCS bucket |
| Bucket Path | `infrastructure/phase1_ingestion/terraform/storage.tf` | 15-20 | `github-archive/raw/` |
| **Service Account** | `infrastructure/phase1_ingestion/terraform/service_accounts.tf` | 1-25 | Downloader SA |
| IAM Bindings | `infrastructure/phase1_ingestion/terraform/iam_bindings.tf` | 1-40 | Roles and permissions |

### 📍 Key Code Snippets

#### Download Script (download.sh:25-35)
```bash
# Calculate target filename
HOURS_AGO=${HOURS_AGO:-1}
TARGET_DATE=$(date -u -d "$HOURS_AGO hours ago" +%Y-%m-%-%H)
TARGET_FILE="${TARGET_DATE}.json.gz"
```

#### Idempotency Check (download.sh:40-45)
```bash
# Check if file already exists
if gsutil -q stat "gs://${BUCKET_NAME}/github-archive/raw/${TARGET_FILE}"; then
    log_message "download_skipped" "File already exists"
    exit 0
fi
```

---

## Phase 2: Data Processing - Code Locations

### 📁 Directory Structure

```
src/github_archive/phase2_process_files/
├── main.py                                    # Flask entry point
├── processors/
│   ├── __init__.py
│   ├── file_processor.py                      # Main orchestrator
│   ├── file_splitter.py                       # ⭐ Large file handling
│   └── transformer.py                         # Schema flattening
├── validators/
│   ├── __init__.py
│   ├── file_validator.py                      # File validation
│   ├── dtype_validator.py                     # Type validation
│   └── value_validator.py                     # Value validation
├── writers/
│   ├── __init__.py
│   └── ndjson_writer.py                       # GCS output
├── utils/
│   ├── __init__.py
│   ├── gcs_client.py                          # GCS utilities
│   └── logger.py                              # Structured logging
├── schemas/
│   ├── __init__.py
│   └── dtype_definitions.py                   # Schema mappings
└── test_local.py                              # Local testing

infrastructure/phase2_process_files/
├── terraform/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── locals.tf
│   ├── storage.tf
│   ├── cloud_run_service.tf                   # Processor service
│   ├── cloud_run_jobs.tf                      # Splitter job
│   ├── eventarc.tf                            # Triggers
│   ├── service_accounts.tf
│   └── iam_bindings.tf
└── scripts/
    ├── build_and_push.sh
    ├── deploy.sh
    └── test_cloud_run.sh
```

### 🔍 Component Locations

#### Entry Point & Event Handling

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Flask App** | `src/github_archive/phase2_process_files/main.py` | 36 | App initialization |
| Health Check | `src/github_archive/phase2_process_files/main.py` | 62-72 | GET /health |
| Readiness Check | `src/github_archive/phase2_process_files/main.py` | 78-95 | GET /ready |
| **Eventarc Handler** | `src/github_archive/phase2_process_files/main.py` | 101-241 | POST / (main) |
| Parse Event | `src/github_archive/phase2_process_files/main.py` | 117-124 | JSON parsing |
| Path Filtering | `src/github_archive/phase2_process_files/main.py` | 138 | github-archive/ check |
| Extension Check | `src/github_archive/phase2_process_files/main.py` | 142-144 | .json.gz validation |
| Subdir Check | `src/github_archive/phase2_process_files/main.py` | 147-149 | raw/ or chunks/ |
| Manual Trigger | `src/github_archive/phase2_process_files/main.py` | 246-286 | POST /process |

#### File Processing

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Processor Class** | `src/github_archive/phase2_process_files/processors/file_processor.py` | 53-379 | Main orchestrator |
| Process File | `src/github_archive/phase2_process_files/processors/file_processor.py` | 98-230 | Main entry point |
| Get Metadata | `src/github_archive/phase2_process_files/processors/file_processor.py` | 122 | GCS metadata |
| **File Validation** | `src/github_archive/phase2_process_files/validators/file_validator.py` | 1-150 | Validation logic |
| Name Pattern Check | `src/github_archive/phase2_process_files/validators/file_validator.py` | 52-70 | YYYY-MM-DD-H |
| Size Check | `src/github_archive/phase2_process_files/validators/file_validator.py` | 95-110 | 100B-10GB |
| **Size Threshold** | `src/github_archive/phase2_process_files/processors/file_processor.py` | 157 | 500MB check |
| Split Required | `src/github_archive/phase2_process_files/processors/file_processor.py` | 166-177 | Return split flag |

#### File Splitter (⭐ Enhanced)

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Splitter Class** | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 47-310 | Main splitter |
| Split File | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 84-161 | Entry point |
| Download to Temp | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 117-122 | Local copy |
| Stream Read | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 188-232 | Line by line |
| Write Chunk | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 257-309 | Upload to GCS |
| ⭐ **Write Metadata** | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 404-462 | Create .split-metadata.json |
| ⭐ **Mark Processed** | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 465-564 | Update metadata |
| ⭐ **Cleanup** | `src/github_archive/phase2_process_files/processors/file_splitter.py` | 525-537 | Delete original |

#### Data Processing Pipeline

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Pandas Processing** | `src/github_archive/phase2_process_files/processors/file_processor.py` | 232-379 | Chunked read |
| Chunk Size | `src/github_archive/phase2_process_files/processors/file_processor.py` | 281 | 100k records |
| **Dtype Validation** | `src/github_archive/phase2_process_files/validators/dtype_validator.py` | 50-120 | Type coercion |
| **Value Validation** | `src/github_archive/phase2_process_files/validators/value_validator.py` | 45-180 | Business rules |
| **Transformer** | `src/github_archive/phase2_process_files/processors/transformer.py` | 49-333 | Flattening |
| Extract Actor | `src/github_archive/phase2_process_files/processors/transformer.py` | 60-82 | Actor fields |
| Extract Repo | `src/github_archive/phase2_process_files/processors/transformer.py` | 84-106 | Repo fields |
| Extract Payload | `src/github_archive/phase2_process_files/processors/transformer.py` | 108-130 | Payload fields |
| Flatten Schema | `src/github_archive/phase2_process_files/processors/transformer.py` | 132-163 | Main transform |
| Add ETL Metadata | `src/github_archive/phase2_process_files/processors/transformer.py` | 160-161 | Timestamp & ID |

#### Output Writing

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **GCS Writer** | `src/github_archive/phase2_process_files/writers/ndjson_writer.py` | 1-150 | NDJSON writer |
| Write Chunk | `src/github_archive/phase2_process_files/processors/file_processor.py` | 317-320 | Per-chunk write |
| ⭐ **Multi-File Output** | `src/github_archive/phase2_process_files/processors/file_processor.py` | 310-315 | Dynamic naming |
| Create Output Path | `src/github_archive/phase2_process_files/writers/ndjson_writer.py` | 45-65 | Path generator |

#### Infrastructure Resources

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Processor Service** | `infrastructure/phase2_process_files/terraform/cloud_run_service.tf` | 1-60 | Cloud Run Service |
| Service Memory | `infrastructure/phase2_process_files/terraform/cloud_run_service.tf` | 35 | 4Gi |
| Service CPU | `infrastructure/phase2_process_files/terraform/cloud_run_service.tf` | 40 | 2 vCPU |
| Service Timeout | `infrastructure/phase2_process_files/terraform/cloud_run_service.tf` | 45 | 3600s |
| **Splitter Job** | `infrastructure/phase2_process_files/terraform/cloud_run_jobs.tf` | 1-45 | Cloud Run Job |
| **Landing Bucket** | `infrastructure/phase2_process_files/terraform/storage.tf` | 1-30 | Input bucket |
| **Staging Bucket** | `infrastructure/phase2_process_files/terraform/storage.tf` | 35-65 | Output bucket |
| **Eventarc Trigger** | `infrastructure/phase2_process_files/terraform/eventarc.tf` | 1-40 | GCS events |
| **Service Accounts** | `infrastructure/phase2_process_files/terraform/service_accounts.tf` | 1-70 | IAM |
| **IAM Bindings** | `infrastructure/phase2_process_files/terraform/iam_bindings.tf` | 1-80 | Permissions |

### 📍 Key Code Snippets

#### Eventarc Handler (main.py:101-149)
```python
@app.route('/', methods=['POST'])
def process_file_event() -> tuple[Dict[str, Any], int]:
    """Handle Eventarc event for new files in landing bucket."""
    start_time = time.time()

    # Parse event payload
    try:
        event = request.get_json()
        if not event:
            return jsonify({'error': 'No event payload'}), 400
    except Exception as e:
        logger.error(f"Failed to parse event: {e}")
        return jsonify({'error': f'Invalid event payload: {e}'}), 400

    # Extract event data
    bucket = event.get('bucket')
    file_name = event.get('name')

    # Path filtering
    if not file_name or not file_name.startswith('github-archive/'):
        return jsonify({'status': 'ignored', 'reason': 'path_not_matching'}), 200

    if not file_name.endswith('.json.gz'):
        return jsonify({'status': 'ignored', 'reason': 'extension_not_matching'}), 200

    if not ('/raw/' in file_name or '/chunks/' in file_name):
        return jsonify({'status': 'ignored', 'reason': 'subdirectory_not_matching'}), 200
```

#### Size Check & Split Decision (file_processor.py:157-177)
```python
# Check if file should be split
if should_split_file(metadata.size, self.file_size_threshold_mb):
    self.logger.info(
        f"File exceeds threshold ({self.file_size_threshold_mb}MB), requires splitting",
        file_name=file_name,
        file_size_mb=round(metadata.size_mb, 2),
        action='file_split_required'
    )
    # Return result indicating splitting is needed
    return FileProcessingResult(
        success=False,
        input_file=input_gcs_path,
        output_file=None,
        output_files=[],
        records_in=0,
        records_out=0,
        errors=0,
        warnings=0,
        duration_seconds=time.time() - start_time,
        error_message='FILE_SPLIT_REQUIRED'
    )
```

#### ⭐ Metadata Write (file_splitter.py:404-462)
```python
def _write_split_metadata(
    project_id: str,
    landing_bucket: str,
    original_file: str,
    output_prefix: str,
    chunk_count: int,
    output_files: List[str],
    logger: Phase2Logger
) -> None:
    """Write metadata file for tracking split files."""
    from google.cloud import storage
    import json
    from datetime import datetime

    client = storage.Client(project=project_id)
    bucket = client.bucket(landing_bucket)

    # Metadata filename
    metadata_filename = f"{output_prefix}.split-metadata.json"
    blob_name = f"github-archive/chunks/{metadata_filename}"

    metadata = {
        'original_file': original_file,
        'split_timestamp': datetime.utcnow().isoformat(),
        'chunk_count': chunk_count,
        'output_files': output_files,
        'chunks_processed': [],  # Will be updated as chunks are processed
        'status': 'pending_cleanup',  # pending_cleanup, cleanup_complete
        'cleanup_after': chunk_count  # Delete original after this many chunks processed
    }

    blob = bucket.blob(blob_name)
    blob.upload_from_string(
        json.dumps(metadata, indent=2),
        content_type='application/json'
    )
```

#### ⭐ Chunk Processing & Cleanup (file_splitter.py:465-564)
```python
def mark_chunk_processed(
    project_id: str,
    landing_bucket: str,
    chunk_file: str,
    logger: Phase2Logger
) -> Dict[str, Any]:
    """Mark a chunk as processed and check if original can be deleted."""
    from google.cloud import storage
    import json
    import re

    client = storage.Client(project=project_id)
    bucket = client.bucket(landing_bucket)

    # Extract prefix from chunk filename
    chunk_name = chunk_file.split('/')[-1]
    match = re.match(r'(.+)-chunk-\d+\.json\.gz', chunk_name)

    if not match:
        return {'status': 'error', 'message': 'Could not extract prefix'}

    output_prefix = match.group(1)
    metadata_filename = f"{output_prefix}.split-metadata.json"
    blob_name = f"github-archive/chunks/{metadata_filename}"

    blob = bucket.blob(blob_name)
    metadata_str = blob.download_as_text()
    metadata = json.loads(metadata_str)

    # Add this chunk to processed list
    if chunk_file not in metadata.get('chunks_processed', []):
        metadata.setdefault('chunks_processed', []).append(chunk_file)

    # Check if all chunks are processed
    all_processed = len(metadata['chunks_processed']) >= metadata['chunk_count']

    if all_processed:
        metadata['status'] = 'cleanup_complete'

        # Delete original file
        original_path = GCSPath.parse(metadata['original_file'])
        original_blob = bucket.blob(original_path.blob_name)
        if original_blob.exists():
            original_blob.delete()
            logger.info(
                f"Original file deleted after all chunks processed",
                original_file=metadata['original_file'],
                chunks_processed=len(metadata['chunks_processed'])
            )

        # Delete the processed chunks
        for chunk_path in metadata['chunks_processed']:
            chunk_blob_name = chunk_path.replace(f'gs://{landing_bucket}/', '')
            chunk_blob = bucket.blob(chunk_blob_name)
            if chunk_blob.exists():
                chunk_blob.delete()
```

#### ⭐ Multi-File Output (file_processor.py:310-323)
```python
# Write this chunk immediately to GCS
if not transform_result.df.empty:
    # Create chunk-specific output path
    if chunks_processed == 1:
        # First chunk - use original filename
        blob_name = f"processed/{date_prefix}.ndjson.gz"
    else:
        # Subsequent chunks - add chunk number
        blob_name = f"processed/{date_prefix}-chunk-{chunks_processed:03d}.ndjson.gz"

    write_result = writer.write_dataframe_to_gcs(
        transform_result.df,
        blob_name
    )

    if write_result.output_path:
        output_files.append(write_result.output_path)
```

---

## Phase 3: BigQuery Loading - Code Locations

### 📁 Directory Structure

```
src/github_archive/phase3_loadbigquery/
├── main.py                                    # Cloud Function entry point
└── cloudbuild.yaml                            # Deployment config

infrastructure/phase3_loadbigquery/
├── terraform/
│   ├── 01_static/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   ├── service_accounts.tf                # Service accounts
│   │   ├── bigquery.tf                        # Dataset & table
│   │   └── iam.tf                            # IAM bindings
│   ├── 02_first_time/
│   │   ├── main.tf
│   │   └── variables.tf
│   └── 03_operational/
│       ├── main.tf
│       ├── variables.tf
│       └── cloud_function.tf                 # Function & trigger
└── scripts/
    └── migrate_table.sh
```

### 🔍 Component Locations

| Diagram Component | File Path | Lines | Description |
|-------------------|-----------|-------|-------------|
| **Cloud Function** | `src/github_archive/phase3_loadbigquery/main.py` | 1-111 | Main entry point |
| Function Handler | `src/github_archive/phase3_loadbigquery/main.py` | 28-110 | load_to_bigquery() |
| Parse Event | `src/github_archive/phase3_loadbigquery/main.py` | 45-49 | Extract bucket/file |
| Extension Check | `src/github_archive/phase3_loadbigquery/main.py` | 52-54 | .ndjson.gz |
| Prefix Check | `src/github_archive/phase3_loadbigquery/main.py` | 57-59 | processed/ |
| Load Config | `src/github_archive/phase3_loadbigquery/main.py` | 69-75 | Job config |
| Execute Load | `src/github_archive/phase3_loadbigquery/main.py` | 78-82 | load_table_from_uri |
| Wait for Complete | `src/github_archive/phase3_loadbigquery/main.py` | 85 | result() |
| **Delete Source** | `src/github_archive/phase3_loadbigquery/main.py` | 91-99 | blob.delete() |
| **BigQuery Dataset** | `infrastructure/phase3_loadbigquery/terraform/01_static/bigquery.tf` | 1-25 | Dataset resource |
| **BigQuery Table** | `infrastructure/phase3_loadbigquery/terraform/01_static/bigquery.tf` | 30-80 | Table resource |
| Table Schema | `infrastructure/phase3_loadbigquery/terraform/01_static/bigquery.tf` | 45-75 | Field definitions |
| Partitioning | `infrastructure/phase3_loadbigquery/terraform/01_static/bigquery.tf` | 60 | DAY on created_at |
| Clustering | `infrastructure/phase3_loadbigquery/terraform/01_static/bigquery.tf` | 65 | event_type |
| **Cloud Function** | `infrastructure/phase3_loadbigquery/terraform/03_operational/cloud_function.tf` | 1-75 | Function resource |
| Built-in Trigger | `infrastructure/phase3_loadbigquery/terraform/03_operational/cloud_function.tf` | 80-120 | Eventarc |
| **Service Accounts** | `infrastructure/phase3_loadbigquery/terraform/01_static/service_accounts.tf` | 1-70 | bq-loader, invoker |
| **IAM Bindings** | `infrastructure/phase3_loadbigquery/terraform/01_static/iam.tf` | 1-50 | Permissions |

### 📍 Key Code Snippets

#### Cloud Function Handler (main.py:28-110)
```python
def load_to_bigquery(data, context):
    """Cloud Function entry point. Triggered by GCS object finalized event."""
    bucket_name = data.get("bucket")
    file_name = data.get("name")
    file_size = data.get("size", "unknown")

    logger.info(f"Processing event: bucket={bucket_name}, file={file_name}, size={file_size}")

    # Validate file extension
    if not file_name.endswith(".ndjson.gz"):
        logger.info(f"Skipping {file_name} - not a .ndjson.gz file")
        return {"status": "skipped", "reason": "invalid_extension"}

    # Only process files in processed/ prefix
    if not file_name.startswith("processed/"):
        logger.info(f"Skipping {file_name} - not in processed/ prefix")
        return {"status": "skipped", "reason": "invalid_prefix"}

    # Construct URIs
    gcs_uri = f"gs://{bucket_name}/{file_name}"
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

    try:
        # Configure load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            ignore_unknown_values=True,
        )

        # Start load job
        load_job = bq_client.load_table_from_uri(
            gcs_uri,
            table_ref,
            job_config=job_config,
        )

        # Wait for completion
        result = load_job.result()

        logger.info(f"Load job completed: {load_job.job_id}")
        logger.info(f"Loaded {result.output_rows} rows")

        # Delete source file after successful load
        if DELETE_AFTER_LOAD:
            try:
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(file_name)
                blob.delete()
                logger.info(f"Deleted source file: {file_name}")
            except Exception as delete_error:
                logger.warning(f"Failed to delete source file: {delete_error}")

        return {
            "status": "success",
            "job_id": load_job.job_id,
            "rows_loaded": result.output_rows,
            "source_file": file_name,
        }

    except Exception as e:
        logger.error(f"Failed to load {gcs_uri}: {e}")
        raise  # Re-raise to trigger retry policy
```

---

## Cross-Cutting Utilities

### Logging

| Component | File Path | Lines | Type |
|-----------|-----------|-------|------|
| **Phase 2 Logger** | `src/github_archive/phase2_process_files/utils/logger.py` | 1-150 | Structured JSON |
| Phase 2Logger Class | `src/github_archive/phase2_process_files/utils/logger.py` | 20-120 | Main logger |
| Log File Start | `src/github_archive/phase2_process_files/utils/logger.py` | 45-55 | File processing start |
| Log Chunk Progress | `src/github_archive/phase2_process_files/utils/logger.py` | 60-70 | Chunk progress |
| Log File Complete | `src/github_archive/phase2_process_files/utils/logger.py` | 75-90 | File completion |
| Log File Error | `src/github_archive/phase2_process_files/utils/logger.py` | 95-110 | Error logging |
| **Phase 3 Logger** | `src/github_archive/phase3_loadbigquery/main.py` | 14-15 | Standard Python |

### GCS Client

| Component | File Path | Lines | Description |
|-----------|-----------|-------|-------------|
| **GCS Client** | `src/github_archive/phase2_process_files/utils/gcs_client.py` | 1-200 | GCS utilities |
| GCSPath Class | `src/github_archive/phase2_process_files/utils/gcs_client.py` | 20-80 | Path parsing |
| Get Metadata | `src/github_archive/phase2_process_files/utils/gcs_client.py` | 100-120 | File metadata |
| Read to Local | `src/github_archive/phase2_process_files/utils/gcs_client.py` | 140-160 | Download |

### Schema Definitions

| Component | File Path | Lines | Description |
|-----------|-----------|-------|-------------|
| **Dtype Definitions** | `src/github_archive/phase2_process_files/schemas/dtype_definitions.py` | 1-100 | Field mappings |
| ACTOR_FIELD_MAPPING | `src/github_archive/phase2_process_files/schemas/dtype_definitions.py` | 15-30 | Actor fields |
| REPO_FIELD_MAPPING | `src/github_archive/phase2_process_files/schemas/dtype_definitions.py` | 35-50 | Repo fields |
| ISSUE_FIELD_MAPPING | `src/github_archive/phase2_process_files/schemas/dtype_definitions.py` | 55-75 | Issue fields |

---

## Environment Variables Reference

### Phase 1

| Variable | Source | Default | Used In |
|----------|--------|---------|---------|
| ENVIRONMENT | Terraform | dev | scheduler.tf:15 |
| PROJECT_ID | Auto-detect | - | download.sh:20 |
| BUCKET_NAME | Derived | - | download.sh:25 |
| HOURS_AGO | Config | 1 | cloud_run_jobs.tf:35 |

### Phase 2

| Variable | Source | Default | Used In |
|----------|--------|---------|---------|
| PROJECT_ID | Terraform | - | main.py:23 |
| LANDING_BUCKET | Terraform | - | main.py:24 |
| STAGING_BUCKET | Terraform | - | main.py:25 |
| FILE_SIZE_THRESHOLD_MB | Terraform | 500 | main.py:26 |
| CHUNKSIZE | Terraform | 100000 | main.py:27 |
| PORT | Cloud Run | 8080 | main.py:31 |

### Phase 3

| Variable | Source | Default | Used In |
|----------|--------|---------|---------|
| PROJECT_ID | Terraform | - | main.py:18 |
| DATASET_ID | Terraform | github_archive | main.py:19 |
| TABLE_ID | Terraform | github_events | main.py:20 |
| DELETE_AFTER_LOAD | Terraform | true | main.py:21 |

---

## Deployment Scripts

| Script | Path | Purpose |
|--------|------|---------|
| Phase 1 Deploy | `infrastructure/scripts/phase1_deploy_layered.sh` | Deploy Phase 1 |
| Phase 2 Build | `infrastructure/phase2_process_files/scripts/build_and_push.sh` | Build container |
| Phase 2 Deploy | `infrastructure/phase2_process_files/scripts/deploy.sh` | Deploy service |
| Phase 3 Migrate | `infrastructure/phase3_loadbigquery/scripts/migrate_table.sh` | Table migration |

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| **Total Python Files** | 19 |
| **Total Terraform Files** | 21 |
| **Total Shell Scripts** | 8 |
| **Total Lines of Python Code** | ~8,500 |
| **Total Lines of Terraform** | ~3,200 |
| **Total Lines of Shell** | ~600 |
| **Documentation Files** | 15 |

---

## File Size Distribution

| Phase | Core Code | Infrastructure | Docs | Total |
|-------|-----------|----------------|------|-------|
| Phase 1 | 80 lines | 400 lines | 250 lines | 730 lines |
| Phase 2 | 3,500 lines | 800 lines | 450 lines | 4,750 lines |
| Phase 3 | 110 lines | 900 lines | 200 lines | 1,210 lines |
| **Total** | **3,690 lines** | **2,100 lines** | **900 lines** | **6,690 lines** |

---

## Index by Functionality

### Data Flow
- Ingestion: `infrastructure/phase1_ingestion/scripts/download.sh`
- Processing: `src/github_archive/phase2_process_files/main.py`
- Loading: `src/github_archive/phase3_loadbigquery/main.py`

### Validation
- File: `src/github_archive/phase2_process_files/validators/file_validator.py`
- Dtype: `src/github_archive/phase2_process_files/validators/dtype_validator.py`
- Value: `src/github_archive/phase2_process_files/validators/value_validator.py`

### Transformation
- Main: `src/github_archive/phase2_process_files/processors/transformer.py`
- Mappings: `src/github_archive/phase2_process_files/schemas/dtype_definitions.py`

### Storage
- Write: `src/github_archive/phase2_process_files/writers/ndjson_writer.py`
- Client: `src/github_archive/phase2_process_files/utils/gcs_client.py`

### Infrastructure
- Phase 1: `infrastructure/phase1_ingestion/terraform/`
- Phase 2: `infrastructure/phase2_process_files/terraform/`
- Phase 3: `infrastructure/phase3_loadbigquery/terraform/`

---

*End of Code Location Reference*
