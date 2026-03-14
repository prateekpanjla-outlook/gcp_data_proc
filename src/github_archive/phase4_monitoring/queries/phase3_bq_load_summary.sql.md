## 1. Overview

`phase3_bq_load_summary.sql` shows BigQuery load job history for the `github_events` table. It combines `INFORMATION_SCHEMA.JOBS` metadata (job status, timestamps) with row counts from the `github_events` table itself to give a complete view of Phase 3 load operations.

## 2. Prerequisites

- The dashboard service account needs `roles/bigquery.resourceViewer` at the project level to access `INFORMATION_SCHEMA.JOBS`.
- The `PROJECT_ID.github_archive.github_events` table must exist (created by Phase 3 Terraform `01_static/main.tf`).
- The dashboard service account needs `roles/bigquery.dataViewer` on the `github_archive` dataset.
- `PROJECT_ID` is replaced at runtime by `app.py._run_query()`. Note: `DATASET_ID` is not used in this query -- it references `github_archive` directly.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `region-us-central1.INFORMATION_SCHEMA.JOBS` -- BigQuery system view providing job metadata (job ID, status, error details, creation time).
- `PROJECT_ID.github_archive.github_events` -- the target table loaded by the Phase 3 Cloud Function. Used here for row counts per date.

**Downstream (consumers)**:
- `app.py` route `/phase3` -- calls `_run_query('phase3_bq_load_summary')` and passes the result as `loads` to `phase3.html`.
- `templates/phase3.html` -- renders a table with columns: `load_date`, `job_type`, `job_id`, `rows_loaded`, `status`, `timestamp_ist`.

## 4. Code Walkthrough

1. **Main SELECT**: Extracts the IST load date, job type, job ID, and a computed `status` column. The status uses a `CASE` expression: if the job state is `DONE`, it checks `error_result` -- `NULL` means success, non-NULL means failed. Other states (e.g., `RUNNING`, `PENDING`) are passed through as-is.

2. **LEFT JOIN subquery**: Aggregates `github_events` rows by `DATE(created_at)` to get `rows_loaded` per day. This is joined to the jobs table on the job creation date.

3. **WHERE clause**: Filters to `LOAD` job types targeting the `github_events` table using `j.destination_table.table_id`.

4. **ORDER BY / LIMIT**: Most recent jobs first, limited to 50 rows.
