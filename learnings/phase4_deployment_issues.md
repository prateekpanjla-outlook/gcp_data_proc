# Phase 4 Monitoring Dashboard — Deployment Issues

## Issue 1: Missing terraform config files

**Problem**: Phase 4 terraform layers had `main.tf` but no `terraform.tf`, `variables.tf`, or `outputs.tf` files. Terraform couldn't run without provider config and variable declarations.

**Fix**: Created `terraform.tf`, `variables.tf`, and `outputs.tf` for all 3 layers (01_static, 02_first_time, 03_operational).

## Issue 2: Naming convention not followed

**Problem**: Phase 4 resource names were not prefixed with the environment (test/prod), unlike Phases 1-3 which consistently use `${var.environment}-` prefix.

| Resource | Before | After |
|----------|--------|-------|
| BQ dataset | `pipeline_logs` | `${var.environment}_pipeline_logs` |
| Service account | `pipeline-dashboard` | `${var.environment}-pipeline-dashboard` |
| Log sink | `github-archive-pipeline-logs` | `${var.environment}-github-archive-pipeline-logs` |
| Cloud Run service | `github-archive-dashboard` | `${var.environment}-github-archive-dashboard` |

**Fix**: Added `var.environment` to all 3 layers and prefixed all GCP resource names.

## Issue 3: Cloud Build requires logs bucket with custom SA

**Problem**: `gcloud builds submit --service-account=...` fails with:
```
INVALID_ARGUMENT: if 'build.service_account' is specified, the build must either
(a) specify 'build.logs_bucket',
(b) use the REGIONAL_USER_OWNED_BUCKET build.options.default_logs_bucket_behavior option, or
(c) use either CLOUD_LOGGING_ONLY / NONE logging options
```

**Fix**: Added `--default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET` flag to `gcloud builds submit`.

## Issue 4: Terraform deployer SA missing logging.sinks.create permission

**Problem**: Log sink creation failed with `Permission 'logging.sinks.create' denied`. The terraform deployer SA had `roles/logging.logWriter` (write log entries) but not `roles/logging.admin` (manage sinks, metrics, views).

**Fix**: Granted `roles/logging.admin` to `test-terraform-deployer` SA:
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:test-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/logging.admin"
```

**Note**: This role should be added to the initial SA setup script so future environments don't hit this.

## Issue 5: GOOGLE_APPLICATION_CREDENTIALS path must be absolute

**Problem**: When running terraform with `-chdir`, relative paths like `infrastructure/test-terraform-deployer-key.json` resolve from the terraform layer directory, not the repo root. Terraform fails with "The system cannot find the path specified."

**Fix**: Use absolute path for the key file:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/c/Users/prateek/Desktop/gcp/gcp_data_processing/infrastructure/test-terraform-deployer-key.json"
```

## Issue 6: SQL queries hardcoded dataset name

**Problem**: All 4 SQL query files hardcoded `pipeline_logs` as the dataset name. After renaming to `test_pipeline_logs`, the dashboard hit 403 errors trying to query non-existent tables in the old dataset.

**Fix**: Replaced `pipeline_logs` with `DATASET_ID` placeholder in all SQL files. Updated `app.py` `_run_query()` to also replace `DATASET_ID` with the env var value (alongside existing `PROJECT_ID` replacement).

## Issue 7: Dashboard crashes when log tables don't exist yet

**Problem**: Log sink auto-creates BQ tables when logs first flow through. Tables like `run_googleapis_com_stdout` and `cloudfunctions_googleapis_com_cloud_functions` only appear after the pipeline has actually run. The dashboard crashed with 500 errors on first deploy because these tables didn't exist.

**Fix**: Added try/except in `_run_query()` — returns empty list `[]` on failure instead of crashing. Dashboard renders with empty tables until pipeline logs start flowing.

## Issue 8: Phase 2 logs go to stderr, not stdout

**Problem**: SQL queries referenced `run_googleapis_com_stdout` but Python's `logging` module writes to stderr by default. Phase 2 processing logs ("Completed ... in, ... out, ... errors") were in `run_googleapis_com_stderr`.

**Fix**: Changed `daily_throughput.sql` and `phase2_processing_summary.sql` to query `run_googleapis_com_stderr` instead.

## Issue 9: Phase 3 Cloud Function logs not in expected table

**Problem**: `phase3_bq_load_summary.sql` queried `cloudfunctions_googleapis_com_cloud_functions` but Cloud Functions 2nd gen runs on Cloud Run — logs appear as `resource.type="cloud_run_revision"` in `run_googleapis_com_*` tables, not in a separate cloud functions table. The bq-loader function also produced zero application-level logs (only Cloud Run infra logs).

**Fix**: Replaced the log-based Phase 3 query with `INFORMATION_SCHEMA.JOBS` query that reads BQ load job metadata directly. This is more reliable than parsing logs.

## Issue 10: Dashboard SA lacks permission for INFORMATION_SCHEMA.JOBS

**Problem**: Querying `region-us-central1.INFORMATION_SCHEMA.JOBS` requires `bigquery.jobs.list` permission. The dashboard SA only had `bigquery.jobUser` + `bigquery.dataViewer`, which is insufficient.

