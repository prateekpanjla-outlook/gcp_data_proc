# Phase 1: Ingestion - Specification

## Overview

Phase 1 is responsible for downloading the hourly GitHub Archive file and landing it in Cloud Storage.

**Diagrams:**
- [Main Flow](diagrams/ingestion_01_main_flow.md) - Complete end-to-end flow
- [Entry Conditions](diagrams/ingestion_02_entry_conditions.md) - Prerequisites
- [Exit Conditions](diagrams/ingestion_03_exit_conditions.md) - Success criteria
- [Failure Scenarios](diagrams/ingestion_04_failure_scenarios.md) - Error handling
- [Sequence Diagram](diagrams/ingestion_05_sequence_diagram.md) - Component interaction
- [Components](diagrams/ingestion_06_components.md) - Architecture view
- [Improvements](diagrams/ingestion_07_improvements.md) - Refactoring opportunities

**Design Documents:**
- [gsutil-based Cloud Run Job Design](cloud_run_job_gsutil_design.md) - Full design rationale
- [Terraform Configuration](terraform_gsutil_config.md) - Infrastructure as Code

**Implementation:**
- [`src/phase1_ingestion/Dockerfile`](../../src/phase1_ingestion/Dockerfile) - Container definition
- [`src/phase1_ingestion/scripts/download.sh`](../../src/phase1_ingestion/scripts/download.sh) - Download script

---

## High-Level Flow

```
GitHub Archive (https://data.gharchive.org/)
        │
        │ Cloud Scheduler (cron: 30 * * * *)
        ▼
Cloud Run Job: dev-github-archive-download-gsutil
        │ gsutil cp (streams data)
        ▼
Cloud Storage: gs://{project}-github-archive-landing/github-archive/raw/YYYY-MM-DD-HH.json.gz
```

**Naming Convention:** Uses `dev-` prefix for development environment. Production uses `prod-` prefix.

**Implementation:** Uses `google-cloud-sdk:slim` base image with gsutil for streaming downloads (memory-efficient).

---

## ENTRY Conditions (Pre-requirements)

### 1. Infrastructure (Static Resources)

| Resource | Type | Description |
|----------|------|-------------|
| `PROJECT_ID` | Env Var | Google Cloud project ID |
| `ENVIRONMENT` | Terraform Var | Environment prefix (`dev` or `prod`) |
| `BUCKET_NAME` | Env Var | Target Cloud Storage bucket (e.g., `${PROJECT_ID}-dev-github-archive-landing`) |
| `REGION` | Env Var | GCP region for resources (e.g., `us-central1`) |
| `HOURS_AGO` | Env Var | Hours to look back for file (default: 1) |
| Cloud Run Job | Resource | `${ENVIRONMENT}-github-archive-download-gsutil` |
| Cloud Scheduler | Resource | `${ENVIRONMENT}-github-archive-download-job` |
| Container Image | Artifact | Built from [`src/github_archive/Dockerfile`](../../src/github_archive/Dockerfile) |

### 2. One-Time Setup (Initial Deployment)

**Service Account Creation:**

```bash
# Service account ID with environment prefix
ENVIRONMENT="dev"  # or "prod" for production

gcloud iam service-accounts create ${ENVIRONMENT}-github-archive-downloader \
  --display-name="${ENVIRONMENT^} GitHub Archive Downloader"
```

**IAM Role Bindings:**

| Role | Purpose | Command |
|------|---------|---------|
| `roles/storage.objectUser` | Create, read, list objects in GCS | `gcloud projects add-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${ENVIRONMENT}-github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" --role="roles/storage.objectUser"` |
| `roles/logging.logWriter` | Write logs to Cloud Logging | `gcloud projects add-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${ENVIRONMENT}-github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" --role="roles/logging.logWriter"` |

**Why `roles/storage.objectUser` instead of `roles/storage.objectCreator`?**

