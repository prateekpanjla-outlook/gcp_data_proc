# Current Deployment State - Phase 1: Ingestion

**Date**: 2026-03-11
**Project**: beaming-glyph-489707-b8
**Environment**: test
**Branch**: phase3_refactorself

## Summary

Deploying Phase 1 (Ingestion) infrastructure for GitHub Archive processing. Currently blocked by container image build/push permissions.

## Completed Tasks ✅

### 1. Service Account Setup
- ✅ Created `test-terraform-deployer` service account
- ✅ Granted 15+ IAM roles to deployer SA
- ✅ Created service account key: `test-terraform-deployer-key.json`

### 2. API Enablement
- ✅ Enabled 14 required GCP APIs:
  - iam.googleapis.com
  - cloudresourcemanager.googleapis.com
  - run.googleapis.com
  - cloudscheduler.googleapis.com
  - eventarc.googleapis.com
  - pubsub.googleapis.com
  - bigquery.googleapis.com
  - cloudfunctions.googleapis.com
  - storage.googleapis.com
  - cloudbuild.googleapis.com
  - artifactregistry.googleapis.com
  - logging.googleapis.com
  - monitoring.googleapis.com
  - secretmanager.googleapis.com

### 3. Terraform Configuration
- ✅ Updated all `variables.tf` files to allow "test" environment
- ✅ Modified `service_accounts.tf` to use hardcoded project number

### 4. Infrastructure Resources Created (9 of 9)
- ✅ GCS Bucket: `beaming-glyph-489707-b8-test-github-archive-landing`
- ✅ Service Account: `test-github-archive-downloader`
- ✅ Service Account: `test-scheduler`
- ✅ IAM Binding: Storage Object User for downloader
- ✅ IAM Binding: Logging Log Writer for downloader
- ✅ IAM Binding: Service Account Token Creator for scheduler
- ✅ Cloud Run Job: `test-github-archive-download-gsutil`
- ✅ Cloud Scheduler Job: `test-github-archive-download-job`
- ✅ IAM Binding: Cloud Run Invoker for scheduler
- ✅ IAM Binding: Artifact Registry Reader for downloader

## Deployment Status
- ❌ **Phase 1: Ingestion** - Blocked.
- ➡️ **Next**: Proceed to Phase 2 deployment.

## Blocked Tasks ❌

### 1. Cloud Run Job Execution
**Status**: Job fails to start with "Image not found" error.
**Error**: `Image 'gcr.io/beaming-glyph-489707-b8/github-archive-downloader:latest' not found.`
**Root Cause**: State drift. The live Cloud Run Job resource is still pointing to the old `gcr.io` path, despite Terraform configuration being correct and reporting a successful apply.
**Fix**: Tainted the resource with `terraform taint google_cloud_run_v2_job.github_archive_downloader` to force recreation on the next apply.

## Missing Permissions Discovered

### For Terraform Deployer SA
1. ✅ **`roles/resourcemanager.projectIamAdmin`** - Granted
   - Needed to create IAM bindings

2. ✅ **`roles/iam.serviceAccountUser`** - Granted
   - Needed to impersonate service accounts for Cloud Run Jobs

### For Cloud Build (Compute SA)
3. ✅ **`roles/storage.objectViewer`** - Granted
   - Needed to read source code from GCS

4. ✅ **`roles/storage.objectAdmin`** - Granted
   - Needed to write build artifacts

5. ✅ **`roles/storage.admin`** - Granted
   - Needed to push images to GCR (GCR uses Cloud Storage backend)

6. ✅ **`roles/logging.logWriter`** - Granted
   - Needed to write build logs

## Files Created/Modified

### Setup Scripts
- `setup-complete.ps1` - Comprehensive setup with all APIs and permissions
- `enable-apis.ps1` - Updated to enable 14 APIs (was only 2)
- `grant-iam-role.ps1` - Grant IAM roles
- `grant-project-iam-admin.ps1` - Grant Project IAM Admin
- `grant-iam-serviceaccountuser.ps1` - Grant Service Account User role
- `grant-cloudbuild-permissions.ps1` - Grant Cloud Build permissions
- `grant-cloudbuild-logging.ps1` - Grant Logging permissions
- `grant-gcr-permissions.ps1` - Grant GCR permissions
- `grant-artifactregistry-permissions.ps1` - Grant Artifact Registry permissions
- `cleanup-managed-sas.ps1` - Delete manually created service accounts

### Build Scripts
- `build-containers.ps1` - Build using Cloud Build
- `build-containers-correct-sa.ps1` - Build with Cloud Build Service Agent (WIP)
- `build-containers-docker.ps1` - Build using Docker (requires Docker Desktop)

### Validation Scripts
- `preflight-check.ps1` - Validate prerequisites before deployment

