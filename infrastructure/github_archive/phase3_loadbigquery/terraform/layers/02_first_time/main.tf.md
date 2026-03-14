# main.tf

## 1. Overview

Terraform Layer 02 (First-time) for Phase 3. Provisions IAM bindings that require APIs to already be enabled (done in Layer 01). Grants the `bq_loader` service account dataset-level BigQuery access and bucket-level Cloud Storage access on the staging bucket. Also grants the Eventarc service agent object viewer access on the staging bucket, which is required for Eventarc to validate the bucket when creating a trigger.

## 2. Prerequisites

- **Layer 01 applied:** Service accounts (`bq_loader`, `eventarc_invoker`) and APIs must already exist. Their emails are read from Layer 01 remote state.
- **GCS staging bucket:** Must exist (created by Phase 2 infrastructure). Its name is passed via `var.staging_bucket_name`.
- **Remote state:** Layer 01 state must be accessible at `terraform/state/phase3-static` in the GCS state bucket.
- **Variables:** `project_id`, `region`, `environment`, `staging_bucket_name` (required); `dataset_id`, `table_id` (have defaults).

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Layer 01 (`01_static`) | Provides service account emails via remote state outputs |
| Upstream | Phase 2 infrastructure | Provides the GCS staging bucket |
| Downstream | Layer 03 (`03_operational`) | Requires these IAM bindings to exist before the Cloud Function can read from the staging bucket and write to BigQuery |
| Downstream | `main.py` (Cloud Function) | The function's runtime SA (`bq_loader`) relies on the bucket and dataset IAM bindings created here |

## 4. Code Walkthrough

1. **Remote state data source (lines 11-17):** Reads Layer 01 outputs from the GCS backend at `terraform/state/phase3-static`.

2. **Locals (lines 22-30):** Defines `env_prefix` and `common_labels` with `layer = "first_time"`.

3. **BigQuery dataset IAM (lines 35-41):** Grants `bq_loader` SA the `bigquery.dataEditor` role scoped to the `github_archive` dataset. This supplements the project-level `bigquery.jobUser` from Layer 01.

4. **Storage Object Viewer (lines 49-54):** Grants `bq_loader` SA `storage.objectViewer` on the staging bucket so BigQuery load jobs can read source files.

5. **Storage Object Admin (lines 59-64):** Grants `bq_loader` SA `storage.objectAdmin` on the staging bucket so the Cloud Function can delete source files after successful loads (`DELETE_AFTER_LOAD`).

6. **Eventarc service agent viewer (lines 70-78):** Grants the Eventarc service agent (`service-{project_number}@gcp-sa-eventarc.iam.gserviceaccount.com`) `storage.objectViewer` on the staging bucket. Required for Eventarc to validate the bucket exists when the trigger is created in Layer 03.

7. **Notes (lines 80-82):** Comments explain that the Cloud Run IAM binding is intentionally deferred to Layer 03 because the Cloud Run service must exist first.
