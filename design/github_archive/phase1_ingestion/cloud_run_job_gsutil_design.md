# Phase 1: Cloud Run Job + gsutil Design

## Overview

Use a Cloud Run Job with the Google Cloud SDK base image to download GitHub Archive files via `gsutil cp`.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CLOUD RUN JOB DESIGN                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   Cloud Scheduler (hourly)                                               │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │              Cloud Run Job: github-archive-downloader               │   │
│   │                                                                  │   │
│   │   Base Image: gcr.io/google.com/cloud-sdk:latest                 │   │
│   │   Entry: /scripts/download.sh                                    │   │
│   │   Memory: 512Mi (Cloud Run v2 minimum with CPU)                 │   │
│   │   Timeout: 1800s (30 min)                                        │   │
│   │                                                                  │   │
│   │   ┌───────────────────────────────────────────────────────────┐   │   │
│   │   │ 1. Calculate target filename (YYYY-MM-DD-H.json.gz)     │   │   │
│   │   └───────────────────────────────────────────────────────────┘   │   │
│   │                                  │                               │   │
│   │   ▼                                  │                               │   │
│   │   ┌───────────────────────────────────────────────────────────┐   │   │
│   │   │ 2. Check if file exists in GCS (idempotency)            │   │   │
│   │   └───────────────────────────────────────────────────────────┘   │   │
│   │                                  │                               │   │
│   │   ▼                                  │                               │   │
│   │   ┌───────────────────────────────────────────────────────────┐   │   │
│   │   │ 3. curl https://data.gharchive.org/{filename} |          │   │   │
│   │   │         gsutil cp - gs://{bucket}/github-archive/raw/    │   │   │
│   │   └───────────────────────────────────────────────────────────┘   │   │
│   │                                  │                               │   │
│   │   ▼                                  │                               │   │
│   │   ┌───────────────────────────────────────────────────────────┐   │   │
│   │   │ 4. Verify upload & report metrics                        │   │   │
│   │   └───────────────────────────────────────────────────────────┘   │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│                              │                                         │
│                              ▼                                         │
│                   Cloud Storage: github-archive/raw/                       │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Why gsutil Approach?

| Benefit | Description |
|---------|-------------|
| **Memory Efficient** | `gsutil cp` streams data - constant low memory usage |
| **Built-in Retry** | Handles transient network errors automatically |
| **Idempotent** | Check if file exists before downloading |
| **Simple** | Single command, no Python code to maintain |
| **Reliable** | Google-maintained tool, battle-tested |
| **No Dependencies** | No Python packages needed |

---

## Architecture

### Container Image

```dockerfile
FROM gcr.io/google.com/cloud-sdk:latest

# Environment variables
ENV BUCKET_NAME=${BUCKET_NAME}
ENV PROJECT_ID=${PROJECT_ID}

# Copy download script
COPY scripts/download.sh /scripts/download.sh
RUN chmod +x /scripts/download.sh

# Set entrypoint
ENTRYPOINT ["/scripts/download.sh"]
```

### Download Script

```bash
#!/bin/bash
set -e

# Configuration
BUCKET_NAME="${BUCKET_NAME:-$PROJECT_ID-data-pipeline}"
GITHUB_ARCHIVE_BASE="https://data.gharchive.org"

# Calculate target filename (previous hour)
TARGET_HOUR=$(date -u -d '1 hour ago' '+%Y-%m-%-H')  # Note: macOS uses -v
FILENAME="${TARGET_HOUR}.json.gz"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"
SOURCE_URL="${GITHUB_ARCHIVE_BASE}/${FILENAME}"

echo "=== GitHub Archive Download ==="
echo "Target file: ${FILENAME}"
echo "Source URL: ${SOURCE_URL}"
echo "GCS Path: ${GCS_PATH}"

# Check if file already exists (idempotency)
if gsutil -q stat "${GCS_PATH}" 2>/dev/null; then
    echo "File already exists in GCS, skipping download"
    exit 0
fi

# Download using curl + pipe to gsutil (streams automatically)
# Note: gsutil cp does NOT support HTTP URLs, must use curl for HTTP
curl -fsSL "${SOURCE_URL}" | gsutil cp - "${GCS_PATH}"

# Verify upload
FILE_SIZE=$(gsutil du "${GCS_PATH}" | awk '{print $1}')
echo "=== Download Complete ==="
echo "File: ${GCS_PATH}"
echo "Size: ${FILE_SIZE} bytes"

# Optional: Trigger processing (finalize event will fire automatically)
```

