# main.tf

## 1. Overview

Terraform Layer 01 (Static) main configuration for Phase 3. Provisions long-lived resources that rarely change after initial deployment: GCP API enablement, the BigQuery dataset and `github_events` table, two service accounts (`bq_loader` and `eventarc_invoker`), and all associated IAM bindings. This is the foundational layer that Layers 02 and 03 depend on via remote state.

## 2. Prerequisites

- **Terraform:** >= 1.5 with Google provider ~> 5.0
- **GCP Project:** Must exist with billing enabled
- **Terraform Deployer SA:** `${environment}-terraform-deployer@${project_id}.iam.gserviceaccount.com` must exist with permissions to create service accounts, enable APIs, manage IAM, and create BigQuery resources
- **Remote State Bucket:** `beaming-glyph-489707-b8-terraform-state` must exist (configured in `terraform.tf`)
- **Input Variables:** `project_id`, `environment` (required); `region`, `dataset_id`, `table_id`, `partition_expiration_days` (have defaults)
- **Schema File:** `schema.json` must be present alongside this file

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Phase 2 infrastructure | Provides the GCS staging bucket that Phase 3 reads from |
| Downstream | Layer 02 (`02_first_time`) | Reads `service_account_email_bq_loader` and `service_account_email_eventarc_invoker` outputs via remote state |
| Downstream | Layer 03 (`03_operational`) | Reads the same outputs to configure the Cloud Function runtime SA and Eventarc trigger SA |
| Downstream | `elt.tf` (same layer) | References `google_bigquery_dataset.github_archive` and `google_bigquery_table.github_events` for ELT views and materialized views |
| Downstream | `main.py` | The Cloud Function writes to the BigQuery table created here |

## 4. Code Walkthrough

1. **Locals (lines 8-22):** Defines `env_prefix`, a `phase3_resources` map for service account IDs, and `common_labels` applied to all resources.

2. **API Enablement (lines 27-46):** Enables `bigquery.googleapis.com`, `cloudfunctions.googleapis.com`, and `bigquerydatatransfer.googleapis.com`. All use `disable_on_destroy = false` to avoid disrupting other consumers.

3. **BigQuery Dataset (lines 51-63):** Creates the `github_archive` dataset with day-level partition expiration derived from `var.partition_expiration_days`. Allows content deletion on destroy only in `dev`/`test` environments.

4. **BigQuery Table (lines 68-88):** Creates `github_events` with DAY partitioning on `created_at`, clustering on `event_type`, and schema loaded from `schema.json`.

5. **Service Accounts (lines 93-108):** Creates two SAs -- `bq_loader` (runs the Cloud Function) and `eventarc_invoker` (authenticates Eventarc trigger delivery).

6. **IAM -- BigQuery (lines 113-125):** Grants `bq_loader` the `bigquery.dataEditor` and `bigquery.jobUser` project-level roles so it can run load jobs and write to tables.

7. **IAM -- Logging/Monitoring (lines 130-146):** Grants both SAs `logging.logWriter` and `bq_loader` gets `monitoring.metricWriter`.

8. **IAM -- Eventarc (lines 151-155):** Grants `eventarc_invoker` the `eventarc.eventReceiver` role for receiving Cloud Storage events.

9. **IAM -- actAs (lines 160-173):** Grants the Terraform deployer SA `iam.serviceAccountUser` on both SAs, required for attaching them to Cloud Function and Eventarc resources during deployment.

10. **IAM -- Pub/Sub Token Creator (lines 178-183):** Grants the Pub/Sub service agent `iam.serviceAccountTokenCreator` on `eventarc_invoker` so Pub/Sub can mint OIDC tokens when delivering events.
