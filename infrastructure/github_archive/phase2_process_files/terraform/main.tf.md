# main.tf Documentation

## 1. Overview

This is the root-level (flat) Terraform configuration for Phase 2 of the GitHub Archive data pipeline. It configures the Google provider, GCS remote backend for state, and defines shared locals used across the flat config files (`build.tf`, `apis.tf`, `ack_deadline.tf`). This flat config is an alternative to the layered approach under `layers/`.

Key responsibilities:
- Pin Terraform and provider versions (Terraform >= 1.5, Google provider ~> 5.0).
- Store state in `gs://beaming-glyph-489707-b8-terraform-state/terraform/state/phase2`.
- Look up the current project metadata via `data.google_project`.
- Define `locals` for environment-prefixed resource names (service accounts, staging bucket) and common labels.

## 2. Prerequisites

- Terraform >= 1.5 installed.
- Google Cloud provider ~> 5.0.
- GCS bucket `beaming-glyph-489707-b8-terraform-state` must exist (created during project bootstrap).
- A `terraform.tfvars` or `-var` flags supplying `project_id`, `environment`, and other required variables from `variables.tf`.
- Authenticated access to the GCP project (via `deployer_sa_key_path` or application default credentials).

## 3. Upstream & Downstream Dependencies

**Upstream (consumed from Phase 1):**
- `var.landing_bucket_name` -- the landing bucket created by Phase 1 ingestion.

**Downstream (consumed by other files in this flat config):**
- `local.env_prefix` and `local.phase2_resources` are referenced by `build.tf`, `apis.tf`, and `ack_deadline.tf` for naming service accounts and buckets.
- `local.common_labels` is applied to resources created in companion files.

**Relationship to layered config:**
- The flat config (`main.tf` + siblings) and the layered config (`layers/01_static`, `02_first_time`, `03_operational`) serve the same purpose but with different state isolation. The layered approach is preferred and used by `deploy-all-phases.sh`.

## 4. Code Walkthrough

1. **`terraform` block (lines 4-17):** Sets the required Terraform version, declares the `hashicorp/google` provider at `~> 5.0`, and configures the GCS backend with prefix `terraform/state/phase2`.

2. **`provider "google"` (lines 19-23):** Configures the Google provider using `var.project_id` and `var.region`, with a 120-second request timeout.

3. **`data "google_project" "current"` (lines 25-27):** Fetches project metadata (notably `project_number`) used by other files for constructing service agent email addresses.

4. **`locals` block (lines 32-47):**
   - `env_prefix` -- set to `var.environment` ("dev" or "prod"), used as a prefix for all resource names.
   - `phase2_resources` -- a map containing standardized names for the processor SA, splitter SA, Eventarc invoker SA, and staging bucket.
   - `common_labels` -- standard labels (`environment`, `phase`, `managed_by`) applied to all resources.
