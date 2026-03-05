# Phase 2: Process Files - Design Document

## Overview

Phase 2 processes GitHub Archive files landed in GCS by Phase 1, validates, transforms, and prepares them for BigQuery loading.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              PHASE 2: PROCESS FILES ARCHITECTURE                                         │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│   INPUT: gs://{project}-{env}-github-archive-landing/github-archive/raw/{YYYY-MM-DD-HH}.json.gz            │
│                                                                                                             │
│   ┌──────────────┐      ┌──────────────┐      ┌──────────────────────────────────────────────────────┐    │
│   │ Cloud Storage│─────▶│  Eventarc    │─────▶│ Cloud Run Service (autoscaling)                    │    │
│   │ finalize evt │      │  Trigger     │      │ github-archive-processor                           │    │
│   └──────────────┘      └──────────────┘      │                                                      │    │
│                                                  ┌────────────────────────────────────────────────┐ │    │
│                                                  │ STEP 1: File Size Check                       │ │    │
│                                                  │ • Read file metadata                           │ │    │
│                                                  │ • Determine processing path                   │ │    │
│                                                  └────────────────────────────────────────────────┘ │    │
│                                                             │                                     │    │
│                                    ┌────────────────────────┴────────────────────────┐            │    │
│                                    ▼                                                                 ▼    │
│                    ┌─────────────────────────────┐                    ┌─────────────────────────────┐    │
│                    │ Small File (< 500MB)        │                    │ Large File (≥ 500MB)        │    │
│                    │ Direct Processing          │                    │ Split First                 │    │
│                    └─────────────────────────────┘                    └─────────────────────────────┘    │
│                                    │                                                 │                  │    │
│                                    ▼                                                 ▼                  │    │
│                    ┌─────────────────────────────┐                    ┌─────────────────────────────┐    │
│                    │ Cloud Run Task:             │                    │ Cloud Run Job:              │    │
│                    │ process_file()              │                    │ file_splitter              │    │
│                    └─────────────────────────────┘                    │ • Splits into chunks        │    │
│                                                                         • Emits chunk events      │    │
│                                                                         └─────────────────────────────┘    │
│                                                                                           │                  │    │
│                                                                                           ▼                  │    │
│                                                                                ┌─────────────────────────────┐   │
│                                                                                │ Cloud Run Task:             │   │
│                                                                                │ process_chunk()             │   │
│                                                                                └─────────────────────────────┘   │
│                                                                                                                     │
│                                                  ┌────────────────────────────────────────────────┐             │
│                                                  │ STEP 2: Schema Validation                     │             │
│                                                  │ • Validate JSON structure                     │             │
│                                                  │ • Validate required fields                    │             │
│                                                  │ • Validate event types                        │             │
│                                                  │ • Validate data types                         │             │
│                                                  └────────────────────────────────────────────────┘             │
│                                                             │                                                 │
│                                                             ▼                                                 │
│                                                  ┌────────────────────────────────────────────────┐             │
│                                                  │ STEP 3: Data Transformation                    │             │
│                                                  │ • Flatten nested JSON                          │             │
│                                                  │ • Extract actor, repo, payload fields          │             │
│                                                  │ • Convert timestamps                           │             │
│                                                  │ • Normalize field names                        │             │
│                                                  └────────────────────────────────────────────────┘             │
│                                                             │                                                 │
│                                                             ▼                                                 │
│                                                  ┌────────────────────────────────────────────────┐             │
│                                                  │ STEP 4: Output Preparation                     │             │
│                                                  │ • Convert to newline-delimited JSON (NDJSON)    │             │
│                                                  │ • Compress with gzip                            │             │
│                                                  │ • Write to staging bucket                      │             │
│                                                  └────────────────────────────────────────────────┘             │
│                                                                                                                     │
│   OUTPUT: gs://{project}-{env}-github-archive-staging/github-archive/processed/{YYYY-MM-DD-HH}.ndjson.gz        │
│                                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Decisions

