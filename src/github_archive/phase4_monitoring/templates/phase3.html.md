## 1. Overview

`phase3.html` is the Phase 3 detail page showing BigQuery load job history for the `github_events` table. It includes a focused architecture diagram highlighting Phase 3 components (Eventarc, Cloud Function, BigQuery) and a table of load jobs with status, row counts, and timestamps in IST.

## 2. Prerequisites

- **Template variable** (passed by `app.py`):
  - `loads` -- list of dicts from `phase3_bq_load_summary.sql` with keys: `load_date`, `job_type`, `job_id`, `rows_loaded`, `status`, `timestamp_ist`.
- Flask with Jinja2 templating.

## 3. Upstream & Downstream Dependencies

**Upstream (what provides data to this template)**:
- `app.py` route `/phase3` -- executes `phase3_bq_load_summary.sql` and passes the result as `loads`.
- `queries/phase3_bq_load_summary.sql` -- provides BQ load job data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

## 4. Code Walkthrough

1. **Styles (lines 5-22)**: Same dark theme. Adds both `error` (red) and `success` (green) CSS classes for colour-coding job status.

2. **Architecture diagram (lines 36-46)**: Shows the Phase 3 portion: GCS Staging -> Eventarc (storage trigger) -> Cloud Function (`bq-loader`) -> BigQuery (`github_events`). The Eventarc, Cloud Function, and BigQuery boxes are marked `active`. The GCS Staging box is not highlighted since it belongs to Phase 2.

3. **Load jobs table (lines 48-69)**: Iterates over `loads` with `{% for row in loads %}`. Columns: Date, Job Type, Job ID, Rows Loaded, Status, Timestamp (IST). Conditionally applies `success` class when `row.status == 'success'` and `error` class otherwise.
