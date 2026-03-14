## 1. Overview

`app.py` is the Flask application powering the Phase 4 monitoring dashboard. It runs as a Cloud Run service, querying BigQuery on each page load to display pipeline health metrics across Phases 1-3 and ELT analytics. All HTML is rendered server-side using Jinja2 templates -- there is no frontend framework.

The app exposes seven routes: an overview dashboard (`/`), per-phase detail pages (`/phase1`, `/phase2`, `/phase3`), an ELT analytics page (`/elt`), two static informational pages (`/infra`, `/service-accounts`), and a health check (`/health`).

## 2. Prerequisites

- **Python 3.12+** (matches the Dockerfile base image).
- **Python packages**: `flask`, `google-cloud-bigquery`, `gunicorn` (see `requirements.txt`).
- **Environment variables**:
  - `PROJECT_ID` (required) -- GCP project ID, used to initialise the BigQuery client and as a placeholder replacement in SQL files.
  - `DATASET_ID` (optional, defaults to `pipeline_logs`) -- BigQuery dataset containing Cloud Logging exports.
  - `PORT` (optional, defaults to `8080`) -- listening port when run via `__main__`.
- **IAM permissions**: the Cloud Run service account (`{env}-pipeline-dashboard`) needs `bigquery.jobUser`, `bigquery.resourceViewer`, and `bigquery.dataViewer` on both the `pipeline_logs` and `github_archive` datasets.
- **BigQuery tables**: the log sink must be active and exporting to `pipeline_logs` so that tables like `run_googleapis_com_stderr` exist.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources this file reads)**:
- `queries/*.sql` -- SQL files loaded at runtime by `_run_query()`. Placeholders `PROJECT_ID` and `DATASET_ID` are string-replaced before execution.
- BigQuery dataset `pipeline_logs` -- contains Cloud Logging exports from Phases 1-3 (created by the log sink in `03_operational/main.tf`).
- BigQuery dataset `github_archive` -- contains `github_events` table (Phase 3), plus ELT views `mv_repo_daily_stats`, `developer_daily_activity`, `bot_vs_human_activity`.
- `INFORMATION_SCHEMA.JOBS` -- queried by `phase3_bq_load_summary.sql` for load job metadata.

**Downstream (what depends on this file)**:
- `templates/*.html` -- Jinja2 templates that receive query results as template variables (`daily`, `errors`, `downloads`, `files`, `loads`, `repos`, `developers`, `bot_human`).
- `Dockerfile` -- copies this file into the container and runs it via gunicorn with the WSGI entry point `app:app`.

## 4. Code Walkthrough

1. **Module-level setup (lines 1-21)**: Imports Flask and BigQuery client. Reads `PROJECT_ID` and `DATASET_ID` from environment variables. Creates a module-level `bq_client` instance reused across all requests.

2. **`_run_query(query_name)` (lines 24-35)**: Helper that loads a `.sql` file from the `queries/` directory, performs string replacement of `PROJECT_ID` and `DATASET_ID` placeholders, executes the query via `bq_client.query()`, and returns results as a list of dicts. On failure (e.g. table does not exist yet because the log sink has not exported data), it logs a warning and returns an empty list so the dashboard still renders.

3. **Route handlers (lines 38-90)**:
   - `/` (`dashboard`) -- runs `daily_throughput` and `pipeline_errors` queries, renders `dashboard.html`.
   - `/phase1` -- runs `phase1_download_summary`, renders `phase1.html`.
   - `/phase2` -- runs `phase2_processing_summary`, renders `phase2.html`.
   - `/phase3` -- runs `phase3_bq_load_summary`, renders `phase3.html`.
   - `/elt` -- runs three ELT queries (`elt_repo_stats`, `elt_developer_activity`, `elt_bot_vs_human`), renders `elt.html`.
   - `/infra` and `/service-accounts` -- render static HTML templates with no query data.
   - `/health` -- returns `{"status": "healthy"}` with HTTP 200 for Cloud Run health checks.

4. **`__main__` block (lines 93-95)**: Starts the Flask dev server on `0.0.0.0:PORT`. In production, gunicorn is used instead (see `Dockerfile`).
