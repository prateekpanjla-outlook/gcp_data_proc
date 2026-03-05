# Cloud Build Local Submissions - Permissions Issue

This document captures learnings about running Cloud Build from local machines.

## The Issue

When running `gcloud builds submit` from a local machine, you may encounter:

```
ERROR: could not resolve source: googleapi: Error 403:
973986259857-compute@developer.gserviceaccount.com does not have
storage.objects.get access to the Google Cloud Storage object.
```

## Root Cause

**Cloud Build changed its default service account in mid-2024:**

| Before (Legacy) | After (Current) |
|------------------|-----------------|
| Cloud Build SA (`@cloudbuild.gserviceaccount.com`) | **Compute Engine SA** (`@compute@developer.gserviceaccount.com`) |

The new default Compute Engine SA lacks storage permissions needed for local builds.

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

## Required Permissions

When running `gcloud builds submit`, the Compute Engine SA needs:

| Permission | Purpose |
|------------|---------|
| `storage.objects.get` | Read source from GCS staging |
| `storage.objects.create` | Upload source to GCS |
| `storage.objects.list` | List GCS objects |
| `cloudbuild.builds.create` | Create builds |
| `logging.logEntries.create` | Write build logs |

---

## The Fix

Grant `roles/storage.objectAdmin` to the Compute Engine service account:

```bash
PROJECT_ID="your-project-id"
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/storage.objectAdmin"
```

---

## Why We Missed This Initially

| What We Reviewed | What We Missed |
|------------------|-----------------|
| Phase 1 Terraform resources (SA, IAM, GCS, Cloud Run Job, Scheduler) | ✅ Reviewed |
| Cloud Build service account permissions | ❌ **Missed** |
| Compute Engine SA permissions for local builds | ❌ **Missed** |

**Takeaway:** When adding new tooling (Cloud Build), always check:
1. What service account executes the build?
2. What permissions does that SA need?
3. Are those permissions granted?

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

## References

- [Cloud Build Service Account](https://cloud.google.com/build/docs/cloud-build-service-account)
- [Cloud Build Permissions](https://cloud.google.com/iam/docs/roles-permissions#cloudbuild)
- [Troubleshooting Cloud Build](https://cloud.google.com/build/docs/troubleshooting)
