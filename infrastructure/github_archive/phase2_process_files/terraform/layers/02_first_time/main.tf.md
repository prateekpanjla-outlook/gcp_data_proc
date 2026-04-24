# layers/02_first_time/main.tf Documentation

## 1. Overview

Layer 02 (First-Time Setup) enables all GCP APIs required by Phase 2 and creates the one-time IAM bindings for Google-managed service agents. It also defines a Cloud Build trigger resource and grants the Cloud Build SA permission to act as the processor SA during deployments.

This layer is applied once when setting up a new project or environment, and rarely revisited afterward.

Resources created:
- **API enablement:** Eventarc, Eventarc Publishing, Cloud Run, Storage, Cloud Resource Manager, IAM, Logging, Monitoring, Cloud Build (9 APIs total).
- **Service Agent IAM:** `roles/pubsub.publisher` for the Storage service agent; `roles/eventarc.eventReceiver` for the Eventarc service agent.
- **Cloud Build trigger:** `${env}-phase2-processor` with inline build steps (docker build, push, deploy to Cloud Run).
- **Cloud Build actAs IAM:** Allows the Cloud Build SA to impersonate the processor SA during deployments.

State is stored at `gs://beaming-glyph-489707-b8-terraform-state/terraform/state/phase2-first-time`.

## 2. Prerequisites

- Terraform >= 1.5 and Google provider ~> 7.0.
- GCS state bucket must exist.
- Layer 01 (Static) should be applied first so the processor SA exists for the `actAs` binding. If Layer 01 has not been applied, the `cloudbuild_actas_processor` binding will fail because the target SA does not exist yet.
- The Cloud Build service account (`${env}-cloud-build@...`) must exist (created in Phase 1).
- Variables supplied: `project_id`, `region`, `environment`.

## 3. Upstream & Downstream Dependencies

**Upstream:**
- **Phase 1:** The Cloud Build SA (`${env}-cloud-build@${project_id}.iam.gserviceaccount.com`) and Artifact Registry repository are created in Phase 1.
- **Layer 01:** The processor SA must exist before the `actAs` IAM binding can be applied.

**Downstream:**
- **Layer 03 (`03_operational`):** Reads `terraform_remote_state.first_time` to confirm APIs are enabled. The Eventarc trigger depends on the service agent IAM bindings created here.
- The Cloud Build trigger created here can be invoked manually or connected to GitHub for automated builds.

## 4. IAM & Service Accounts

| Identity | Format | Purpose |
|----------|--------|---------|
| **Storage service agent** | `service-{project_number}@gs-project-accounts.iam.gserviceaccount.com` | Google-managed agent that publishes Cloud Storage events to Pub/Sub. |
| **Eventarc service agent** | `service-{project_number}@gcp-sa-eventarc.iam.gserviceaccount.com` | Google-managed agent that manages Eventarc trigger lifecycle. |
| **Cloud Build SA** | `{env}-cloud-build@{project}.iam.gserviceaccount.com` | Runs Cloud Build builds and deploys Cloud Run services. Created in Phase 1. |
| **Processor SA** | `{env}-github-archive-processor@{project}.iam.gserviceaccount.com` | Referenced as the target of the `actAs` binding so Cloud Build can deploy Cloud Run services that run as this SA. Created in Layer 01. |

**IAM bindings created:**

| SA / Agent | Role | Resource | Why |
|------------|------|----------|-----|
| Storage service agent | `roles/pubsub.publisher` | Project | Allows Cloud Storage to publish `object.finalized` events to Pub/Sub, which Eventarc consumes. |
| Eventarc service agent | `roles/eventarc.eventReceiver` | Project | Allows the Eventarc agent to receive and route events. |
| Cloud Build SA | `roles/iam.serviceAccountUser` | Processor SA | Allows Cloud Build to impersonate the processor SA when deploying Cloud Run services (`--service-account` flag on `gcloud run deploy`). |

**IAM propagation notes:**
- The service agent IAM bindings (`pubsub.publisher`, `eventarc.eventReceiver`) must propagate before Layer 03's Eventarc trigger can function. If Layer 03 is applied immediately after Layer 02, the trigger may fail to create or may not receive events. Allow at least 60 seconds between layer applies.
- The `actAs` binding on the processor SA is critical for Cloud Build deployments. If this binding is missing or has not propagated, `gcloud run deploy` in the Cloud Build step will fail with "Permission 'iam.serviceAccounts.actAs' denied."
- Stale SA risk: if the Cloud Build SA from Phase 1 is deleted and recreated, the `actAs` binding references the SA by email, so it will automatically apply to the new SA -- but the old Cloud Build trigger resource may still cache the old SA UID internally. Re-applying this layer resolves the reference.

## 5. Code Walkthrough

1. **Terraform/provider block (lines 1-25):** Standard setup with state at prefix `phase2-first-time`.

2. **Locals (lines 37-44):** Defines `common_labels` with `layer = "first-time"`.

3. **API enablement (lines 48-102):** Enables 9 APIs, all with `disable_on_destroy = false`:
   - `eventarc.googleapis.com`, `eventarcpublishing.googleapis.com` -- for Eventarc triggers.
   - `run.googleapis.com` -- for Cloud Run services.
   - `storage.googleapis.com` -- for GCS bucket operations.
   - `cloudresourcemanager.googleapis.com`, `iam.googleapis.com` -- for IAM and project metadata.
   - `logging.googleapis.com`, `monitoring.googleapis.com` -- for observability.
   - `cloudbuild.googleapis.com` -- for building Docker images.

4. **Service Agent IAM (lines 107-128):**
   - Grants `roles/pubsub.publisher` to the Storage service agent (`service-PROJECT_NUM@gs-project-accounts.iam.gserviceaccount.com`). This allows Cloud Storage to publish object-finalized events to Pub/Sub, which Eventarc needs.
   - Grants `roles/eventarc.eventReceiver` to the Eventarc service agent (`service-PROJECT_NUM@gcp-sa-eventarc.iam.gserviceaccount.com`).
   - Both depend on their respective API resources being enabled first.

5. **Cloud Build trigger (lines 140-228):**
   - Name: `${env}-phase2-processor`.
   - Inline build with 3 steps: (1) Docker build with `$SHORT_SHA` and `latest` tags, (2) Docker push all tags, (3) `gcloud run deploy` to update the Cloud Run service.
   - Uses the Cloud Build SA from Phase 1 via `service_account`.
   - Logging set to `CLOUD_LOGGING_ONLY`.

6. **Cloud Build SA reference (lines 235-237):** `local.cloudbuild_sa_email` constructs the SA email from `var.environment` and `var.project_id`.

7. **actAs IAM binding (lines 245-249):** Grants `roles/iam.serviceAccountUser` on the processor SA to the Cloud Build SA, allowing Cloud Build to deploy Cloud Run services that run as the processor SA.