### Decision 1: Eventarc vs Cloud Scheduler for Triggering

| Aspect | Eventarc (Chosen) | Cloud Scheduler |
|--------|-------------------|-----------------|
| **Latency** | Near real-time (~seconds) | Polling interval (min) |
| **Efficiency** | Event-driven, no polling | Wasted polling cycles |
| **Scalability** | Automatic per-file | Manual concurrency limits |
| **Cost** | $0 per million events | Scheduler costs |
| **Idempotency** | Requires deduplication | Easier to control |

**Decision:** Use Eventarc for real-time, event-driven processing.

---

### Decision 2: Cloud Run Service vs Job for Processing

| Aspect | Cloud Run Service (Chosen) | Cloud Run Job |
|--------|---------------------------|---------------|
| **Scaling** | Autoscaling (0-N) | Manual task count |
| **Trigger** | HTTP/Eventarc | Scheduled/Manual |
| **Latency** | Low (always ready if min_instances) | Higher (startup) |
| **Cost** | Pay-per-request | Pay-per-execution |
| **Use Case** | Event-driven processing | Batch/scheduled |

**Decision:**
- **Cloud Run Service** for main processor (autoscaling, event-driven)
- **Cloud Run Job** for file splitter (batch, longer running)

---

### Decision 3: Large File Splitting Strategy

**Threshold:** 500MB compressed (~2.5GB uncompressed)

**Rationale:**
- Cloud Run max memory: 32GB
- Processing 1.2GB compressed = ~6.5GB uncompressed + processing overhead
- Large files risk OOM and timeouts
- Splitting enables parallel processing

**Splitting Approach:**

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              FILE SPLITTER ARCHITECTURE                                                      │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│   Large File Detection:                                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ IF file_size_compressed >= 500MB:                                                                   │   │
│   │     → Invoke file_splitter Cloud Run Job                                                           │   │
│   │ ELSE:                                                                                               │   │
│   │     → Direct processing                                                                             │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
│   File Splitter Job:                                                                                        │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ INPUT:  gs://landing-bucket/raw/2026-03-05-12.json.gz (1.2GB)                                      │   │
│   │                                                                                                      │   │
│   │ PROCESS:                                                                                             │   │
│   │   1. Download file to /tmp (fast local SSD)                                                         │   │
│   │   2. Read line by line (memory efficient)                                                           │   │
│   │   3. Every N lines (e.g., 10,000 events), write chunk to temp file                                   │   │
│   │   4. Upload each chunk to: gs://landing-bucket/chunks/2026-03-05-12-chunk-001.json.gz              │   │
│   │   5. Emit Pub/Sub message for each chunk                                                            │   │
│   │   6. Delete original file after all chunks uploaded                                                 │   │
│   │                                                                                                      │   │
│   │ OUTPUT: gs://landing-bucket/chunks/2026-03-05-12-chunk-*.json.gz (N files of ~50MB each)           │   │
│   │ MESSAGES: N Pub/Sub messages → trigger N processing tasks (parallel)                                │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
│   Chunk Processing (Parallel):                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Each chunk → Cloud Run Task → Process → Staging                                                    │   │
│   │ Chunks processed in parallel (autoscaling)                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
│   Merge Tracking:                                                                                            │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Track original file → chunks mapping in Firestore                                                    │   │
│   │ All chunks processed → Mark original file as complete                                               │   │
│   │ Trigger BigQuery load for all chunks of original file                                                │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Schema Definition & Validation

### Schema Location

```
src/github_archive/phase2_process_files/
├── schemas/
│   ├── __init__.py
│   ├── github_event_schema.py     # Pydantic models for GitHub events
│   ├── field_definitions.py       # Field type mappings
│   └── validation_rules.py        # Validation logic
└── ...
```

### Schema Definition Strategy

**Option A: Pydantic Models (Chosen)**

