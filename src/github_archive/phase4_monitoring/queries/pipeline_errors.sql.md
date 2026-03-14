## 1. Overview

`pipeline_errors.sql` retrieves the 100 most recent ERROR and WARNING log entries across all three pipeline phases (ingestion, processing, BigQuery load). It maps GCP resource types to human-readable phase names for display on the dashboard.

## 2. Prerequisites

- The BigQuery dataset `PROJECT_ID.DATASET_ID` must contain log sink export tables (e.g., `run_googleapis_com_stderr`, `cloud_function_googleapis_com_*`). The query uses a wildcard table suffix (`.*`) to scan all tables in the dataset.
- `PROJECT_ID` and `DATASET_ID` placeholders are replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.DATASET_ID.*` -- all tables in the log sink dataset, covering Cloud Run Jobs (Phase 1), Cloud Run Services (Phase 2), and Cloud Functions (Phase 3).
- The Cloud Logging sink (Phase 4 Terraform `03_operational/main.tf`) must be active and exporting logs.

**Downstream (consumers)**:
- `app.py` route `/` (`dashboard`) -- calls `_run_query('pipeline_errors')` and passes the result as `errors` to `dashboard.html`.
- `templates/dashboard.html` -- renders the "Recent Errors" table using columns: `timestamp_ist`, `phase`, `severity`, `error_message`.

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

1. **SELECT clause**: Converts `timestamp` to IST using `DATETIME(timestamp, 'Asia/Kolkata')`. Uses a `CASE` statement on `resource.type` to map `cloud_run_job` to `phase1_ingestion`, `cloud_run_revision` to `phase2_processing`, and `cloud_function` to `phase3_bq_load`.

2. **FROM clause**: Uses wildcard table `PROJECT_ID.DATASET_ID.*` to query across all log export tables in the dataset simultaneously.

3. **WHERE clause**: Filters to only `ERROR` and `WARNING` severity entries.

4. **ORDER BY / LIMIT**: Orders by timestamp descending (most recent first) and limits to 100 rows to keep the dashboard page responsive.
