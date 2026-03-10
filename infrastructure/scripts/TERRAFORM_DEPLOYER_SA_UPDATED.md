# Terraform Deployer Service Account - UPDATED

**Last Updated:** 2026-03-11
**Verified Against:** dev-dataprocessing-489305 (Live Environment)

This document describes the Terraform Deployer Service Account used for infrastructure deployment, with actual verification from the Google Cloud project.

## Overview

The Terraform Deployer Service Account is used to authenticate Terraform when deploying Google Cloud resources. This follows security best practices by:

1. **Separation of concerns** - Infrastructure deployment uses a dedicated service account
2. **Principle of least privilege** - Only required roles are granted
3. **Auditability** - All actions are tracked under a single identity
4. **Key-based authentication** - Uses service account key stored in `secrets/terraform/`

## ✅ Live Environment Verification

**Project:** dev-dataprocessing-489305
**Service Account:** dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com
**Status:** ✅ Active and properly configured
**OAuth2 Client ID:** 117781807734901407743

## Naming Convention

Following the project convention:
```
{env_prefix}-terraform-deployer@{project_id}.iam.gserviceaccount.com
```

**Examples:**
- Dev: `dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com` ✅ Verified
- Prod: `prod-terraform-deployer@{project_id}.iam.gserviceaccount.com`

## Required Roles (✅ VERIFIED - 15/15 Present)

All 15 required roles have been verified in the live environment:

| Role | Purpose | Status |
|------|---------|--------|
| `roles/editor` | Base permissions for most GCP resources | ✅ Verified |
| `roles/resourcemanager.projectIamAdmin` | Create SAs & grant IAM bindings | ✅ Verified |
| `roles/iam.serviceAccountAdmin` | Manage SA properties | ✅ Verified |
| `roles/cloudbuild.builds.builder` | Build container images | ✅ Verified |
| `roles/run.admin` | Cloud Run Jobs & Services | ✅ Verified |
| `roles/cloudscheduler.admin` | Cloud Scheduler jobs | ✅ Verified |
| `roles/storage.admin` | Create GCS buckets | ✅ Verified |
| `roles/iam.serviceAccountTokenCreator` | Impersonate service accounts | ✅ Verified |
| `roles/artifactregistry.admin` | Artifact Registry | ✅ Verified |
| `roles/bigquery.admin` | BigQuery datasets | ✅ Verified |
| `roles/pubsub.admin` | Pub/Sub topics & subscriptions | ✅ Verified |
| `roles/cloudfunctions.admin` | Cloud Functions | ✅ Verified |
| `roles/monitoring.admin` | Monitoring dashboards & alerts | ✅ Verified |
| `roles/eventarc.admin` | Eventarc triggers | ✅ Verified |
| `roles/logging.admin` | Cloud Logging resources | ✅ Verified |

## ✅ Deployed Resources (Live Verification)

### Service Accounts (11 found)

**Phase 1 - Ingestion:**
| Service Account | Email | Status | Purpose |
|-----------------|-------|--------|---------|
| Dev GitHub Archive Downloader | `dev-github-archive-downloader@...` | ✅ Active | Downloads GitHub Archive files |
| Dev Cloud Scheduler | `dev-scheduler@...` | ✅ Active | Triggers hourly downloads |

**Phase 2 - Processing:**
| Service Account | Email | Status | Purpose |
|-----------------|-------|--------|---------|
| Dev GitHub Archive Processor | `dev-github-archive-processor@...` | ✅ Active | Processes JSON files |
| Dev File Splitter | `dev-file-splitter@...` | ✅ Active | Splits large files |
| Dev Eventarc Invoker | `dev-eventarc-invoker@...` | ✅ Active | Invokes processor service |

**Phase 3 - BigQuery Loading:**
| Service Account | Email | Status | Purpose |
|-----------------|-------|--------|---------|
| Dev BQ Loader | `dev-bq-loader@...` | ✅ Active | Loads data to BigQuery |
| Dev Eventarc Invoker (BQ) | `dev-eventarc-invoker-bq@...` | ✅ Active | Invokes loader function |

