# Phase 3: Test Project Deployment Errors

**Date:** 2026-03-13
**Project:** beaming-glyph-489707-b8 (test)

---

## Error 25: Missing schema.json for BigQuery Table

**Error Message:**
```
Error: Invalid function argument
  on main.tf line 60:
  60:   schema = file("${path.module}/schema.json")
File not found: schema.json
```

**Root Cause:**
Layer 01 references `file("${path.module}/schema.json")` for the BigQuery table schema, but the file was never created. The schema definition exists only in Python (`src/github_archive/schemas.py`).

**Fix:**
Generated `schema.json` from the Python `get_github_events_schema()` function. The JSON schema must use BigQuery JSON format with `name`, `type`, `mode`, and `description` fields. Key requirement: `created_at` must be `TIMESTAMP` type (not `STRING`) for DAY partitioning.

---

## Error 26: Provider Version ~> 7.0 Lock File Conflict

**Error Message:**
```
Error: Failed to query available provider packages
locked provider registry.terraform.io/hashicorp/google 7.22.0 does not match
configured version constraint ~> 5.0; must use terraform init -upgrade
```

**Root Cause:**
Phase 3 Terraform was written for provider `~> 7.0` but the test project uses `~> 5.0` (v5.45.2). The `.terraform.lock.hcl` file locked v7.22.0.

**Fix:**
1. Changed provider constraint from `~> 7.0` to `~> 5.0` in all 3 layers
2. Ran `terraform init -upgrade` to download v5.45.2

**Workaround for DNS failures:**
When `registry.terraform.io` DNS fails, copy the lock file from a layer that already initialized and use `-plugin-dir`:
```bash
cp ../01_static/.terraform.lock.hcl .
terraform init -plugin-dir=../01_static/.terraform/providers
```

---

## Error 27: Environment Validation Missing "test"

**Error Message:**
```
Error: Invalid value for variable
Environment must be dev or prod
```

**Root Cause:**
Layer 01 `variables.tf` only allowed `["dev", "prod"]` for the environment variable.

**Fix:**
```hcl
condition = contains(["dev", "test", "prod"], var.environment)
```

---

## Error 28: Cloud Function Using Wrong Event Format (1st gen vs 2nd gen)

**Root Cause:**
The Cloud Function `main.py` used the 1st gen background function signature:
```python
def load_to_bigquery(data, context):
    context.event_id  # 1st gen only
    data.get("bucket")  # works in both, but context doesn't exist in 2nd gen
```

Cloud Functions 2nd gen uses **CloudEvents** format, not the legacy `(data, context)` format.

**Fix:**
```python
import functions_framework
from cloudevents.http import CloudEvent

@functions_framework.cloud_event
def load_to_bigquery(cloud_event: CloudEvent):
    data = cloud_event.data
    bucket_name = data.get("bucket")
    file_name = data.get("name")
    # Event metadata via cloud_event["id"], cloud_event["type"]
```

**Key Differences:**
| Aspect | 1st Gen | 2nd Gen |
|--------|---------|---------|
| Signature | `def fn(data, context)` | `@cloud_event def fn(cloud_event)` |
| Event data | `data` parameter directly | `cloud_event.data` |
| Event ID | `context.event_id` | `cloud_event["id"]` |
| Event type | `context.event_type` | `cloud_event["type"]` |
| Decorator | None needed | `@functions_framework.cloud_event` |
| Dependencies | None extra | `functions-framework`, `cloudevents` |

---

## Error 29: CloudEvents Dependency Pinning

**Error Message (from learnings):**
```
Build failed: found incompatible dependencies:
"functions-framework 3.9.1 has requirement cloudevents<=1.11.0,>=1.2.0,
but you have cloudevents 1.12.0."
```

**Root Cause:**
The `cloudevents` package must be pinned to a version compatible with `functions-framework`.

**Fix:**
```txt
functions-framework>=3.0.0
cloudevents>=1.2.0,<=1.11.0
google-cloud-bigquery>=3.0.0
google-cloud-storage>=2.0.0
```

---

## Error 30: Relative Path Depth Wrong for Layered Terraform

**Error Message:**
```
Error: Error in function call
  on main.tf line 98:
  98:   name = "function-source-${filemd5("${path.module}/../../../../src/...")}.zip"
Call to function "filemd5" failed: open ..\..\..\..\src\...: The system cannot find the path specified.
```

