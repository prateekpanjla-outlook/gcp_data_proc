## 1. Overview

`phase1.html` is the Phase 1 detail page showing individual file download records from the GitHub Archive ingestion pipeline. It includes a focused architecture diagram highlighting the Phase 1 components (Cloud Scheduler, Cloud Run Job, GCS Landing) and a table of recent downloads with file names, sizes, and timestamps in IST.

## 2. Prerequisites

- **Template variable** (passed by `app.py`):
  - `downloads` -- list of dicts from `phase1_download_summary.sql` with keys: `download_date`, `file_name`, `file_size_mb`, `file_size_bytes`, `timestamp_ist`.
- Flask with Jinja2 templating.

## 3. Upstream & Downstream Dependencies

**Upstream (what provides data to this template)**:
- `app.py` route `/phase1` -- executes `phase1_download_summary.sql` and passes the result as `downloads`.
- `queries/phase1_download_summary.sql` -- provides download log data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

## 4. Code Walkthrough

1. **Styles (lines 5-22)**: Same dark theme as `dashboard.html`. Adds an `active` class for architecture boxes (green border with glow effect) to highlight the Phase 1 components.

2. **Architecture diagram (lines 36-42)**: Shows only the Phase 1 portion of the pipeline: Cloud Scheduler -> Cloud Run Job (`download.sh`) -> GCS Landing (`*.json.gz`). All three boxes have the `active` class applied for visual emphasis.

3. **Downloads table (lines 44-61)**: Iterates over `downloads` with `{% for row in downloads %}`. Columns: Date, File Name, Size (MB), Size (bytes), Timestamp (IST). No conditional styling is applied -- all rows use the default table style.
