# Phase 1 Deployment Issues and Fixes

This document captures all issues encountered during Phase 1 GitHub Archive Ingestion deployment and their fixes.

## Summary

Deployed Phase 1 in 3 layers: Foundation → Compute → Automation. Each layer revealed schema and configuration issues that required fixes.

---

## Issue 1: Terraform Schema Errors in `google_cloud_run_v2_job`

### Error Messages

```
Error: Unsupported argument
  on cloud_run_jobs.tf line 45:
  45: service_account_name = google_service_account.github_archive_downloader.email
  An argument named "service_account_name" is not expected here.

Error: Unsupported argument
  on cloud_run_jobs.tf line 48:
  48: timeout_seconds = 1800
  An argument named "timeout_seconds" is not expected here.
```

### Root Cause

Terraform Google provider v7.x uses different argument names than older versions for Cloud Run v2 Job resources.

### Fix

| Incorrect | Correct |
|-----------|---------|
| `service_account_name` | `service_account` |
| `timeout_seconds = 1800` | `timeout = "1800s"` |

**Fixed in:** [`cloud_run_jobs.tf:45-48`](infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf)

---

## Issue 2: Terraform Schema Error in `google_cloud_run_v2_job_iam_member`

### Error Message

```
Error: Unsupported argument
  on scheduler.tf line 40:
  40: job_name = google_cloud_run_v2_job.github_archive_downloader.name
  An argument named "job_name" is not expected here.

Error: Missing required argument
  on scheduler.tf line 36:
  36: resource "google_cloud_run_v2_job_iam_member" "scheduler_github_invoker" {
  The argument "name" is required, but no definition was found.
```

### Root Cause

The `google_cloud_run_v2_job_iam_member` resource uses `name` for the job name (the resource being bound), not `job_name`.

### Fix

```hcl
# BEFORE (wrong)
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_invoker" {
  name     = "scheduler-github-invoker"  # This was the resource name
  job_name = google_cloud_run_v2_job.github_archive_downloader.name  # Wrong
  ...
}

# AFTER (correct)
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_invoker" {
  name     = google_cloud_run_v2_job.github_archive_downloader.name  # Job name
  ...
}
```

**Verified via:** Terraform MCP Google provider docs for `cloud_run_v2_job_iam`

**Fixed in:** [`scheduler.tf:36-42`](infrastructure/phase1_ingestion/terraform/scheduler.tf)

---

## Issue 3: Terraform Schema Error in `google_cloud_scheduler_job` retry_config

### Error Message

```
Error: Unsupported argument
  on scheduler.tf line 25:
  25: min_backoff = "10s"
  An argument named "min_backoff" is not expected here.
```

### Root Cause

Cloud Scheduler's `retry_config` block uses `min_backoff_duration` not `min_backoff`.

### Fix

| Incorrect | Correct |
|-----------|---------|
| `min_backoff = "10s"` | `min_backoff_duration = "10s"` |

**Fixed in:** [`scheduler.tf:23-26`](infrastructure/phase1_ingestion/terraform/scheduler.tf)

---

## Issue 4: Cloud Run v2 Memory Requirement

### Error Message

```
Error: Error creating Job: googleapi: Error 400: template.template.containers[0].limits.memory:
Invalid value specified for memory. Total memory < 512 Mi is not supported with gen2
execution environment with cpu always allocated (unthrottled).
```

### Root Cause

Cloud Run v2 (gen2 execution environment) requires **minimum 512Mi memory** when CPU is allocated (unthrottled).

### Fix

| Incorrect | Correct |
|-----------|---------|
| `memory = "256Mi"` | `memory = "512Mi"` |

**Verified via:** Terraform MCP Google provider docs for `cloud_run_v2_job`

**Fixed in:** [`cloud_run_jobs.tf:37-41`](infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf)

---

## Issue 5: gsutil Does Not Support HTTP/HTTPS URLs

### Error Message

```
InvalidUrlError: Unrecognized scheme "https".
```

