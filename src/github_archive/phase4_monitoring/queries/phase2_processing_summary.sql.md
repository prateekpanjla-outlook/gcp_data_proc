## 1. Overview

`phase2_processing_summary.sql` extracts per-file processing details from Phase 2 completion logs. It shows each processed file's record counts (in/out), error count, processing duration, and timestamp.

## 2. Prerequisites

- The BigQuery table `PROJECT_ID.DATASET_ID.run_googleapis_com_stderr` must exist, populated by the Cloud Logging sink.
- Phase 2 `file_processor.py` must emit completion logs in the format: `Completed {file_name}: {records_in} in, {records_out} out, {errors} errors, {duration}s`.
- `PROJECT_ID` and `DATASET_ID` placeholders are replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.DATASET_ID.run_googleapis_com_stderr` -- BigQuery table containing Phase 2 Cloud Run service stderr logs.
- Phase 2 `file_processor.py` -- the source of the structured log lines parsed by this query.

**Downstream (consumers)**:
- `app.py` route `/phase2` -- calls `_run_query('phase2_processing_summary')` and passes the result as `files` to `phase2.html`.
- `templates/phase2.html` -- renders a table with columns: `processing_date`, `file_name`, `records_in`, `records_out`, `errors`, `duration_seconds`, `timestamp_ist`.

## 4. IAM & Service Accounts

These queries are executed by the Flask dashboard app running as `{env}-pipeline-dashboard@{project}.iam.gserviceaccount.com`.

| Role | Purpose |
|---|---|
| `bigquery.jobUser` | Run BigQuery queries (create jobs) |
| `bigquery.dataViewer` | Read tables in the `pipeline_logs` dataset |

### Cross-references

- **Learnings Issue 10** (`phase4_deployment_issues.md`): The dashboard SA initially lacked `bigquery.resourceViewer`, which is needed for `INFORMATION_SCHEMA.JOBS` access (relevant to `phase3_bq_load_summary.sql`, not this query).
- **Learnings Issue 11** (`phase4_deployment_issues.md`): The dashboard SA initially only had `dataViewer` on `pipeline_logs`, not on `github_archive`. This caused silent failures -- `_run_query()` catches exceptions and returns empty results, so missing permissions surface as empty tables rather than errors.

## 5. Code Walkthrough

1. **SELECT clause**: Buckets by IST date. Uses `REGEXP_EXTRACT` to parse the file name (text between `Completed ` and `:`), records in, records out, errors, and duration from `textPayload`. Casts numeric extractions to `INT64` (counts) and `FLOAT64` (duration).

2. **FROM clause**: Reads from `run_googleapis_com_stderr` since Phase 2 logs processing output to stderr via Python's `logging` module.

3. **WHERE clause**: Filters to `Completed` lines matching the `in,...out,...errors` pattern, same filter as `daily_throughput.sql` but without aggregation.

4. **ORDER BY**: Most recent first. No `LIMIT` is applied, so all matching rows are returned.
