## 1. Overview

`phase1_download_summary.sql` extracts Phase 1 download completion logs to show which GitHub Archive files were downloaded, their sizes, and when the downloads occurred. It parses the file name and byte count from unstructured log messages.

## 2. Prerequisites

- The BigQuery table `PROJECT_ID.DATASET_ID.run_googleapis_com_stdout` must exist. This table is auto-created by the Cloud Logging sink when the Phase 1 Cloud Run Job writes to stdout.
- Phase 1 download logs must follow the format: `Download completed: gs://bucket/path/filename (bytes bytes)`.
- `PROJECT_ID` and `DATASET_ID` placeholders are replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.DATASET_ID.run_googleapis_com_stdout` -- BigQuery table populated by the Cloud Logging sink.
- Phase 1 download script -- produces the `Download completed` log lines this query parses.

**Downstream (consumers)**:
- `app.py` route `/phase1` -- calls `_run_query('phase1_download_summary')` and passes the result as `downloads` to `phase1.html`.
- `templates/phase1.html` -- renders a table with columns: `download_date`, `file_name`, `file_size_mb`, `file_size_bytes`, `timestamp_ist`.

## 4. Code Walkthrough

1. **SELECT clause**: Extracts the IST date via `DATE(timestamp, 'Asia/Kolkata')`. Uses `REGEXP_EXTRACT` to pull the file name from the GCS path (captures text between the last `/` and a space-`(`) and the byte count from the parenthesised size. Converts bytes to MB by dividing by 1,048,576 (1 MiB), rounded to 1 decimal.

2. **FROM clause**: Reads from `run_googleapis_com_stdout` -- the stdout table, since download completion messages are written to stdout (not stderr).

3. **WHERE clause**: Filters to rows containing `Download completed` in `textPayload`.

4. **ORDER BY / LIMIT**: Most recent downloads first, limited to 50 rows.
