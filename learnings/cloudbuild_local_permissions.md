# Cloud Build Local Submissions - Complete Permissions Analysis

This document captures learnings about running Cloud Build from local machines, including
ALL required permissions for container image builds.

## The Issue

When running `gcloud builds submit` from a local machine, you may encounter multiple permission errors:

```
# Error 1: Storage permissions
ERROR: could not resolve source: googleapi: Error 403:
973986259857-compute@developer.gserviceaccount.com does not have
storage.objects.get access to the Google Cloud Storage object.

# Error 2: Artifact Registry permissions (pulling base images)
Permission "artifactregistry.repositories.downloadArtifacts" denied on resource "projects/google.com:cloud-sdk"

# Error 3: Build permissions
ERROR: (gcloud.builds.submit) PERMISSION_DENIED: Request had insufficient authentication scopes
```

## Root Cause

**Cloud Build changed its default service account in mid-2024:**

| Before (Legacy) | After (Current) |
|------------------|-----------------|
| Cloud Build SA (`@cloudbuild.gserviceaccount.com`) | **Compute Engine SA** (`@compute@developer.gserviceaccount.com`) |

The new default Compute Engine SA has **minimal permissions** by default and must be granted
explicit permissions for Cloud Build operations.

---

## How It Works: Two Service Accounts

```
┌─────────────────────────────────────────────────────────────────┐
│           gcloud builds submit (from your laptop)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. YOUR Personal Account (authentication)                    │
│      └── your-email@gmail.com                                 │
│         (logged in via `gcloud auth login`)                   │
│                              ↓                                  │
│   2. Cloud Build API receives your request                       │
│                              ↓                                  │
│   3. Cloud Build EXECUTES the build using:                    │
│      └── {PROJECT_NUMBER}-compute@developer.gserviceaccount.com │
│         (Project's Compute Engine Service Account)              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key Point:** Your personal account authenticates to Cloud Build, but Cloud Build uses a **project-level service account** to execute the build.

---

## Complete Required Permissions for Container Builds

When running `gcloud builds submit` for Docker image builds, the Compute Engine SA needs:

| Role | Purpose | Status |
|------|---------|--------|
| `roles/storage.objectAdmin` | Upload source to GCS staging bucket | Required |
| `roles/artifactregistry.reader` | Pull base images (e.g., `gcr.io/google.com/cloud-sdk:slim`) | Required |
| `roles/cloudbuild.builds.builder` | Push images, create builds, execute all Cloud Build operations | **Comprehensive** |

**Recommended Approach:** Grant `roles/cloudbuild.builds.builder` which includes:
- `artifactregistry.repositories.downloadArtifacts` - Pull images
- `artifactregistry.repositories.uploadArtifacts` - Push images
- `artifactregistry.repositories.createOnPush` - Auto-create repo on push
- `storage.objects.create/get/list/update` - GCS operations
- `cloudbuild.builds.create` - Create builds
- `logging.logEntries.create` - Write logs

---

## The Fix (Complete)

Grant all required roles to the Compute Engine service account:

```bash
PROJECT_ID="your-project-id"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Option 1: Grant individual roles (for least privilege)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/artifactregistry.reader"

# Option 2: Grant the comprehensive Cloud Build role (RECOMMENDED)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/cloudbuild.builds.builder"
```

---

## Permissions Breakdown by Build Stage

| Stage | Operation | Required Permission | Role |
|-------|-----------|-------------------|------|
| Source Upload | `gcloud builds submit` uploads source to GCS | `storage.objects.create` | `storage.objectAdmin` or `cloudbuild.builds.builder` |
| Pull Base Image | Docker pulls `gcr.io/google.com/cloud-sdk:slim` | `artifactregistry.repositories.downloadArtifacts` | `artifactregistry.reader` or `cloudbuild.builds.builder` |
| Pull Builder | Docker pulls `gcr.io/cloud-builders/docker` | `artifactregistry.repositories.downloadArtifacts` | Same as above |
| Build Image | Docker build executes | (local to build worker) | N/A |
| Push Image | Docker pushes to `gcr.io/$PROJECT_ID/...` | `artifactregistry.repositories.uploadArtifacts` | `cloudbuild.builds.builder` |
| Create Repo | Auto-create on first push | `artifactregistry.repositories.createOnPush` | `cloudbuild.builds.builder` |
| Logging | Write build logs | `logging.logEntries.create` | `cloudbuild.builds.builder` |

---

## Why We Missed This Initially

| What We Reviewed | What We Missed |
|------------------|-----------------|
| Phase 1 Terraform resources (SA, IAM, GCS, Cloud Run Job, Scheduler) | ✅ Reviewed |
| Cloud Build service account permissions | ❌ **Missed** |
| Compute Engine SA permissions for local builds | ❌ **Missed** |
| Artifact Registry permissions for pulling/pushing images | ❌ **Missed** |

**Takeaway:** When adding new tooling (Cloud Build), ALWAYS use MCP tools to check:
1. What service account executes the build?
2. What permissions does that SA need for EACH build stage?
3. Are those permissions granted?
4. Does the comprehensive role (`cloudbuild.builds.builder`) cover all requirements?

---

## Analysis: Roles and What They Include

### `roles/cloudbuild.builds.builder`

Based on [Google Cloud IAM documentation](https://cloud.google.com/iam/docs/roles-permissions#cloudbuild),
this role includes:

| Permission Category | Key Permissions |
|---------------------|-----------------|
| **Artifact Registry** | `artifactregistry.repositories.downloadArtifacts`, `uploadArtifacts`, `createOnPush` |
| **Storage** | `storage.objects.create`, `get`, `list`, `update`, `delete` |
| **Cloud Build** | `cloudbuild.builds.create`, `get`, `list`, `update` |
| **Logging** | `logging.logEntries.create`, `list` |

**This single role covers all requirements for Cloud Build local submission.**

---

## Verify Permissions Are Correct

```bash
PROJECT_ID="your-project-id"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# List all roles for Compute Engine SA
gcloud projects get-iam-policy ${PROJECT_ID} --flatten="bindings[].members" \
  --format="csv(bindings.role,bindings.members)" | grep "${COMPUTE_SA}"

