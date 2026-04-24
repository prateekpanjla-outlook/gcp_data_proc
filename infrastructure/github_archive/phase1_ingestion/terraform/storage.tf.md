# storage.tf

## 1. Overview

Creates the GCS landing bucket where raw GitHub Archive `.json.gz` files are deposited by the Phase 1 Cloud Run Job. This bucket is the handoff point between Phase 1 (ingestion) and Phase 2 (processing), which watches it via Eventarc for new object notifications.

## 2. Prerequisites

- `var.project_id`, `var.region`, `var.environment`, `var.force_destroy`, and `var.bucket_lifecycle_days` must be set.
- `locals.tf` must define `local.github_archive.bucket_name`.
- The Cloud Storage API must be enabled on the project.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `variables.tf` | `project_id`, `region`, `environment`, `force_destroy`, `bucket_lifecycle_days` |
| Upstream | `locals.tf` | `local.github_archive.bucket_name` (naming convention) |
| Downstream | `cloud_run_jobs.tf` | The bucket name is passed as the `BUCKET_NAME` env var to the Cloud Run Job |
| Downstream | Phase 2 Eventarc | Phase 2 creates an Eventarc trigger that fires on `google.cloud.storage.object.v1.finalized` events on this bucket |

## 4. Code Walkthrough

1. **`google_storage_bucket.github_archive_landing`** -- Creates a regional GCS bucket named `{project_id}-{env}-github-archive-landing`.

2. **`force_destroy`** -- Automatically set to `true` in `dev` environment; otherwise uses the `var.force_destroy` variable. This allows `terraform destroy` to delete the bucket even when it contains objects.

3. **`uniform_bucket_level_access`** -- Enabled (`true`), which disables per-object ACLs and enforces IAM-only access control.

4. **`lifecycle_rule`** -- Deletes objects older than `var.bucket_lifecycle_days` (default 6 days). This keeps the landing bucket lean since Phase 2 processes files shortly after arrival.

5. **`labels`** -- Tags the bucket with `environment`, `source`, `layer`, `phase`, and `managed_by` for cost tracking and resource inventory.
