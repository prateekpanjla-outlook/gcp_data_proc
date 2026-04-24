# Data Flow: Processing a Single .gz File

## Complete Lifecycle: `2025-01-15-14.json.gz` → BigQuery

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PHASE 1: FILE INGESTION                                            │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────┐         ┌─────────────────────────┐      │
│  │   GitHub Archive        │         │   Cloud Scheduler       │         │   Cloud Storage         │      │
│  │                         │         │                         │         │                         │      │
│  │  https://data.gharchive.│         │  Job: github-archive    │         │  Bucket: {project}-     │      │
│  │  org/2025-01-15-14.json.gz│        │      -downloader        │         │     data-pipeline/       │      │
│  │                         │         │                         │         │                         │      │
│  │  ~1.2 GB (compressed)   │         │  Schedule: 30 * * * *   │         │  /github-archive/raw/   │      │
│  │  ~6.5 GB (uncompressed) │         │  (hourly at :30 past)    │         │                         │      │
│  │  ~142,000 events        │         │                         │         │  ┌───────────────────┐  │      │
│  └──────────┬──────────────┘         └─────────────┬───────────┘         │  │ 2025-01-15-14.json.gz│ │      │
│             │                                     │                      │  │                       │  │      │
│             │                                     │                      │  └───────────────────┘  │      │
│             │                                     ▼                      │                         │      │
│             │                        ┌────────────────────┐            │                         │      │
│             │                        │  HTTP POST         │            │                         │      │
│             │                        │  (run job)         │            │                         │      │
│             │                        └─────────┬──────────┘            │                         │      │
│             │                                  │                       │                         │      │
│             │                                  ▼                       │                         │      │
│             │                        ┌────────────────────┐            │                         │      │
│             │                        │  Cloud Run Job:    │            │                         │      │
│             │                        │  hn-fetcher        │            │                         │      │
│             │                        │  (downloads file)  │            │                         │      │
│             │                        └─────────┬──────────┘            │                         │      │
│             │                                  │                       │                         │      │
│             └──────────────────────────────────┼───────────────────────┘                         │      │
│                                                ▼                                                │      │
│                              ┌──────────────────────────────────────────────────────────────┐      │
│                              │  gsutil cp / curl → gs://{bucket}/github-archive/raw/    │      │
│                              └──────────────────────────────────────────────────────────────┘      │
│                                                                                │                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                │
                                                                                │ File created →
                                                                                │ triggers Eventarc
                                                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PHASE 2: TRIGGERING                                                     │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────┐         ┌─────────────────────────┐      │
│  │   Cloud Storage         │         │      Eventarc           │         │   Cloud Run Job:       │      │
│  │                         │         │                         │         │                         │      │
│  │  Event: finalize        │────────▶│  Trigger: github-       │────────▶│  github-archive-        │      │
│  │  Object: 2025-01-15-14  │         │      archive-trigger     │         │      processor          │      │
│  │  .json.gz               │         │                         │         │                         │      │
│  │                         │         │  Filter:                │         │  Spawns up to 100       │      │
│  │  gs://.../raw/2025-01- │         │  - prefix = "github-"    │         │  concurrent tasks       │      │
│  │     15-14.json.gz       │         │  - suffix = ".json.gz"   │         │  (configurable)         │      │
│  └─────────────────────────┘         └─────────────────────────┘         └────────────┬──────────┘      │
│                                                                                   │                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                   │
                                                                                   │ Each task gets:
                                                                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PHASE 3: PROCESSING (Per Task)                                           │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Cloud Run Job: github-archive-processor                                   │  │
