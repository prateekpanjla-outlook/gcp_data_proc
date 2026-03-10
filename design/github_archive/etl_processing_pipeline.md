# GitHub Archive ETL Processing Pipeline

Complete data flow for processing a single `.gz` file from GitHub Archive through to BigQuery.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  SOURCE: https://data.gharchive.org/2025-01-15-14.json.gz                                                  │
│  Size: ~1.2 GB compressed → ~6.5 GB uncompressed (~142,000 events)                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 1: INGESTION (~1-5 min)                                                                          │
│                                                                                  │
│  ┌───────────────────┐    ┌───────────────┐    ┌───────────────────────────────────────┐                  │
│  │  GitHub Archive    │───▶│ Cloud         │───▶│ Cloud Storage Bucket                │                  │
│  │  Public Data       │    │ Scheduler     │    │ {project}-data-pipeline/            │                  │
│  │                    │    │ (Hourly @:30) │    │   github-archive/raw/               │                  │
│  └───────────────────┘    └───────────────┘    │   2025-01-15-14.json.gz             │                  │
│                                                    │                                │                  │
│                                                    └────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                    │ finalize event
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 2: TRIGGERING (Instant)                                                                         │
│                                                                                  │
│  ┌───────────────┐         ┌───────────────┐         ┌───────────────────────────────┐                  │
│  │  Cloud Storage │────────▶│  Eventarc     │────────▶│ Cloud Run Job:              │                  │
│  │  finalize      │         │  Trigger      │         │ github-archive-processor    │                  │
│  │  event         │         │               │         │ (up to 100 tasks)           │                  │
│  └───────────────┘         └───────────────┘         └───────────────────────────────┘                  │
│                                                                                  │
│  Eventarc Filter: prefix="github-archive/raw/" AND suffix=".json.gz"                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 3: PROCESSING (~5-15 min)                                                                         │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         Cloud Run Job: github-archive-processor                                     │  │
│  │                                                                                                    │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  STEP 1: INITIALIZATION                                                                 │    │  │
│  │  │     • Parse env vars (bucket, file, dataset, table)                                      │    │  │
│  │  │     • Initialize BigQueryEmulatorAwareClient                                               │    │  │
│  │  │     • Initialize StorageClient                                                              │    │  │
│  │  │     • Initialize PipelineMonitor                                                           │    │  │
│  │  │     • Initialize DeadLetterQueueHandler                                                     │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  STEP 2: READ FROM GCS                                                                   │    │  │
│  │  │     storage_client.read_jsonl_file(                                                      │    │  │
│  │  │         "github-archive/raw/2025-01-15-14.json.gz",                                      │    │  │
│  │  │         compressed=True                                                                   │    │  │
│  │  │     )                                                                                      │    │  │
│  │  │     Returns: Generator[yield dict]  (memory efficient)                                    │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  STEP 3: PROCESS CHUNKS (10,000 events per chunk)                                         │    │  │
│  │  │                                                                                             │    │  │
│  │  │     for chunk_df in processor.read_jsonl_chunks(...):                                      │    │  │
│  │  │         # chunk_df: pandas.DataFrame with 10,000 rows                                      │    │  │
│  │  │                                                                                             │    │  │
│  │  │         processed_df = GitHubEventProcessor.process_chunk(chunk_df)                         │    │  │
│  │  │                                                                                             │    │  │
│  │  │     Extracts nested fields:                                                                 │    │  │
│  │  │     • actor.id, actor.login, actor.avatar_url                                                 │    │  │
│  │  │     • repo.id, repo.name, repo.url                                                           │    │  │
│  │  │     • payload.size, payload.ref, payload.push_id...                                          │    │  │
│  │  │                                                                                             │    │  │
│  │  │     Output columns:                                                                          │    │  │
│  │  │     • event_id, event_type, created_at, actor_id, actor_login                                 │    │  │
│  │  │     • repo_id, repo_name, public, payload_*...                                               │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  STEP 4: LOAD TO BIGQUERY (FREE - batch load)                                              │    │  │
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
│  │  │     Creates BigQuery Load Job (uses FREE shared compute pool)                               │    │  │
│  │  │     Waits for completion (30s timeout)                                                       │    │  │
│  │  │     Returns: {job_id, state, num_rows, errors}                                              │    │  │
│  │  │                                                                                             │    │  │
│  │  │     On failure → dlq_handler.publish_failure(original_event, error, source)                  │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                          │                                                       │  │
│  │                                          ▼                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────┐    │  │
│  │  │  STEP 5: COMPLETION & CLEANUP                                                             │    │  │
│  │  │                                                                                             │    │  │
│  │  │     Log metrics: total_events, processed, failed, processing_time_ms                        │    │  │
│  │  │     Move file: raw/ → processed/                                                            │    │  │
│  │  │     Return ProcessingResult                                                                  │    │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────┘    │  │
│  │                                                                                                    │  │
│  └────────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │                      │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
                                    │ Success
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 4: BIGQUERY STORAGE                                                                               │
│                                                                                  │
│  Table: github_dataset.events                                                                          │
│  Partition: 20250115 (by DATE(created_at))                                                             │
│  Clustered by: event_type, repo_id                                                                     │
│  Rows: 142,000                                                                                         │
│  Cost: FREE (batch load uses shared compute pool)                                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

                                    OR Error
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  PHASE 5: ERROR HANDLING (DLQ)                                                                         │
│                                                                                  │
│  Processing Error → Publish to Pub/Sub: pipeline-dlq                                                    │
│  DLQ Processor (runs every 10 min)                                                                      │
│    → Retry (max 3x with exponential backoff: 1s, 2s, 4s, 8s...)                                         │
│    → Permanent failures → gs://.../dlq/permanent-failures/                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Metrics

| Metric | Value |
|--------|-------|
| **Input File** | ~1.2 GB compressed (~6.5 GB uncompressed) |
| **Events per File** | ~142,000 events |
| **Processing Time** | ~5-15 minutes |
| **Chunk Size** | 10,000 events |
| **Chunks per File** | ~15 chunks |
| **BigQuery Load** | FREE (batch load) |
| **Retry Attempts** | 3 (exponential backoff) |

---

## Source Files

| Component | File |
|-----------|------|
| Main Entry | [`src/github_archive/main.py`](src/github_archive/main.py) |
| Processor | [`src/github_archive/processor.py`](src/github_archive/processor.py) |
| Schemas | [`src/github_archive/schemas.py`](src/github_archive/schemas.py) |
| BQ Client | [`src/shared/bigquery_emulator_client.py`](src/shared/bigquery_emulator_client.py) |
| Retry Logic | [`src/shared/retry.py`](src/shared/retry.py) |
| DLQ Handler | [`src/dlq/handler.py`](src/dlq/handler.py) |
| Monitoring | [`src/shared/monitoring.py`](src/shared/monitoring.py) |
