# Project Learnings & Operational Notes

This document captures key learnings, cost calculations, and operational commands for the GitHub Archive data pipeline project.

---

## Cost Optimization

### Cloud Storage Lifecycle Management

#### Problem
With 90-day retention, storage would grow significantly:
- Average file size: ~35 MB/hour
- Daily growth: 35 MB × 24 = ~840 MB/day
- 90-day retention: 840 MB × 90 = ~75 GB

This would exceed the 5 GB free tier limit and incur costs.

#### Solution
Set lifecycle rule to delete files after 6 days:
- Maximum storage: 840 MB × 6 = ~5 GB (within free tier)

#### Command Used

```bash
# Create lifecycle configuration
cat > /tmp/lifecycle.json << 'EOF'
{
  "lifecycle": {
    "rule": [
      {
        "action": {
          "type": "Delete"
        },
        "condition": {
          "age": 6,
          "matchesStorageClass": ["REGIONAL"]
        }
      }
    ]
  }
}
EOF

# Apply to bucket
gsutil lifecycle set /tmp/lifecycle.json gs://YOUR_BUCKET_NAME/

# Verify
gsutil lifecycle get gs://YOUR_BUCKET_NAME/
```

#### Terraform Configuration

```hcl
# variables.tf
variable "bucket_lifecycle_days" {
  description = "Number of days before landing bucket files are deleted"
  type        = number
  default     = 6

  validation {
    condition     = var.bucket_lifecycle_days >= 1
    error_message = "Lifecycle days must be at least 1."
  }
}

# storage.tf
resource "google_storage_bucket" "github_archive_landing" {
  name          = local.github_archive.bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment == "dev" ? true : var.force_destroy

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = var.bucket_lifecycle_days
    }
    action {
      type = "Delete"
    }
  }
}
```

---

## Google Cloud Free Tier Limits (2025)

| Service | Free Tier Limit | Current Usage |
|---------|-----------------|---------------|
| **Cloud Storage** | 5 GB/month (US regions only) | ~491 MB (within limit) |
| **Cloud Run** | 360K GB-sec memory, 180K vCPU-sec/month | ~32K GB-sec, ~65K vCPU-sec |
| **Cloud Scheduler** | 3 jobs/month | 1 job |

### Cloud Run Cost Calculation

```
Per execution:
  - Memory: 512 MiB × ~90 seconds = 45 GB-seconds
  - vCPU: 1 vCPU × ~90 seconds = 90 vCPU-seconds

Monthly (24 executions/day × 30 days = 720 executions):
  - Memory: 45 × 720 = 32,400 GB-seconds  → 9% of free tier
  - vCPU: 90 × 720 = 64,800 vCPU-seconds → 36% of free tier
```

### Storage Cost Projection

| Retention Days | Max Storage | Free Tier (5 GB) |
|----------------|-------------|------------------|
| 1 day | ~840 MB | ✅ |
| 6 days | ~5 GB | ✅ At limit |
| 7 days | ~6 GB | ❌ $0.02/GB overage |
| 30 days | ~25 GB | ❌ ~$0.40/month |
| 90 days | ~75 GB | ❌ ~$1.40/month |

> **Note:** Regional storage pricing in us-central1 is approximately $0.02 per GB/month.

---

## Operational Commands

### Check Bucket Size

```bash
# List files with sizes
gsutil ls -lah gs://BUCKET_NAME/path/

# Count objects
gsutil ls gs://BUCKET_NAME/path/ | wc -l

# Get total size
gsutil du -sh gs://BUCKET_NAME/path/
```

### Check Cloud Run Job Executions

```bash
# List jobs
gcloud run jobs list --region=us-central1

# List executions for a job
gcloud run jobs executions list --region=us-central1 --job=JOB_NAME --limit=20

# View execution logs
gcloud run jobs executions logs read EXECUTION_NAME --region=us-central1

# View logs via Cloud Logging
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=JOB_NAME" --limit=20
```

### Check Cloud Scheduler

```bash
# List scheduler jobs
gcloud scheduler jobs list --location=us-central1

# Describe a scheduler job
gcloud scheduler jobs describe JOB_NAME --location=us-central1

# Check job history
gcloud scheduler jobs describe JOB_NAME --location=us-central1 --format=json | jq '.lastAttemptTime'
```