---

## Entry & Exit Conditions

### Entry Conditions

| Requirement | Value | Source |
|-------------|-------|--------|
| `PROJECT_ID` | GCP project ID | Environment variable |
| `BUCKET_NAME` | Target bucket name | Environment variable |
| Google Cloud SDK image | `gcr.io/google.com/cloud-sdk:latest` | Container base |
| Service Account | `Storage.ObjectCreator` role | IAM |
| Internet access | To `data.gharchive.org` | VPC egress |
| gsutil installed | Included in SDK image | N/A |

### Exit Conditions

| Condition | Value | Verification |
|-----------|-------|-------------|
| File exists in GCS | `gsutil stat` returns success | `gsutil -q stat {path}` |
| File size > 0 | `gsutil du` returns size | Size in bytes |
| Content-Type | `application/gzip` (automatic) | Blob metadata |
| Download skipped | If file already exists | Idempotent |

---

## File Structure

```
cloud_storage_run_bigquery_data_project/
├── src/github_archive/
│   ├── Dockerfile          # Cloud Run Job Dockerfile
│   ├── scripts/
│   │   └── download.sh         # Download script
│   └── main.py                 # (Flask app - kept for manual use)
```

---

## Terraform Configuration

### Cloud Run Job

```hcl
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = "github-archive-downloader"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # Use google-cloud-sdk image
        image = "gcr.io/google.com/cloud-sdk:slim"

        # Environment variables
        env {
          name  = "BUCKET_NAME"
          value = "${var.project_id}-data-pipeline"
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        # Resource limits (minimal - gsutil streams)
        # Cloud Run v2 requires min 512Mi when CPU is allocated
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"  # v2 minimum with CPU
          }
        }
      }

      # Timeout for download
      timeout = "1800s"  # 30 minutes

      # Service account
      service_account = google_service_account.hn_fetcher.email
      region                = var.region
    }
  }
}
```

### Cloud Scheduler

```hcl
resource "google_cloud_scheduler_job" "github_archive_downloader" {
  name             = "github-archive-downloader"
  description      = "Download hourly GitHub Archive file"

  schedule         = "30 * * * *"  # 30 minutes past each hour
  time_zone        = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/github-archive-downloader:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 1
    min_backoff_duration = "60s"
  }
}
```

---

## Comparison: Current vs gsutil Approach

| Aspect | Current (Python Flask) | gsutil Approach |
|--------|------------------------|-----------------|
| **Base Image** | python:3.12-slim | google-cloud-sdk:slim |
| **Memory Usage** | ~1.2 GB (loads file in RAM) | ~50 MB (streams) |
| **Code Required** | ~50 lines Python | ~10 lines bash |
| **Retry Logic** | Manual (not implemented) | Built-in |
| **Idempotency** | Manual (not implemented) | Built-in |
| **Complexity** | Higher | Lower |
| **Container Size** | ~100 MB | ~200 MB |

---

## Implementation Steps

### Step 1: Create Download Script

**File:** `src/github_archive/scripts/download.sh`