```python
# schemas/github_event_schema.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime

class GitHubActor(BaseModel):
    id: int = Field(..., description="GitHub user ID")
    login: str = Field(..., description="GitHub username")
    avatar_url: str = Field(..., description="Avatar URL")
    gravatar_id: Optional[str] = None
    url: str = Field(..., description="GitHub API URL")
    type: str = Field(..., description="User type")

class GitHubRepo(BaseModel):
    id: int = Field(..., description="Repository ID")
    name: str = Field(..., description="Repository name (owner/repo)")
    url: str = Field(..., description="Repository URL")

class GitHubEventBase(BaseModel):
    id: str = Field(..., description="Event ID")
    type: str = Field(..., description="Event type (PushEvent, etc.)")
    created_at: datetime = Field(..., description="Event timestamp")
    actor: GitHubActor
    repo: GitHubRepo
    payload: Dict[str, Any] = Field(default_factory=dict)

    @validator('type')
    def validate_event_type(cls, v):
        valid_types = {
            'PushEvent', 'CreateEvent', 'DeleteEvent', 'WatchEvent',
            'IssuesEvent', 'IssueCommentEvent', 'PullRequestEvent',
            # ... all 18+ event types
        }
        if v not in valid_types:
            raise ValueError(f"Invalid event type: {v}")
        return v

class ProcessedGitHubEvent(BaseModel):
    """Flattened schema for BigQuery loading"""
    event_id: str
    event_type: str
    created_at: datetime
    actor_id: int
    actor_login: str
    repo_id: int
    repo_name: str
    public: bool
    # Payload fields (flattened based on event type)
    payload_ref: Optional[str] = None
    payload_push_id: Optional[int] = None
    payload_size: Optional[int] = None
    # ... more fields
```

**Benefits:**
- Runtime validation
- Type safety
- Clear error messages
- Easy to extend

### Validation Points

| Validation Point | What | Where | Error Handling |
|------------------|------|-------|----------------|
| **Eventarc Trigger** | File path pattern | Eventarc filter | Non-matching files ignored |
| **File Header** | Gzip validity | Process start | Move to DLQ |
| **JSON Structure** | Valid JSON per line | Stream read | Skip line, log error |
| **Schema** | Field types, required fields | Pydantic model | Move to DLQ |
| **Business Rules** | Event type enums, references | Pydantic validators | Move to DLQ |

---

## Validation Strategy

### Multi-Layer Validation

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              VALIDATION LAYERS                                                               │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│   Layer 1: File-Level Validation (Fast Fail)                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • File extension: .json.gz                                                                           │   │
│   │ • File size: > 0 and < 10GB                                                                         │   │
│   │ • File name pattern: YYYY-MM-DD-HH.json.gz                                                          │   │
│   │ • Gzip validity: Can decompress                                                                     │   │
│   │                                                                                                      │   │
│   │ FAIL → Move to gs://.../invalid-files/                                                               │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 2: Line-Level Validation (Stream Processing)                                                         │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Valid JSON per line                                                                               │   │
│   │ • Line contains all required fields (id, type, created_at, actor, repo)                            │   │
│   │                                                                                                      │   │
│   │ FAIL → Skip line, count error, continue processing                                                   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 3: Schema Validation (Pydantic)                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Field type validation                                                                             │   │
│   │ • Event type enum validation                                                                        │   │
│   │ • Timestamp format validation                                                                       │   │
│   │ • Nested object validation                                                                          │   │
│   │                                                                                                      │   │
│   │ FAIL → Move event to DLQ, continue processing                                                        │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 4: Business Rule Validation                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Actor IDs exist in actors dimension (if doing dimension lookup)                                   │   │
│   │ • Repo IDs exist in repos dimension                                                                 │   │
│   │ • Referenced entities are valid                                                                     │   │
│   │                                                                                                      │   │
│   │ FAIL → Move event to DLQ, continue processing                                                        │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Strategy

