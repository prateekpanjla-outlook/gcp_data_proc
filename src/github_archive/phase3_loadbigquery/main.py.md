# main.py

## 1. Overview

Cloud Function (2nd gen) entry point that loads processed GitHub Archive `.ndjson.gz` files from a GCS staging bucket into BigQuery. The function is triggered via Eventarc when a new object is finalized in the staging bucket. After a successful BigQuery load job, it optionally deletes the source file from GCS. This is pure GCP integration glue with no portable business logic.

## 2. Prerequisites

- **Runtime:** Python 3.11 (Cloud Functions 2nd gen)
- **GCP APIs:** Cloud Functions, BigQuery, Cloud Storage, Eventarc
- **Service Account:** `bq_loader` SA with BigQuery Data Editor, Job User, and Storage Object Admin roles
- **Environment Variables:**
  - `PROJECT_ID` -- GCP project ID (required)
  - `DATASET_ID` -- BigQuery dataset (default: `github_archive`)
  - `TABLE_ID` -- BigQuery table (default: `github_events`)
  - `DELETE_AFTER_LOAD` -- whether to delete the source file after loading (default: `true`)
- **BigQuery Table:** `github_events` must already exist with the schema defined in `schema.json` (created by Terraform Layer 01)
- **Dependencies:** listed in `requirements.txt` (functions-framework, cloudevents, google-cloud-bigquery, google-cloud-storage)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Phase 2 Cloud Run processor | Writes `.ndjson.gz` files to the `processed/` prefix in the GCS staging bucket |
| Upstream | Eventarc trigger | Fires `google.cloud.storage.object.v1.finalized` events to invoke this function |
| Downstream | BigQuery `github_events` table | Receives appended rows via BQ load jobs |
| Downstream | ELT views/MV (`elt.tf`) | Materialized view `mv_repo_daily_stats`, scheduled query `hourly_activity_summary`, staging view `stg_events`, mart views `developer_daily_activity` and `bot_vs_human_activity` all read from `github_events` |

## 4. Code Walkthrough

1. **Module-level initialization (lines 15-34):** Imports GCP client libraries, configures logging, reads environment variables, and creates singleton `bigquery.Client` and `storage.Client` instances (reused across invocations for connection pooling).

2. **`load_to_bigquery(cloud_event)` (line 38):** The `@functions_framework.cloud_event` decorated entry point receives a CloudEvent from Eventarc.

3. **Event parsing (lines 48-55):** Extracts `bucket`, `name`, and `size` from `cloud_event.data`. Logs the event ID, type, and file metadata.

4. **File filtering (lines 57-65):** Two guard clauses skip files that do not end with `.ndjson.gz` or do not reside under the `processed/` prefix. Returns a `skipped` status dict in both cases.

5. **BigQuery load job (lines 73-91):** Configures a `LoadJobConfig` with `NEWLINE_DELIMITED_JSON` source format, `WRITE_APPEND` disposition, and `ignore_unknown_values=True`. Starts the load job from the GCS URI and blocks on `result()`.

6. **Post-load cleanup (lines 96-104):** If `DELETE_AFTER_LOAD` is true, deletes the source blob. Deletion failures are logged as warnings but do not fail the function.

7. **Error handling (lines 114-116):** Any exception during the load job is logged and re-raised so Eventarc's retry policy can redeliver the event.