```bash
#!/bin/bash
set -euo pipefail

# Configuration
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project)}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-data-pipeline}"
GITHUB_ARCHIVE_BASE="https://data.gharchive.org"

# Calculate target filename (previous hour)
if date +%s >/dev/null 2>&1; then
    # Linux date
    TARGET_HOUR=$(date -u -d '1 hour ago' '+%Y-%m-%-H')
else
    # macOS date
    TARGET_HOUR=$(date -u -v -1H '+%Y-%m-%-H')
fi

FILENAME="${TARGET_HOUR}.json.gz"
GCS_PATH="gs://${BUCKET_NAME}/github-archive/raw/${FILENAME}"
SOURCE_URL="${GITHUB_ARCHIVE_BASE}/${FILENAME}"

echo "=== GitHub Archive Download ==="
echo "Target file: ${FILENAME}"
echo "Source URL: ${SOURCE_URL}"
echo "GCS Path: ${GCS_PATH}"

# Check if file already exists (idempotency)
if gsutil -q stat "${GCS_PATH}" 2>/dev/null; then
    echo "File already exists in GCS, skipping download"
    exit 0
fi

# Download using curl + pipe to gsutil (streams automatically)
# Note: gsutil cp does NOT support HTTP URLs, must use curl for HTTP
echo "Starting download..."
curl -fsSL "${SOURCE_URL}" | gsutil cp - "${GCS_PATH}"

# Verify upload
FILE_SIZE=$(gsutil du "${GCS_PATH}" | awk '{print $1}')
echo "=== Download Complete ==="
echo "File: ${GCS_PATH}"
echo "Size: ${FILE_SIZE} bytes"
```

### Step 2: Create Dockerfile

**File:** `src/github_archive/Dockerfile`

```dockerfile
FROM gcr.io/google.com/cloud-sdk:slim

# Install additional utilities
RUN apt-get update && apt-get install -y \
    coreutils \
    && rm -rf /var/lib/apt/lists/*

# Copy download script
COPY scripts/download.sh /scripts/download.sh
RUN chmod +x /scripts/download.sh

# Set environment variables
ENV BUCKET_NAME=""
ENV PROJECT_ID=""

# Set entrypoint
ENTRYPOINT ["/scripts/download.sh"]
```

### Step 3: Deploy

```bash
# Build image
gcloud builds submit --tag gcr.io/$PROJECT_ID/github-archive-downloader .

# Deploy Cloud Run Job
gcloud run jobs create github-archive-downloader \
    --image gcr.io/$PROJECT_ID/github-archive-downloader \
    --region $REGION \
    --memory 512Mi \
    --cpu 1 \
    --timeout 30m \
    --set-env-vars BUCKET_NAME=$PROJECT_ID-data-pipeline,PROJECT_ID=$PROJECT_ID \
    --service-account=sa-hn-fetcher@$PROJECT_ID.iam.gserviceaccount.com
```

---

## Monitoring & Logging

### Structured Logging

```bash
echo "{\"level\":\"info\",\"message\":\"download_started\",\"filename\":\"${FILENAME}\"}"
echo "{\"level\":\"info\",\"message\":\"download_completed\",\"file_size\":\"${FILE_SIZE}\",\"gcs_path\":\"${GCS_PATH}\"}"
```

### Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| `job_duration_ms` | Total execution time | < 600s (10 min) |
| `file_size_bytes` | Downloaded file size | ~1.2 GB |
| `download_success` | Job succeeded | 100% |
| `download_skipped` | File already existed | Idempotent check |

---

## Advantages Over Current Implementation

| Issue | Current (Python) | gsutil Solution |
|-------|------------------|-----------------|
| Memory error risk | High (loads 1.2 GB in RAM) | None (streams) |
| No idempotency | Downloads every time | Skips if exists |
| No retry | Fails immediately | Automatic retry |
| Complexity | Flask + Python code | Simple bash script |
| Maintenance | Python dependencies | No extra deps |

---

## Rollback Plan

If gsutil approach fails, keep Flask app for manual use:

```bash
# Manual trigger (if needed)
curl -X POST https://github-archive-processor-{REGION}/tasks/download
```
