## 1. Overview

`dashboard.html` is the main landing page of the Phase 4 monitoring dashboard. It displays a visual architecture diagram of the full pipeline (Phases 1-3 plus ELT), a "Daily Throughput" table summarising processing metrics per day, and a "Recent Errors" table showing the latest ERROR/WARNING entries across all phases. All timestamps are displayed in IST.

## 2. Prerequisites

- **Template variables** (passed by `app.py`):
  - `daily` -- list of dicts from `daily_throughput.sql` with keys: `day`, `files_processed`, `total_records_in`, `total_records_out`, `total_errors`, `error_rate_pct`, `avg_duration_s`.
  - `errors` -- list of dicts from `pipeline_errors.sql` with keys: `timestamp_ist`, `phase`, `severity`, `error_message`.
- Flask with Jinja2 templating (provided by the `flask` package).

## 3. Upstream & Downstream Dependencies

**Upstream (what provides data to this template)**:
- `app.py` route `/` (`dashboard`) -- executes `daily_throughput.sql` and `pipeline_errors.sql`, passes results to this template.
- `queries/daily_throughput.sql` -- provides the throughput data.
- `queries/pipeline_errors.sql` -- provides the error data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages: `/phase1`, `/phase2`, `/phase3`, `/elt`, `/infra`, `/service-accounts`.

## 4. Code Walkthrough

1. **Styles (lines 5-25)**: Inline CSS with a dark theme (`#1a1a2e` background). Defines styles for the navigation bar, HTML tables, error/warning colour coding, and the architecture diagram boxes/arrows. ELT boxes use a distinct yellow (`#ffd93d`) border.

2. **Navigation bar (lines 29-37)**: Horizontal link bar to all dashboard pages: Overview, Phase 1-3 Detail, ELT Analytics, Infrastructure, Service Accounts.

3. **Architecture diagram (lines 39-55)**: A flexbox-based visual pipeline flow showing: Cloud Scheduler -> Cloud Run Job -> GCS Landing -> Cloud Run Service -> GCS Staging -> Cloud Function -> BigQuery -> ELT. Each box has a service type label and a descriptive name.

4. **Daily Throughput table (lines 57-79)**: Iterates over `daily` with `{% for row in daily %}`. Columns: Date, Files, Records In, Records Out, Errors, Error Rate %, Avg Duration. Conditionally applies the `error` CSS class when `total_errors > 0` or `error_rate_pct > 5`.

5. **Recent Errors table (lines 81-97)**: Iterates over `errors` with `{% for row in errors %}`. Columns: Timestamp (IST), Phase, Severity, Message. Applies `error` class for ERROR severity and `warning` class for WARNING severity.