│  │                                                                                                    │  │
│  │  ENTRYPOINT: src/github_archive/main.py                                                          │  │
│  │                                                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  1. INITIALIZATION                                                                           │    │  │
│  │  │     • Parse environment variables (bucket, file, dataset, table)                           │    │  │
│  │  │     • Initialize BigQueryEmulatorAwareClient                                                │    │  │
│  │  │     • Initialize StorageClient                                                               │    │  │
│  │  │     • Initialize PipelineMonitor                                                            │    │  │
│  │  │     • Initialize DeadLetterQueueHandler                                                      │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  2. READ FROM GCS                                                                           │    │  │
│  │  │     storage_client.read_jsonl_file(                                                      │    │  │
│  │  │         "github-archive/raw/2025-01-15-14.json.gz",                                      │    │  │
│  │  │         compressed=True                                                                   │    │  │
│  │  │     )                                                                                      │    │  │
│  │  │                                                                                             │    │  │
│  │  │     Returns generator (memory-efficient)                                                   │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  3. PROCESS CHUNKS (10,000 events per chunk)                                              │    │  │
│  │  │                                                                                             │    │  │
│  │  │     for chunk_df in processor.read_jsonl_chunks(...):                                      │    │  │
│  │  │         # chunk_df: pandas.DataFrame with 10,000 rows                                      │    │  │
│  │  │                                                                                             │    │  │
│  │  │         processed_df = GitHubEventProcessor.process_chunk(chunk_df)                         │    │  │
│  │  │                                                                                             │    │  │
│  │  │         # Extracts nested fields:                                                          │    │  │
│  │  │         # - actor.id, actor.login, actor.avatar_url                                         │    │  │
│  │  │         # - repo.id, repo.name, repo.url                                                   │    │  │
│  │  │         # - payload fields (size, ref, push_id, etc.)                                      │    │  │
│  │  │                                                                                             │    │  │
│  │  │         processed_df contains:                                                              │    │  │
│  │  │         - event_id, event_type, created_at                                                  │    │  │
│  │  │         - actor_id, actor_login, repo_id, repo_name                                         │    │  │
│  │  │         - public, payload fields...                                                         │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  4. LOAD TO BIGQUERY (FREE - batch load)                                                 │    │  │
│  │  │                                                                                             │    │  │
│  │  │     @retry_with_exponential_backoff(max_attempts=3)                                        │    │  │
│  │  │     def load_chunk(df):                                                                    │    │  │
│  │  │         bigquery_client.load_dataframe(                                                     │    │  │
│  │  │             dataset_id="github_dataset",                                                    │    │  │
│  │  │             table_id="events",                                                              │    │  │
│  │  │             dataframe=processed_df,                                                         │    │  │
│  │  │             schema=GITHUB_EVENTS_SCHEMA,                                                     │    │  │
│  │  │             write_disposition="WRITE_APPEND"                                                │    │  │
│  │  │         )                                                                                   │    │  │
│  │  │                                                                                             │    │  │
│  │  │         # Creates BigQuery Load Job (uses free shared compute pool)                          │    │  │
│  │  │         # Waits for job completion (30s timeout)                                             │    │  │
│  │  │         # Returns: {job_id, state, num_rows, errors}                                        │    │  │
│  │  │                                                                                             │    │  │
│  │  │     # On success:                                                                           │    │  │
│  │  │     monitor.record_rows_processed(source="github", count=10000)                             │    │  │
│  │  │                                                                                             │    │  │
│  │  │     # On failure (after retries):                                                           │    │  │
│  │  │     dlq_handler.publish_failure(original_event, error, source="github-archive")              │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  5. COMPLETION & CLEANUP                                                                   │    │  │
│  │  │                                                                                             │    │  │
│  │  │     # Log final metrics                                                                     │    │  │
│  │  │     logger.info("Processing complete", {                                                   │    │  │
│  │  │         "file": "2025-01-15-14.json.gz",                                                   │    │  │
│  │  │         "total_events": 142000,                                                            │    │  │
│  │  │         "processed": 141950,                                                               │    │  │
│  │  │         "failed": 50,                                                                      │    │  │
│  │  │         "processing_time_ms": 45000                                                        │    │  │
│  │  │     })                                                                                      │    │  │
│  │  │                                                                                             │    │  │
│  │  │     # Move file to processed/                                                               │    │  │
│  │  │     storage_client.move(                                                                   │    │  │
│  │  │         "github-archive/raw/2025-01-15-14.json.gz",                                         │    │  │
│  │  │         "github-archive/processed/2025-01-15-14.json.gz"                                    │    │  │
│  │  │     )                                                                                       │    │  │
│  │  │                                                                                             │    │  │
│  │  │     return ProcessingResult(                                                               │    │  │
│  │  │         total_events=142000,                                                                │    │  │
│  │  │         processed=141950,                                                                   │    │  │
│  │  │         failed=50,                                                                         │    │  │
│  │  │         errors=[]                                                                           │    │  │
│  │  │     )                                                                                       │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                                                                                    │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                   │                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                                                    │
                                                                                    │ Success Path
                                                                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PHASE 4: BIGQUERY STORAGE                                                 │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         BigQuery: github_dataset.events                                            │  │