**Infrastructure:**
| Service Account | Email | Status | Purpose |
|-----------------|-------|--------|---------|
| Dev Terraform Deployer | `dev-terraform-deployer@...` | ✅ Active | Terraform deployments |
| Dev Cloud Build | `dev-cloud-build@...` | ✅ Active | Builds container images |

**Default (Google-managed):**
| Service Account | Email | Status | Purpose |
|-----------------|-------|--------|---------|
| App Engine default | `{project}@appspot.gserviceaccount.com` | ✅ Active | App Engine |
| Compute default | `{project_number}-compute@developer.gserviceaccount.com` | ✅ Active | Compute Engine |

### Compute Resources

**Cloud Run Jobs (1 found):**
| Name | Status | Purpose |
|------|--------|---------|
| `dev-github-archive-download-gsutil` | ✅ Active | Downloads GitHub Archive hourly |

**Cloud Run Services (2 found):**
| Name | UID | Purpose |
|------|-----|---------|
| `dev-github-archive-processor` | `60b634cd-1b95-4610-b80a-71bdfbd4ccc2` | Processes GitHub events |
| `dev-bq-loader` | `fcb72488-ceef-4fc7-bf52-85f235dd9fff` | Loads data to BigQuery |

**Cloud Scheduler Jobs (1 found):**
| Name | Status | Purpose |
|------|--------|---------|
| `dev-github-archive-download-job` | ✅ Enabled | Triggers hourly download |

**Cloud Functions (1 found):**
| Name | Status | Purpose |
|------|--------|---------|
| `dev-bq-loader` | ✅ Active | Event-triggered BigQuery loading |

### Storage & Data Resources

**GCS Buckets (5 found):**
| Name | Location | Purpose |
|------|----------|---------|
| `dev-dataprocessing-489305-dev-github-archive-landing` | US-CENTRAL1 | Raw GitHub Archive files |
| `dev-dataprocessing-489305-dev-github-archive-staging` | US-CENTRAL1 | Processed NDJSON files |
| `dev-dataprocessing-489305-dev-gcf-source` | US-CENTRAL1 | Cloud Functions source |
| `dev-dataprocessing-489305_cloudbuild` | US | Cloud Build logs |
| `gcf-v2-sources-973986259857-us-central1` | US-CENTRAL1 | Cloud Functions v2 sources |

**BigQuery Datasets (3 found):**
| Dataset | Location | Purpose |
|---------|----------|---------|
| `github_archive` | US | Production GitHub events |
| `github_archive_test` | US | Testing/development |
| `local_testing` | US | Local development testing |

**Pub/Sub Topics (2 found):**
| Topic | Purpose |
|-------|---------|
| `eventarc-us-central1-dev-github-archive-storage-895` | Eventarc for GitHub storage events |
| `eventarc-us-central1-dev-bq-loader-199448-109` | Eventarc for BQ loader trigger |

**Eventarc Triggers (2 found):**
| Name | Target | Purpose |
|------|--------|---------|
| `dev-github-archive-storage` | Processor Service | Triggers on new files in landing bucket |
| `dev-bq-loader-199448` | BQ Loader Function | Triggers on processed files |

**Artifact Registry Repositories (2 found):**
| Repository | Format | Purpose |
|------------|--------|---------|
| `gcf-artifacts` | DOCKER | Cloud Functions container images |
| `github-archive` | DOCKER | GitHub Archive pipeline images |

**Container Images (1 found):**
| Image | Created | Purpose |
|-------|---------|---------|
| `gcr.io/dev-dataprocessing-489305/github-archive-downloader` | - | Phase 1 downloader job |

**Logging Sinks (2 found - Default):**
| Name | Destination | Purpose |
|------|-------------|---------|
| `_Required` | Cloud Logging _Required bucket | Required logs |
| `_Default` | Cloud Logging _Default bucket | All logs |

## Terraform Resources Requiring These Roles

### Service Accounts & IAM
**Total Created:** 11 service accounts (6 custom pipeline SAs + 1 deployer + 1 cloud build + 3 default)

**Pipeline SAs:**
- Phase 1: `dev-github-archive-downloader`, `dev-scheduler`
- Phase 2: `dev-github-archive-processor`, `dev-file-splitter`, `dev-eventarc-invoker`
- Phase 3: `dev-bq-loader`, `dev-eventarc-invoker-bq`

