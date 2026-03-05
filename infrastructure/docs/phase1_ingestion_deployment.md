# Phase 1: Ingestion - Deployment Guide

This guide covers the complete first-time deployment process for Phase 1 (GitHub Archive Ingestion) of the data pipeline.

---

## Prerequisites

| Item | Value |
|------|-------|
| **Project ID** | `dev-dataprocessing-489305` |
| **Region** | `us-central1` |
| **Environment** | `dev` (for development) |
| **Source Code** | `src/github_archive/` |
| **Terraform** | `terraform/` |

---

## Deployment Steps Overview

| # | Step | Method | Required APIs |
|---|------|--------|--------------|
| 0 | Enable Required APIs | gcloud | Service Usage API |
| 1 | Build Container Image | gcloud / Docker | Cloud Build, Artifact Registry |
| 2 | Initialize Terraform | Terraform | None (local) |
| 3 | Create Terraform workspace | Terraform | None (local) |
| 4 | Review Terraform plan | Terraform | Cloud Resource Manager, IAM |
| 5 | Apply Terraform | Terraform | Cloud Run, Cloud Scheduler, Cloud Storage, IAM |
| 6 | Verify Cloud Run Job | gcloud | Cloud Run |
| 7 | Verify Cloud Scheduler | gcloud | Cloud Scheduler |
| 8 | Test manual execution | gcloud | Cloud Run, Cloud Logging |

---

## Step 0: Enable Required APIs

### APIs to Enable

| API | Service Name | Purpose |
|-----|--------------|---------|
| Cloud Build API | `cloudbuild.googleapis.com` | Build container images |
| Cloud Run API | `run.googleapis.com` | Create/manage Cloud Run Jobs |
| Cloud Scheduler API | `cloudscheduler.googleapis.com` | Create/manage scheduled jobs |
| IAM API | `iam.googleapis.com` | Create service accounts |
| Artifact Registry API | `artifactregistry.googleapis.com` | Store container images |
| Cloud Resource Manager API | `cloudresourcemanager.googleapis.com` | Required by Terraform |

### Option A: Using the provided script

```bash
./scripts/enable-apis.sh dev-dataprocessing-489305
```

### Option B: Manual command

```bash
gcloud services enable \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  cloudscheduler.googleapis.com \
  iam.googleapis.com \
  artifactregistry.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=dev-dataprocessing-489305
```

### Verify APIs are enabled

```bash
gcloud services list --enabled --project=dev-dataprocessing-489305 \
  --filter="name:cloudbuild.googleapis.com OR name:run.googleapis.com OR name:cloudscheduler.googleapis.com OR name:iam.googleapis.com OR name:artifactregistry.googleapis.com"
```

---

## Step 1: Build Container Image

Build the container image using Cloud Build and push to Artifact Registry.

```bash
# Create Artifact Registry repository (if not exists)
gcloud artifacts repositories create github-archive \
  --repository-format=docker \
  --location=us-central1 \
  --project=dev-dataprocessing-489305

# Build and push image
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/dev-dataprocessing-489305/github-archive/github-archive-downloader:latest \
  src/github_archive/
```

**Container Details:**
- Base image: `gcr.io/google.com/cloud-sdk:slim`
- Script: `src/github_archive/scripts/download.sh`
- Uses `curl | gsutil cp -` for streaming downloads (memory-efficient)

---

## Step 2: Initialize Terraform

```bash
cd terraform
terraform init
```

---

## Step 3: Create Terraform Workspace

```bash
terraform workspace new dev
```

---

## Step 4: Review Terraform Plan

```bash
terraform plan \
  -var="environment=dev" \
  -var="project_id=dev-dataprocessing-489305" \
  -var="region=us-central1"
```

### Resources that will be created:

| Resource | Name (dev) |
|----------|------------|
| Service Account | `dev-github-archive-downloader` |
| Scheduler Service Account | `dev-scheduler` |
| Storage Bucket | `dev-dataprocessing-489305-dev-github-archive-landing` |
| Cloud Run Job | `dev-github-archive-download-gsutil` |
| Cloud Scheduler Job | `dev-github-archive-download-job` |

---

## Step 5: Apply Terraform

```bash
terraform apply \
  -var="environment=dev" \
  -var="project_id=dev-dataprocessing-489305" \
  -var="region=us-central1"
```