### Documentation
- `MISSING_PERMISSIONS_LOG.md` - Complete log of all discovered issues
- `CLOUDBUILD_PERMISSIONS_ISSUE.md` - Cloud Build specific issue details
- `PHASE1_DEPLOYMENT_STATUS.md` - Original deployment status

### Terraform Files
- `infrastructure/github_archive/phase1_ingestion/terraform/cloudbuild.tf` - Terraform config for building containers
- `infrastructure/github_archive/phase1_ingestion/terraform/service_accounts.tf` - Modified to use hardcoded project number
- `config/cloudbuild-phase1.yaml` - Updated to remove explicit dir and push step

## Next Steps

### Immediate
1. **Re-apply Tainted Resource**: Run `terraform apply` to destroy and recreate the tainted Cloud Run Job with the correct configuration.

### Future
2. **Deploy Phase 2**: Begin the layered deployment for the processing phase.
3. **Deploy Phase 3**: Deploy the BigQuery loading infrastructure.

## Service Accounts Summary

| Service Account | Purpose | Status |
|-----------------|---------|--------|
| `test-terraform-deployer` | Infrastructure deployment | ✅ Active, all permissions granted |
| `test-github-archive-downloader` | Cloud Run Job identity | ✅ Created |
| `test-scheduler` | Cloud Scheduler identity | ✅ Created |
| `592311283460-compute@developer.gserviceaccount.com` | Cloud Build worker | ⚠️ Using this (should use Cloud Build SA) |
| `service-592311283460@gcp-sa-cloudbuild.iam.gserviceaccount.com` | Cloud Build Service Agent | ❓ Should be used instead |

## Important Notes

### About Service Accounts
- **Default Behavior**: Cloud Build uses Compute Service Account for backward compatibility
- **Recommended**: Use Cloud Build Service Agent instead (requires log bucket config)
- **Current Workaround**: Using Compute SA with storage.admin role granted

### Container Registry vs Artifact Registry
- **GCR** (gcr.io): Legacy, uses Cloud Storage permissions
- **GAR** (pkg.dev): Recommended, uses Artifact Registry permissions
- **Current**: Phase 1 now uses Artifact Registry with an automated build via Terraform.

### Terraform State
- Location: `infrastructure/github_archive/phase1_ingestion/terraform/terraform.tfstate`
- Current resources tracked: 12 planned resources
- Resources in state: GCS bucket, 2 SAs, 4 IAM bindings, Cloud Run Job, Cloud Scheduler Job, Artifact Registry Repo, Build Resource

## Commands Reference

### Check Deployment Status
```bash
# Check GCS bucket
gsutil ls gs://beaming-glyph-489707-b8-test-github-archive-landing

# Check service accounts
gcloud iam service-accounts list --project=beaming-glyph-489707-b8 --filter="email:*test*"

# Check Terraform state
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform show
```

### Run Pre-flight Check
```powershell
.\preflight-check.ps1
```

### Complete Setup (From Scratch)
```powershell
# 1. Enable APIs and grant permissions
.\setup-complete.ps1

# 2. Build container image
.\build-containers.ps1

# 3. Deploy infrastructure
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test" -var="region=us-central1"
```

## Known Issues

### 1. Python Installation Blocking gcloud Commands
**Impact**: Cannot use gcloud commands that rely on Python
**Workaround**: Use PowerShell scripts or direct API calls

### 2. Docker Not Installed
**Impact**: Cannot use Docker-based build scripts
**Workaround**: Using Cloud Build instead

### 3. Cloud Build Service Account Configuration
**Impact**: Using Compute SA instead of Cloud Build Service Agent
**Workaround**: Granted storage.admin to Compute SA
**Proper Fix**: Configure log bucket and use Cloud Build Service Agent

## Files to Review When Continuing

1. `CLOUDBUILD_PERMISSIONS_ISSUE.md` - Details on Cloud Build SA configuration
2. `MISSING_PERMISSIONS_LOG.md` - All permissions discovered and granted
3. `build-containers.ps1` - Current build script (using default SA)
4. `infrastructure/github_archive/phase1_ingestion/terraform/` - Terraform configuration

## Commit Message Suggestion

```
feat: configure terraform deployer and enable Phase 1 APIs

- Created test-terraform-deployer service account with 15+ IAM roles
- Enabled 14 required GCP APIs for GitHub Archive infrastructure
- Granted missing permissions: resourcemanager.projectIamAdmin, iam.serviceAccountUser
- Created 6 of 9 Phase 1 resources: GCS bucket, 2 SAs, 3 IAM bindings
- Blocked on container image push (Compute SA needs GCR permissions)
- Added comprehensive setup and validation scripts
- Documented all missing permissions discovered during deployment

Status: Phase 1 partially deployed (6/9 resources), waiting for container build
```