| Error Type | Action | Destination |
|------------|--------|-------------|
| **Corrupted file** | Move entire file | `gs://.../invalid-files/` |
| **Invalid JSON lines** | Skip line, log | Error counter |
| **Schema violations** | Move event to DLQ | `gs://.../dlq/events/` |
| **Processing errors** | Retry (3x) then DLQ | Pub/Sub DLQ topic |

---

## Autoscaling Configuration

### Cloud Run Service Autoscaling

```yaml
# Cloud Run Service: github-archive-processor
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: github-archive-processor
spec:
  template:
    metadata:
      annotations:
        # Autoscaling settings
        autoscaling.knative.dev/maxScale: "100"        # Max 100 instances
        autoscaling.knative.dev/minScale: "0"          # Scale to zero when idle
        autoscaling.knative.dev/target: "10"           # 10 requests per instance
        autoscaling.knative.dev/scaleDownDelay: "30s"  # Wait 30s before scale down

        # Concurrency
        run.googleapis.com/cpu-throttling: "false"     # Full CPU always
        run.googleapis.com/execution-environment: gen2

    spec:
      containerConcurrency: 10      # Process 10 files concurrently per instance
      timeoutSeconds: 3600          # 1 hour max per request
      serviceAccountName: github-archive-processor@project.iam.gserviceaccount.com

      containers:
      - name: processor
        image: us-central1-docker.pkg.dev/project/github-archive/processor:latest
        resources:
          limits:
            cpu: "4"
            memory: "8Gi"
          requests:
            cpu: "100m"
            memory: "512Mi"
```

### Scaling Calculations

| Metric | Value |
|--------|-------|
| **Target concurrency** | 10 requests/instance |
| **Max instances** | 100 |
| **Max concurrent requests** | 1,000 |
| **Avg processing time** | 2-5 min/file |
| **Throughput (max)** | ~12,000-30,000 files/hour |

---

## Output Format for BigQuery

### Why NDJSON (Newline-Delimited JSON)?

| Format | BigQuery Load | Streaming | Schema Evolution |
|--------|---------------|-----------|------------------|
| **NDJSON** | ✅ Native | ✅ Easy | ✅ Additive |
| Avro | ✅ Native | ❌ Complex | ✅ Full |
| Parquet | ✅ Native | ❌ Complex | ⚠️ Limited |
| CSV | ✅ Native | ✅ Easy | ❌ Positional |

**Decision:** NDJSON for simplicity and schema flexibility.

### Output Schema

```json
// Line format (one event per line)
{
  "event_id": "1234567890",
  "event_type": "PushEvent",
  "created_at": "2026-03-05T12:34:56Z",
  "actor_id": 12345,
  "actor_login": "octocat",
  "repo_id": 67890,
  "repo_name": "octocat/Hello-World",
  "public": true,
  "payload_ref": "refs/heads/main",
  "payload_push_id": 987654321,
  "payload_size": 123,
  "payload_distinct_size": 45,
  "payload_head": "abc123...",
  "payload_before": "def456..."
}

// Compressed with gzip
// File: gs://.../staging/github-archive/processed/2026-03-05-12.ndjson.gz
```

---

## GCS Bucket Structure

```
gs://{project}-{env}-github-archive-landing/
├── github-archive/
│   ├── raw/                      # INPUT: Phase 1 landing zone
│   │   └── {YYYY-MM-DD-HH}.json.gz
│   │
│   ├── chunks/                   # Large file chunks (split)
│   │   └── {YYYY-MM-DD-HH}-chunk-{NNN}.json.gz
│   │
│   ├── invalid-files/            # Files that failed validation
│   │   └── {YYYY-MM-DD-HH}.json.gz
│   │
│   └── processed/                # Successfully processed (marked)
│       └── {YYYY-MM-DD-HH}.processed

gs://{project}-{env}-github-archive-staging/    # OUTPUT: Ready for BigQuery
├── github-archive/
│   └── processed/
│       └── {YYYY-MM-DD-HH}.ndjson.gz

gs://{project}-{env}-github-archive-dlq/        # Dead Letter Queue
├── events/
│   └── {YYYY-MM-DD-HH}-{event-id}.json
└── failures/
    └── {timestamp}-failure.json
```

