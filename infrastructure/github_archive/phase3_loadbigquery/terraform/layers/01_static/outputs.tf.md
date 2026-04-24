# outputs.tf

## 1. Overview

Terraform outputs for Phase 3 Layer 01 (Static). Exports five values that downstream layers (02_first_time and 03_operational) consume via `terraform_remote_state` data sources. These outputs expose the BigQuery dataset/table IDs and the two service account emails created in this layer.

## 2. Prerequisites

- **Layer 01 applied successfully:** All resources in `main.tf` must exist (dataset, table, service accounts) before outputs are populated
- **Remote state backend:** Outputs are stored in the GCS state at `terraform/state/phase3-static`

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | `main.tf` (same layer) | Output values reference `google_bigquery_dataset.github_archive`, `google_bigquery_table.github_events`, `google_service_account.bq_loader`, `google_service_account.eventarc_invoker` |
| Downstream | Layer 02 `main.tf` | Reads `service_account_email_bq_loader` for dataset-level and bucket-level IAM bindings |
| Downstream | Layer 03 `main.tf` | Reads both SA emails to configure the Cloud Function runtime SA and Eventarc trigger SA |

## 4. Code Walkthrough

1. **`dataset_id`** -- The BigQuery dataset ID (`github_archive`). Used by downstream layers for IAM bindings and function env vars.

2. **`dataset_name`** -- The dataset's friendly name (`GitHub Archive Events`). Informational output.

3. **`table_id`** -- The BigQuery table ID (`github_events`). Used by downstream layers for function env vars.

4. **`service_account_email_bq_loader`** -- Email of the `bq_loader` SA. Consumed by Layers 02 and 03 for IAM bindings (Storage, BigQuery, Artifact Registry) and as the Cloud Function runtime SA.

5. **`service_account_email_eventarc_invoker`** -- Email of the `eventarc_invoker` SA. Consumed by Layer 03 to configure the Eventarc trigger's authentication identity.