| Operation | gsutil command | Required Permission | objectCreator | objectUser |
|-----------|----------------|---------------------|---------------|------------|
| Check if file exists | `gsutil stat` | `storage.objects.get` | ❌ No | ✅ Yes |
| Upload file | `gsutil cp` | `storage.objects.create` | ✅ Yes | ✅ Yes |
| Verify upload | `gsutil du` | `storage.objects.get` | ❌ No | ✅ Yes |

**Deployer Permissions (for the person deploying):**

| Permission | Purpose |
|------------|---------|
| `roles/iam.serviceAccountUser` on `${ENVIRONMENT}-github-archive-downloader` SA | Required to attach SA to Cloud Run Job |
| `roles/run.developer` on the project | Required to deploy Cloud Run Jobs |
| `roles/cloudbuild.builds.builder` | Required to build container images (if using Cloud Build) |

**Cloud Scheduler Service Account Permissions:**

The `${ENVIRONMENT}-scheduler` service account requires specific permissions to invoke Cloud Run Jobs:

| Permission | Target | Purpose |
|------------|--------|---------|
| `roles/run.invoker` | Cloud Run Job: `${ENVIRONMENT}-github-archive-download-gsutil` | Allows scheduler to execute the download job |

**Permission Chain Flow:**

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

**Terraform Configuration (scheduler.tf):**

```hcl
# Scheduler Job with OIDC authentication
resource "google_cloud_scheduler_job" "github_archive_download" {
  name        = "${local.env_prefix}-github-archive-download-job"
  schedule    = "30 * * * *"
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${local.env_prefix}-github-archive-download-gsutil:run"
    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}

# IAM binding: Grant scheduler permission to invoke the job
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_download_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_downloader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
```

