# Phase 2: Process Files - Design Document

## Overview

Phase 2 processes GitHub Archive files landed in GCS by Phase 1, validates, transforms, and writes them to the staging bucket in NDJSON format. **BigQuery loading is handled by Phase 3.**

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
│                                                                         • Writes to /chunks/
                                                                         • Cloud Storage triggers
                                                                         •   direct events for chunks      │    │
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
│   │   5. Cloud Storage emits direct event for each chunk                                                            │   │
│   │   6. Delete original file after all chunks uploaded                                                 │   │
│   │                                                                                                      │   │
│   │ OUTPUT: gs://landing-bucket/chunks/2026-03-05-12-chunk-*.json.gz (N files of ~50MB each)           │   │
│   │ EVENTS: N direct events → trigger N processing tasks (parallel)                                │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
│   Chunk Processing (Parallel):                                                                               │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ Each chunk → Cloud Run Task → Process → Staging (GCS)                                            │   │
│   │ Chunks processed in parallel (autoscaling)                                                          │   │
│   │ Phase 3 will load from staging to BigQuery                                                        │   │
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
│   ├── dtype_definitions.py      # Pandas dtype mappings for GitHub events
│   ├── validation_rules.py        # Validation logic
│   └── sample_data.py             # Sample data for testing
└── ...
```

### Schema Definition Strategy

**Option: Pandas with Chunked Processing (Chosen)**

```python
# schemas/dtype_definitions.py
import pandas as pd
from typing import Dict, Any

# Define expected dtypes for GitHub events
GITHUB_EVENT_DTYPES: Dict[str, str] = {
    'id': 'string',
    'type': 'string',
    'created_at': 'string',
    'public': 'boolean',
}

# Nested fields (extracted during transformation)
ACTOR_DTYPES: Dict[str, str] = {
    'actor_id': 'int64',
    'actor_login': 'string',
    'actor_avatar_url': 'string',
    'actor_gravatar_id': 'string',
    'actor_type': 'string',
}

REPO_DTYPES: Dict[str, str] = {
    'repo_id': 'int64',
    'repo_name': 'string',
    'repo_url': 'string',
}

# Valid event types
VALID_EVENT_TYPES = {
    'PushEvent', 'CreateEvent', 'DeleteEvent', 'WatchEvent',
    'IssuesEvent', 'IssueCommentEvent', 'PullRequestEvent',
    'PullRequestReviewEvent', 'PullRequestReviewCommentEvent',
    'ForkEvent', 'ReleaseEvent', 'MemberEvent', 'WatchEvent',
    'GollumEvent', 'CommitCommentEvent', 'TeamAddEvent',
    'ProtectBranchEvent'
}

