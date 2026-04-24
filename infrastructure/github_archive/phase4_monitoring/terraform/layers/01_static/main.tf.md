## 1. Overview

`main.tf` (Layer 01: Static) creates the foundational, long-lived resources for Phase 4 monitoring: a BigQuery dataset for Cloud Logging exports and a service account for the dashboard Cloud Run service. These resources are created once and rarely change.

## 2. Prerequisites

- **Terraform** installed and initialised in this layer directory.
- **GCP project** with BigQuery API enabled.
- **Terraform variables**:
  - `var.project_id` -- GCP project ID.
  - `var.region` -- GCP region for the BQ dataset location.
  - `var.environment` -- environment prefix (e.g., `dev`, `prod`) used in resource naming.
- Phases 1-3 must already be deployed (this is Phase 4).

## 3. Upstream & Downstream Dependencies

**Upstream (what must exist before this layer)**:
- The GCP project with BigQuery API enabled.
- Phases 1-3 deployed (the log sink in Layer 03 will export their logs).

**Downstream (what depends on this layer's outputs)**:
- `02_first_time/main.tf` -- references `var.dashboard_sa_email` (the SA created here) and `var.pipeline_logs_dataset_id` (the dataset created here) to grant IAM permissions.
- `03_operational/main.tf` -- references the SA email for the Cloud Run service account and the dataset ID for the log sink destination.

## 4. IAM & Service Accounts

- **`{env}-pipeline-dashboard` SA** — created in this layer as `google_service_account.dashboard`. Used by the Cloud Run dashboard service to authenticate BigQuery queries.
  - This SA does NOT serve as the log sink writer identity — GCP auto-generates a separate writer identity for log sinks.
  - IAM roles are granted in Layer 02, not here, because the SA must exist before permissions can be bound.
- **Cross-reference:** `learnings/phase4_deployment_issues.md`:
  - Issue 15 — when this SA is destroyed and recreated, stale `deleted:serviceAccount:` entries appear in the `github_archive` dataset IAM. Layer 02 includes a cleanup step for this.

## 5. Code Walkthrough

1. **`google_bigquery_dataset.pipeline_logs` (lines 4-16)**: Creates a BigQuery dataset named `{env}_pipeline_logs`. Key settings:
   - `default_table_expiration_ms = 7776000000` -- 90-day TTL for all tables. Log data is transient and does not need permanent retention.
   - `delete_contents_on_destroy = true` -- allows `terraform destroy` to delete the dataset even when it contains tables (created automatically by the log sink).

2. **`google_service_account.dashboard` (lines 20-24)**: Creates the dashboard service account with ID `{env}-pipeline-dashboard`. This SA is used by the Cloud Run dashboard service to authenticate BigQuery queries. A comment notes this SA is NOT used for the log sink writer identity -- GCP auto-generates a separate writer identity for log sinks.