**Source:** [Google Cloud Documentation - Execute Cloud Run jobs on a schedule](https://cloud.google.com/run/docs/execute/jobs-on-schedule)

**Storage Bucket Creation:**

```bash
# Bucket name with environment prefix
ENVIRONMENT="dev"  # or "prod"
BUCKET_NAME="${PROJECT_ID}-${ENVIRONMENT}-github-archive-landing"

# Create bucket with uniform access
gsutil mb -p ${PROJECT_ID} -l ${REGION} gs://${BUCKET_NAME}
```

**Source:** [Google Cloud Official Documentation - Cloud Storage Volume Mounts](https://cloud.google.com/run/docs/configuring/jobs/cloud-storage-volume-mounts)

### 3. Daily / Operational (Runtime Requirements)

**External Dependencies:**

| Dependency | URL | Availability |
|------------|-----|--------------|
| GitHub Archive | `https://data.gharchive.org/` | Public, no auth required |
| File Naming Pattern | `{YYYY}-{MM}-{DD}-{HH}.json.gz` | Files available within 1-2 hours after hour ends |

**Runtime Environment Variables:**

| Variable | Source | Description |
|----------|--------|-------------|
| `BUCKET_NAME` | Terraform / Cloud Run config | Target GCS bucket |
| `PROJECT_ID` | Terraform / Cloud Run config | GCP project ID |
| `HOURS_AGO` | Cloud Run config | How many hours back to look (default: 1) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Automatic (in Cloud Run) | Service account key (auto-injected) |

**Operational Prerequisites:**

| Condition | Check | Action if Failed |
|-----------|-------|------------------|
| Cloud Run Job is healthy | `gcloud run jobs describe ${ENVIRONMENT}-github-archive-download-gsutil` | Redeploy job |
| Scheduler is active | `gcloud scheduler jobs describe ${ENVIRONMENT}-github-archive-download-job` | Check schedule |
| Bucket is accessible | `gsutil ls gs://${BUCKET_NAME}` | Check IAM permissions |
| Service account has permissions | `gcloud projects get-iam-policy ${PROJECT_ID}` | Grant missing roles |

---

## Process Flow

### Step 1: Calculate Target Filename

```python
# Current implementation (src/github_archive/main.py:140-141)
from datetime import datetime, timedelta

hours_ago = 1  # Download previous hour's file
target_time = datetime.utcnow() - timedelta(hours=hours_ago)
filename = target_time.strftime("%Y-%m-%d-%-H.json.gz")

# Example: 2025-01-15-14.json.gz
```

**Entry Condition:**
- System time is synchronized (NTP)
- Target time calculation is correct

**Exit Condition:**
- `filename` variable contains valid filename string

---

### Step 2: Build Download URL

```python
url = f"https://data.gharchive.org/{filename}"

# Example: https://data.gharchive.org/2025-01-15-14.json.gz
```

**Entry Condition:**
- GitHub Archive domain is reachable
- Internet connectivity exists

**Failure Mode:**
- HTTP 404: File not yet available → Should retry
- HTTP 500/503: Server error → Should retry
- Network timeout → Should retry

---

### Step 3: Download File

```python
from urllib.request import urlopen

with urlopen(url, timeout=300) as response:
    if response.status == 200:
        compressed_data = response.read()
        # Expecting ~1.2 MB to 1.2 GB (varies by hour)
```

**Entry Conditions:**
| Condition | Value |
|-----------|-------|
| `url` | Valid GitHub Archive URL |
| `timeout` | 300 seconds (5 minutes) |
| Available memory | Sufficient for file size |

**Exit Conditions:**
| Condition | Value | Description |
|-----------|-------|-------------|
| `response.status` | 200 | HTTP success |
| `compressed_data` | bytes | File content in memory |
| `len(compressed_data)` | > 0 | Non-empty file |

**Failure Modes:**
| Error | Action |
|-------|--------|
| `HTTP 404` | Retry after 5 minutes (file not ready) |
| `HTTP 500/502/503` | Retry with exponential backoff |
| `Timeout` | Retry with longer timeout |
| `Memory Error` | Use streaming download (refactor needed) |

---

### Step 4: Validate Gzip Format

```python
import gzip

try:
    gzip.decompress(compressed_data)
except gzip.BadGzipFile:
    # File is corrupted or not valid gzip
    raise ValueError("Downloaded file is not valid gzip")
```

**Entry Conditions:**
- `compressed_data` contains downloaded bytes

**Exit Conditions:**
| Condition | Value |
|-----------|-------|
| Validation | Pass | File is valid gzip |
| Validation | Fail | Corrupted download |

**Failure Mode:**
- BadGzipFile → Log error, skip file (do NOT upload invalid data)

---

### Step 5: Upload to Cloud Storage

**Implementation: gsutil-based (Streaming)**

```bash
# From src/github_archive/scripts/download.sh
# gsutil streams data directly - memory efficient (~50MB constant usage)

SOURCE_URL="https://data.gharchive.org/${FILENAME}"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"

# Upload with streaming
gsutil cp "${SOURCE_URL}" "${GCS_PATH}"
```

**Alternative: Python Client Library (Original)**

```python
from google.cloud import storage

client = storage.Client(project=PROJECT_ID)
bucket = client.bucket(BUCKET_NAME)
blob_name = f"github-archive/raw/{filename}"
blob = bucket.blob(blob_name)

blob.upload_from_string(
    compressed_data,
    content_type="application/gzip"
)
```

**Entry Conditions:**
| Condition | Value | Source |
|-----------|-------|--------|
| `compressed_data` | Valid gzip bytes | Step 4 (Python only) |
| `BUCKET_NAME` | Existing bucket | Terraform/Manual |
| `PROJECT_ID` | Valid project | Environment |
| Service Account | Has `roles/storage.objectUser` | IAM |

**Exit Conditions:**
| Condition | Value | Verification |
|-----------|-------|-------------|
| Upload Success | `gsutil stat` returns 0 | File exists in GCS |
| File Size | `gsutil du` shows size | Integrity check |
| Content Type | `application/gzip` | Correct MIME type |

**Failure Modes:**
| Error | Cause | Action |
|-------|-------|--------|
| `NotFound` | Bucket doesn't exist | Create bucket first |
| `PermissionDenied` | SA lacks permissions | Grant `roles/storage.objectUser` |
| `Network Error` | Upload interruption | gsutil auto-retries 3x |

---

## SUCCESS Criteria (Exit Conditions)

Phase 1 is **successful** when ALL of the following are true:

| # | Condition | Verification |
|---|-----------|--------------|
| 1 | File downloaded from GitHub Archive | HTTP 200 response |
| 2 | File is valid gzip format | `gzip.decompress()` succeeds |
| 3 | File uploaded to correct GCS path | `gs://{bucket}/github-archive/raw/{filename}` exists |
| 4 | File size matches download | `blob.size == len(compressed_data)` |
| 5 | Content-Type is set correctly | `blob.content_type == "application/gzip"` |
| 6 | No errors logged | Log shows "Successfully uploaded {blob_name}" |

---

## FAILURE SCENARIOS & HANDLING

| Scenario | Detection | Action | Retry? |
|----------|-----------|--------|--------|
| File not available (404) | HTTP status | Wait 5 min, retry | Yes (up to 6x = 30 min) |
| Server error (5xx) | HTTP status | Wait 1 min, retry | Yes (up to 3x) |
| Network timeout | Exception | Wait 2 min, retry | Yes (up to 3x) |
| Corrupted gzip | `BadGzipFile` | Log error, skip file | No |
| Insufficient memory | `MemoryError` | Use streaming download | No (requires refactor) |
| Bucket not found | `NotFound` | Create bucket or fail | No (infra issue) |
| Permission denied | `PermissionDenied` | Fix IAM and retry | No (infra issue) |

---

## CURRENT CODE LOCATION

### gsutil-based Implementation (Recommended)

**Files:**
- [`src/github_archive/Dockerfile`](../../src/github_archive/Dockerfile) - Container definition
- [`src/github_archive/scripts/download.sh`](../../src/github_archive/scripts/download.sh) - Download script

**Dockerfile:**
```dockerfile
FROM gcr.io/google.com/cloud-sdk:slim

# Install coreutils for date command
RUN apt-get update && apt-get install -y coreutils && rm -rf /var/lib/apt/lists/*

# Copy download script
COPY scripts/download.sh /scripts/download.sh
RUN chmod +x /scripts/download.sh

# Environment variables (set at runtime)
ENV BUCKET_NAME=""
ENV PROJECT_ID=""
ENV HOURS_AGO="1"
ENV GOOGLE_APPLICATION_CREDENTIALS=""

ENTRYPOINT ["/scripts/download.sh"]
```

**download.sh (key operations):**
```bash
#!/bin/bash
set -e

# Calculate target filename
if [[ "$OSTYPE" == "darwin"* ]]; then
    FILENAME=$(date -u -v-${HOURS_AGO}H +"%Y-%m-%d-%-H.json.gz")
else
    FILENAME=$(date -u -d "${HOURS_AGO} hours ago" +"%Y-%m-%d-%-H.json.gz")
fi

SOURCE_URL="https://data.gharchive.org/${FILENAME}"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"

# Check if file already exists (idempotency)
if gsutil -q stat "${GCS_PATH}" 2>/dev/null; then
    echo "File ${FILENAME} already exists in GCS, skipping download"
    exit 0
fi

# Download and upload in one streaming operation (memory efficient)
gsutil cp "${SOURCE_URL}" "${GCS_PATH}"

# Verify upload
SIZE=$(gsutil du "${GCS_PATH}" | awk '{print $1}')
echo "Successfully uploaded ${FILENAME} (${SIZE} bytes)"
```

### Original Python Implementation (Legacy)

**File:** [`src/github_archive/main.py`](../../src/github_archive/main.py)
**Function:** `download_github_archive()` (lines 127-176)

```python
@app.route("/tasks/download", methods=["GET", "POST"])
def download_github_archive():
    hours_ago = int(request.args.get("hours_ago", 1))
    target_time = datetime.utcnow() - timedelta(hours=hours_ago)
    filename = target_time.strftime("%Y-%m-%d-%-H.json.gz")
    url = f"https://data.gharchive.org/{filename}"

    # Download (loads entire file into memory - NOT recommended for large files)
    with urlopen(url, timeout=300) as response:
        compressed_data = response.read()

    # Validate
    try:
        gzip.decompress(compressed_data)
    except gzip.BadGzipFile:
        return jsonify({"error": "Invalid gzip data"}), 400

    # Upload
    blob_name = f"github-archive/raw/{filename}"
    blob = storage_client.bucket.blob(blob_name)
    blob.upload_from_string(compressed_data, content_type="application/gzip")

    return jsonify({"message": "File downloaded and uploaded", ...})
```

### Memory Comparison

| Implementation | Memory Usage | Notes |
|----------------|--------------|-------|
| Python (original) | ~1.2 GB peak | Loads entire file into RAM |
| gsutil (recommended) | ~50 MB constant | Streams data directly |

---

## IMPLEMENTATION STATUS

### Completed (gsutil-based Implementation)

| Feature | Status | Implementation |
|---------|--------|----------------|
| Streaming download | ✅ Complete | Uses `gsutil cp` for direct streaming |
| Memory efficiency | ✅ Complete | ~50MB constant usage vs ~1.2GB peak |
| File existence check | ✅ Complete | `gsutil stat` before download |
| Cross-platform date | ✅ Complete | Linux/macOS detection in download.sh |
| Service account setup | ✅ Documented | See Service Account Permissions above |

### Design Documents

| Document | Description |
|----------|-------------|
| [gsutil-based Design](cloud_run_job_gsutil_design.md) | Full design rationale |
| [Terraform Configuration](terraform_gsutil_config.md) | Infrastructure as Code |

### Future Enhancements

**1. Better Retry Logic**

**Current:** gsutil has built-in retry (3 attempts).

**Enhancement:**
```python
from src.shared.retry import retry_with_exponential_backoff

@retry_with_exponential_backoff(
    max_attempts=6,  # Try for up to 30 minutes
    wait_min=60,     # Start at 1 minute
    wait_max=300,    # Max 5 minutes
    multiplier=2
)
def download_from_github_archive(url: str) -> bytes:
    # Wrapper for gsutil with additional retry logic
    ...
```

---

## MONITORING

### Cloud Logging

The download.sh script outputs structured logs:

| Log Message | Level | Meaning |
|-------------|-------|---------|
| `File ${FILENAME} already exists in GCS, skipping download` | INFO | Idempotent skip (not an error) |
| `Successfully uploaded ${FILENAME} (${SIZE} bytes)` | INFO | Success |
| `Failed to download ${FILENAME}` | ERROR | Download failed |
| `gsutil cp failed` | ERROR | Upload failed |

### Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| `job_execution_time` | Total job duration | < 300 seconds |
| `file_size_bytes` | Size of downloaded file | ~1.2 GB (varies by hour) |
| `job_success` | Job completed successfully | 100% |
| `file_already_exists_count` | Idempotent skips | Info only |

### Cloud Run Job Metrics

Available in Cloud Monitoring:
- `run.googleapis.com/job/completions` - Number of successful job completions
- `run.googleapis.com/job/attempts` - Number of job execution attempts
- `run.googleapis.com/job/latencies` - Job execution duration

### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Job fails 3 consecutive times | **ERROR** | Check GitHub Archive status, GCS permissions |
| File size < 100 MB | **WARNING** | Possible partial download or quiet hour |
| Job execution time > 600 seconds | **WARNING** | Performance degradation |
| File already exists < 10% of runs | **INFO** | Normal operation (idempotency working) |

---

## TERRAFORM CONFIGURATION

### Variables

**File:** [`terraform/variables.tf`](../../terraform/variables.tf)

```hcl
variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}
```

### Locals (Helper Values)

**File:** [`terraform/locals.tf`](../../terraform/locals.tf)

```hcl
locals {
  # Environment prefix for resource naming
  env_prefix = var.environment

  # GitHub Archive Ingestion Resource Names
  github_archive = {
    service_account_id = "${local.env_prefix}-github-archive-downloader"
    bucket_name         = "${var.project_id}-${local.env_prefix}-github-archive-landing"
    job_name            = "${local.env_prefix}-github-archive-download-gsutil"
    scheduler_name      = "${local.env_prefix}-github-archive-download-job"
  }
}
```

### Service Account

**File:** [`terraform/service_accounts.tf`](../../terraform/service_accounts.tf)

```hcl
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

resource "google_project_iam_member" "github_archive_downloader_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}

resource "google_project_iam_member" "github_archive_downloader_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}
```

### Cloud Run Job

**File:** [`terraform/cloud_run_jobs.tf`](../../terraform/cloud_run_jobs.tf)

```hcl
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = local.github_archive.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "gcr.io/google.com/cloud-sdk:slim"

        # Environment variables
        env {
          name  = "BUCKET_NAME"
          value = google_storage_bucket.github_archive_landing.name
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "HOURS_AGO"
          value = "1"
        }

        # Resource limits
        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }
      }

      # Service account
      service_account_name = google_service_account.github_archive_downloader.email

      # Timeout
      timeout_seconds = 1800  # 30 minutes
    }
  }
}
```

### Cloud Scheduler

**File:** [`terraform/scheduler.tf`](../../terraform/scheduler.tf)

```hcl
resource "google_cloud_scheduler_job" "github_archive_download" {
  name        = local.github_archive.scheduler_name
  description = "Downloads hourly GitHub Archive files using gsutil-based Cloud Run Job"

  schedule    = "30 * * * *"  # 30 minutes past each hour
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${local.github_archive.job_name}:run"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 2
    min_backoff = "10s"
  }
}

# IAM binding: Grant scheduler permission to invoke the job
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_download_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_downloader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
```

### Storage Bucket

**File:** [`terraform/storage.tf`](../../terraform/storage.tf)

```hcl
resource "google_storage_bucket" "github_archive_landing" {
  name          = local.github_archive.bucket_name
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90  # Delete files after 90 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    layer       = "landing"
    managed_by  = "terraform"
  }
}
```

---

## LEARNINGS & GOTCHAS

### Timezone and Time Rationalization for External Integrations

**Issue:** When integrating with external APIs like GitHub Archive (`https://data.gharchive.org/`), proper timezone handling is critical.

**Key Points:**

1. **Always use UTC for time calculations**
   - GitHub Archive uses UTC for all file naming: `{YYYY}-{MM}-{DD}-{HH}.json.gz`
   - Cloud Scheduler is configured with `time_zone = "UTC"`
   - Script uses `date -u` flags for UTC consistency

2. **Hour precision matters**
   - Files are named with hour: `2026-03-05-12.json.gz` (not just `2026-03-05.json.gz`)
   - The hour field `-H` must be included in the filename format
   - Files are typically available 1-2 hours after the hour ends

3. **Date format string bug (fixed)**
   - Original bug: Missing `%d` in format string `'+%Y-%m-%-H'` produced `2026-03-12.json.gz` (hour interpreted as day!)
   - Fixed: Use `'+%Y-%m-%d-%-H'` to produce correct `2026-03-05-12.json.gz`
   - Always verify date format strings produce expected output

4. **File availability considerations**
   - Current hour's file returns 404 (not yet available)
   - Use `HOURS_AGO=1` (default) to fetch previous hour's file
   - Scheduler runs at `:30` past the hour to allow file generation

**Example:**
```bash
# Current time: 2026-03-05 13:00 UTC
# HOURS_AGO=1 should fetch: 2026-03-05-12.json.gz (previous hour)
# HOURS_AGO=24 should fetch: 2026-03-04-13.json.gz (same time yesterday)

# Verify file exists before attempting download:
curl -sI "https://data.gharchive.org/2026-03-05-12.json.gz" | head -1
# HTTP/2 200 = file exists
# HTTP/2 404 = file not yet available
```
