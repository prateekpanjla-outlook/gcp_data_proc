# Terraform Deployer Service Account

This document describes the Terraform Deployer Service Account used for infrastructure deployment.

## Overview

The Terraform Deployer Service Account is used to authenticate Terraform when deploying Google Cloud resources. This follows security best practices by:

1. **Separation of concerns** - Infrastructure deployment uses a dedicated service account
2. **Principle of least privilege** - Only required roles are granted
3. **Auditability** - All actions are tracked under a single identity
4. **Key-based authentication** - Uses service account key stored in `secrets/terraform/`

## Naming Convention

Following the project convention:
```
{env_prefix}-terraform-deployer@{project_id}.iam.gserviceaccount.com
```

**Example:**
- Dev: `dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com`
- Prod: `prod-terraform-deployer@{project_id}.iam.gserviceaccount.com`

## Required Roles

Based on Google Cloud documentation and Terraform resources created:

| Role | Purpose | Resources Managed |
|------|---------|-------------------|
| `roles/editor` | Base permissions for most GCP resources | All resources |
| `roles/resourcemanager.projectIamAdmin` | Create SAs & grant IAM bindings | `google_service_account`, `google_project_iam_member` |
| `roles/iam.serviceAccountAdmin` | Manage SA properties | `google_service_account` |
| `roles/cloudbuild.builds.builder` | Build container images | Container builds |
| `roles/run.admin` | Cloud Run Jobs & Services | `google_cloud_run_v2_job`, `google_cloud_run_v2_service` |
| `roles/cloudscheduler.admin` | Cloud Scheduler jobs | `google_cloud_scheduler_job` |
| `roles/storage.admin` | Create GCS buckets | `google_storage_bucket` |
| `roles/iam.serviceAccountTokenCreator` | Impersonate service accounts | Workload Identity |
| `roles/artifactregistry.admin` | Artifact Registry | `google_artifact_registry_repository` |
| `roles/bigquery.admin` | BigQuery datasets | `google_bigquery_dataset` |
| `roles/pubsub.admin` | Pub/Sub topics & subscriptions | `google_pubsub_topic`, `google_pubsub_subscription` |
| `roles/cloudfunctions.admin` | Cloud Functions | `google_cloudfunctions2_function` |
| `roles/monitoring.admin` | Monitoring dashboards & alerts | `google_monitoring_*` |
| `roles/eventarc.admin` | Eventarc triggers | `google_eventarc_trigger` |
| `roles/logging.admin` | Cloud Logging resources | Logging sinks, metrics |

## Terraform Resources Requiring These Roles

### Service Accounts & IAM (7 SAs created)
- `dev-github-archive-downloader`
- `dev-github-processor`
- `dev-scheduler`
- `sa-github-processor`
- `sa-hn-fetcher`
- `sa-hn-processor`
- `sa-dlq-handler`

### Compute Resources
- **5 Cloud Run Jobs**: github_archive_downloader, github_archive_processor, hacker_news_fetcher, hacker_news_processor, dlq_processor
- **2 Cloud Run Services**: github_processor, hn_processor
- **7 Cloud Scheduler Jobs**: github_archive_download, github_archive_downloader, hacker_news_poller, hacker_news_user_refresh, dlq_processor, partition_cleanup, hn_fetch

### Storage & Data
- **3 GCS Buckets**: github-archive-landing, github-data, hn-data
- **2 BigQuery Datasets**: github, hacker_news
- **2 Pub/Sub Topics**: pipeline_dlq, permanent_failures
- **2 Pub/Sub Subscriptions**: pipeline_dlq_sub, permanent_failures_sub

### Integration
- **2 Eventarc Triggers**: github_storage, hn_scheduler

### Monitoring
- **4 Monitoring Resources**: notification channel, 3 alert policies, 2 metric descriptors, 1 dashboard

## Setup

### 1. Create Service Account

```bash
cd infrastructure/scripts
./create-terraform-deployer-account.sh <PROJECT_ID> <ENVIRONMENT>
```

**Example:**
```bash
./create-terraform-deployer-account.sh dev-dataprocessing-489305 dev
```

This creates:
- Service account: `dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com`
- Key file: `infrastructure/secrets/terraform/dev-terraform-deployer-dev-dataprocessing-489305.json`
- Grants all 15 required roles

### 2. Use with Terraform

**Option A: Environment Variable**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="infrastructure/secrets/terraform/dev-terraform-deployer-dev-dataprocessing-489305.json"
cd infrastructure/terraform
terraform init
terraform plan -var="project_id=dev-dataprocessing-489305" -var="environment=dev"
terraform apply -var="project_id=dev-dataprocessing-489305" -var="environment=dev"
```

**Option B: Terraform Provider Configuration**

Add to `provider.tf` or `backend.tf`:
```hcl
provider "google" {
  project = "dev-dataprocessing-489305"
  region  = "us-central1"

  credentials = "../secrets/terraform/dev-terraform-deployer-dev-dataprocessing-489305.json"
}
```

## Security Considerations

1. **Key Storage**: Keys are stored in `infrastructure/secrets/terraform/` which is gitignored
2. **Key Rotation**: Rotate keys periodically (recommended every 90 days)
3. **Key Permissions**: Keys are created with `chmod 600` (owner read/write only)
4. **Audit**: All Terraform actions are logged under the service account identity in Cloud Audit Logs

## References

- [Google Cloud - Infrastructure Manager Service Account](https://cloud.google.com/infrastructure-manager/docs/configure-service-account)
- [Google Cloud - IAM Service Account Permissions](https://cloud.google.com/iam/docs/service-account-permissions)
- [Terraform Google Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest)