### Root Cause

**gsutil `cp` command only supports:**
- `gs://` URLs for Cloud Storage resources
- Local file paths

**gsutil does NOT support:**
- `http://` URLs
- `https://` URLs

This is by design - gsutil is a Cloud Storage-specific tool.

### Verification

```bash
$ gsutil cp "https://data.gharchive.org/2026-03-05-12.json.gz" /tmp/test.json.gz
InvalidUrlError: Unrecognized scheme "https".

$ gsutil cp "http://data.gharchive.org/2026-03-05-12.json.gz" /tmp/test.json.gz
InvalidUrlError: Unrecognized scheme "http".
```

### Fix

Use `curl` for HTTP download, pipe to `gsutil cp` for GCS upload:

```bash
# WRONG
gsutil cp "https://data.gharchive.org/2026-03-05-12.json.gz" "gs://bucket/file.json.gz"

# CORRECT - streaming without temp file
curl -fsSL "${SOURCE_URL}" | gsutil cp - "${TARGET_PATH}"
```

**Verified via:** Google Cloud Storage documentation - "The input must be a list of **local file paths or Cloud Storage object URLs**"

**Fixed in:** [`download.sh:169`](src/github_archive/phase1_ingestion/scripts/download.sh)

---

## Issue 6: Deployment Script Target Flag Syntax

### Error Message

```
Error: Too many command line arguments
```

### Root Cause

When passing multiple targets to Terraform, each target needs its own `-target=` flag. The script was passing space-separated targets after a single `-target=`.

### Fix

```bash
# BEFORE (wrong)
-target=resource1 resource2 resource3

# AFTER (correct)
-target=resource1 -target=resource2 -target=resource3
```

**Fixed in:** [`phase1_deploy_layered.sh:181-185`](infrastructure/scripts/phase1_deploy_layered.sh)

---

## Deployment Script Target Flag Fix

### The Problem

The deployment script used a single `-target=` flag with multiple space-separated resources:

```bash
-target=$targets  # Where targets="resource1 resource2 resource3"
```

This caused Terraform to interpret subsequent resources as positional arguments.

### The Solution

Build individual `-target=` flags for each resource:

```bash
# Build target flags for each resource
target_flags=""
for target in $targets; do
  target_flags="$target_flags -target=$target"
done

terraform plan ... $target_flags
```

**Fixed in:** [`phase1_deploy_layered.sh:181-192`](infrastructure/scripts/phase1_deploy_layered.sh)

---

## Issue 7: Cloud Scheduler 401 UNAUTHENTICATED - OIDC vs OAuth

### Error Message

```
jsonPayload.status: UNAUTHENTICATED
httpRequest.status: 401
debugInfo: URL_ERROR-ERROR_AUTHENTICATION. Original HTTP response code number = 401
```

### Root Cause

**Using OIDC tokens to call a Google API endpoint (`*.googleapis.com`).**

The Cloud Run **Jobs API** endpoint is:
```
https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/...
```

This is a **Google API endpoint** (`*.googleapis.com`), which only accepts **OAuth tokens**, not OIDC tokens.

### Token Type Guide

| Token Type | Use Case | Target URL Pattern |
|------------|----------|-------------------|
| **OAuth Token** | Google APIs (`*.googleapis.com`) | `https://*.googleapis.com/...` |
| **OIDC Token** | Cloud Run services, external endpoints | `https://*.a.run.app`, external APIs |

### Fix

Changed from `oidc_token` to `oauth_token` in the Cloud Scheduler job:

```hcl
# BEFORE (401 error)
http_target {
  oidc_token {
    service_account_email = google_service_account.scheduler.email
  }
}

# AFTER (works correctly)
http_target {
  oauth_token {
    service_account_email = google_service_account.scheduler.email
  }
}
```

**Verified via:**
- Terraform MCP provider docs for `google_cloud_scheduler_job`
- Google Cloud documentation: "OIDC is generally used **except for Google APIs hosted on `*.googleapis.com`** as these APIs expect an **OAuth token**."