**Fix**: Granted `roles/bigquery.resourceViewer` to the dashboard SA at project level. Added to terraform Layer 02 (`google_project_iam_member.dashboard_bq_resource_viewer`).

## Issue 11: Dashboard SA lacks permission on github_archive dataset

**Problem**: Phase 3 dashboard query joins `INFORMATION_SCHEMA.JOBS` with `github_archive.github_events` for row counts. Dashboard SA only had `dataViewer` on `test_pipeline_logs`, not on `github_archive`.

**Fix**: Granted `roles/bigquery.dataViewer` on `github_archive` dataset to dashboard SA. Added to terraform Layer 02 (`google_bigquery_dataset_iam_member.dashboard_github_archive_viewer`).

## Issue 12: BQ dataset destroy fails — "dataset is still in use"

**Problem**: `terraform destroy` on Layer 01 fails with `Dataset test_pipeline_logs is still in use` because the log sink created tables inside the dataset. Terraform's default behavior is to refuse deleting a non-empty dataset.

**Fix**: Added `delete_contents_on_destroy = true` to the `google_bigquery_dataset.pipeline_logs` resource in Layer 01. This tells terraform to delete all tables first, then the dataset.

## Issue 13: Terraform tries to disable logging API on destroy

**Problem**: `terraform destroy` on Layer 02 fails trying to disable `logging.googleapis.com` because other active services (Cloud Build, Cloud Functions, Cloud Run) depend on it.

**Fix**: Added `disable_on_destroy = false` to the `google_project_service.logging` resource in Layer 02. The API stays enabled after destroy — it's a shared project-level service, not Phase 4 specific.

## Issue 14: Null provider lock file mismatch

**Problem**: After adding `null_resource.build_dashboard_image` to Layer 03, `terraform destroy` (and apply) fails with "provider registry.terraform.io/hashicorp/null: required by this configuration but no version is selected".

**Fix**: Run `terraform init -upgrade` before destroy/apply to pick up the `hashicorp/null` provider in the lock file. Only needed once after adding the null_resource.

### How `terraform init` and `-upgrade` work

Terraform uses a **two-file system** for provider management:

1. **`.terraform.lock.hcl`** (lock file) — Records the exact provider versions selected. Committed to version control. Ensures everyone uses the same provider versions (like `package-lock.json` in npm).

2. **`.terraform/` directory** — Contains the actual downloaded provider binaries. Not committed (like `node_modules/`).

**`terraform init`** does three things:
- Initializes the backend (local or remote state)
- Downloads providers listed in the lock file into `.terraform/`
- If no lock file exists, resolves versions from `required_providers` blocks and creates the lock file

**`terraform init -upgrade`** is needed when:
- You **add a new provider** (e.g., `hashicorp/null` for `null_resource`) — the lock file doesn't have it yet
- You **change version constraints** in `required_providers` — the lock file has an older version
- You want to **update providers** to newer versions within the constraint range

Without `-upgrade`, terraform refuses to use a provider not already in the lock file. This is a safety feature — it prevents accidental version changes. The `-upgrade` flag tells terraform "I know I changed the config, update the lock file to match."

**Rule of thumb**: Use `init` normally. Use `init -upgrade` when you've changed providers or added `null_resource` / `random` / other new provider-backed resources.

## Issue 15: Stale deleted SA blocks dataset IAM update

**Problem**: After destroying and recreating Phase 4, the old dashboard SA (`test-pipeline-dashboard`) was deleted and recreated with a new UID. But the `github_archive` dataset still had a stale IAM entry referencing `deleted:serviceAccount:test-pipeline-dashboard@...?uid=OLD_UID`. Terraform's `google_bigquery_dataset_iam_member` fails with "member is of an unknown type" because BQ rejects IAM updates when stale deleted members exist.

**Fix**: Remove the stale entry before re-applying terraform:
```sql
REVOKE `roles/bigquery.dataViewer`
ON SCHEMA `PROJECT_ID.github_archive`
FROM "deleted:serviceAccount:SA_EMAIL?uid=OLD_UID"
```

**Prevention**: This happens whenever a SA is destroyed and recreated while it has dataset-level IAM bindings in other datasets (outside its own terraform state). Consider using project-level IAM (`google_project_iam_member`) instead of dataset-level IAM for cross-phase access, as project-level bindings auto-clean stale members.

**Note**: Terraform cannot clean stale deleted SAs automatically. BQ dataset IAM is the most common place this occurs because dataset-level bindings persist independently of the SA lifecycle.

## Issue 16: pip "Running as root" warning during Docker build

**Problem**: Cloud Build output shows `WARNING: Running pip as the 'root' user can result in broken permissions...` during Docker image build. This is normal in Docker containers where everything runs as root during build, but clutters the build output.

**Fix**: Added `--root-user-action=ignore` to the pip install command in the Dockerfile:
```dockerfile
RUN pip install --no-cache-dir --root-user-action=ignore -r requirements.txt
```

## Deployment Order

Phase 4 requires this sequence:
1. Layer 01 (static) — BQ dataset + dashboard SA
2. Layer 02 (first-time) — IAM grants for dashboard SA
3. Layer 03 (operational) — Cloud Build (via null_resource) + log sink + Cloud Run dashboard service

Note: Cloud Build step is now automated in Layer 03 via `null_resource.build_dashboard_image` with `--default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET`.
