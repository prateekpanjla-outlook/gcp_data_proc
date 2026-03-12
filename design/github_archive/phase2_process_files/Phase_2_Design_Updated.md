# GitHub Archive Data Pipeline - Updated Phase 2 Design

## Overview

Phase 2 implements the data transformation layer that processes raw GitHub Archive files from the landing bucket, validates and transforms the data, and writes processed NDJSON files to the staging bucket for BigQuery loading.

## Architecture (Updated)

```mermaid
graph TB
    subgraph Storage["Storage Layer"]
        LB[GCS Landing Bucket<br>github-archive-landing]
        SB[GCS Staging Bucket<br>github-archive-staging]
    end

    subgraph Eventarc["Event Routing"]
        ET[Eventarc Trigger<br>storage.object.v1.finalized<br>Single trigger on landing bucket]
    end

    subgraph Compute["Compute Layer"]
        CRS[Cloud Run Service<br>github-archive-processor<br>Handles splitting in-process]
    end

    subgraph IAM["Identity"]
        SA1[Service Account<br>github-archive-processor]
        SA2[Service Account<br>eventarc-invoker]
        SA3[Service Account<br>file-splitter]
    end

    subgraph Metadata["Metadata Tracking"]
        MD[Split Metadata Files<br>.split-metadata.json]
        CL[Cleanup Logic<br>Track chunk processing]
    end

    LB -->|"file finalized"| ET
    ET -->|"POST /"| CRS
    CRS -->|"read raw files"| LB
    CRS -->|"write .ndjson.gz"| SB

    CRS -->|"large file: split in-process"| LB
    CRS -.->|"write metadata"| MD

    CRS -.->|"mark chunk processed"| MD
    MD -.->|"all chunks done"| CL
    CL -->|"delete original"| LB

    CRS -.->|"runs as"| SA1
    ET -.->|"invokes as"| SA2

    style LB fill:#fff3e0,stroke:#333
    style SB fill:#e8f5e9,stroke:#333
    style CRS fill:#e3f2fd,stroke:#333
    style MD fill:#fff9c4,stroke:#333
    style CL fill:#f3e5f5,stroke:#333
```

> **Note:** File splitting is handled within the processor service, not as a separate Cloud Run Job.
> There is a single Eventarc trigger for the landing bucket. Path filtering is done in application code.

## Enhanced Data Flow

```mermaid
graph LR
    subgraph Input["Input"]
        R1[raw/2026-03-10-12.json.gz<br>~2GB compressed]
        R2[raw/2026-03-10-13.json.gz<br>~50MB compressed]
    end

    subgraph Decision{"Size Check"}
        D1{> 500MB?}
    end

    subgraph Split["⭐ File Splitter with Metadata"]
        S1[Chunk 1<br>~50MB]
        S2[Chunk 2<br>~50MB]
        S3[Chunk N<br>~50MB]
        SM[📄 split-metadata.json<br>tracks all chunks]
    end

    subgraph Process["Processor"]
        P1[Validate]
        P2[Transform]
        P3[Write NDJSON]
    end

    subgraph Output["⭐ Multi-File Output"]
        O1[processed/2026-03-10-12.ndjson.gz]
        O2[processed/2026-03-10-12-chunk-001.ndjson.gz]
        O3[processed/2026-03-10-12-chunk-002.ndjson.gz]
        O4[processed/2026-03-10-13.ndjson.gz]
    end

    subgraph Cleanup["⭐ NEW: Cleanup Workflow"]
        C1[Mark chunk processed]
        C2[Check all chunks done]
        C3[Delete original file]
        C4[Delete processed chunks]
    end

    R1 --> D1
    R2 --> D1
    D1 -->|"Yes"| Split
    D1 -->|"No"| Process
    Split --> SM
    Split --> Process
    Process --> Output

    Output --> C1
    C1 --> C2
    C2 -->|"all chunks processed"| C3
    C3 --> C4

    style R1 fill:#ffcdd2,stroke:#333
    style R2 fill:#c8e6c9,stroke:#333
    style SM fill:#fff9c4,stroke:#333
    style O1 fill:#e8f5e9,stroke:#333
    style O2 fill:#e8f5e9,stroke:#333
    style O3 fill:#e8f5e9,stroke:#333
    style O4 fill:#e8f5e9,stroke:#333
    style C1 fill:#f3e5f5,stroke:#333
    style C2 fill:#f3e5f5,stroke:#333
    style C3 fill:#f3e5f5,stroke:#333
    style C4 fill:#f3e5f5,stroke:#333
```

