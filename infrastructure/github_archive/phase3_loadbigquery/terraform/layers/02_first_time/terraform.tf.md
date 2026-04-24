# terraform.tf

## 1. Overview

Terraform backend and provider configuration for Phase 3 Layer 02 (First-time). Specifies the required Terraform version, Google provider version, GCS remote backend for state, and the Google provider settings.

## 2. Prerequisites

- **Terraform:** >= 1.5
- **Google Provider:** ~> 5.0 (hashicorp/google)
- **GCS State Bucket:** `beaming-glyph-489707-b8-terraform-state` must exist and be writable
- **Authentication:** Valid GCP credentials for the target project
- **Variables:** `project_id` and `region` must be set

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | GCS state bucket | Stores state at prefix `terraform/state/phase3-first-time` |
| Downstream | Layer 03 | Layer 03 references this state via `data.terraform_remote_state.first_time` |
| Same layer | `main.tf` | All resources use the provider and backend defined here |

## 4. Code Walkthrough

1. **`terraform` block (lines 4-17):** Sets `required_version >= 1.5`, pins Google provider to `~> 5.0`, and configures a GCS backend at prefix `terraform/state/phase3-first-time`.

2. **`provider "google"` (lines 19-23):** Sets the default project and region from variables with a 120-second request timeout.