│  │                                                                                                    │  │
│  │  Table Schema:                                                                                      │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  event_id              STRING    (REQUIRED)                                                  │ │  │
│  │  │  event_type            STRING                                                                  │ │  │
│  │  │  created_at            TIMESTAMP (partitioning field)                                         │ │  │
│  │  │  actor_id              INTEGER                                                                │ │  │
│  │  │  actor_login           STRING                                                                  │ │  │
│  │  │  repo_id               INTEGER                                                                │ │  │
│  │  │  repo_name             STRING                                                                  │ │  │
│  │  │  payload               JSON                                                                   │ │  │
│  │  │  ... (20+ more fields)                                                                  │ │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                                                    │  │
│  │  Partitioning: DATE(created_at)  —  Each day's data is in a separate partition                    │  │
│  │  Clustering: event_type, repo_id     —  Queries filter by these fields are faster                 │  │
│  │                                                                                                    │  │
│  │  Data Organization:                                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  Table: github_dataset.events                                                                  │ │  │
│  │  │  ├─ 20250115 (partition)  ←  This file's data                                                │ │  │
│  │  │  │  ├─ 2025-01-15-14.json.gz (source)                                                       │ │  │
│  │  │  │  └─ 142,000 rows                                                                         │ │  │
│  │  │  ├─ 20250115 (partition)  ←  From previous hourly files                                       │ │  │
│  │  │  └─ ...                                                                                      │ │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                                                    │  │
│  │  Query Example:                                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐ │  │
│  │  │  SELECT                                                                                       │ │  │
│  │  │      event_type,                                                                             │ │  │
│  │  │      COUNT(*) as count,                                                                     │ │  │
│  │  │      COUNT(DISTINCT repo_id) as unique_repos                                                 │ │  │
│  │  │  FROM `project.github_dataset.events`                                                        │ │  │
│  │  │  WHERE DATE(created_at) = "2025-01-15"                                                       │ │  │
│  │  │  GROUP BY event_type                                                                         │ │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                                                    │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

                                        OR (Error Path)
                                             ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                    PHASE 5: ERROR HANDLING (DLQ)                                           │
│                                                                              │
│  ┌─────────────────────────┐         ┌─────────────────────────┐         ┌─────────────────────────┐      │
│  │   Processing Fails      │         │      Pub/Sub Topic      │         │   DLQ Processor Job    │      │
│  │                         │         │                         │         │                         │      │
│  │  Error: Exception       │────────▶│  pipeline-dlq           │────────▶│  Runs every 10 min     │      │
│  │  Context: {             │         │                         │         │                         │      │
│  │    file: "...",         │         │  Message: {             │         │  For each message:     │      │
│  │    event: {...},        │         │    original_event,       │         │  1. Deserialize        │      │
│  │    error: "..."         │         │    error_message,        │         │  2. Check retry_count   │      │
│  │  }                      │         │    source: "github",     │         │  3. If < max_retries:   │      │
│  │                         │         │    retry_count: 0,        │         │     - Re-process       │      │
│  │                         │         │    timestamp             │         │  4. Else:              │      │
│  │                         │         │  }                      │         │     - Move to GCS       │      │
│  │                         │         │                         │         │       /dlq/permanent-   │      │
│  │                         │         │                         │         │       failures/         │      │
│  └─────────────────────────┘         └─────────────────────────┘         └─────────────────────────┘      │
│                                                                              │                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Breakdown

### Phase 1: File Ingestion (Takes ~1-5 minutes)

| Step | Component | Action | Duration |
|------|-----------|--------|----------|
| 1.1 | Cloud Scheduler | Triggers at `:30` past the hour | Instant |
| 1.2 | Cloud Run Job | `hn-fetcher` downloads from gharchive.org | ~1-3 min |
| 1.3 | Cloud Storage | File stored at `gs://.../raw/2025-01-15-14.json.gz` | ~30 sec |

### Phase 2: Triggering (Instant)

| Step | Component | Action |
|------|-----------|--------|
| 2.1 | Cloud Storage | `finalize` event emitted |
| 2.2 | Eventarc | Matches filter (prefix=`github-archive/raw/`, suffix=`.json.gz`) |
| 2.3 | Cloud Run Job | `github-archive-processor` triggered |

### Phase 3: Processing (Takes ~5-15 minutes depending on file size)

| Step | Component | Action | Rows/Sec |
|------|-----------|--------|----------|
| 3.1 | Storage Client | Read & decompress `.json.gz` | ~500 MB/s |
| 3.2 | Processor | Parse JSON lines (generator) | ~50K events/s |
| 3.3 | Processor | Flatten nested fields | ~30K events/s |
| 3.4 | BigQuery | Load chunk (10,000 rows) | ~5-10 sec |
| 3.5 | Repeat | For 15 chunks (142,000 events) | Total ~2 min |

### Phase 4: BigQuery Storage

| Step | Component | Action |
|------|-----------|--------|
| 4.1 | Load Job | Created (uses FREE shared compute pool) |
| 4.2 | Data Written | To partition `20250115` |
| 4.3 | Clustered By | `event_type`, `repo_id` for query performance |

### Phase 5: Error Handling (If needed)

| Step | Component | Action |
|------|-----------|--------|
| 5.1 | DLQ Handler | Publish failed event to Pub/Sub |
| 5.2 | DLQ Processor | Retry (max 3 times with exponential backoff) |
| 5.3 | Permanent Failure | Store to `gs://.../dlq/permanent-failures/` |

---

## Key Metrics

| Metric | Value |
|--------|-------|
| **File Size** | ~1.2 GB compressed → ~6.5 GB uncompressed |
| **Event Count** | ~142,000 events per hour |
| **Processing Time** | ~5-15 minutes total |
| **Cost** | FREE (BigQuery batch load uses shared pool) |
| **Retry Attempts** | 3 (exponential backoff: 1s, 2s, 4s) |
| **DLQ Retention** | 7 days |
