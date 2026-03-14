# download.sh

## 1. Overview

`download.sh` is the core script for Phase 1 of the GitHub Archive pipeline. It downloads a single hourly GitHub Archive `.json.gz` file from `data.gharchive.org` and streams it directly into a GCS landing bucket. The script is designed to run inside a Cloud Run Job container, triggered once per hour by Cloud Scheduler.

Key behaviours:
- Downloads the file for the **previous hour** (UTC), so a run at 14:00 UTC fetches the 13:00 file.
- Streams data directly from the source URL into GCS (`curl | gsutil cp -`), avoiding local disk usage.
- Is **idempotent**: if the target object already exists in GCS, the script exits successfully without re-downloading.

## 2. Prerequisites

| Requirement | Detail |
|---|---|
| **Runtime image** | Must run inside a container that provides `gcloud`, `gsutil`, `curl`, and GNU `date` (the companion Dockerfile satisfies this). |
| **Authentication** | The Cloud Run Job service account must have `roles/storage.objectAdmin` (or at minimum `storage.objects.create` and `storage.objects.get`) on the landing bucket. |
| **Environment variables** | `PROJECT_ID` (required unless `gcloud config` is set), `ENVIRONMENT` (optional, defaults to `dev`), `BUCKET_NAME` (optional, auto-derived as `{PROJECT_ID}-{ENVIRONMENT}-github-archive-landing`). |
| **Network access** | Outbound HTTPS to `data.gharchive.org` and `storage.googleapis.com`. |

## 3. Upstream & Downstream Dependencies

```
Upstream
--------
Cloud Scheduler (hourly cron)
  --> Cloud Run Job (runs this script inside the Dockerfile container)

Downstream
----------
GCS Landing Bucket: gs://{PROJECT_ID}-{ENVIRONMENT}-github-archive-landing/github-archive/raw/
  --> Phase 2 picks up the .json.gz files from this bucket for further processing
```

- **Upstream**: Cloud Scheduler triggers the Cloud Run Job on an hourly schedule. No other input is required; the filename is derived from the current UTC time.
- **Downstream**: The uploaded `.json.gz` file lands at `gs://{BUCKET}/github-archive/raw/{YYYY-MM-DD-H}.json.gz`. Phase 2 of the pipeline consumes files from this path.

## 4. IAM & Service Accounts

**Runtime identity**: `{env}-github-archive-downloader@{project}.iam.gserviceaccount.com`

This script runs inside a Cloud Run Job that uses the downloader SA. The SA requires:

| Role | Why |
|------|-----|
| `roles/storage.objectUser` | Read/write GCS objects in the landing bucket (`gsutil cp`, `gsutil stat`, `gsutil du`) |
| `roles/logging.logWriter` | Emit structured logs from the Cloud Run Job |
| `roles/artifactregistry.reader` | Pull the container image from Artifact Registry at job startup |

These roles are granted in `service_accounts.tf` and `iam.tf`.

**Cross-reference**: See `learnings/phase4_deployment_issues.md` (Issue 15) for how stale deleted SAs can block IAM updates on datasets, and `learnings/github_actions_ci_issues.md` (Issue 7) for how ephemeral CI runners require remote state so IAM-dependent resources are tracked correctly.

## 5. Code Walkthrough

1. **Shell options** (line 11): `set -euo pipefail` enables strict error handling -- the script exits on any command failure, undefined variable, or pipe error.

2. **Configuration block** (lines 17-23):
   - `ENVIRONMENT` defaults to `dev`.
   - `PROJECT_ID` falls back to the value from `gcloud config` if not explicitly set.
   - `BUCKET_NAME` is auto-derived using the pattern `{PROJECT_ID}-{ENVIRONMENT}-github-archive-landing` unless overridden.
   - `FILENAME` is computed as the previous hour in UTC using `date -u -d '-1 hour'` with the format `YYYY-MM-DD-H.json.gz` (non-zero-padded hour via `%-H`).
   - `SOURCE_URL` and `TARGET_PATH` are assembled from the filename.

3. **Idempotency check** (lines 36-39): `gsutil -q stat` checks whether the target object already exists in GCS. If it does, the script logs a message and exits with code 0, preventing duplicate downloads.

4. **Download and upload** (lines 49-55): `curl -fsSL` fetches the file from GitHub Archive and pipes the output directly to `gsutil cp -`, which streams it to the GCS target path without writing to local disk. On success, the script logs the file size via `gsutil du`. On failure, it prints an error to stderr and exits with code 1.