## Detailed Processing Pipeline (Updated)

```mermaid
sequenceDiagram
    participant GCS as Landing Bucket
    participant ET as Eventarc
    participant P as Processor Service
    participant MD as Metadata File
    participant SB as Staging Bucket

    GCS->>ET: Object finalized event
    ET->>P: POST / (event payload)

    Note over P: Parse event, validate path
    P->>GCS: Get file metadata

    alt File > 500MB
        P->>GCS: Download and split in-process
        loop For each 10k lines
            P->>GCS: Upload chunk to chunks/
        end
        P->>MD: Write split-metadata.json
        Note over MD: Tracks: original_file,<br>chunk_count, status
        Note over GCS,ET: Chunk finalized events trigger processor again
    else File <= 500MB
        P->>GCS: Download file
    end

    Note over P: Chunked Pandas processing
    loop Each chunk (100k records)
        P->>P: Validate dtypes
        P->>P: Validate values
        P->>P: Transform (flatten schema)
        P->>SB: Write NDJSON chunk(s)

        alt Chunk file
            P->>MD: Mark chunk processed
            alt All chunks processed
                P->>GCS: Delete original file
                P->>GCS: Delete processed chunks
                P->>MD: Update status = cleanup_complete
            end
        end
    end

    P-->>ET: Return 200 (success)
```

## Metadata File Structure

```mermaid
graph TB
    subgraph "Split Metadata File (.split-metadata.json)"
        ROOT[Metadata Object]
        ORIG[original_file<br>gs://.../raw/file.json.gz]
        TIME[split_timestamp<br>2026-03-10T12:00:00Z]
        COUNT[chunk_count<br>42]
        FILES[output_files<br>List of chunk paths]
        PROCESSED[chunks_processed<br>[] - updated as chunks complete]
        STATUS[status<br>pending_cleanup → cleanup_complete]
        CLEANUP_AFTER[cleanup_after<br>42 - delete after this many]

        ROOT --> ORIG
        ROOT --> TIME
        ROOT --> COUNT
        ROOT --> FILES
        ROOT --> PROCESSED
        ROOT --> STATUS
        ROOT --> CLEANUP_AFTER

        style ROOT fill:#e3f2fd,stroke:#333
        style ORIG fill:#fff3e0,stroke:#333
        style TIME fill:#fff3e0,stroke:#333
        style COUNT fill:#fff3e0,stroke:#333
        style FILES fill:#fff3e0,stroke:#333
        style PROCESSED fill:#c8e6c9,stroke:#333
        style STATUS fill:#c8e6c9,stroke:#333
        style CLEANUP_AFTER fill:#c8e6c9,stroke:#333
    end
```

## Components

### 1. Cloud Run Service (Processor)

| Property | Deployed Value | Notes |
|----------|----------------|-------|
| **Name** | `dev-github-archive-processor` | Environment-prefixed |
| **Image** | Custom Python container | gunicorn + Flask |
| **Memory** | 4GiB | Handles large files |
| **CPU** | 2 | Parallel processing |
| **Timeout** | 3600s (1 hour) | Long-running processing |
| **Max Instances** | 5 | Concurrency control |
| **Concurrency** | 10 | Per-instance |
| **Region** | `us-central1` | Same as all resources |

**Environment Variables:**
| Variable | Value | Description |
|----------|-------|-------------|
| `PROJECT_ID` | `dev-dataprocessing-489305` | GCP Project ID |
| `LANDING_BUCKET` | `dev-dataprocessing-489305-dev-github-archive-landing` | Input bucket |
| `STAGING_BUCKET` | `dev-dataprocessing-489305-dev-github-archive-staging` | Output bucket |
| `CHUNKSIZE` | `100000` | Pandas chunk size |
| `FILE_SIZE_THRESHOLD_MB` | `500` | Large file threshold |

