# terraform.tf

## 1. Overview

Terraform backend and provider configuration for Phase 3 Layer 03 (Operational). Specifies the required Terraform version, Google provider version, GCS remote backend for state, and the Google provider settings.

## 2. Prerequisites

- **Terraform:** >= 1.5
- **Google Provider:** ~> 5.0 (hashicorp/google)
- **GCS State Bucket:** `beaming-glyph-489707-b8-terraform-state` must exist and be writable
- **Authentication:** Valid GCP credentials for the target project
- **Variables:** `project_id` and `region` must be set

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | GCS state bucket | Stores state at prefix `terraform/state/phase3-operational` |
| Same layer | `main.tf` | All resources use the provider and backend defined here |
| References | Layer 01 and Layer 02 state | `main.tf` reads remote state from `phase3-static` and `phase3-first-time` prefixes in the same bucket |

## 4. Code Walkthrough

1. **`terraform` block (lines 1-14):** Sets `required_version >= 1.5`, pins Google provider to `~> 5.0`, and configures a GCS backend at prefix `terraform/state/phase3-operational`.

2. **`provider "google"` (lines 16-20):** Sets the default project and region from variables with a 120-second request timeout.
