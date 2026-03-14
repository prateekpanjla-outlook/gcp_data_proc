# apis.tf Documentation

## 1. Overview

Enables the GCP APIs required by Phase 2 and initializes the Google-managed service agents that those APIs create. These service agents need explicit IAM bindings before Eventarc triggers can function (the Storage service agent must be able to publish Pub/Sub messages).

APIs enabled: Eventarc, Pub/Sub, Cloud Run, and Cloud Storage.

## 2. Prerequisites

- `var.project_id` must reference a project where the deployer SA has `serviceusage.services.enable` permission (typically via `roles/serviceusage.serviceUsageAdmin` or `roles/owner`).
- `gcloud` CLI must be available (used by the `null_resource` provisioner).
- `var.deployer_sa_key_path` must be a valid SA key for `gcloud auth`.

## 3. Upstream & Downstream Dependencies

**Upstream:**
- None beyond the GCP project itself. API enablement is a foundational step.

**Downstream:**
- All Phase 2 resources depend on these APIs being enabled:
  - `google_eventarc_trigger` requires `eventarc.googleapis.com`.
  - `google_cloud_run_v2_service` requires `run.googleapis.com`.
  - GCS bucket operations require `storage.googleapis.com`.
- The `null_resource.init_service_agents` creates the Storage and Eventarc service agents, which are needed before IAM bindings can reference them (e.g., granting `roles/pubsub.publisher` to the Storage service agent).

## 4. Code Walkthrough

1. **API resources (lines 5-31):** Four `google_project_service` resources enable `eventarc`, `pubsub`, `run`, and `storage` APIs. All have `disable_on_destroy = false` to prevent accidental API disabling on `terraform destroy`.

2. **`null_resource.init_service_agents` (lines 35-49):**
   - Depends on the Storage and Eventarc API resources.
   - Runs `gcloud beta services identity create` for both `storage.googleapis.com` and `eventarc.googleapis.com`.
   - This forces GCP to create the Google-managed service agents (`service-PROJECT_NUM@gs-project-accounts.iam.gserviceaccount.com` and `service-PROJECT_NUM@gcp-sa-eventarc.iam.gserviceaccount.com`) which are not created automatically by `google_project_service` alone.
   - These agents are then available for IAM bindings in subsequent resources.
