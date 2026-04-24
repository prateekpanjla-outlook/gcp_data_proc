# Summary: Cloud Build Container Image Deployment

## Issue Encountered

When trying to build and push container images using Cloud Build, we discovered that the Cloud Build service account needs additional permissions to push to Google Container Registry (GCR).

## Missing Permission

**Service Account**: `592311283460-compute@developer.gserviceaccount.com`
**Permission Needed**: Push to GCR (`gcr.io`)

**Root Cause**:
- GCR (Google Container Registry) uses different permissions than GAR (Google Artifact Registry)
- The error `Permission 'artifactregistry.repositories.uploadArtifacts' denied` indicates it's checking GAR permissions even though we're using GCR

## Solutions

### Option 1: Grant GCR-Specific Permissions (RECOMMENDED for GCR)

```powershell
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$CLOUD_BUILD_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

# Grant Storage Admin (GCR permissions are part of Cloud Storage)
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CLOUD_BUILD_SA" `
    --role="roles/storage.admin" `
    --quiet
```

### Option 2: Use Cloud Build Service Agent (ALTERNATIVE)

The Cloud Build Service Agent already has the necessary permissions but may need to be enabled:

```powershell
gcloud services enable cloudbuild.googleapis.com --project=$PROJECT_ID

# This automatically grants the Cloud Build Service Agent the necessary roles
# The service agent is: service-PROJECT_NUMBER@gcp-sa-cloudbuild.iam.gserviceaccount.com
```

### Option 3: Switch to Artifact Registry (RECOMMENDED for New Projects)

Instead of using `gcr.io`, migrate to Google Artifact Registry:

1. Create an Artifact Registry repository:
```bash
gcloud artifacts repositories create docker \
    --repository-format=docker \
    --location=us-central1 \
    --project=$PROJECT_ID
```

2. Update the image reference in cloudbuild.yaml:
```yaml
# Change from: gcr.io/$PROJECT_ID/github-archive-downloader:latest
# To: us-central1-docker.pkg.dev/$PROJECT_ID/docker/github-archive-downloader:latest
```

3. Update terraform configuration to use the new image location

## Current Status

**Container Build**: ✅ Successfully built
**Container Push**: ❌ Blocked by GCR permissions

## Next Steps

Choose one of the following:

1. **Quick Fix**: Grant `roles/storage.admin` to the Cloud Build SA
2. **Better Fix**: Migrate to Artifact Registry (recommended for new projects)
3. **Terraform Approach**: Use the `cloudbuild.tf` file to build as part of infrastructure deployment

## Files Created

- `cloudbuild.tf` - Terraform configuration for building containers
- `build-containers.ps1` - PowerShell script to build using Cloud Build
- `build-containers-docker.ps1` - PowerShell script to build using Docker (requires Docker Desktop)
- `grant-cloudbuild-permissions.ps1` - Grant Cloud Storage permissions
- `grant-cloudbuild-logging.ps1` - Grant Logging permissions
- `grant-gcr-permissions.ps1` - Grant GCR-specific permissions
- `grant-artifactregistry-permissions.ps1` - Grant Artifact Registry permissions
