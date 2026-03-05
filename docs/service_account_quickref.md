# Quick Reference: Service Account & Permissions

## Environment Configuration

```bash
# Set environment (dev or prod)
export ENVIRONMENT="dev"  # or "prod"
export PROJECT_ID="your-project-id"
export REGION="us-central1"
```

## Service Account Setup Commands

### 1. GitHub Archive Downloader Service Account

```bash
# Create Service Account
gcloud iam service-accounts create ${ENVIRONMENT}-github-archive-downloader \
    --display-name="${ENVIRONMENT^} GitHub Archive Downloader" \
    --description="Service account for Cloud Run Job that downloads GitHub Archive files using gsutil"

# Grant Storage Permissions
# Note: objectUser instead of objectCreator for gsutil stat support
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${ENVIRONMENT}-github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectUser"

# Grant Logging Permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${ENVIRONMENT}-github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

### 2. Cloud Scheduler Service Account

```bash
# Create Scheduler Service Account
gcloud iam service-accounts create ${ENVIRONMENT}-scheduler \
    --display-name="${ENVIRONMENT^} Cloud Scheduler Service Account" \
    --description="Service account for Cloud Scheduler jobs"

# Grant Scheduler permission to invoke the Cloud Run Job
gcloud run jobs add-iam-policy-binding ${ENVIRONMENT}-github-archive-download-gsutil \
    --member="serviceAccount:${ENVIRONMENT}-scheduler@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/run.invoker" \
    --region=${REGION}
```

## Required Permissions

### GitHub Archive Downloader SA

| Action | Permission | Role | Purpose |
|--------|------------|------|---------|
| Upload file | `storage.objects.create` | `roles/storage.objectUser` | gsutil cp |
| Check if exists | `storage.objects.get` | `roles/storage.objectUser` | gsutil stat |
| Verify upload | `storage.objects.get` | `roles/storage.objectUser` | gsutil du |
| List files | `storage.objects.list` | `roles/storage.objectUser` | gsutil ls |
| Write logs | `logging.logEntries.create` | `roles/logging.logWriter` | Cloud Logging |

### Cloud Scheduler SA

| Action | Permission | Role | Purpose |
|--------|------------|------|---------|
| Invoke Cloud Run Job | `run.jobs.run` | `roles/run.invoker` | Trigger scheduled jobs |

## Why `roles/storage.objectUser` instead of `roles/storage.objectCreator`?

| Operation | gsutil command | Required Permission | objectCreator | objectUser |
|-----------|----------------|---------------------|---------------|------------|
| Check if file exists | `gsutil stat` | `storage.objects.get` | ❌ No | ✅ Yes |
| Upload file | `gsutil cp` | `storage.objects.create` | ✅ Yes | ✅ Yes |
| Verify upload | `gsutil du` | `storage.objects.get` | ❌ No | ✅ Yes |

## Run Container Locally (for testing)

```bash
# Create key file (local testing only - NOT recommended for production)
gcloud iam service-accounts keys create github-archive-downloader-key.json \
    --iam-account="${ENVIRONMENT}-github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com"

# Build
cd src/github_archive/
docker build -f Dockerfile -t github-archive-downloader:latest .

# Run with key file
docker run --rm \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json \
    -v ${PWD}/../github-archive-downloader-key.json:/tmp/key.json:ro \
    -e PROJECT_ID="${PROJECT_ID}" \
    -e BUCKET_NAME="${PROJECT_ID}-${ENVIRONMENT}-github-archive-landing" \
    github-archive-downloader:latest
```

## Terraform Reference

```hcl
# terraform/locals.tf
locals {
  env_prefix = var.environment
  github_archive = {
    service_account_id = "${local.env_prefix}-github-archive-downloader"
    bucket_name         = "${var.project_id}-${local.env_prefix}-github-archive-landing"
    job_name            = "${local.env_prefix}-github-archive-download-gsutil"
    scheduler_name      = "${local.env_prefix}-github-archive-download-job"
  }
}

# terraform/service_accounts.tf
resource "google_service_account" "github_archive_downloader" {
  account_id   = local.github_archive.service_account_id
  display_name = "${title(var.environment)} GitHub Archive Downloader"
  description  = "Service account for Cloud Run Job that downloads GitHub Archive files using gsutil"
}

resource "google_service_account" "scheduler" {
  account_id   = "${local.env_prefix}-scheduler"
  display_name = "${title(var.environment)} Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}

# IAM binding for Scheduler to invoke Cloud Run Job
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_download_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_downloader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
```

## Permission Chain Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD SCHEDULER PERMISSION CHAIN                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Cloud Scheduler Job (${ENVIRONMENT}-github-archive-download-job)       │
│      ├─ Schedule: "30 * * * *" (every hour at 30 min past)                 │
│      ├─ Uses: OIDC token with ${ENVIRONMENT}-scheduler SA email            │
│      └─ Target: Cloud Run Job (:run endpoint)                               │
│                             ↓                                               │
│   2. Scheduler Service Account (${ENVIRONMENT}-scheduler)                   │
│      ├─ Requires: roles/run.invoker ON the Cloud Run Job                   │
│      └─ Granted by: google_cloud_run_v2_job_iam_member resource            │
│                             ↓                                               │
│   3. Cloud Run Job (${ENVIRONMENT}-github-archive-download-gsutil)          │
│      └─ Runs as: ${ENVIRONMENT}-github-archive-downloader SA                │
│          ├─ roles/storage.objectUser (for gsutil upload)                   │
│          └─ roles/logging.logWriter (for Cloud Logging)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Sources

- [Google Cloud Documentation - Execute Cloud Run jobs on a schedule](https://cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Google Cloud Documentation - Cloud Scheduler HTTP target authentication](https://cloud.google.com/scheduler/docs/http-target-auth)