**Service Account:** `dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com`

### 2. File Splitter (In-Process)

The file splitting logic runs within the processor service code (not a separate Cloud Run Job).
A `{env}-file-splitter` service account exists for future use if splitting is separated.
Metadata tracking via `.split-metadata.json` enables safe cleanup after all chunks are processed.

### 3. Cloud Storage Buckets

#### Landing Bucket (Input)
| Property | Value |
|----------|-------|
| **Name** | `{project}-{env}-github-archive-landing` |
| **Location** | `us-central1` |
| **Paths** | `github-archive/raw/`, `github-archive/chunks/` |

#### Staging Bucket (Output)
| Property | Value |
|----------|-------|
| **Name** | `{project}-{env}-github-archive-staging` |
| **Location** | `us-central1` |
| **Path** | `processed/` |

### 4. Eventarc Trigger

| Trigger | Event Type | Filter | Destination |
|---------|------------|--------|-------------|
| `{env}-github-archive-storage` | `google.cloud.storage.object.v1.finalized` | Landing bucket | Processor service |

> Single trigger for the entire landing bucket. Path filtering (raw/ vs chunks/) is done in application code (`main.py`).

## Processing Pipeline

### ⭐ Enhanced Workflow

```mermaid
stateDiagram-v2
    [*] --> FileReceived

    FileReceived --> ValidateFile: Eventarc trigger

    ValidateFile --> RejectFile: Invalid name/size
    ValidateFile --> CheckSize: Valid file

    CheckSize --> NormalProcessing: ≤ 500MB
    CheckSize --> TriggerSplitter: > 500MB

    TriggerSplitter --> Splitting: Cloud Run Job
    Splitting --> ChunksCreated: Upload N chunks
    ChunksCreated --> WriteMetadata: ⭐ Create metadata file
    WriteMetadata --> ChunkProcessing: Eventarc triggers

    NormalProcessing --> DownloadFile: Download from GCS
    ChunkProcessing --> DownloadFile: Each chunk

    DownloadFile --> ProcessChunks: Pandas chunked read

    state ProcessChunks {
        [*] --> ValidateDtypes
        ValidateDtypes --> ValidateValues
        ValidateValues --> TransformSchema
        TransformSchema --> WriteOutput
        WriteOutput --> [*]
    }

    ProcessChunks --> CheckChunkType: After write

    CheckChunkType --> OriginalFile: Not a chunk
    CheckChunkType --> UpdateMetadata: ⭐ Is chunk file

    OriginalFile --> [*]: Complete
    UpdateMetadata --> CheckAllProcessed: ⭐ Update metadata

    CheckAllProcessed --> [*]: More chunks remain
    CheckAllProcessed --> Cleanup: ⭐ All chunks processed

    state Cleanup {
        [*] --> DeleteOriginal
        DeleteOriginal --> DeleteChunks
        DeleteChunks --> MarkComplete
        MarkComplete --> [*]
    }

    Cleanup --> [*]: Complete

    RejectFile --> [*]: Log and acknowledge
```

## Code Architecture

### Module Structure

```
src/github_archive/phase2_process_files/
├── main.py                    # Flask entry point, Eventarc handler
├── processors/
│   ├── file_processor.py      # Main processing logic
│   ├── file_splitter.py       # ⭐ Large file splitting with metadata
│   └── transformer.py         # Schema flattening
├── validators/
│   ├── file_validator.py      # File name/size validation
│   ├── dtype_validator.py     # Data type validation
│   └── value_validator.py     # Value range validation
├── writers/
│   └── ndjson_writer.py       # GCS NDJSON writer
├── utils/
│   ├── gcs_client.py          # GCS utilities
│   └── logger.py              # Structured logging
└── schemas/
    └── dtype_definitions.py   # Schema definitions
```

### Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `GitHubArchiveFileProcessor` | `file_processor.py` | Main orchestrator |
| `GitHubArchiveFileSplitter` | `file_splitter.py` | ⭐ Large file handling with metadata |
| `GitHubEventTransformer` | `transformer.py` | Schema flattening |
| `DtypeValidator` | `dtype_validator.py` | Type coercion |
| `ValueValidator` | `value_validator.py` | Business rules |
| `GCSNDJSONWriter` | `ndjson_writer.py` | Streaming writes |

## Schema Transformation

### Input Schema (GitHub Archive)

```json
{
  "id": "12345",
  "type": "PushEvent",
  "created_at": "2026-03-10T12:00:00Z",
  "actor": {
    "id": 123,
    "login": "username",
    "display_login": "Username",
    "avatar_url": "https://...",
    "gravatar_id": "",
    "url": "https://api.github.com/users/username",
    "site_admin": false
  },
  "repo": {
    "id": 456,
    "name": "owner/repo",
    "url": "https://api.github.com/repos/owner/repo"
  },
  "payload": { ... }
}
```

### Output Schema (Flattened)

| Field | Type | Source |
|-------|------|--------|
| `event_id` | STRING | `id` |
| `event_type` | STRING | `type` |
| `created_at` | TIMESTAMP | `created_at` |
| `actor_id` | INT64 | `actor.id` |
| `actor_login` | STRING | `actor.login` |
| `actor_display_login` | STRING | `actor.display_login` |
| `actor_avatar_url` | STRING | `actor.avatar_url` |
| `actor_gravatar_id` | STRING | `actor.gravatar_id` |
| `actor_url` | STRING | `actor.url` |
| `actor_site_admin` | BOOL | `actor.site_admin` |
| `repo_id` | INT64 | `repo.id` |
| `repo_name` | STRING | `repo.name` |
| `repo_url` | STRING | `repo.url` |
| `payload_*` | Various | `payload.*` (selected fields) |
| `etl_create_ts` | TIMESTAMP | Processing timestamp |
| `etl_create_id` | STRING | `"GITHUB_PROCESSOR"` |

## Validation Rules

### File Validation

| Check | Rule | Error |
|-------|------|-------|
| Extension | Must be `.json.gz` | Reject |
| Filename pattern | `YYYY-MM-DD-H.json.gz` | Reject |
| Year range | 2011-2100 | Reject |
| Month range | 1-12 | Reject |
| Day range | 1-31 | Reject |
| Hour range | 0-23 | Reject |
| File size | < 10GB | Reject |
| File size | > 100 bytes | Reject |
| File size | >= 500MB | Split |

### Data Validation

| Field | Validation | Handling |
|-------|------------|----------|
| `event_id` | Non-null string | Drop row |
| `event_type` | Known event type | Keep (with warning) |
| `created_at` | ISO 8601 format | Coerce to timestamp |
| `actor_id` | Integer | Coerce to Int64 |
| `repo_id` | Integer | Coerce to Int64 |

## IAM Roles and Permissions

### Service Account: `{env}-github-archive-processor`

| Role | Scope | Purpose |
|------|-------|---------|
| `roles/storage.objectViewer` | Landing bucket | Read input files |
| `roles/storage.objectCreator` | Staging bucket | Write output files |
| `roles/storage.objectViewer` | Staging bucket | Read staging files (blob.reload) |
| `roles/logging.logWriter` | Project | Structured logging |
| `roles/monitoring.metricWriter` | Project | Write metrics |

### Service Account: `{env}-eventarc-invoker`

| Role | Scope | Purpose |
|------|-------|---------|
| `roles/eventarc.eventReceiver` | Project | Receive events |
| `roles/run.invoker` | Processor service | Invoke service |
| `roles/logging.logWriter` | Project | Logging |

## Google Cloud Default Modifications

