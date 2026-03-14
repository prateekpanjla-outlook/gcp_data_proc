# layers/01_static/main.tf Documentation

## 1. Overview

Layer 01 (Static) creates the long-lived, rarely changing resources for Phase 2: service accounts, the staging GCS bucket, and all IAM bindings for those identities. These resources are created once and only re-applied when IAM or bucket configuration changes.

Resources created:
- **Service accounts:** Processor SA, Splitter SA, Eventarc Invoker SA.
- **Staging bucket:** `${project_id}-${env}-github-archive-staging` with lifecycle auto-deletion.
- **Project-level IAM:** Logging and monitoring writer roles for all three SAs.
- **Bucket-level IAM:** Least-privilege read/write bindings on the landing and staging buckets.

State is stored at `gs://beaming-glyph-489707-b8-terraform-state/terraform/state/phase2-static`.

## 2. Prerequisites

- Terraform >= 1.5 and Google provider ~> 7.0.
- GCS state bucket must exist.
- `var.landing_bucket_name` -- the Phase 1 landing bucket must already exist.
- Variables supplied: `project_id`, `region`, `environment`, `landing_bucket_name`, `staging_retention_days`.

## 3. Upstream & Downstream Dependencies

**Upstream (from Phase 1):**
- `var.landing_bucket_name` -- the landing bucket where raw GitHub Archive files are deposited by Phase 1 ingestion. Used as the source for `processor_landing_read` and `splitter_landing_read` IAM bindings.

**Downstream (consumed by other layers):**
- **Layer 02 (`02_first_time`):** References the processor SA by constructed email for the Cloud Build `actAs` binding.
- **Layer 03 (`03_operational`):** Reads `terraform_remote_state.static` outputs to get:
  - `processor_service_account_email` (Cloud Run service account)
  - `eventarc_invoker_service_account_email` (Eventarc trigger SA)
  - `staging_bucket_name` and `landing_bucket_name` (Cloud Run env vars)
- **Phase 3:** The staging bucket created here is watched by Phase 3's Eventarc trigger to load data into BigQuery.

## 4. IAM & Service Accounts

This layer is the **primary IAM layer** for Phase 2 -- it creates all three service accounts and their IAM bindings.

| Identity | Format | Purpose |
|----------|--------|---------|
| **Processor SA** | `{env}-github-archive-processor@{project}.iam.gserviceaccount.com` | Cloud Run service runtime identity. Processes GitHub Archive files. |
| **Splitter SA** | `{env}-file-splitter@{project}.iam.gserviceaccount.com` | Cloud Run Job identity for splitting large files. Not yet used in production. |
| **Eventarc Invoker SA** | `{env}-eventarc-invoker@{project}.iam.gserviceaccount.com` | Authenticates the Eventarc trigger when invoking the Cloud Run processor service. |

**IAM bindings created:**

| SA | Role | Resource | Why |
|----|------|----------|-----|
| Processor | `roles/storage.objectViewer` | Landing bucket | Read source `.json.gz` files and call `blob.reload()` for metadata. |
| Processor | `roles/storage.objectCreator` | Staging bucket | Write processed `.ndjson.gz` chunks. |
| Processor | `roles/storage.objectViewer` | Staging bucket | Post-upload `blob.reload()` verification. |
| Processor | `roles/logging.logWriter` | Project | Write structured logs from Cloud Run. |
| Processor | `roles/monitoring.metricWriter` | Project | Emit custom metrics. |
| Splitter | `roles/storage.objectViewer` | Landing bucket | Read raw files to split. |
| Splitter | `roles/storage.objectCreator` | Landing bucket | Write chunk files back to `landing/chunks/`. |
| Splitter | `roles/logging.logWriter` | Project | Write logs. |
| Splitter | `roles/monitoring.metricWriter` | Project | Emit metrics. |
| Eventarc Invoker | `roles/logging.logWriter` | Project | Write logs. |

**IAM propagation notes:**
- After `terraform apply` on this layer, IAM bindings may take up to 60 seconds to propagate. Do not immediately apply Layer 03 (which deploys the Cloud Run service) -- if the processor SA's storage bindings have not propagated, early Eventarc-triggered requests will fail with `403 Forbidden`.
- If a SA is deleted and recreated (e.g., `terraform destroy` then `apply`), the SA email stays the same but the underlying UID changes. Any existing Cloud Run revisions referencing the old SA will fail with stale credential errors until a new revision is deployed.
- Service Agent IAM (for the Storage and Eventarc Google-managed agents) is intentionally deferred to Layer 02 because those agents require their APIs to be enabled first.

## 5. Code Walkthrough

1. **Terraform/provider block (lines 1-25):** Pins Terraform >= 1.5, Google provider ~> 7.0, and stores state at prefix `phase2-static`.

2. **Data source and locals (lines 30-53):** Fetches project metadata. Defines `env_prefix`, `phase2_resources` map (SA names, bucket name), and `common_labels` with `layer = "static"`.

3. **Service accounts (lines 58-74):** Creates three SAs:
   - `processor` -- runs the Cloud Run Service that processes files.
   - `splitter` -- runs the Cloud Run Job that splits large files.
   - `eventarc_invoker` -- authenticates the Eventarc trigger when invoking Cloud Run.

4. **Staging bucket (lines 79-97):** Creates the staging bucket with:
   - `uniform_bucket_level_access = true`.
   - Lifecycle rule to auto-delete objects after `staging_retention_days`.
   - `force_destroy = true` only in dev.

5. **Project-level IAM (lines 102-133):** Grants `roles/logging.logWriter` and `roles/monitoring.metricWriter` to the processor and splitter SAs. Grants `roles/logging.logWriter` to the Eventarc invoker SA.

6. **Bucket-level IAM (lines 139-174):** Least-privilege bindings:
   - Processor SA gets `objectViewer` on landing bucket (read source files) and both `objectCreator` + `objectViewer` on staging bucket (write processed files and `blob.reload()` after upload).
   - Splitter SA gets `objectViewer` on landing bucket (read raw files) and `objectCreator` on landing bucket (write chunk files back to `landing/chunks/`).

7. **Note (line 137):** Service Agent IAM bindings are intentionally deferred to Layer 02, because they require APIs to be enabled first.
