# Google Service Agents - Learnings

This document captures learnings about Google-managed service accounts and how to properly activate them for Terraform deployments.

---

## The Problem

When deploying infrastructure with Terraform, you may encounter errors like:
```
Error: Service account service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com does not exist.
Error: Service account service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com does not exist.
```

This happens even after enabling the required APIs (Storage, Eventarc, etc.).

---

## Root Cause

**Google-managed service agents are NOT created automatically when APIs are enabled.**

According to [Google Cloud documentation](https://cloud.google.com/storage/docs/projects):
> The Cloud Storage service agent is **not initially available** when you make a project. Instead, it is automatically activated the first time it's accessed, either by:
> - Pub/Sub Notifications for Cloud Storage
> - Customer-Managed Encryption Keys
> - Or when you **request the service agent's name**

The same applies to other service agents like Eventarc.

---

## Solution: Explicitly Activate Service Agents

### 1. Cloud Storage Service Agent

**Purpose:** Publishes Cloud Storage events to Pub/Sub (required for Eventarc triggers)

**Activation command:**
```bash
gcloud storage service-agent --project=PROJECT_ID
```

**Grant required role:**
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"
```

### 2. Eventarc Service Agent

**Purpose:** Receives events and triggers Cloud Run services

**Activation command:**
```bash
gcloud beta services identity create --service=eventarc.googleapis.com --project=PROJECT_ID
```

**Grant required role:**
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com" \
  --role="roles/eventarc.eventReceiver"
```

---

## Terraform Considerations

### The `depends_on` Pitfall

```hcl
resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"

  depends_on = [
    google_project_service.storage,
    google_project_service.eventarc,
  ]
}
```

**Problem:** `depends_on` only waits for the `google_project_service` resource to report "created". It does NOT wait for the service agent accounts to actually be provisioned, which happens asynchronously.

**Solutions:**

1. **Pre-activate service agents** before running Terraform (recommended for initial setup)

2. **Add `time_sleep` resource** in Terraform:
   ```hcl
   resource "time_sleep" "wait_for_service_agents" {
     create_duration = "60s"
     depends_on = [
       google_project_service.eventarc,
       google_project_service.storage,
     ]
   }

   resource "google_project_iam_member" "storage_pubsub_publisher" {
     # ...
     depends_on = [ time_sleep.wait_for_service_agents ]
   }
   ```

3. **Use `null_resource` with `local-exec`** to activate:
   ```hcl
   resource "null_resource" "activate_storage_service_agent" {
     provisioner "local-exec" {
       command = "gcloud storage service-agent --project=${var.project_id}"
     }
   }
   ```

---

## Event Flow Diagram

```
┌─────────────────┐      pubsub       ┌──────────────┐      Eventarc      ┌─────────────┐
│ GCS Bucket      │ ─────────────────→  │   Pub/Sub    │  ────────────────→ │ Cloud Run   │
│ (file arrived)  │  (storage SA)      │   (topic)     │                   │  Service    │
└─────────────────┘                     └──────────────┘                     └─────────────┘
```

**Roles required:**
- **Storage service agent** → `roles/pubsub.publisher` (publishes to Pub/Sub)
- **Eventarc service agent** → `roles/eventarc.eventReceiver` (receives events)

---

## Verification Commands

### Check if service agent exists:
```bash
gcloud iam service-accounts list --project=PROJECT_ID \
  --filter="serviceAccount:*@gs-project-accounts.iam.gserviceaccount.com"
```

### Get Storage service agent email:
```bash
gcloud storage service-agent --project=PROJECT_ID
```

### Check enabled APIs:
```bash
gcloud services list --enabled --project=PROJECT_ID | grep -E "(eventarc|storage)"
```

---

## Common Service Agents

| Service Agent | Role Needed | Purpose |
|---------------|-------------|---------|
| `service-NUMBER@gs-project-accounts.iam.gserviceaccount.com` | `roles/pubsub.publisher` | Cloud Storage → Pub/Sub notifications |
| `service-NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com` | `roles/eventarc.eventReceiver` | Eventarc event receiver |
| `service-NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` | `roles/pubsub.serviceAgent` | Pub/Sub service agent |
| `service-NUMBER@serverless-robot-prod.iam.gserviceaccount.com` | `roles/run.serviceAgent` | Cloud Run service agent |
| `service-NUMBER@gcp-sa-artifactregistry.iam.gserviceaccount.com` | `roles/artifactregistry.serviceAgent` | Artifact Registry service agent |

---

## Eventarc: Pub/Sub Service Agent Token Creator Permission

**Error Message (Console):**
```
Cloud Pub/Sub needs the role roles/iam.serviceAccountTokenCreator granted to service account
service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com on this project to create identity tokens.
```

**Root Cause:**
When using Eventarc to trigger **authenticated Cloud Run services**, the Pub/Sub service agent needs to generate OIDC tokens to authenticate to Cloud Run. This requires granting `roles/iam.serviceAccountTokenCreator` to the Pub/Sub service agent **on the Eventarc invoker service account**.

**Fix:**
```bash
# Grant Pub/Sub SA permission to create tokens for Eventarc invoker SA
gcloud iam service-accounts add-iam-policy-binding \
  EVENTARC_INVOKER_SA@PROJECT_ID.iam.gserviceaccount.com \
  --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

**Terraform:**
```hcl
resource "google_service_account_iam_member" "pubsub_token_creator" {
  service_account_id = google_service_account.eventarc_invoker.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}
```

**Important:** This is **service account IAM** (granted on the SA), not project IAM.

---

## References

- [Cloud Storage Service Agents](https://cloud.google.com/storage/docs/projects)
- [Getting the Storage Service Agent](https://cloud.google.com/storage/docs/getting-service-agent)
- [IAM Service Agents](https://cloud.google.com/iam/docs/service-agents)
- [Eventarc Troubleshooting](https://cloud.google.com/eventarc/docs/troubleshooting)

---

## Terraform Apply Behavior with Existing Resources

When re-running `terraform apply` after a failed attempt, Terraform may show existing resources as "changed" even when no actual changes are needed.

### Example: Artifact Registry Labels

**Symptom:** `google_artifact_registry_repository` shows as "Modifying..." on re-apply

**Cause:** Labels were not fully applied in the initial creation attempt, or Terraform detected drift between the actual resource and the configuration.

**What was added:**
```hcl
labels = {
  environment = "dev"
  layer       = "first-time"
  managed_by  = "terraform"
  phase       = "processing"
}
# Plus: goog-terraform-provisioned = "true" (auto-added by Google)
```

**Takeaway:** This is normal Terraform behavior - it ensures the actual infrastructure matches the configuration. The "modification" is simply applying the missing labels to align with the desired state.
