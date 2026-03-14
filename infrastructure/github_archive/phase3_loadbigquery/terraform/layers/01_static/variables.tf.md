# variables.tf

## 1. Overview

Input variable declarations for Phase 3 Layer 01 (Static). Defines the six configurable parameters used across `main.tf` and `elt.tf` to provision BigQuery resources, service accounts, and IAM bindings.

## 2. Prerequisites

- **Terraform workspace or `.tfvars` file:** Must supply at least `project_id` and `environment` (the only variables without defaults)
- **Valid environment value:** Must be one of `dev`, `test`, or `prod` (enforced by validation block)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Downstream | `main.tf` | Uses `project_id`, `region`, `environment`, `dataset_id`, `table_id`, `partition_expiration_days` |
| Downstream | `elt.tf` | Uses `project_id`, `dataset_id`, `table_id` for fully-qualified BQ table references in SQL |
| Downstream | `outputs.tf` | Outputs are derived from resources that depend on these variables |

## 4. Code Walkthrough

1. **`project_id`** (string, required) -- GCP project ID. Used as the provider default and in resource configurations.

2. **`region`** (string, default `us-central1`) -- GCP region for BigQuery dataset location and resource placement.

3. **`environment`** (string, required) -- Environment name. Validated to be one of `dev`, `test`, or `prod`. Used as a prefix for service account IDs and in labels. Controls `delete_contents_on_destroy` behavior on the dataset.

4. **`dataset_id`** (string, default `github_archive`) -- BigQuery dataset ID.

5. **`table_id`** (string, default `github_events`) -- BigQuery table ID within the dataset.

6. **`partition_expiration_days`** (number, default `366`) -- Number of days before partitions expire. Set to `0` to disable expiration. Validated to be >= 0. Applied to both the dataset default expiration and the table's time partitioning expiration.

7. **`kms_key_name`** (string, default `null`) -- Optional KMS key for BigQuery encryption. Currently declared but not referenced by any resource in this layer.
