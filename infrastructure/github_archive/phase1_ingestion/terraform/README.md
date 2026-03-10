# Phase 1: GitHub Archive Ingestion

This Terraform configuration deploys **only the resources needed for Phase 1** of the GitHub Archive data pipeline.

## What Gets Deployed (4 resources)

| Resource | Name Pattern | Purpose |
|----------|--------------|---------|
| Service Account | `{env}-github-archive-downloader` | Downloads files from GitHub Archive |
| GCS Bucket | `{project_id}-{env}-github-archive-landing` | Landing zone for raw archive files |
| Cloud Run Job | `{env}-github-archive-download-gsutil` | gsutil-based streaming download |
| Cloud Scheduler | `{env}-github-archive-download-job` | Hourly trigger (30 min past) |

## Prerequisites

1. **Enable Required APIs** (run from project root):
   ```bash
   ./infrastructure/scripts/enable-apis.sh <PROJECT_ID>
   ```

2. **Create Terraform Deployer Service Account**:
   ```bash
   ./infrastructure/scripts/create-terraform-deployer-account.sh <PROJECT_ID> <ENVIRONMENT>
   ```

## Quick Start

```bash
cd infrastructure/phase1_ingestion/terraform

# Initialize Terraform
terraform init

# Review the plan
terraform plan -var="project_id=dev-dataprocessing-489305" -var="environment=dev"

# Apply
terraform apply -var="project_id=dev-dataprocessing-489305" -var="environment=dev"
```

## Or Use the Deployment Script

```bash
# From project root
./infrastructure/scripts/phase1_deploy.sh <PROJECT_ID> <ENVIRONMENT> [REGION]
```

Example:
```bash
./infrastructure/scripts/phase1_deploy.sh dev-dataprocessing-489305 dev us-central1
```

## Resource Names (dev environment example)

| Resource | Full Name/ID |
|----------|--------------|
| SA Email | `dev-github-archive-downloader@dev-dataprocessing-489305.iam.gserviceaccount.com` |
| Bucket | `dev-dataprocessing-489305-dev-github-archive-landing` |
| Job | `dev-github-archive-download-gsutil` |
| Scheduler | `dev-github-archive-download-job` |

## Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `project_id` | GCP Project ID | - | Yes |
| `region` | GCP Region | `us-central1` | No |
| `environment` | Environment name | `dev` | No |
| `force_destroy` | Allow bucket deletion with data | `false` | No |
| `bucket_lifecycle_days` | Days before auto-delete | `90` | No |

## Verification After Deployment

```bash
# Check service account
gcloud iam service-accounts describe dev-github-archive-downloader@<PROJECT_ID>.iam.gserviceaccount.com

# Check bucket
gsutil ls gs://<PROJECT_ID>-dev-github-archive-landing

# Check Cloud Run Job
gcloud run jobs list --filter="dev-github-archive-download-gsutil"

# Check Scheduler
gcloud scheduler jobs list --filter="dev-github-archive-download-job"
```

## What's NOT Included (Phase 2+)

This Phase 1 configuration intentionally does NOT include:
- BigQuery datasets/tables
- Data processing Cloud Run Jobs
- Cloud Run Services
- Pub/Sub topics/subscriptions
- Eventarc triggers
- Monitoring/alerting

These will be added in later phases.

## Next Steps After Phase 1

1. Build and deploy the gsutil download script container
2. Run a manual test of the Cloud Run Job
3. Verify files appear in the landing bucket
4. Proceed to Phase 2 (processing)