**Additional Permissions Required:**

1. **Cloud Scheduler Service Agent** - Granted `roles/cloudscheduler.serviceAgent` at project level
2. **Scheduler Service Account** - Granted `roles/run.invoker` at project level
3. **Service Account Token Creator** - Granted `roles/iam.serviceAccountTokenCreator` to Cloud Scheduler service agent on scheduler SA

**Fixed in:** [`scheduler.tf:18-20`](infrastructure/phase1_ingestion/terraform/scheduler.tf), [`service_accounts.tf:51-57`](infrastructure/phase1_ingestion/terraform/service_accounts.tf)

---

## Lessons Learned

### 1. Always Verify Schemas with MCP Tools

Before running Terraform, use MCP tools to verify resource schemas:

```bash
# For any Google Cloud resource
mcp__terraform__search_providers \
  provider_name="google" \
  provider_namespace="hashicorp" \
  service_slug="<service>" \
  provider_document_type="resources"
```

### 2. Cloud Run v2 Has Different Requirements

| Requirement | Value |
|-------------|-------|
| Min memory (with CPU) | 512Mi |
| Min memory (without CPU) | 128Mi |
| Valid CPU values | "1", "2", "4", "6", "8" |
| Timeout format | String with "s" suffix |

### 3. gsutil is Cloud Storage Only

For downloads from external HTTP sources:
- Use `curl` for HTTP download
- Pipe to `gsutil cp -` for GCS upload
- This streams without writing to disk (memory-efficient)

### 4. Use Terraform MCP for Schema Verification

After encountering schema errors, I used the Terraform MCP server to get correct schemas:
- `google_cloud_run_v2_job` → providerDocID: 11604113
- `google_cloud_run_v2_job_iam` → providerDocID: 11604114
- `google_cloud_scheduler_job` → providerDocID: 11604119

---

## Verification Commands

### After Layer 1 (Foundation)
```bash
gcloud iam service-accounts list --project=<PROJECT_ID> --filter="github-archive"
gsutil ls gs://<PROJECT_ID>-<ENV>-github-archive-landing
```

### After Layer 2 (Compute)
```bash
gcloud run jobs list --project=<PROJECT_ID> --filter="github-archive"
gcloud run jobs execute <JOB_NAME> --region=<REGION>
```

### After Layer 3 (Automation)
```bash
gcloud scheduler jobs list --project=<PROJECT_ID> --location=<REGION> --filter="github-archive"
gcloud run jobs executions list <JOB_NAME> --region=<REGION> --limit=5
```

---

## Deployment Status

| Layer | Resources | Status |
|-------|-----------|--------|
| Layer 1: Foundation | Service Accounts, IAM, GCS Bucket | ✅ Complete |
| Layer 2: Compute | Cloud Run Job | ✅ Complete |
| Layer 3: Automation | Cloud Scheduler, IAM | ✅ Complete |

---

## Files Modified

1. [`infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf`](infrastructure/phase1_ingestion/terraform/cloud_run_jobs.tf)
2. [`infrastructure/phase1_ingestion/terraform/scheduler.tf`](infrastructure/phase1_ingestion/terraform/scheduler.tf)
3. [`infrastructure/phase1_ingestion/terraform/service_accounts.tf`](infrastructure/phase1_ingestion/terraform/service_accounts.tf)
4. [`infrastructure/scripts/phase1_deploy_layered.sh`](infrastructure/scripts/phase1_deploy_layered.sh)
5. [`src/github_archive/phase1_ingestion/scripts/download.sh`](src/github_archive/phase1_ingestion/scripts/download.sh)

---

## References

- [Terraform Google Provider - Cloud Run v2 Job](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job)
- [Cloud Run v2 Job IAM](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job_iam)
- [Cloud Scheduler Job](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_scheduler_job)
- [gsutil Documentation](https://cloud.google.com/storage/docs/gsutil)
