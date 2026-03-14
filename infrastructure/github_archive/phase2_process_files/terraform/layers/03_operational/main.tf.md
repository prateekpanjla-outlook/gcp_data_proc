# layers/03_operational/main.tf Documentation

## 1. Overview

Layer 03 (Operational) defines the resources that change frequently with code deployments: the Cloud Run processor service, the Eventarc storage trigger, invoker IAM binding, and the Pub/Sub ack deadline override. This is the layer applied most often (daily/weekly) when deploying new code.

Resources created:
- **Cloud Run v2 Service:** `${env}-github-archive-processor` -- the processor that handles GitHub Archive files.
- **Eventarc Trigger:** `${env}-github-archive-storage` -- fires on `object.finalized` events in the landing bucket.
- **IAM:** Grants `roles/run.invoker` to the Eventarc invoker SA on the processor service.
- **Ack Deadline Override:** Updates the auto-created Pub/Sub subscription to 600s (max) to prevent duplicate message delivery.

State is stored at `gs://beaming-glyph-489707-b8-terraform-state/terraform/state/phase2-operational`.

## 2. Prerequisites

- Terraform >= 1.5 and Google provider ~> 7.0.
- **Layer 01 (Static)** must be applied first -- this layer reads its remote state for SA emails, bucket names, and other outputs.
- **Layer 02 (First-Time)** must be applied first -- APIs must be enabled and service agent IAM must exist.
- The processor Docker image must be available in Artifact Registry (built by Cloud Build or `build.tf`).
- `gcloud` CLI must be available on the machine running `terraform apply` (needed by the ack deadline `local-exec`).
- Variables supplied: `project_id`, `region`, `environment`, `image_tag`, `processor_memory`, `processor_cpu`, `max_instances`, `file_size_threshold_mb`, `chunksize`, `eventarc_ack_deadline_seconds`.

## 3. Upstream & Downstream Dependencies

**Upstream (from other layers):**
- `terraform_remote_state.static` (Layer 01) provides:
  - `landing_bucket_name` -- used as the `LANDING_BUCKET` env var and Eventarc trigger source.
  - `staging_bucket_name` -- used as the `STAGING_BUCKET` env var.
  - `processor_service_account_email` -- the identity the Cloud Run service runs as.
  - `eventarc_invoker_service_account_email` -- the identity the Eventarc trigger authenticates with.
- `terraform_remote_state.first_time` (Layer 02) -- confirms APIs and service agent IAM are ready.

**Upstream (from Phase 1):**
- Landing bucket -- the Eventarc trigger watches this bucket for `object.finalized` events.
- Artifact Registry -- the processor image is pulled from here.

**Downstream (to Phase 3):**
- Processed files are written to the staging bucket. Phase 3's Eventarc trigger watches the staging bucket to load NDJSON into BigQuery.

## 4. IAM & Service Accounts

| Identity | Format | Purpose |
|----------|--------|---------|
| **Processor SA** | `{env}-github-archive-processor@{project}.iam.gserviceaccount.com` | Cloud Run service identity. Read from Layer 01 remote state via `processor_service_account_email`. The Cloud Run service's `service_account` field is set to this SA. |
| **Eventarc Invoker SA** | `{env}-eventarc-invoker@{project}.iam.gserviceaccount.com` | Authenticates the Eventarc trigger when calling the Cloud Run service. Read from Layer 01 remote state via `eventarc_invoker_service_account_email`. |

**IAM bindings created:**

| SA | Role | Resource | Why |
|----|------|----------|-----|
| Eventarc Invoker | `roles/run.invoker` | Cloud Run processor service | Allows the Eventarc trigger to invoke the Cloud Run service via authenticated HTTP POST. |
| Eventarc Invoker | `roles/eventarc.eventReceiver` | (inherited from Layer 02 service agent binding) | Allows the trigger to receive Cloud Storage events. |

**IAM propagation notes:**
- The `run.invoker` binding is applied directly to the Cloud Run service resource (not at the project level). This binding must propagate before the Eventarc trigger can successfully invoke the service. If the trigger fires before propagation completes, the invocation will fail with `403` and the event will be retried by Pub/Sub (up to the ack deadline).
- The Processor SA and Eventarc Invoker SA are created in Layer 01 and referenced here by email via remote state. If Layer 01 is re-applied and a SA is deleted/recreated, this layer must also be re-applied to update the Cloud Run service and Eventarc trigger with the new SA identity. Stale SA references will cause `403 Forbidden` errors on both the Cloud Run service (storage access) and the Eventarc trigger (invocation).

## 5. Code Walkthrough

1. **Remote state data sources (lines 29-44):** Reads the `phase2-static` and `phase2-first-time` remote state from GCS. These provide SA emails, bucket names, and confirmation that prerequisite resources exist.

2. **Locals (lines 49-58):** Defines `env_prefix` and `common_labels` with `layer = "operational"`.

3. **Cloud Run v2 Service (lines 63-148):**
   - Name: `${env}-github-archive-processor`.
   - Uses Gen2 execution environment with a 1-hour timeout.
   - Concurrency set to 3 requests per instance (with a TODO to tune based on memory usage).
   - Container image: `${region}-docker.pkg.dev/${project_id}/${env}-github-archive/processor:${image_tag}`.
   - Environment variables: `PROJECT_ID`, `LANDING_BUCKET`, `STAGING_BUCKET`, `FILE_SIZE_THRESHOLD_MB`, `CHUNKSIZE`.
   - Resources: configurable CPU and memory via variables; `cpu_idle = false` keeps CPU allocated for the full request duration.
   - Scaling: 0 to `max_instances`.
   - `lifecycle.ignore_changes` on the container image so Cloud Build can update the image without Terraform reverting it.

4. **Eventarc Trigger (lines 153-192):**
   - Matches `google.cloud.storage.object.v1.finalized` events on the landing bucket.
   - Routes events to the processor Cloud Run service.
   - Uses the Eventarc invoker SA for authentication.
   - Note in comments: Cloud Storage Eventarc triggers do not support path/name filtering; filtering is done in the Cloud Run application code.

5. **Invoker IAM (lines 197-203):** Grants `roles/run.invoker` to the Eventarc invoker SA on the processor service, allowing the trigger to invoke the service.

6. **Ack Deadline Override (lines 208-227):**
   - Uses `terraform_data` (not `null_resource`) with `triggers_replace` to re-run when the trigger ID or deadline value changes.
   - Runs `gcloud pubsub subscriptions update` to set the ack deadline on the Eventarc-managed subscription.
   - Accesses the subscription name via `google_eventarc_trigger.storage_events.transport[0].pubsub[0].subscription`.
   - This is an improvement over the flat config's `ack_deadline.tf` which used `gcloud eventarc triggers describe` to discover the subscription name.
