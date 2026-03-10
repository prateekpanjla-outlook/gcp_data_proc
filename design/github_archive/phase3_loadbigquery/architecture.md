# Phase 3 Architecture

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLOUD STORAGE                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Staging Bucket: PROJECT_ID-dev-github-archive-staging              │  │
│  │                                                                   │  │
│  │  processed/                                                          │  │
│  │    ├── 2026-03-07-1.ndjson.gz  ← Phase 2 writes here              │  │
│  │    ├── 2026-03-07-2.ndjson.gz                                      │  │
│  │    └── ...                                                           │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 ↓                                           │
│                         finalized event                                     │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    EVENTARC                                         │  │
│  │  Event: google.cloud.storage.object.v1.finalized                    │  │
│  │  Filter: bucket ends with "-github-archive-staging"                 │  │
│  │          prefix = "processed/"                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 ↓                                           │
│                         push delivery                                      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                 CLOUD RUN v2 SERVICE                                 │  │
│  │  dev-bq-loader                                                       │  │
│  │                                                                   │  │
│  │  POST / (Eventarc endpoint)                                         │  │
│  │    1. Parse event (bucket, file_name)                               │  │
│  │    2. Extract date from filename (YYYY-MM-DD-H)                     │  │
│  │    3. Trigger BigQuery load job                                     │  │
│  │    4. Wait for completion (async poll)                              │  │
│  │    5. Delete source file on success                                  │  │
│  │    6. Return 200 on success, 500 on failure                         │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 ↓                                           │
│  ┌──────────────────────────────┬──────────────────────────────────────┐  │
│  │         BIGQUERY              │         CLOUD STORAGE                 │  │
│  │  ┌────────────────────────┐   │                                    │  │
│  │  │ github_events Table    │   │   Delete source file               │  │
│  │  │                        │   │   processed/2026-03-07-1.ndjson.gz │  │
│  │  │  Partitioned by:       │   │                                    │  │
│  │  │  - created_at (DATE)   │   │                                    │  │
│  │  │  Clustered by:         │   │                                    │  │
│  │  │  - event_type          │   │                                    │  │
│  │  │                        │   │                                    │  │
│  │  │  Schema: autodetect    │   │                                    │  │
│  │  │  + flattened fields    │   │                                    │  │
│  │  └────────────────────────┘   │                                    │  │
│  └──────────────────────────────┴──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Eventarc Trigger

**Purpose:** Detects when Phase 2 writes new processed files

**Configuration:**
- **Event Provider:** Cloud Storage
- **Event Type:** `google.cloud.storage.object.v1.finalized`
- **Event Filters:**
  - `bucket`: `*github-archive-staging`
  - `prefix`: `processed/`
- **Destination:** Cloud Run service `dev-bq-loader`
- **Service Account:** Eventarc invoker SA

**Important:** Set Pub/Sub ack deadline to 600 seconds (10 minutes) since BigQuery loads can take time.

### 2. Cloud Run bq-loader Service

**Purpose:** Orchestrates BigQuery load and file cleanup

**Handler Flow:**

```python
POST /  (Eventarc endpoint)
{
  "bucket": "PROJECT_ID-dev-github-archive-staging",
  "name": "processed/2026-03-07-1.ndjson.gz"
}
```

**Processing Steps:**

1. **Validate Event**
   - Check file is in `processed/` path
   - Check extension is `.ndjson.gz`
   - Extract date from filename (YYYY-MM-DD format)

2. **Determine Target Partition**
   - Parse date from filename for partition decorator
   - Target table: `github_events$YYYYMMDD` (daily partition)

3. **Trigger BigQuery Load**
   ```python
   job_config = bigquery.LoadJobConfig(
       source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
       write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
       schema=None,  # Autodetect
       create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
       compression='GZIP'
   )

   load_job = client.load_table_from_uri(
       f"gs://{bucket}/{file_name}",
       f"{project_id}.{dataset_id}.github_events${date_partition}",
       job_config=job_config
   )
   ```

4. **Wait for Completion**
   - Poll job status with exponential backoff
   - Timeout: 10 minutes
   - On timeout: return 500, keep file for retry

5. **Handle Result**
   - **Success:** Delete source file, return 200
   - **Failure:** Log error, return 500, keep file for investigation

### 3. BigQuery Table

**Table:** `github_events`

**Schema:** Autodetected from first file, then locked

**Partitioning:**
- **Type:** DAY (daily partitions)
- **Field:** `created_at` (DATE type extracted from timestamp)
- **Expiration:** 1 year (366 days)

**Clustering:**
- **Fields:** `event_type`
- **Purpose:** Optimize queries filtering by event type

**Partition Decorator Format:**
```
github_events$20260307  # March 7, 2026
```

### 4. Error Handling

| Scenario | Action | Retry |
|----------|--------|-------|
| Load timeout (10min) | Return 500 | Yes (Eventarc redelivers) |
| Load failure (schema error) | Return 500, log error | No (manual fix needed) |
| Delete failure | Log warning, return 200 | No (manual cleanup) |
| Invalid filename | Return 200 (ignore) | No |

## Service Accounts

| Service Account | Purpose | Roles |
|-----------------|---------|-------|
| `dev-bq-loader@PROJECT_ID.iam.gserviceaccount.com` | Cloud Run service identity | - `roles/bigquery.dataEditor`<br>- `roles/bigquery.jobUser`<br>- `roles/logging.logWriter`<br>- `roles/monitoring.metricWriter`<br>- `roles/storage.objectViewer` (staging) |
| `dev-eventarc-invoker@PROJECT_ID.iam.gserviceaccount.com` | Eventarc authentication | - `roles/eventarc.eventReceiver`<br>- `roles/run.invoker` (on bq-loader) |

## Monitoring

**Metrics to Track:**
- Load job success rate
- Load job duration
- File deletion success rate
- Eventarc delivery success rate

**Logging:**
- Structured logs for each load attempt
- Include: filename, partition, rows loaded, duration

## Security Considerations

1. **Least Privilege:** Service accounts have minimum required permissions
2. **File Deletion:** Only delete after confirmed successful load
3. **Schema Evolution:** Autodetect disabled after initial schema; manual changes required
4. **Idempotency:** Loads are idempotent (WRITE_APPEND with duplicate handling)

## Deployment

See [terraform.md](./terraform.md) for infrastructure deployment details.
