## 1. Overview

`main.tf` (Layer 02: First-time Setup) grants the dashboard service account the IAM permissions it needs to query BigQuery. It also handles cleanup of stale SA bindings that can occur when Phase 4 is destroyed and recreated, and verifies IAM propagation before proceeding.

## 2. Prerequisites

- **Layer 01 (Static)** must be applied first -- the dashboard SA and `pipeline_logs` dataset must exist.
- **Phase 3** must be deployed -- the `github_archive` dataset must exist for the cross-dataset viewer grant.
- **Terraform variables**:
  - `var.project_id` -- GCP project ID.
  - `var.dashboard_sa_email` -- email of the dashboard SA (output from Layer 01).
  - `var.pipeline_logs_dataset_id` -- dataset ID from Layer 01.
- **`bq` CLI** must be available for the stale SA cleanup script.
- **`gcloud` CLI** must be available for the IAM verification script (SA impersonation).

## 3. Upstream & Downstream Dependencies

**Upstream (what must exist before this layer)**:
- `01_static/main.tf` -- provides the dashboard SA and pipeline_logs dataset.
- Phase 3 `01_static/main.tf` -- provides the `github_archive` dataset.

**Downstream (what depends on this layer)**:
- `03_operational/main.tf` -- the Cloud Run service needs IAM permissions to be in place before it can successfully query BigQuery.

## 4. IAM & Service Accounts

This layer grants all IAM permissions needed by the `{env}-pipeline-dashboard` SA (created in Layer 01):

- **Project-level roles:**
  - `roles/bigquery.jobUser` — run BigQuery queries.
  - `roles/bigquery.resourceViewer` — query `INFORMATION_SCHEMA.JOBS` for load job metadata.
- **Dataset-level roles:**
  - `roles/bigquery.dataViewer` on `pipeline_logs` — read Cloud Logging export tables.
  - `roles/bigquery.dataViewer` on `github_archive` — read `github_events`, ELT views, and materialized views (cross-phase access).
- **Stale SA cleanup:** `null_resource.cleanup_stale_sa_bindings` removes `deleted:serviceAccount:` entries from the `github_archive` dataset IAM that accumulate after Phase 4 destroy/recreate cycles. Without this cleanup, Terraform's `google_bigquery_dataset_iam_member` fails with "member is of an unknown type".
- **IAM verification:** `null_resource.verify_dashboard_iam` polls to confirm the SA can actually access `github_archive` after granting, accounting for IAM propagation delay.
- **Cross-reference:** `learnings/phase4_deployment_issues.md`:
  - Issue 10 — `bigquery.resourceViewer` was added here after discovering `INFORMATION_SCHEMA.JOBS` queries failed without it.
  - Issue 11 — `dataViewer` on `github_archive` was added here after the dashboard could not read Phase 3 data.
  - Issue 15 — stale SA cleanup was added here to handle destroy/recreate IAM conflicts.

## 5. Code Walkthrough

1. **Commented-out `logging.googleapis.com` (lines 4-11)**: The logging API resource is intentionally not managed here. A comment explains that `logging.googleapis.com` is always enabled by default and managing it causes stale state issues on destroy.

2. **`google_project_iam_member.dashboard_bq_job_user` (lines 14-18)**: Grants `roles/bigquery.jobUser` at the project level, allowing the dashboard SA to run BigQuery queries.

3. **`google_bigquery_dataset_iam_member.dashboard_data_viewer` (lines 20-25)**: Grants `roles/bigquery.dataViewer` on the `pipeline_logs` dataset so the dashboard can read log sink export tables.

4. **`null_resource.cleanup_stale_sa_bindings` (lines 30-53)**: Runs on every apply (`triggers = { always_run = timestamp() }`). Uses `bq show` to check for `deleted:serviceAccount:...` entries in the `github_archive` dataset IAM, which appear after a Phase 4 destroy/recreate cycle. If found, issues a `REVOKE` DDL statement to remove the stale binding. This prevents IAM conflicts when re-granting access.

5. **`google_bigquery_dataset_iam_member.dashboard_github_archive_viewer` (lines 56-63)**: Grants `roles/bigquery.dataViewer` on the `github_archive` dataset (Phase 3). Depends on the stale SA cleanup to avoid conflicts. This allows the dashboard to read `github_events` and ELT views.

6. **`null_resource.verify_dashboard_iam` (lines 66-104)**: Polls up to 6 times (10-second intervals) to verify the dashboard SA can actually access the `github_archive` dataset. Uses SA impersonation to get a token and tests with a BigQuery API call. Exits successfully even on timeout (warning only) to avoid blocking the deployment.

7. **`google_project_iam_member.dashboard_bq_resource_viewer` (lines 107-111)**: Grants `roles/bigquery.resourceViewer` at the project level, required for querying `INFORMATION_SCHEMA.JOBS` in `phase3_bq_load_summary.sql`.
