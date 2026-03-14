# variables.tf

## 1. Overview

Input variable declarations for Phase 3 Layer 02 (First-time). Defines six parameters consumed by `main.tf` to create IAM bindings on the BigQuery dataset and GCS staging bucket.

## 2. Prerequisites

- **Terraform workspace or `.tfvars` file:** Must supply `project_id`, `region`, `environment`, and `staging_bucket_name` (none have universally safe defaults except `dataset_id` and `table_id`)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Phase 2 infrastructure | The `staging_bucket_name` value comes from the Phase 2 staging bucket |
| Downstream | `main.tf` (same layer) | All variables are consumed by IAM binding resources |

## 4. Code Walkthrough

1. **`project_id`** (string, required) -- GCP project ID.

2. **`region`** (string, required) -- GCP region. No default in this layer (unlike Layer 01).

3. **`environment`** (string, required) -- Environment name (`dev`, `prod`). Used in labels.

4. **`staging_bucket_name`** (string, required) -- Name of the GCS staging bucket from Phase 2. Used to scope IAM bindings for `bq_loader` and the Eventarc service agent.

5. **`dataset_id`** (string, default `github_archive`) -- BigQuery dataset ID for the dataset-level IAM binding.

6. **`table_id`** (string, default `github_events`) -- BigQuery table ID. Declared for consistency but not directly referenced in Layer 02 resources.