---

## Component Summary

| Component | Type | Purpose | Scaling |
|-----------|------|---------|---------|
| **Eventarc Trigger** | Trigger | Detects new files in raw/ | N/A (event) |
| **github-archive-processor** | Cloud Run Service | Main file processor | 0-100 instances |
| **file-splitter** | Cloud Run Job | Splits large files | Manual concurrency |
| **chunk-processor** | Cloud Run Task | Processes chunks | Inherits from service |
| **Pub/Sub DLQ** | Topic | Failed event handling | N/A |
| **Firestore** | Database | Chunk tracking | N/A |

---

## File Structure

```
phase2_process_files/
├── design/
│   └── github_archive/
│       └── phase2_process_files/
│           ├── phase2_processing_design.md          # This file
│           ├── diagrams/
│           │   ├── 01_main_flow.md
│           │   ├── 02_eventarc_trigger.md
│           │   ├── 03_file_splitting.md
│           │   ├── 04_validation_layers.md
│           │   └── 05_autoscaling.md
│           └── terraform_config.md
│
├── src/
│   └── github_archive/
│       └── phase2_process_files/
│           ├── main.py                             # Cloud Run Service entry
│           ├── schemas/
│           │   ├── __init__.py
│           │   ├── github_event_schema.py          # Pydantic models
│           │   ├── field_definitions.py            # Type mappings
│           │   └── validation_rules.py             # Validators
│           ├── processors/
│           │   ├── __init__.py
│           │   ├── file_processor.py               # Main processing logic
│           │   ├── chunk_processor.py              # Chunk handling
│           │   ├── file_splitter.py                # Large file splitting
│           │   └── transformer.py                  # JSON flattening
│           ├── validators/
│           │   ├── __init__.py
│           │   ├── file_validator.py               # File-level validation
│           │   ├── schema_validator.py             # Schema validation
│           │   └── business_validator.py          # Business rules
│           ├── writers/
│           │   ├── __init__.py
│               │   └── ndjson_writer.py              # Output writer
│           ├── utils/
│           │   ├── __init__.py
│           │   ├── gcs_client.py                   # GCS utilities
│           │   ├── pubsub_client.py                # Pub/Sub utilities
│           │   └── firestore_client.py             # Firestore utilities
│           ├── config.py                           # Configuration
│           ├── requirements.txt
│           └── Dockerfile
│
├── test/
│   └── github_archive/
│       └── phase2_process_files/
│           ├── __init__.py
│           ├── test_schemas.py
│           ├── test_processors.py
│           ├── test_validators.py
│           ├── test_transformers.py
│           └── fixtures/
│               ├── sample_events.json
│               └── sample_file.json.gz
│
└── infrastructure/
    └── phase2_process_files/
        ├── terraform/
        │   ├── main.tf
        │   ├── variables.tf
        │   ├── outputs.tf
        │   ├── eventarc.tf                    # Eventarc trigger
        │   ├── cloud_run_service.tf           # Processor service
        │   ├── cloud_run_job_splitter.tf      # File splitter job
        │   ├── pubsub.tf                      # DLQ topic
        │   ├── firestore.tf                   # Chunk tracking
        │   ├── storage.tf                     # Staging/DLQ buckets
        │   ├── service_accounts.tf
        │   └── locals.tf
        ├── scripts/
        │   ├── deploy.sh
        │   └── deploy_layered.sh
        └── docs/
            └── phase2_deployment.md
```

---

## Next Steps

1. **Create schema definitions** - Pydantic models for GitHub events
2. **Create Eventarc trigger** - Terraform configuration
3. **Build processor service** - Cloud Run service with autoscaling
4. **Build file splitter** - Cloud Run job for large files
5. **Create validation layers** - File, schema, and business validators
6. **Create output writer** - NDJSON writer with compression
7. **Deploy and test** - End-to-end testing with sample files
