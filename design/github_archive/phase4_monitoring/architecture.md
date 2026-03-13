# Phase 4: Pipeline Monitoring Dashboard

## Approach

Cloud Logging -> Log Sink -> BigQuery -> Cloud Run Dashboard

No application code changes to phases 1-3. All 3 phases already emit logs
to Cloud Logging via stdout. A log sink exports those logs to a BigQuery
dataset. A lightweight Flask app on Cloud Run queries BQ and renders
HTML dashboard pages.

## Data Flow

```
Phase 1 (Cloud Run Job)     --stdout--> Cloud Logging --\
Phase 2 (Cloud Run Service) --stdout--> Cloud Logging --> Log Sink --> BQ dataset (pipeline_logs)
Phase 3 (Cloud Function)    --stdout--> Cloud Logging --/
                                                                          |
                                                                          v
                                                            Cloud Run Dashboard (Flask)
                                                              /        |        \
                                                             /         |         \
                                                          [/]      [/phase2]   [/phase3]
                                                        overview    detail      detail
```

## Components

### 1. Log Sink (Terraform)
Single sink covering all 3 phases:
```
(resource.type="cloud_run_job" OR resource.type="cloud_run_revision" OR resource.type="cloud_function")
AND (resource.labels.service_name=~"github-archive" OR resource.labels.job_name=~"github-archive")
```
Exports to BQ with partitioned tables for cost-efficient queries.

### 2. BigQuery Dataset (pipeline_logs)
Cloud Logging auto-creates the table schema when exporting. Key columns:
- `timestamp` — log entry time
- `severity` — INFO / WARNING / ERROR
- `textPayload` — the log message (f-string)
- `resource.type` — identifies which phase (cloud_run_job / cloud_run_revision / cloud_function)
- `resource.labels.service_name` — service identifier

90-day table expiration — logs are transient, not archival.

### 3. Dashboard Queries (SQL files)
Queries parse the unstructured f-string log messages using REGEXP_EXTRACT.
This is fragile — if log messages change, queries break. Acceptable for now
since the current refactor is untested and we don't want more code changes.

| Query file | What it shows |
|------------|---------------|
| `daily_throughput.sql` | Daily aggregates: files, records, error rate, avg duration |
| `phase2_processing_summary.sql` | Per-file detail: records in/out, errors, duration |
| `phase3_bq_load_summary.sql` | Per-file BQ load: rows loaded, success/failed |
| `pipeline_errors.sql` | Recent errors/warnings across all phases |

### 4. Cloud Run Dashboard Service (Flask)
- Lightweight Flask app, server-side rendered HTML (no JS framework)
- Reads SQL files from `queries/` directory, runs them against BQ
- 3 routes: `/` (overview), `/phase2` (detail), `/phase3` (detail)
- Scale to zero when not in use (min instances = 0, max = 1)
- 512Mi memory, 1 vCPU — queries are small, rendering is trivial

#### Pages
| Route | Content |
|-------|---------|
| `/` | Daily throughput table + recent errors |
| `/phase2` | Per-file processing detail (records, errors, duration) |
| `/phase3` | Per-file BQ load detail (rows loaded, status) |
| `/health` | Health check endpoint |

## Dashboard SA Permissions
- `roles/bigquery.jobUser` — run queries
- `roles/bigquery.dataViewer` — read pipeline_logs dataset
- No write access to any pipeline resources

## Key Metrics

| Metric | Phase | Source log message |
|--------|-------|--------------------|
| Files downloaded | 1 | download completion logs |
| Files processed | 2 | `"Completed {file_name}: {records_in} in, {records_out} out, {errors} errors, {duration}s"` |
| Records in / out | 2 | same as above |
| Error rate | 2 | same as above |
| Processing duration | 2 | same as above |
| Files skipped | 2, 3 | `"Ignoring file"` / `"Skipping"` |
| Files rejected (too large) | 2 | `"File too large"` |
| BQ rows loaded | 3 | `"Loaded {rows} rows"` |
| BQ load failures | 3 | `"Failed to load"` |
| Source files deleted | 3 | `"Deleted source file"` |

## Cost

- Log sink to BQ: first 50 GB/month free, then $0.50/GB
- Pipeline logs are small (~KB per file processed), cost will be negligible
- Cloud Run dashboard: scale-to-zero, pay only when accessed
- No always-on infrastructure

## Future Improvement

Switch to structured JSON logging in phases 1-3. Fields become BQ columns
automatically, no regex parsing needed. Do this after the current refactor
is tested and deployed.
