## 1. Overview

`daily_throughput.sql` calculates daily pipeline throughput metrics by parsing Phase 2 processing completion logs. It aggregates files processed, total records in/out, error counts, error rate percentage, and average processing duration per day.

## 2. Prerequisites

- The BigQuery table `PROJECT_ID.DATASET_ID.run_googleapis_com_stderr` must exist. This table is auto-created by the Cloud Logging sink when Phase 2 Cloud Run service writes to stderr.
- Phase 2 log messages must follow the format: `Completed {file_name}: {records_in} in, {records_out} out, {errors} errors, {duration}s`.
- `PROJECT_ID` and `DATASET_ID` placeholders are replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.DATASET_ID.run_googleapis_com_stderr` -- BigQuery table populated by the Cloud Logging sink (Phase 4 Terraform `03_operational/main.tf`).
- Phase 2 `file_processor.py` -- produces the structured log lines this query parses.

**Downstream (consumers)**:
- `app.py` route `/` (`dashboard`) -- calls `_run_query('daily_throughput')` and passes the result as `daily` to `dashboard.html`.
- `templates/dashboard.html` -- renders the "Daily Throughput" table using columns: `day`, `files_processed`, `total_records_in`, `total_records_out`, `total_errors`, `error_rate_pct`, `avg_duration_s`.

## 4. Code Walkthrough

1. **SELECT clause**: Uses `DATE(timestamp, 'Asia/Kolkata')` to bucket rows by IST date. Applies `REGEXP_EXTRACT` with capture groups to parse numeric values from the unstructured `textPayload` field: records in (`(\d+) in,`), records out (`(\d+) out,`), errors (`(\d+) errors,`), and duration (`([\d.]+)s$`).

2. **Computed columns**: `files_processed` is `COUNT(*)` of matching log lines. `error_rate_pct` uses `SAFE_DIVIDE` to compute `(total_errors / total_records_in) * 100`, rounded to 2 decimal places. `avg_duration_s` averages the per-file duration.

3. **FROM clause**: Reads from the `run_googleapis_com_stderr` table within the log sink dataset.

4. **WHERE clause**: Filters to only "Completed" lines that contain the expected `in,...out,...errors` pattern, excluding other stderr output.

5. **GROUP BY / ORDER BY**: Groups by IST date and orders most recent day first.
