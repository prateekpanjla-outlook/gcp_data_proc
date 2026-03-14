# main.tf

## 1. Overview

Configures the Terraform backend and Google Cloud provider for Phase 1 (GitHub Archive Ingestion). This is the entrypoint that pins the Terraform version, declares the `hashicorp/google` provider, and stores remote state in a GCS bucket under the `terraform/state/phase1-ingestion` prefix.

## 2. Prerequisites

- Terraform >= 1.5.0 installed.
- The GCS state bucket `beaming-glyph-489707-b8-terraform-state` must already exist and be accessible to the identity running `terraform init`.
- The `google` provider version `~> 5.0` must be resolvable from the configured registry.
- Input variables `var.project_id` and `var.region` must be supplied (defined in `variables.tf`).

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | GCS state bucket (`beaming-glyph-489707-b8-terraform-state`) | Must exist before `terraform init` |
| Upstream | `variables.tf` | Provides `project_id` and `region` |
| Downstream | Every other `.tf` file in this layer | All resources inherit the provider and backend configured here |

## 4. Code Walkthrough

1. **`terraform` block** (lines 8-23) -- Sets `required_version` to `>= 1.5.0` and declares the `hashicorp/google` provider at `~> 5.0`. Configures a `gcs` backend with a hardcoded bucket name and a `phase1-ingestion` state prefix to isolate this layer's state from other phases.

2. **`provider "google"` block** (lines 26-30) -- Configures the Google provider with the project, region, and a 120-second request timeout. All resources in the layer inherit these defaults.