# Expected output should include:
# - roles/cloudbuild.builds.builder
# - (optionally) roles/storage.objectAdmin
# - (optionally) roles/artifactregistry.reader
```

---

## Alternative: User-Specified Service Account

For more control, you can specify a custom SA for Cloud Build:

```bash
gcloud builds submit --config=config/cloudbuild.yaml \
  --service-account="projects/$PROJECT_ID/serviceAccounts/custom-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  .
```

Then grant that custom SA the necessary permissions instead of the Compute Engine SA.

---

## Layer 1 Terraform vs Cloud Build

**Important:** Layer 1 Terraform resources are NOT needed for Cloud Build.

| Layer 1 Resource | Purpose | Needed for Cloud Build? |
|------------------|---------|------------------------|
| `github_archive_downloader` SA | For Cloud Run Job execution | ❌ No |
| `scheduler` SA | For Cloud Scheduler | ❌ No |
| GCS Landing Bucket | For storing downloaded files | ❌ No |
| IAM bindings for downloader SA | Runtime permissions | ❌ No |

**Cloud Build uses the Compute Engine SA**, not any service accounts created by Terraform Layer 1.

---

## Complete Checklist Before Running Cloud Build

- [ ] Compute Engine SA has `roles/cloudbuild.builds.builder`
- [ ] (Optional) `roles/storage.objectAdmin` if not using comprehensive role
- [ ] (Optional) `roles/artifactregistry.reader` if not using comprehensive role
- [ ] Personal account is authenticated via `gcloud auth login`
- [ ] Cloud Build API is enabled in the project
- [ ] **Dockerfile uses CURRENT Google Cloud SDK image path** (see below)

---

## Docker Image Path Issue (CRITICAL)

### The Problem

**The Google Cloud SDK Docker image path changed in 2024:**

| Old (Deprecated) | New (Current) |
|------------------|---------------|
| `gcr.io/google.com/cloud-sdk:slim` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:slim` |
| `gcr.io/google.com/cloud-sdk:latest` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:latest` |
| `gcr.io/google.com/cloud-sdk:alpine` | `gcr.io/google.com/cloudsdktool/google-cloud-cli:alpine` |

### Error You'll See

```
Head "https://gcr.io/v2/google.com/cloud-sdk/manifests/slim": denied:
Permission "artifactregistry.repositories.downloadArtifacts" denied on resource
"projects/google.com:cloud-sdk/locations/us/repositories/gcr.io" (or it may not exist)
```

**This is NOT a permission issue!** The old image path simply doesn't exist anymore.

### The Fix

Update your Dockerfile to use the new image path:

```dockerfile
# OLD (deprecated)
FROM gcr.io/google.com/cloud-sdk:slim

# NEW (current)
FROM gcr.io/google.com/cloudsdktool/google-cloud-cli:slim
```

### Available Tags

- `:stable` - Recommended for production (smaller, more secure)
- `:slim` - Minimal installation with gsutil
- `:latest` - Full installation with all components
- `:alpine` - Alpine-based minimal image
- `:VERSION-stable` - Pinned version (e.g., `:496.0.0-stable`)

### Reference

- [Google Cloud CLI Docker Images](https://cloud.google.com/sdk/docs/downloads-docker)
- [Migrating Docker Images](https://cloud.google.com/sdk/docs/migrate-docker-images)

---

## References

- [Cloud Build Service Account](https://cloud.google.com/build/docs/cloud-build-service-account)
- [Cloud Build Permissions](https://cloud.google.com/iam/docs/roles-permissions#cloudbuild)
- [Troubleshooting Cloud Build](https://cloud.google.com/build/docs/troubleshooting)
- [IAM Roles for Cloud Build](https://cloud.google.com/iam/docs/roles-permissions#cloudbuild)
