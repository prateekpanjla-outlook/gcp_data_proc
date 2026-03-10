# Missing Permissions Discovered During Deployment

## Summary
During the deployment of Phase 1: Ingestion infrastructure, we encountered several missing permissions that needed to be added to the terraform deployer service account.

## Missing Permissions Found

### 1. **roles/resourcemanager.projectIamAdmin**
- **Error**: `Policy update access denied` when creating IAM bindings
- **Required For**: Granting IAM permissions to service accounts created by Terraform
- **Status**: ✅ Added to setup-complete.ps1
- **Already In**: infrastructure/setup-terraform-deployer.sh (line 156)

### 2. **roles/iam.serviceAccountUser**
- **Error**: `Permission 'iam.serviceaccounts.actAs' denied`
- **Required For**: Impersonating service accounts when creating Cloud Run Jobs
- **Why It's Needed**: When Terraform creates a Cloud Run Job that uses a service account, it needs permission to "act as" that service account
- **Status**: ✅ Added to setup-complete.ps1
- **Already In**: infrastructure/setup-terraform-deployer.sh (line 157)

### 3. **APIs That Were Missing**
The initial `enable-apis.ps1` script only enabled 2 APIs. We needed to add:

- `run.googleapis.com` - Cloud Run Jobs
- `cloudscheduler.googleapis.com` - Cloud Scheduler
- `eventarc.googleapis.com` - Eventarc triggers
- `pubsub.googleapis.com` - Pub/Sub (used by Eventarc)
- `bigquery.googleapis.com` - BigQuery
- `cloudfunctions.googleapis.com` - Cloud Functions
- `cloudbuild.googleapis.com` - Cloud Build
- `artifactregistry.googleapis.com` - Artifact Registry
- `logging.googleapis.com` - Cloud Logging
- `monitoring.googleapis.com` - Cloud Monitoring
- `secretmanager.googleapis.com` - Secret Manager
- `compute.googleapis.com` - Compute API (for VPC access)
- `serviceusage.googleapis.com` - Service Usage API
- `servicemanagement.googleapis.com` - Service Management API

**Status**: ✅ Updated enable-apis.ps1 to include all 14 APIs

## Current Deployment Status

### ✅ Successfully Created (5 resources):
1. GCS Bucket: `beaming-glyph-489707-b8-test-github-archive-landing`
2. Service Account: `test-github-archive-downloader`
3. Service Account: `test-scheduler`
4. IAM Binding: Storage Object User for downloader
5. IAM Binding: Logging Log Writer for downloader
6. IAM Binding: Service Account Token Creator for scheduler

### ❌ Blocked by Missing Container Image (3 resources):
1. Cloud Run Job: `test-github-archive-download-gsutil`
   - **Issue**: Container image `gcr.io/beaming-glyph-489707-b8/github-archive-downloader:latest` doesn't exist
   - **Solution**: Need to build and push the container image

2. Cloud Run Job IAM Binding: Scheduler invoker
   - **Blocked By**: Depends on Cloud Run Job

3. Cloud Scheduler Job: `test-github-archive-download-job`
   - **Blocked By**: Depends on Cloud Run Job

## Updated Scripts

### setup-complete.ps1
✅ Now includes:
- All 17 required GCP APIs
- All 15 required IAM roles including the critical `roles/iam.serviceAccountUser`

### enable-apis.ps1
✅ Now includes:
- 14 APIs (was only 2)
- Better error handling and output

### infrastructure/setup-terraform-deployer.sh
✅ Already had all required permissions
- Includes `roles/iam.serviceAccountUser` (line 157)
- Includes `roles/resourcemanager.projectIamAdmin` (line 156)

## Next Steps

To complete the deployment, you need to:

1. **Build the container image** for the github-archive-downloader
   ```bash
   # Navigate to the application code directory
   cd applications/github-archive-downloader

   # Build and push the image
   gcloud builds submit --tag gcr.io/beaming-glyph-489707-b8/github-archive-downloader:latest
   ```

2. **Retry terraform apply**
   ```bash
   cd infrastructure/github_archive/phase1_ingestion/terraform
   terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1"
   ```

## Lessons Learned

1. **Pre-flight Validation**: Always check APIs and permissions BEFORE running terraform apply
2. **Service Account Impersonation**: When creating Cloud Run Jobs with service accounts, the deployer needs `roles/iam.serviceAccountUser`
3. **Project IAM Permissions**: When creating IAM bindings, the deployer needs `roles/resourcemanager.projectIamAdmin`
4. **API Propagation**: After enabling APIs, wait 2-3 minutes for them to propagate across GCP

## Pre-flight Check Script

Created `preflight-check.ps1` that validates:
- ✅ All required APIs are enabled
- ✅ All required IAM roles are granted
- ✅ Service account key exists and can authenticate
- ✅ Terraform is installed

Run this before any deployment:
```powershell
.\preflight-check.ps1
```
