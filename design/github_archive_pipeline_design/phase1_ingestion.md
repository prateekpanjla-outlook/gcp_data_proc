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

---

## High-Level Flow

```
GitHub Archive (https://data.gharchive.org/)
        │
        │ Cloud Scheduler (cron: 30 * * * *)
        ▼
Cloud Run Job: hn-fetcher
        │ downloads file
        ▼
Cloud Storage: gs://{project}-data-pipeline/github-archive/raw/YYYY-MM-DD-HH.json.gz
```

---

## ENTRY Conditions (Pre-requirements)

### Infrastructure Requirements

| Requirement | Type | Description |
|-------------|------|-------------|
| `PROJECT_ID` | Env Var | Google Cloud project ID |
| `BUCKET_NAME` | Env Var | Target Cloud Storage bucket name |
| `REGION` | Env Var | GCP region (e.g., `us-central1`) |
| Cloud Scheduler | Resource | Must be configured with hourly schedule |
| Cloud Run Job | Resource | `hn-fetcher` job must be deployed |
| Service Account | IAM | Must have `Storage.ObjectCreator` role |

### External Dependencies

| Dependency | URL | Availability |
|------------|-----|--------------|
| GitHub Archive | `https://data.gharchive.org/` | Public, no auth required |
| File Format | `{YYYY}-{MM}-{DD}-{HH}.json.gz` | Files available within 1-2 hours |

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
| `compressed_data` | Valid gzip bytes | Step 4 |
| `BUCKET_NAME` | Existing bucket | Terraform/Manual |
| `PROJECT_ID` | Valid project | Environment |
| Service Account | Has `roles/storage.objectCreator` | IAM |

**Exit Conditions:**
| Condition | Value | Verification |
|-----------|-------|-------------|
| Upload Success | `blob.exists() == True` | `blob.upload_from_string()` |
| File Size | `blob.size == len(compressed_data)` | Integrity check |
| Content Type | `blob.content_type == "application/gzip"` | Correct MIME type |

**Failure Modes:**
| Error | Cause | Action |
|-------|-------|--------|
| `NotFound` | Bucket doesn't exist | Create bucket first |
| `PermissionDenied` | SA lacks permissions | Grant `Storage.ObjectCreator` |
| `Network Error` | Upload interruption | Retry entire upload |

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

**File:** [`src/github_archive/main.py`](../../src/github_archive/main.py)
**Function:** `download_github_archive()` (lines 127-176)

```python
@app.route("/tasks/download", methods=["GET", "POST"])
def download_github_archive():
    hours_ago = int(request.args.get("hours_ago", 1))
    target_time = datetime.utcnow() - timedelta(hours=hours_ago)
    filename = target_time.strftime("%Y-%m-%d-%-H.json.gz")
    url = f"https://data.gharchive.org/{filename}"

    # Download
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

---

## IMPROVEMENTS NEEDED

### 1. Streaming Download (Memory Issue)

**Current Problem:** Downloads entire file (~1.2 GB) into memory.

**Solution:**
```python
# Stream directly to GCS without loading entire file in memory
from google.cloud import storage

bucket = storage.Client().bucket(BUCKET_NAME)
blob = bucket.blob(f"github-archive/raw/{filename}")

# Stream from URL to GCS
with urlopen(url) as response:
    with blob.open("wb") as f:
        while chunk := response.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)
```

### 2. Better Retry Logic

**Current:** No retry for HTTP failures.

**Solution:**
```python
from src.shared.retry import retry_with_exponential_backoff

@retry_with_exponential_backoff(
    max_attempts=6,  # Try for up to 30 minutes
    wait_min=60,     # Start at 1 minute
    wait_max=300,    # Max 5 minutes
    multiplier=2
)
def download_from_github_archive(url: str) -> bytes:
    with urlopen(url, timeout=300) as response:
        return response.read()
```

### 3. File Existence Check

**Current:** Assumes file needs to be downloaded every time.

**Solution:**
```python
# Check if file already exists in GCS
blob = bucket.blob(f"github-archive/raw/{filename}")
if blob.exists():
    logger.info(f"File {filename} already exists, skipping download")
    return {"status": "already_exists"}
```

---

## MONITORING

### Metrics to Track

| Metric | Description | Target |
|--------|-------------|--------|
| `download_duration_ms` | Time to download file | < 300 seconds |
| `file_size_bytes` | Size of downloaded file | ~1.2 GB |
| `upload_duration_ms` | Time to upload to GCS | < 60 seconds |
| `download_success` | Download succeeded | 100% |
| `download_retries` | Number of retries | < 6 |

### Alert Conditions

| Condition | Severity | Action |
|-----------|----------|--------|
| Download fails for > 30 min | Warning | Investigate GitHub Archive status |
| File size < 100 MB | Warning | Possible partial download |
| Upload fails | Error | Check GCS bucket & permissions |

---

## TERRAFORM CONFIGURATION

**File:** [`terraform/scheduler.tf`](../../terraform/scheduler.tf)

```hcl
resource "google_cloud_scheduler_job" "github_archive_downloader" {
  name        = "github-archive-downloader"
  schedule    = "30 * * * *"  # 30 minutes past each hour
  time_zone   = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{project}/jobs/hn-fetcher:run"

    body = base64encode(jsonencode({
      hours_ago = 1,
      bucket_name = "{project}-data-pipeline"
    }))

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 2
    min_backoff = "10s"
  }
}
```
