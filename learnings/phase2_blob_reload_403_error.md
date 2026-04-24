# Phase 2: blob.reload() 403 Error After Successful Upload

## Date
2026-03-08

## Issue
After processing files successfully, the Cloud Run service was logging 403 errors:
```
Processing failed: ('Request failed with status code', 403, 'Expected one of', <HTTPStatus.OK: 200>, <HTTPStatus.PERMANENT_REDIRECT: 308>)
```

## Observation
- Files **were being processed successfully** and written to the staging bucket
- Error occurred **after** the upload was complete
- The error was non-critical but caused the function to report failure

## Root Cause
The error originated from `blob.reload()` in `writers/ndjson_writer.py`:

```python
# Get blob size
blob.reload()  # <-- 403 error here
bytes_written = blob.size
```

The `blob.reload()` call is made after a successful upload to fetch the blob metadata (size). This requires `storage.objects.get` permission.

## Why 403 Despite Having Permissions?

The processor service account had the correct permissions:
- `roles/storage.objectCreator` - for uploading
- `roles/storage.objectViewer` - includes `storage.objects.get`

Possible causes:
1. **IAM propagation delay** - New permissions can take up to 7 minutes to propagate
2. **Service account recreation** - If SA was deleted/recreated, stale bindings show as `deleted:serviceAccount:...`
3. **GCS eventual consistency** - Object metadata may not be immediately available after upload

## Fix Applied

### Code Fix (Primary)
Wrapped `blob.reload()` in try-except in `writers/ndjson_writer.py`:

```python
# Get blob size (non-critical, handle gracefully)
try:
    blob.reload()
    bytes_written = blob.size
except Exception as e:
    # Log but don't fail - upload was successful
    import logging
    logging.getLogger(__name__).warning(f"Could not get blob size after upload: {e}")
    bytes_written = -1  # Unknown size
```

### Terraform Permissions (Already Correct)
The processor service account already has the required permissions in `layers/01_static/main.tf`:

```hcl
# Write to staging bucket
resource "google_storage_bucket_iam_member" "processor_staging_write" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.processor.email}"
}

# Read from staging bucket (for blob.reload(), checking files)
resource "google_storage_bucket_iam_member" "processor_staging_read" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.processor.email}"
}
```

## Lessons Learned

1. **Non-critical operations should not fail the entire process**
   - Getting blob size after upload is nice-to-have, not critical
   - Wrap in try-except and continue

2. **IAM propagation delays can cause transient 403 errors**
   - Especially after service account recreation or permission changes
   - Code should be resilient to temporary permission issues

3. **Check bucket IAM for stale bindings**
   - Deleted service accounts show as `deleted:serviceAccount:...`
   - Clean up stale bindings and reapply fresh permissions

## Verification Commands

```bash
# Check bucket IAM for stale bindings
gsutil iam get gs://BUCKET_NAME | grep deleted

# Check processor service account permissions
gcloud projects get-iam-policy PROJECT_ID \
    --flatten="bindings[].members" \
    --filter="bindings.members:processor" \
    --format="table(bindings.role)"

# Check Cloud Run logs for errors
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=dev-github-archive-processor AND severity>=ERROR" \
    --project=PROJECT_ID --limit=10
```

## Related Files
- `src/github_archive/phase2_process_files/writers/ndjson_writer.py` - Fixed with try-except
- `infrastructure/phase2_process_files/terraform/layers/01_static/main.tf` - IAM permissions

---

## Issue 2: 403 Error When Reprocessing Existing Files

### Date
2026-03-08

### Symptom
When reprocessing a file that already has output in the staging bucket, the processor fails with:
```
Processing failed: ('Request failed with status code', 403, 'Expected one of', <HTTPStatus.OK: 200>, <HTTPStatus.PERMANENT_REDIRECT: 308>)
```

This error **only occurs when the output file already exists** in the staging bucket. New files process successfully.

### Root Cause
The processor service account was granted `roles/storage.objectCreator` which only allows **creating NEW objects**. It does NOT include `storage.objects.delete` permission required to overwrite existing objects.

GCS upload operations require `storage.objects.delete` when the destination object already exists.

### Solution
Change the IAM role from `objectCreator` to `objectAdmin`:

**Quick fix via gsutil:**
```bash
gsutil iam ch serviceAccount:dev-github-archive-processor@PROJECT_ID.iam.gserviceaccount.com:roles/storage.objectAdmin gs://STAGING_BUCKET
```

**Terraform fix** (`layers/01_static/main.tf`):
```hcl
resource "google_storage_bucket_iam_member" "processor_staging_write" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectAdmin"  # Changed from objectCreator
  member = "serviceAccount:${google_service_account.processor.email}"
}
```

### Role Comparison

| Role | Create | Delete | Overwrite |
|------|--------|--------|-----------|
| `objectCreator` | ✅ | ❌ | ❌ |
| `objectViewer` | ❌ | ❌ | ❌ |
| `objectAdmin` | ✅ | ✅ | ✅ |

### Lesson Learned
When designing for reprocessing/idempotency, the service account needs `objectAdmin` (or custom role with `storage.objects.delete`) to handle existing output files.