### Compute Resources
**Deployed:**
- 1 Cloud Run Job: github_archive_downloader
- 2 Cloud Run Services: github_processor, bq_loader
- 1 Cloud Function: bq_loader
- 1 Cloud Scheduler Job: github_archive_download

**Planned (from docs):**
- Additional Cloud Run Jobs: hacker_news_fetcher, hacker_news_processor, dlq_processor
- Additional Cloud Scheduler Jobs: hacker_news_poller, partition_cleanup, etc.

### Storage & Data
**Deployed:**
- 3 GCS Buckets (2 pipeline + 1 Cloud Functions)
- 3 BigQuery Datasets
- 2 Pub/Sub Topics (via Eventarc)
- 2 Eventarc Triggers
- 2 Artifact Registry Repositories

### Monitoring
**Current:**
- Default logging sinks only

**Planned (from docs):**
- 4 Monitoring Resources: notification channel, 3 alert policies, 2 metric descriptors, 1 dashboard

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
5. **Principle of Least Privilege**: Only required roles are granted (15 roles total)

## Verification Commands

### Verify Service Account
```bash
gcloud iam service-accounts describe dev-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com
```

### Verify Roles
```bash
gcloud projects get-iam-policy PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:dev-terraform-deployer" \
  --format="table(bindings.role)"
```

### Verify Deployed Resources
```bash
# Service Accounts
gcloud iam service-accounts list --project=PROJECT_ID

# Cloud Run Jobs
gcloud run jobs list --project=PROJECT_ID --region=us-central1

# Cloud Run Services
gcloud run services list --project=PROJECT_ID --region=us-central1

# Cloud Scheduler Jobs
gcloud scheduler jobs list --project=PROJECT_ID --location=us-central1

# GCS Buckets
gcloud storage buckets list --project=PROJECT_ID

# BigQuery Datasets
bq ls --project_id=PROJECT_ID

# Eventarc Triggers
gcloud eventarc triggers list --project=PROJECT_ID --location=us-central1

# Pub/Sub Topics
gcloud pubsub topics list --project=PROJECT_ID

# Artifact Registry
gcloud artifacts repositories list --project=PROJECT_ID --location=us-central1
```

## Discrepancies & Notes

### Additional Resources Found (Not in Original Documentation)

1. **Phase 2 & 3 Service Accounts**: The original documentation listed 7 service accounts, but the live environment has 11 custom service accounts including Phase 2 and 3 specific SAs:
   - `dev-file-splitter` (Phase 2)
   - `dev-eventarc-invoker` (Phase 2)
   - `dev-bq-loader` (Phase 3)
   - `dev-eventarc-invoker-bq` (Phase 3)
   - `dev-cloud-build` (Infrastructure)

2. **Cloud Functions**: The original documentation didn't explicitly mention Cloud Functions, but `dev-bq-loader` is deployed as a 2nd gen Cloud Function.

3. **Eventarc Integration**: The documentation mentions Eventarc triggers, but the live implementation uses Pub/Sub topics auto-created by Eventarc.

### Recommendations

1. **Update Documentation**: This file now includes all verified resources from the live environment.

2. **Complete Deployment**: Some resources from the original documentation are not yet deployed:
   - Additional Cloud Run Jobs (hacker_news, dlq_processor)
   - Additional Cloud Scheduler Jobs
   - Monitoring resources (alert policies, dashboards)

3. **Consider Workload Identity**: For improved security, consider migrating from service account keys to Workload Identity Federation.

4. **Add Monitoring**: Deploy the planned monitoring resources (alert policies, dashboards) for better observability.

## References

- [Google Cloud - Infrastructure Manager Service Account](https://cloud.google.com/infrastructure-manager/docs/configure-service-account)
- [Google Cloud - IAM Service Account Permissions](https://cloud.google.com/iam/docs/service-account-permissions)
- [Terraform Google Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)

---

**Document Version:** 2.0
**Verification Date:** 2026-03-11
**Verified By:** Live environment check against dev-dataprocessing-489305
**Status:** ✅ All 15 roles verified, deployment status documented
