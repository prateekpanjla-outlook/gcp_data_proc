# variables.tf

## 1. Overview

Declares all input variables for the Phase 1 Terraform layer. These variables control the target GCP project, region, environment name, bucket lifecycle policy, and the path to a deployer service account key used for Cloud Build authentication.

## 2. Prerequisites

- A valid GCP project ID.
- A deployer service account JSON key file on disk (referenced by `deployer_sa_key_path`).
- Values are typically supplied via a `.tfvars` file or CI/CD pipeline variables.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | Caller / `.tfvars` file | Supplies values at plan/apply time |
| Downstream | `main.tf` | `project_id`, `region` feed the provider |
| Downstream | `storage.tf` | `force_destroy`, `bucket_lifecycle_days` configure the landing bucket |
| Downstream | `cloud_run_jobs.tf`, `scheduler.tf`, `service_accounts.tf` | `project_id`, `region`, `environment` used in resource names |
| Downstream | `build.tf` | `deployer_sa_key_path` authenticates the Cloud Build local-exec provisioner |

## 4. Code Walkthrough

1. **`project_id`** (string, required) -- Google Cloud project ID. No default; must be explicitly provided.

2. **`region`** (string, default `"us-central1"`) -- GCP region for all regional resources (buckets, Cloud Run, Scheduler, Artifact Registry).

3. **`environment`** (string, default `"dev"`) -- Environment label used in resource naming. Validated to one of `dev`, `test`, `staging`, or `prod`.

4. **`force_destroy`** (bool, default `false`) -- When `true`, allows Terraform to delete GCS buckets that still contain objects. In `storage.tf` this is always forced `true` for `dev` regardless of this variable.

5. **`bucket_lifecycle_days`** (number, default `6`) -- Number of days before objects in the landing bucket are automatically deleted. Must be >= 1.

6. **`deployer_sa_key_path`** (string, required) -- Filesystem path to a JSON key for the deployer service account. Used in `build.tf` to authenticate `gcloud builds submit`.
