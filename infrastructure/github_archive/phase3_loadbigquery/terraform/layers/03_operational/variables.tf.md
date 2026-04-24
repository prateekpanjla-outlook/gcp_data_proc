# variables.tf

## 1. Overview

Input variable declarations for Phase 3 Layer 03 (Operational). Defines twelve parameters for deploying the Cloud Functions 2nd gen BigQuery loader, including project settings, BigQuery target coordinates, staging bucket name, and function runtime configuration (memory, timeout, max instances, delete-after-load behavior).

## 2. Prerequisites

- **Terraform workspace or `.tfvars` file:** Must supply `project_id` and `staging_bucket_name` at minimum; all other variables have defaults

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Phase 2 infrastructure | The `staging_bucket_name` value comes from the Phase 2 staging bucket |
| Downstream | `main.tf` (same layer) | All variables are consumed by the Cloud Function resource, source bucket, IAM bindings, and Eventarc trigger configuration |
| Related | `main.py` environment variables | `dataset_id`, `table_id`, `delete_after_load` are passed through to the function's runtime environment |

## 4. Code Walkthrough

**Project & environment variables:**

1. **`project_id`** (string, required) -- GCP project ID.
2. **`region`** (string, default `us-central1`) -- GCP region for function deployment and Eventarc trigger.
3. **`environment`** (string, default `dev`) -- Environment name. Used in function name prefix, source bucket name, labels, and `force_destroy` logic.

**BigQuery target variables:**

4. **`staging_bucket_name`** (string, required) -- GCS staging bucket from Phase 2. Used as the Eventarc trigger source and in function env vars.
5. **`dataset_id`** (string, default `github_archive`) -- BigQuery dataset ID passed to the function as an environment variable.
6. **`table_id`** (string, default `github_events`) -- BigQuery table ID passed to the function as an environment variable.

**Function configuration variables:**

7. **`function_memory`** (string, default `256M`) -- Memory allocated to the Cloud Function.
8. **`function_timeout`** (number, default `120`) -- Function timeout in seconds. Must accommodate BigQuery load job completion time.
9. **`max_instances`** (number, default `10`) -- Maximum concurrent function instances. Limits parallelism of BigQuery load jobs.
10. **`delete_after_load`** (bool, default `false`) -- Whether the function should delete the source GCS file after a successful BigQuery load. Passed to the function as the `DELETE_AFTER_LOAD` environment variable. Note: the Terraform default is `false` while `main.py` defaults to `true` if the env var is unset.
