# Phase 1 Deployment Status and Next Steps

## Current Status

✅ **Completed:**
- Terraform installed (v1.14.6)
- Terraform initialized
- Variables updated to allow "test" environment
- Old Terraform state cleaned up
- APIs enabled (iam.googleapis.com, cloudresourcemanager.googleapis.com)
- Terraform plan shows 8 resources to create

⏸️ **Waiting:**
- APIs need time to propagate (can take 1-5 minutes)
- Ready to run `terraform apply` when APIs are active

## What Will Be Created (Phase 1: Ingestion)

**8 Resources:**

1. **GCS Bucket** - `beaming-glyph-489707-b8-test-github-archive-landing`
   - Landing zone for raw GitHub Archive files
   - Lifecycle: Delete after 6 days
   - Location: US-CENTRAL1

2. **Cloud Run Job** - `test-github-archive-download-gsutil`
   - Downloads GitHub Archive files using gsutil
   - Memory: 512Mi, CPU: 1
   - Timeout: 30 minutes
   - Image: `gcr.io/beaming-glyph-489707-b8/github-archive-downloader:latest`

3. **Scheduler Job** - `test-github-archive-download-job`
   - Triggers Cloud Run Job hourly
   - Schedule: 30 minutes past every hour
   - Timezone: UTC

4. **Service Account** - `test-github-archive-downloader`
   - Used by Cloud Run Job
   - Permissions: Storage Object User, Log Writer

5. **Service Account** - `test-scheduler`
   - Used by Cloud Scheduler
   - Permissions: Run Invoker (via service agent)

6. **IAM Member** - Storage permissions for downloader
7. **IAM Member** - Logging permissions for downloader
8. **IAM Member** - Run Invoker for scheduler

## Next Steps

### Step 1: Wait for API Propagation (1-5 minutes)

The APIs we just enabled need time to propagate across GCP. You can verify they're ready by running:

```bash
cd C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\github_archive\phase1_ingestion\terraform

# Set authentication
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json'

# Test if APIs are ready
terraform plan -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1"
```

**If you see "Cloud Resource Manager API has not been used"**, wait another minute and retry.

### Step 2: Apply When Ready

Once the plan completes without API errors:

```bash
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1" -auto-approve
```

Or with manual approval:
```bash
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1"
# Type 'yes' when prompted
```

### Step 3: Verify Deployment

After apply completes:

```bash
# Check GCS bucket
gsutil ls gs://beaming-glyph-489707-b8-test-github-archive-landing

# Check Cloud Run Job
gcloud run jobs list --project=beaming-glyph-489707-b8 --region=us-central1

# Check Scheduler Job
gcloud scheduler jobs list --project=beaming-glyph-489707-b8 --location=us-central1
```

### Step 4: Deploy Remaining Phases

After Phase 1 succeeds, continue with:

**Phase 2: Processing**
```bash
cd ../../phase2_process_files/terraform/layers/01_static
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1" -var="landing_bucket_name=beaming-glyph-489707-b8-test-github-archive-landing"

# Repeat for layers 02_first_time and 03_operational
```

**Phase 3: Loading**
```bash
cd ../../../phase3_loadbigquery/terraform/layers/01_static
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1" -var="staging_bucket_name=beaming-glyph-489707-b8-test-github-archive-staging"

# Repeat for layers 02_first_time and 03_operational
```

## Troubleshooting

### "API has not been used" Error
**Solution:** Wait 1-2 more minutes for API propagation, then run plan again.

### "Permission denied" Error
**Solution:** Verify service account has correct roles:
```powershell
.\verify-iam-setup.ps1
```

### "Authentication failed" Error
**Solution:** Set environment variable again:
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json'
```

## Summary

We're paused before apply, waiting for API propagation. Once ready, the deployment will create 8 resources for Phase 1 (Ingestion). You can proceed when ready!
