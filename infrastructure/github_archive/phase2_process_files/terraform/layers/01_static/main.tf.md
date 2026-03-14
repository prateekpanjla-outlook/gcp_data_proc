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

## 4. Code Walkthrough

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