**Root Cause:**
The source code path used `../../../../` (4 levels up) but the actual directory structure is:
```
03_operational/ → layers/ → terraform/ → phase3_loadbigquery/ → github_archive/ → infrastructure/ → (root)
```
That's **6 levels**, not 4.

**Fix:**
```hcl
# Wrong: 4 levels
${path.module}/../../../../src/github_archive/phase3_loadbigquery

# Correct: 6 levels
${path.module}/../../../../../../src/github_archive/phase3_loadbigquery
```

**Lesson:** Always count directory levels carefully when using layered Terraform structures.

---

## Error 31: Cloud Functions Build Fails — AR Permission Denied

**Error Message:**
```
ERROR: failed to create image cache: accessing cache image
"us-central1-docker.pkg.dev/PROJECT/gcf-artifacts/.../cache:latest":
DENIED: Permission 'artifactregistry.repositories.downloadArtifacts'
denied on resource (or it may not exist).
```

**Root Cause:**
Cloud Functions 2nd gen uses Cloud Build internally to build the function container. By default, it uses the **Compute Engine default service account** (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`) as the build service account. This SA doesn't have `artifactregistry.writer` permission on the `gcf-artifacts` Artifact Registry repository.

**Wrong approach:** Granting AR permissions to the default compute SA or the `gcf-admin-robot` SA.

**Correct Fix:**
Specify the Phase 1 Cloud Build SA (which already has `artifactregistry.writer` and `storage.objectAdmin`) as the build service account:

```hcl
build_config {
  runtime         = "python311"
  entry_point     = "load_to_bigquery"
  # Use Phase 1 cloud-build SA instead of default compute SA
  service_account = "projects/${var.project_id}/serviceAccounts/${var.environment}-cloud-build@${var.project_id}.iam.gserviceaccount.com"
  # ...
}
```

**Key Insight:**
The `service_account` in `build_config` requires the **full resource name** format:
`projects/PROJECT_ID/serviceAccounts/SA_EMAIL`

Not just the email address.

**Cloud Build SA roles needed for CF 2nd gen builds:**
- `roles/artifactregistry.writer` — push built images to gcf-artifacts
- `roles/storage.objectAdmin` — read source code, write build logs
- `roles/cloudbuild.builds.builder` — (optional, redundant if above roles exist)
- `roles/iam.serviceAccountUser` — for terraform deployer to act as this SA

---

## Error 32: Duplicate IAM Binding Across Layers

**Root Cause:**
`roles/bigquery.jobUser` was granted to `bq_loader` SA in both Layer 01 (`google_project_iam_member.bq_loader_job_user`) and Layer 02 (same resource name). While Terraform doesn't error on duplicate project-level IAM bindings (they're idempotent), it creates unnecessary state entries.

**Fix:**
Removed the duplicate from Layer 02 since it was already defined in Layer 01.

---

## Error 33: Missing API Enablement (BigQuery, Cloud Functions)

**Root Cause:**
Phase 1 and 2 enabled `cloudbuild`, `eventarc`, `run`, `storage`, `pubsub` APIs. Phase 3 additionally needs:
- `bigquery.googleapis.com` — for BigQuery dataset/table creation
- `cloudfunctions.googleapis.com` — for Cloud Functions 2nd gen

These were not in any Phase 3 Terraform layer.

**Fix:**
Added to Layer 01:
```hcl
resource "google_project_service" "bigquery" {
  project            = var.project_id
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudfunctions" {
  project            = var.project_id
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}
```

BigQuery dataset depends on the API: `depends_on = [google_project_service.bigquery]`

---

## Error 34: Missing Eventarc SA Bucket Permission

**Error Message (from Phase 3 learnings):**
```
Permission "storage.buckets.get" denied on "Bucket"
```

**Root Cause:**
Eventarc service agent needs `roles/storage.objectViewer` on the staging bucket to validate the bucket when creating a trigger. This was documented in the learnings but not codified in Terraform.

**Fix:**
Added to Layer 02:
```hcl
resource "google_storage_bucket_iam_member" "eventarc_sa_staging_viewer" {
  bucket = var.staging_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}
```

---

## Error 35: Missing Pub/Sub SA Token Creator

**Root Cause:**
Same as Phase 2 Error 18 — Pub/Sub SA needs `serviceAccountTokenCreator` on the eventarc_invoker SA to generate OIDC tokens when delivering events.

**Fix:**
Added to Layer 01:
```hcl
resource "google_service_account_iam_member" "pubsub_token_creator_eventarc_invoker" {
  service_account_id = google_service_account.eventarc_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
```

---

## Error 36: BQ Load Failed — Schema Generated from Wrong Source

**Error Message:**
```
google.api_core.exceptions.BadRequest: 400 JSON parsing error in row starting at position 0:
Missing required fields: ingestion_timestamp, processed_at.
```

**Root Cause:**
`schema.json` was generated from `src/github_archive/schemas.py` (an outdated/incorrect schema file) instead of the actual Phase 2 processor schema in `src/github_archive/phase2_process_files/schemas/dtype_definitions.py`.

The wrong schema had:
- 3 REQUIRED fields (`event_id`, `event_type`, `created_at`) — actual data has all NULLABLE
- Wrong field names: `ref` instead of `payload_ref`, `push_size` instead of `payload_size`, etc.
- Phantom fields not in data: `org_*`, `payload` (JSON), `action`, `pr_*`, `issue_*`, `release_*`, `ingestion_timestamp`, `processed_at`
- Missing fields: `actor_type`, `actor_site_admin`, `payload_push_id`, `payload_issue_labels` (RECORD/REPEATED), `etl_create_ts`, `etl_create_id`

**Fix:**
1. Updated `dtype_definitions.py`: `created_at` from `STRING` → `TIMESTAMP`, added `etl_create_ts` and `etl_create_id`
2. Regenerated `schema.json` from actual dev BQ schema (`bq show --schema`) — 25 fields, all NULLABLE
3. Applied Layer 01 terraform to recreate BQ table with correct schema

**Key Lesson:**
Always verify schema source against the actual data pipeline output. The Phase 2 processor's `dtype_definitions.py` (and the dev BQ table) is the source of truth, NOT `schemas.py`.

**Result after fix:** Eventarc retries automatically loaded 350,486 rows successfully.

---

## Deployment Summary

### Layer 01 (Static): Attempt 1 — SUCCESS
- **Plan:** 15 to add
- **Apply:** 15 added, 0 changed, 0 destroyed
- Resources: 2 APIs, 1 BQ dataset, 1 BQ table, 2 SAs, 5 project IAM, 3 SA IAM, 1 data source

### Layer 02 (First-time): Attempt 1 — SUCCESS
- **Plan:** 4 to add
- **Apply:** 4 added, 0 changed, 0 destroyed
- Resources: 1 dataset IAM, 2 bucket IAM (bq_loader), 1 bucket IAM (eventarc SA)

### Layer 03 (Operational): Attempt 1 — FAILED (Error 31: AR permission)
- **Plan:** 6 to add
- **Apply:** 5 created, 1 failed (Cloud Function build failed)

### Layer 03 (Operational): Attempt 2 — SUCCESS
- **Plan:** 2 to add, 1 to destroy (replace failed function)
- **Apply:** 2 added, 0 changed, 1 destroyed
- Resources: 1 Cloud Function (ACTIVE), 1 IAM (cloud_build_builder)

### Final Resource Count
| Layer | Resources |
|-------|-----------|
| Layer 01 | 15 resources + 1 data source |
| Layer 02 | 4 resources + 2 data sources |
| Layer 03 | 7 resources + 4 data sources |
| **Total** | **26 resources + 7 data sources = 33 entries** |

### End-to-End Flow
```
Phase 2 Cloud Run processor
  → writes .ndjson.gz to staging bucket (processed/ prefix)
    → Eventarc detects new file
      → triggers Cloud Function (test-bq-loader)
        → BigQuery load job
          → data in github_archive.github_events table
```

### Function Details
- **Name:** test-bq-loader
- **State:** ACTIVE
- **URI:** https://test-bq-loader-iu6epaogwa-uc.a.run.app
- **Runtime:** Python 3.11
- **Entry point:** load_to_bigquery
- **Service Account:** test-bq-loader@beaming-glyph-489707-b8.iam.gserviceaccount.com
- **Build SA:** test-cloud-build@beaming-glyph-489707-b8.iam.gserviceaccount.com
- **Trigger:** GCS object finalized on staging bucket