### Lifecycle Management

```bash
# Get current lifecycle configuration
gsutil lifecycle get gs://BUCKET_NAME/

# Set lifecycle configuration
gsutil lifecycle set config.json gs://BUCKET_NAME/

# Clear lifecycle configuration
gsutil lifecycle clear gs://BUCKET_NAME/
```

---

## Phase 1 Status Summary

### Current Deployment (as of 2026-03-06)

| Component | Name | Status |
|-----------|------|--------|
| **Bucket** | dev-dataprocessing-489305-dev-github-archive-landing | ✅ Active |
| **Cloud Run Job** | dev-github-archive-download-gsutil | ✅ Running |
| **Cloud Scheduler** | dev-github-archive-download-job | ✅ Enabled (30 * * * * UTC) |
| **Service Account** | dev-github-archive-downloader@... | ✅ Active |

### Data Ingestion

```
Files ingested: 13 objects
Total size: ~491 MB
Frequency: Hourly (at 30 minutes past each hour)
Retention: 6 days (lifecycle rule)
```

---

## Architecture Decisions

### IAM: Project-Level vs Bucket-Level

**Current:** Project-level `roles/storage.objectUser` (over-permissive)

**Recommended:** Bucket-level permissions for least privilege
- Downloader SA: Landing bucket → `roles/storage.objectCreator` (write-only)
- Processor SA: Landing bucket → `roles/storage.objectViewer` (read-only)

**Status:** TODO - Refactor IAM to bucket-level permissions

---

## Common Issues & Solutions

### Issue: Terraform OAuth2 "invalid_grant"

**Error:**
```
oauth2: "invalid_grant" "Account has been deleted"
```

**Solution:**
```bash
# Re-authenticate
gcloud auth login
gcloud auth application-default login

# Or use service account impersonation
gcloud auth activate-service-account --key-file=key.json
```

### Issue: Files Not Appearing in Bucket

**Diagnosis:**
```bash
# Check scheduler status
gcloud scheduler jobs describe JOB_NAME --location=REGION

# Check recent executions
gcloud run jobs executions list --region=REGION --job=JOB_NAME --limit=5

# Check execution logs
gcloud logging read "resource.type=cloud_run_job" --limit=20
```

---

---

## Future Enhancements

### BigQuery Nested Schema Support

#### Current State
- **Flattened schema**: We flatten nested JSON structures into single-level columns
- **Payload handling**: Only common payload fields are extracted (ref, push_id, size, etc.)
- **Complex nested data**: Full payload objects (issue, pull_request, user, labels, etc.) are NOT stored

#### Proposed: BigQuery Nested/Repeated Fields

BigQuery supports nested (STRUCT) and repeated (ARRAY) fields, which would preserve the complete GitHub Archive structure without flattening.

**Example Nested Schema:**
```sql
CREATE TABLE `project.dataset.github_events_nested` (
  event_id STRING,
  event_type STRING,
  created_at TIMESTAMP,

  -- Nested actor (STRUCT)
  actor STRUCT<
    id INT64,
    login STRING,
    display_login STRING,
    avatar_url STRING
  >,

  -- Nested repo (STRUCT)
  repo STRUCT<
    id INT64,
    name STRING,
    url STRING
  >,

  -- Nested payload with arrays
  payload STRUCT<
    action STRING,
    issue STRUCT<
      id INT64,
      title STRING,
      labels ARRAY<STRUCT<
        name STRING,
        color STRING
      >>
    >
  >
)
```

**Benefits:**
- Preserve complete GitHub data (50+ fields vs 15-20)
- More flexible querying with dot notation
- No data loss from flattening

**Trade-offs:**
- Larger storage requirements
- Slightly slower query performance
- More complex schema management

**Decision:** Keep flattened schema for Phase 2. Consider nested schema when business requirements justify the complexity.

**Reference:** [BigQuery Nested & Repeated Fields](https://cloud.google.com/bigquery/docs/nested-repeated)

---

## References

- [Google Cloud Free Tier](https://docs.cloud.google.com/free/docs/free-cloud-features)
- [Cloud Storage Pricing](https://cloud.google.com/storage/pricing)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Cloud Scheduler Pricing](https://cloud.google.com/scheduler/pricing)
- [Lifecycle Management](https://cloud.google.com/storage/docs/lifecycle)