Type `yes` when prompted to confirm.

---

## Step 6: Verify Cloud Run Job

```bash
gcloud run jobs describe dev-github-archive-download-gsutil \
  --region=us-central1 \
  --project=dev-dataprocessing-489305
```

Expected output should show job details with status `READY`.

---

## Step 7: Verify Cloud Scheduler

```bash
gcloud scheduler jobs describe dev-github-archive-download-job \
  --region=us-central1 \
  --project=dev-dataprocessing-489305
```

Expected schedule: `30 * * * *` (every hour at 30 minutes past)

---

## Step 8: Test Manual Execution

Run the job manually to verify end-to-end functionality:

```bash
gcloud run jobs execute dev-github-archive-download-gsutil \
  --region=us-central1 \
  --project=dev-dataprocessing-489305
```

### Verify Success

1. **Check execution status:**
   ```bash
   gcloud run jobs executions list dev-github-archive-download-gsutil \
     --region=us-central1 \
     --limit=1
   ```

2. **View logs:**
   ```bash
   gcloud run jobs executions logs-tail dev-github-archive-download-gsutil \
     --region=us-central1 \
     --execution=latest
   ```

3. **Verify files in GCS:**
   ```bash
   gsutil ls gs://dev-dataprocessing-489305-dev-github-archive-landing/github-archive/raw/
   ```

---

## Permission Chain Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CLOUD SCHEDULER PERMISSION CHAIN                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Cloud Scheduler Job (dev-github-archive-download-job)                  │
│      ├─ Schedule: "30 * * * *" (every hour at 30 min past)                 │
│      ├─ Uses: OAuth token with dev-scheduler SA email                      │
│      └─ Target: Cloud Run Job API (:run endpoint)                           │
│                             ↓                                               │
│   2. Scheduler Service Account (dev-scheduler)                              │
│      ├─ Requires: roles/run.invoker ON the Cloud Run Job                   │
│      └─ Granted by: google_cloud_run_v2_job_iam_member resource            │
│                             ↓                                               │
│   3. Cloud Run Job (dev-github-archive-download-gsutil)                     │
│      └─ Runs as: dev-github-archive-downloader SA                           │
│          ├─ roles/storage.objectUser (for gsutil upload)                   │
│          └─ roles/logging.logWriter (for Cloud Logging)                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Troubleshooting

### API Not Enabled Error

**Error:** `API ... is not enabled for project ...`

**Solution:** Run Step 0 to enable the missing API.

### Permission Denied Error

**Error:** `Permission denied 'cloudbuild.builds.create'`

**Solution:** Ensure your account has `roles/cloudbuild.builds.builder` or Project Editor role.

### Container Image Not Found

**Error:** `The image to "us-docker.pkg.dev/..." does not exist`

**Solution:** Ensure Step 1 (build image) completed successfully.

### Job Failed to Start

**Error:** `Job execution failed`

**Solution:**
1. Check logs: `gcloud run jobs executions logs-tail ...`
2. Verify service account has correct IAM roles
3. Verify GCS bucket exists and is accessible

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PROJECT_ID` | GCP Project ID | - |
| `ENVIRONMENT` | Environment name (dev/prod) | `dev` |
| `REGION` | GCP Region | `us-central1` |
| `BUCKET_NAME` | Target GCS bucket | `{PROJECT_ID}-{ENVIRONMENT}-github-archive-landing` |
| `HOURS_AGO` | Hours to look back for file | `1` |

---

## Production Deployment

For production (`ENVIRONMENT=prod`), the same steps apply with:

```bash
terraform plan \
  -var="environment=prod" \
  -var="project_id=<prod-project-id>" \
  -var="region=us-central1"
```

**Note:** Production resources will use `prod-` prefix instead of `dev-` prefix.

---

## Sources

- [Google Cloud Documentation - Execute Cloud Run jobs on a schedule](https://cloud.google.com/run/docs/execute/jobs-on-schedule)
- [Google Cloud Documentation - Cloud Scheduler HTTP target authentication](https://cloud.google.com/scheduler/docs/http-target-auth)
- [Google Cloud Documentation - Cloud Build submit builds](https://cloud.google.com/build/docs/running-builds/submit-build-via-cli-api)
- [Google Cloud Documentation - Enable APIs](https://cloud.google.com/service-usage/docsenable-api)