| Default | Modification | Reason |
|---------|--------------|--------|
| **Cloud Run timeout** | 3600s (vs default 300s) | Large file processing |
| **Memory** | 4GiB (vs default 512MiB) | Pandas chunk processing |
| **Concurrency** | 10 (vs default 80) | Memory constraints |
| **Max instances** | 5 (vs unlimited) | Cost control |
| **Ingress** | Internal only | Security |
| **Authentication** | Required | Eventarc requirement |
| **⭐ Splitter execution** | Synchronous vs async | Simpler error handling |
| **⭐ Metadata tracking** | Custom implementation | Safe cleanup |

## Error Handling

### HTTP Response Codes

| Code | Condition | Action |
|------|-----------|--------|
| 200 | Success | Normal completion |
| 200 | Ignored (wrong path) | Log and acknowledge |
| 207 | Partial success | Some records failed |
| 400 | Invalid event | Log and reject |
| 500 | Processing error | Retry by Eventarc |

### Retry Policy

- **Eventarc**: `RETRY_POLICY_RETRY` (exponential backoff)
- **Cloud Run**: 3 retries by default
- **Max retry duration**: 7 days (Eventarc default)

## Monitoring

### Key Metrics

| Metric | Type | Alert |
|--------|------|-------|
| Request count | Counter | - |
| Request latency | Histogram | > 5 min |
| Error count | Counter | > 5/hour |
| Memory utilization | Gauge | > 80% |
| Records processed | Counter | - |
| ⭐ Split operations | Counter | Track large files |
| ⭐ Metadata updates | Counter | Track cleanup |

### Logging

All logs use structured JSON format:
```json
{
  "timestamp": "2026-03-10T12:00:00Z",
  "severity": "INFO",
  "component": "phase2-processor",
  "message": "File processing completed",
  "file_name": "2026-03-10-12.json.gz",
  "records_in": 150000,
  "records_out": 149850,
  "errors": 150,
  "duration_seconds": 45.2,
  "⭐ chunk_files": ["processed/2026-03-10-12-chunk-001.ndjson.gz", ...],
  "⭐ metadata_updated": true
}
```

## Deployment

### Cloud Build

```bash
# Deploy via Cloud Build
gcloud builds submit \
  --config=src/github_archive/phase2_process_files/cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_ENVIRONMENT=dev
```

### Manual Deployment

```bash
# Build and deploy
gcloud run deploy dev-github-archive-processor \
  --source=src/github_archive/phase2_process_files \
  --region=us-central1 \
  --memory=4Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=5 \
  --concurrency=10 \
  --no-allow-unauthenticated
```

## Cost Considerations

| Resource | Pricing | Est. Monthly |
|----------|---------|--------------|
| Cloud Run (requests) | $0.40/million | ~$1 |
| Cloud Run (compute) | $0.00002400/vCPU-sec | ~$50 |
| Cloud Storage | $0.02/GB | ~$20 |
| Eventarc | Free | $0 |

## Security

### Network
- **Ingress**: Internal only (`ALLOW_INTERNAL_ONLY`)
- **Egress**: GCS APIs only

### Authentication
- **Service-to-service**: IAM authentication
- **No public access**: Authentication required

## ⭐ New Features Summary

### 1. Metadata-Based Cleanup
- **What**: Track split operations and cleanup after all chunks processed
- **Why**: Prevent data loss if chunk processing fails
- **How**: `.split-metadata.json` file with state tracking

### 2. Safe Original File Deletion
- **What**: Only delete original after ALL chunks successfully processed
- **Why**: Avoid losing data if processing fails midway
- **How**: Counter-based check in metadata file

### 3. Chunk Processing Tracking
- **What**: Mark each chunk as processed in metadata
- **Why**: Visibility into progress and recovery capability
- **How**: `mark_chunk_processed()` function

### 4. Multi-File Output
- **What**: Processor writes multiple chunk files (e.g., `-chunk-001`, `-chunk-002`)
- **Why**: Streaming design, avoid memory accumulation
- **How**: Dynamic filename generation in processor

## Next Phase

Output files are written to:
- **Path**: `gs://{staging-bucket}/processed/{YYYY-MM-DD-H}[-chunk-XXX].ndjson.gz`
- **Trigger**: Eventarc detects new files → Phase 3 BigQuery loading

---

*Document updated on 2026-03-11 to reflect enhanced implementation*
