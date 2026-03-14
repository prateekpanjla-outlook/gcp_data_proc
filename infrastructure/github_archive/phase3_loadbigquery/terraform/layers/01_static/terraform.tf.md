# terraform.tf

## 1. Overview

Terraform backend and provider configuration for Phase 3 Layer 01 (Static). Configures the required Terraform version, the Google provider, a GCS remote backend for state storage, and a `google_project` data source used by other resources in the layer (e.g., to obtain the project number for service agent IAM bindings).

## 2. Prerequisites

- **Terraform:** >= 1.5
- **Google Provider:** ~> 5.0 (hashicorp/google)
- **GCS State Bucket:** `beaming-glyph-489707-b8-terraform-state` must exist and be accessible by the Terraform runner
- **Authentication:** Valid GCP credentials with permission to read/write the state bucket and manage resources in the target project
- **Variables:** `project_id` and `region` must be set (used by the provider block)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | GCS state bucket | Stores Terraform state at prefix `terraform/state/phase3-static` |
| Downstream | Layer 02 and Layer 03 | Both layers reference this state via `data.terraform_remote_state.static` to read outputs (SA emails, dataset ID, table ID) |
| Same layer | `main.tf`, `elt.tf` | All resources in Layer 01 use the provider and backend defined here |
| Same layer | `main.tf` line 182 | Uses `data.google_project.current.number` for Pub/Sub service agent IAM binding |

## 4. Code Walkthrough

1. **`terraform` block (lines 1-14):** Sets `required_version >= 1.5`, pins the Google provider to `~> 5.0`, and configures a GCS backend with bucket `beaming-glyph-489707-b8-terraform-state` and prefix `terraform/state/phase3-static`.

2. **`provider "google"` (lines 17-21):** Sets the default project and region from variables, with a 120-second request timeout.

3. **`data "google_project" "current"` (lines 23-25):** Looks up the current project metadata. The `.number` attribute is used in `main.tf` to construct the Pub/Sub service agent email (`service-{number}@gcp-sa-pubsub.iam.gserviceaccount.com`).
