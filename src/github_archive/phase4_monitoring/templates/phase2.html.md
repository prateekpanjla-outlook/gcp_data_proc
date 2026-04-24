## 1. Overview

`phase2.html` is the Phase 2 detail page showing per-file processing results from the file processor Cloud Run service. It includes a focused architecture diagram highlighting Phase 2 components (Eventarc, Cloud Run Service, GCS Staging) and a table of processed files with record counts, error counts, and durations in IST.

## 2. Prerequisites

- **Template variable** (passed by `app.py`):
  - `files` -- list of dicts from `phase2_processing_summary.sql` with keys: `processing_date`, `file_name`, `records_in`, `records_out`, `errors`, `duration_seconds`, `timestamp_ist`.
- Flask with Jinja2 templating.

## 3. Upstream & Downstream Dependencies

**Upstream (what provides data to this template)**:
- `app.py` route `/phase2` -- executes `phase2_processing_summary.sql` and passes the result as `files`.
- `queries/phase2_processing_summary.sql` -- provides per-file processing data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

## 4. Code Walkthrough

1. **Styles (lines 5-22)**: Same dark theme. Includes the `active` class (green glow) and the `error` class (red text) for highlighting errors.

2. **Architecture diagram (lines 36-45)**: Shows the Phase 2 portion: GCS Landing -> Eventarc (storage trigger) -> Cloud Run Service (`file_processor`) -> GCS Staging (`*.ndjson.gz`). The Eventarc, Cloud Run, and GCS Staging boxes are marked `active`. The GCS Landing box is not highlighted since it belongs to Phase 1.

3. **Processing table (lines 47-69)**: Iterates over `files` with `{% for row in files %}`. Columns: Date, File, Records In, Records Out, Errors, Duration (s), Timestamp (IST). Conditionally applies the `error` CSS class to the Errors cell when `row.errors > 0`.