class GitHubEventProcessor:
    """Process GitHub events using pandas with chunked processing"""

    def __init__(self, chunksize: int = 100_000):
        self.chunksize = chunksize
        self.stats = {
            'total_records': 0,
            'valid_records': 0,
            'invalid_records': 0,
            'chunks_processed': 0
        }

    def validate_dtypes(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate and coerce dtypes for a chunk"""
        # Apply dtypes with coercion
        for col, dtype in GITHUB_EVENT_DTYPES.items():
            if col in df.columns:
                try:
                    df[col] = df[col].astype(dtype, errors='raise')
                except (ValueError, TypeError):
                    # Log coercion failures
                    self.stats['invalid_records'] += df[col].isna().sum()

        return df

    def validate_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Validate values in a chunk"""
        # Check required columns
        required_cols = ['id', 'type', 'created_at', 'actor', 'repo']
        missing_cols = set(required_cols) - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing columns: {missing_cols}")

        # Check for null values in required fields
        null_counts = df[required_cols].isnull().sum()
        if null_counts.any():
            null_fields = null_counts[null_counts > 0].to_dict()
            print(f"Warning: Null values found - {null_fields}")

        # Validate event type (vectorized)
        invalid_mask = ~df['type'].isin(VALID_EVENT_TYPES)
        invalid_count = invalid_mask.sum()

        if invalid_count > 0:
            print(f"Warning: {invalid_count} records have invalid event type")
            # Filter out invalid types
            df = df[~invalid_mask].copy()

        return df

    def extract_nested_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Extract nested actor/repo fields (vectorized)"""
        # Extract actor fields
        df['actor_id'] = df['actor'].apply(
            lambda x: x.get('id') if isinstance(x, dict) else None
        )
        df['actor_login'] = df['actor'].apply(
            lambda x: x.get('login') if isinstance(x, dict) else None
        )

        # Extract repo fields
        df['repo_id'] = df['repo'].apply(
            lambda x: x.get('id') if isinstance(x, dict) else None
        )
        df['repo_name'] = df['repo'].apply(
            lambda x: x.get('name') if isinstance(x, dict) else None
        )

        return df

    def flatten_for_staging(self, df: pd.DataFrame) -> pd.DataFrame:
        """Flatten schema for staging output (NDJSON format)"""
        result = pd.DataFrame({
            'event_id': df['id'],
            'event_type': df['type'],
            'created_at': df['created_at'],
            'actor_id': df['actor_id'],
            'actor_login': df['actor_login'],
            'repo_id': df['repo_id'],
            'repo_name': df['repo_name'],
            'public': df.get('public', True),
        })
        return result

    def process_chunk(self, chunk: pd.DataFrame) -> pd.DataFrame:
        """Process a single chunk"""
        # Validate
        chunk = self.validate_dtypes(chunk)
        chunk = self.validate_values(chunk)

        # Extract and flatten
        chunk = self.extract_nested_fields(chunk)
        flattened = self.flatten_for_staging(chunk)

        # Update stats
        self.stats['chunks_processed'] += 1
        self.stats['total_records'] += len(chunk)
        self.stats['valid_records'] += len(flattened)

        return flattened
```

**Benefits:**
- Vectorized operations (2-10x faster than row-by-row)
- Chunked processing controls memory usage
- Efficient for large files (100K+ records)
- Built-in type coercion and validation

### Validation Points

| Validation Point | What | Where | Error Handling |
|------------------|------|-------|----------------|
| **Eventarc Trigger** | File path pattern | Eventarc filter | Non-matching files ignored |
| **File Header** | Gzip validity | Process start | Move to invalid-files/ |
| **JSON Structure** | Valid JSON per line | Pandas read_json | Skip line, log error |
| **Dtype Validation** | Field types, coercion | Pandas astype() | Set to NaN, count error |
| **Value Validation** | Event type enums, required fields | Pandas isin(), isnull() | Filter out invalid |
| **Business Rules** | References, timestamps | Custom validators | Log to Cloud Logging |

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
│   Layer 2: Pandas JSON Parsing (Chunked)                                                                   │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Read file in chunks (default: 100,000 records)                                                    │   │
│   │ • Parse JSON lines using pd.read_json(chunksize=N)                                                  │   │
│   │ • Invalid JSON lines → set to NaN, skip                                                            │   │
│   │                                                                                                      │   │
│   │ • Memory: ~500MB per chunk vs 4GB for full load                                                      │   │
│   │ FAIL → Skip line, count error, continue processing                                                   │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 3: Dtype Validation (Vectorized)                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Coerce columns to expected dtypes                                                                 │   │
│   │ • id, type → string                                                                                │   │
│   │ • public → boolean                                                                                 │   │
│   │ • created_at → string (preserve ISO format)                                                         │   │
│   │                                                                                                      │   │
│   │ FAIL → Set to NaN, count error, continue processing                                                  │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 4: Value Validation (Vectorized)                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Required fields check (vectorized isnull())                                                       │   │
│   │ • Event type validation (vectorized isin())                                                         │   │
│   │ • Nested field extraction (actor.id, repo.name)                                                     │   │
│   │                                                                                                      │   │
│   │ FAIL → Filter out invalid rows, log warning                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                             │                                             │
│                                                             ▼                                             │
│   Layer 5: Business Rule Validation                                                                      │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ • Timestamp sanity check (not future dates)                                                         │   │
│   │ • Actor IDs, Repo IDs > 0                                                                           │   │
│   │ • Referenced entities are valid                                                                     │   │
│   │                                                                                                      │   │
│   │ FAIL → Filter out invalid rows, log warning                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Chunked Processing Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                              CHUNKED PROCESSING WITH PANDAS                                                 │
├─────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                                             │
│   Input File (600MB, ~1M records)                                                                          │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ gs://landing/raw/2025-03-05-14.json.gz                                                             │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                                      │
│                                    ▼                                                                      │
│   Create Chunk Iterator                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ pd.read_json(file_path, lines=True, chunksize=100_000)                                           │   │
│   │                                                                                                     │   │
│   │ Creates: 10 chunks of 100K records each                                                            │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                                      │
│                                    ▼                                                                      │
│   Process Each Chunk (One at a time)                                                                     │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │                                                                                                      │   │
│   │   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐                       │   │
│   │   │ Chunk 1 │ ───▶│ Chunk 2 │ ───▶│ Chunk 3 │ ───▶│  ...    │ ───▶│Chunk 10 │                       │   │
│   │   └─────────┘     └─────────┘     └─────────┘     └─────────┘     └─────────┘                       │   │
│   │      │              │              │              │              │                                │   │
│   │      ▼              ▼              ▼              ▼              ▼                                │   │
│   │   Validate      Validate       Validate       Validate       Validate                             │   │
│   │   Transform     Transform      Transform      Transform      Transform                             │   │
│   │   Write         Write          Write          Write          Write                                 │   │
│   │   Discard       Discard        Discard        Discard        Discard                               │   │
│   │                                                                                                      │   │
│   │   Peak Memory: ~500MB per chunk (not 4GB!)                                                          │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                                                      │
│                                    ▼                                                                      │
│   Output: Aggregated NDJSON.gz                                                                           │
│   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│   │ gs://staging/processed/2025-03-05-14.ndjson.gz                                                     │   │
│   └─────────────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                                             │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Error Handling Strategy

| Error Type | Action | Logging |
|------------|--------|---------|
| **Corrupted file** | Move entire file | ERROR level to Cloud Logging |
| **Invalid JSON lines** | Skip line, continue | WARN level + counter |
| **Schema violations** | Skip record, continue | WARN level + counter |
| **Business rule violations** | Skip record, continue | WARN level + counter |
| **High error rate** (>10%) | Abort processing | CRITICAL + monitoring alert |
| **Processing errors** | Log, continue | ERROR level |

**No DLQ or retry mechanism** - errors are logged to Cloud Logging with monitoring alerts for critical issues.

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

## Output Format for Staging

### Why NDJSON (Newline-Delimited JSON)?

| Format | Phase 3 BigQuery Ready | Streaming | Schema Evolution |
|--------|----------------------|-----------|------------------|
| **NDJSON** | ✅ Native | ✅ Easy | ✅ Additive |
| Avro | ✅ Native | ❌ Complex | ✅ Full |
| Parquet | ✅ Native | ❌ Complex | ⚠️ Limited |
| CSV | ✅ Native | ✅ Easy | ❌ Positional |

**Decision:** NDJSON for simplicity and Phase 3 BigQuery loading compatibility.

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
│   └── invalid-files/            # Files that failed validation
│       └── {YYYY-MM-DD-HH}.json.gz

gs://{project}-{env}-github-archive-staging/    # OUTPUT: Processed files (Phase 3 loads to BigQuery from here)
└── github-archive/
    └── processed/
        └── {YYYY-MM-DD-HH}.ndjson.gz
```

---

## Component Summary

| Component | Type | Purpose | Scaling |
|-----------|------|---------|---------|
| **Eventarc Trigger #1** | Trigger | Detects new files in raw/ | N/A (event) |
| **Eventarc Trigger #2** | Trigger | Detects new files in chunks/ | N/A (event) |
| **github-archive-processor** | Cloud Run Service | Main file processor | 0-100 instances |
| **file-splitter** | Cloud Run Job | Splits large files | Manual concurrency |
| **chunk-processor** | Cloud Run Task | Processes chunks | Inherits from service |
| **Cloud Logging** | Monitoring | Error logging and metrics | N/A |
| **Cloud Logging** | Monitoring | Error logging and metrics | N/A |

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
│           │   ├── dtype_definitions.py            # Pandas dtype mappings
│           │   └── validation_rules.py             # Validators
│           ├── processors/
│           │   ├── __init__.py
│           │   ├── file_processor.py               # Main processing logic
│           │   ├── chunked_processor.py            # Pandas chunked processing
│           │   ├── file_splitter.py                # Large file splitting
│           │   └── transformer.py                  # JSON flattening
│           ├── validators/
│           │   ├── __init__.py
│           │   ├── file_validator.py               # File-level validation
│           │   ├── dtype_validator.py              # Dtype validation
│           │   ├── value_validator.py              # Value validation
│           │   └── business_validator.py          # Business rules
│           ├── writers/
│           │   ├── __init__.py
│               │   └── ndjson_writer.py              # Output writer
│           ├── utils/
│           │   ├── __init__.py
│           │   ├── gcs_client.py                   # GCS utilities
│           │   └── logger.py                       # Cloud Logging utilities
│           ├── config.py                           # Configuration
│           ├── requirements.txt
│           └── Dockerfile
│
├── test/
│   └── github_archive/
│       └── phase2_process_files/
│           ├── __init__.py
│           ├── test_dtype_definitions.py
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
        │   ├── eventarc.tf                    # Eventarc trigger (direct events)
        │   ├── cloud_run_service.tf           # Processor service
        │   ├── cloud_run_job_splitter.tf      # File splitter job
        │   ├── storage.tf                     # Staging bucket
        │   ├── monitoring.tf                  # Cloud Logging & Monitoring alerts
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

1. **Create dtype definitions** - Pandas dtype mappings for GitHub events
2. **Create Eventarc trigger** - Terraform configuration
3. **Build processor service** - Cloud Run service with autoscaling
4. **Build file splitter** - Cloud Run job for large files
5. **Create validation layers** - File, dtype, and value validators
6. **Create chunked processor** - Pandas chunked processing with memory control
7. **Create output writer** - NDJSON writer with compression
8. **Deploy and test** - End-to-end testing with sample files
