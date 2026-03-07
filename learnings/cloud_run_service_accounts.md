# Cloud Run Service Accounts - Service Agent vs Service Identity

## Overview

Cloud Run involves **two different service accounts** that are often confused:

| Service Account | Type | Created By | Email Format | Purpose |
|-----------------|------|------------|--------------|---------|
| **Service Agent** | Google-managed | Google (auto) | `service-NUMBER@serverless-robot-prod.iam.gserviceaccount.com` | Pull images, manage infra |
| **Service Identity** | User-managed | You | `NAME@PROJECT_ID.iam.gserviceaccount.com` | Your code's permissions |

---

## Service Agent (Google-Managed)

**You CANNOT create your own.** This is automatically created when you enable Cloud Run API.

**Purpose:**
- Pulls container images from Artifact Registry
- Manages revisions and scaling
- Handles internal Cloud Run operations

**Permissions needed:**
- `roles/artifactregistry.reader` - to pull images (auto-granted in same project)
- `roles/run.serviceAgent` - auto-granted by Google

---

## Service Identity (User-Managed)

**You SHOULD create your own.** This is the service account that runs INSIDE your container.

**Purpose:**
- Your application code uses this to access Google Cloud resources
- Permissions are based on what your app needs (GCS, BigQuery, etc.)

**Example:** `dev-github-archive-processor@PROJECT_ID.iam.gserviceaccount.com`

**Typical permissions for data processing:**
- `roles/storage.objectViewer` - read input files
- `roles/storage.objectCreator` - write output files
- `roles/logging.logWriter` - write logs
- `roles/monitoring.metricWriter` - write metrics

---

## The Required Relationship (CRITICAL!)

The Service Agent must have permission to **impersonate** the Service Identity.

### Why This Is Needed

```
┌─────────────────────┐         ┌──────────────────────┐
│  Service Agent      │ ───────→ │   Service Identity   │
│  (Google-managed)   │  (actAs) │   (Your Processor SA)│
│  @serverless-robot  │         │   dev-github-...      │
└─────────────────────┘         └──────────────────────┘
         │                                  │
         │ Pulls image                      │ Runs container
         │                                  │ Your code uses this
         ▼                                  ▼
    Artifact Registry                  GCS, Logging, etc.
```

### How to Grant

```bash
# Grant Service Agent permission to impersonate Service Identity
gcloud iam service-accounts add-iam-policy-binding \
  dev-github-archive-processor@PROJECT_ID.iam.gserviceaccount.com \
  --member="serviceAccount:service-PROJECT_NUMBER@serverless-robot-prod.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

### Terraform

```hcl
# Get project number
data "google_project" "current" {}

# Service Agent: Token Creator on Service Identity
resource "google_service_account_iam_member" "service_agent_token_creator" {
  service_account_id = google_service_account.processor.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@serverless-robot-prod.iam.gserviceaccount.com"
}
```

---

## Common Errors

### Error 1: Missing Token Creator Permission

**Error Message:**
```
The caller does not have permission to execute the request
```

**Root Cause:** Service Agent cannot impersonate your Service Identity.

**Fix:** Grant `roles/iam.serviceAccountTokenCreator` as shown above.

---

### Error 2: Container Cannot Access Resources

**Error Message:**
```
403 Your service account does not have storage.objects.get access
```

**Root Cause:** Your Service Identity (not Service Agent) is missing permissions.

**Fix:** Grant the required role (e.g., `roles/storage.objectViewer`) to your Service Identity.

---

## Summary

| Question | Answer |
|----------|--------|
| Can I create my own Service Agent? | ❌ NO - Google-managed only |
| Can I create my own Service Identity? | ✅ YES - Recommended |
| Does Service Agent need Artifact Registry access? | ✅ YES - To pull images |
| Does Service Identity need Artifact Registry access? | ❌ NO - Agent handles this |
| What permission links them? | `roles/iam.serviceAccountTokenCreator` |

---

## References

- [Cloud Run Service Identity](https://cloud.google.com/run/docs/securing/service-identity)
- [Service Account Types](https://cloud.google.com/iam/docs/service-account-types)
- [IAM Service Account Token Creator](https://cloud.google.com/iam/docs/roles-permissions)
