# variables.tf Documentation

## 1. Overview

Defines all input variables for the flat Phase 2 Terraform configuration. These variables control project identity, region, compute sizing for the Cloud Run processor, file-processing parameters, and lifecycle policies for the staging bucket.

## 2. Prerequisites

- A valid GCP project ID.
- A deployer service account JSON key file (referenced by `deployer_sa_key_path`).
- Knowledge of the Phase 1 landing bucket name to pass as `landing_bucket_name`.

## 3. Upstream & Downstream Dependencies

**Upstream (values provided externally):**
- `project_id`, `region`, `environment` -- core GCP project identifiers.
- `landing_bucket_name` -- the name of the landing bucket created by Phase 1. Passed in via `terraform.tfvars` or `-var`.
- `deployer_sa_key_path` -- path to the deployer service account key, created during project bootstrap.

**Downstream (consumed by):**
- Every file in the flat config (`main.tf`, `build.tf`, `apis.tf`, `ack_deadline.tf`) references these variables.
- `processor_memory`, `processor_cpu`, `max_instances`, `chunksize`, `file_size_threshold_mb` are passed as Cloud Run service configuration and environment variables.

## 4. Code Walkthrough

| Variable | Type | Default | Validation | Purpose |
|---|---|---|---|---|
| `project_id` | string | (required) | -- | GCP project ID |
| `region` | string | `us-central1` | -- | GCP region for all resources |
| `environment` | string | (required) | Must be `dev`, `test`, or `prod` | Environment name, used as resource name prefix |
| `landing_bucket_name` | string | (required) | -- | Phase 1 landing bucket name (Eventarc source) |
| `file_size_threshold_mb` | number | `50` | >= 50 | Files larger than this are split before processing |
| `processor_memory` | number | `8` | 1-32 GiB | Memory allocated to each Cloud Run processor instance |
| `processor_cpu` | number | `4` | 1-8 | CPU cores allocated to each Cloud Run processor instance |
| `max_instances` | number | `100` | 1-1000 | Maximum Cloud Run autoscaling instances |
| `chunksize` | number | `100000` | 10,000-1,000,000 | Number of JSON records per processing chunk |
| `deployer_sa_key_path` | string | (required) | -- | Path to deployer SA JSON key for `local-exec` provisioners |
| `staging_retention_days` | number | `30` | >= 1 day | Lifecycle rule: auto-delete staging objects after this many days |
