# Terraform Deployer Service Account Setup Guide

## Overview

This guide explains how to set up a Terraform deployer service account with all necessary permissions to deploy the GitHub Archive infrastructure across all 3 phases.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed
- Active GCP project
- Appropriate permissions to create service accounts and grant IAM roles

## Quick Start

### 1. Run the Setup Script

```bash
export PROJECT_ID="your-project-id"
export ENVIRONMENT="test"  # or dev/prod

./infrastructure/setup-terraform-deployer.sh
```

### 2. Configure Authentication

**Option A: Service Account Impersonation (Recommended)**

```bash
# Authenticate with gcloud
gcloud auth application-default login

# Set impersonation
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=test-terraform-deployer@your-project-id.iam.gserviceaccount.com
```

**Option B: Service Account Key**

```bash
# The script creates a key file
export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/test-terraform-deployer-key.json

# Secure the key
chmod 600 test-terraform-deployer-key.json
```

## Permissions Breakdown

### Core Infrastructure Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/compute.admin` | Manage compute resources | VPC networks, subnets |
| `roles/compute.networkAdmin` | Manage networking | Network configuration |
| `roles/compute.securityAdmin` | Manage security | Firewalls, security rules |

### Cloud Run Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/run.admin` | Full control of Cloud Run | Jobs, Services, revisions |
| `roles/run.developer` | Deploy and manage | Cloud Run resources |

### Cloud Functions Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/cloudfunctions.admin` | Full control | Cloud Functions, triggers |

### Storage Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/storage.admin` | Full control | All GCS buckets and objects |

### BigQuery Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/bigquery.admin` | Full control | Datasets, tables, jobs |

### IAM and Service Account Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/iam.serviceAccountAdmin` | Create/manage service accounts | All service accounts |
| `roles/iam.serviceAccountUser` | Impersonate service accounts | Grant actAs permission |
| `roles/resourcemanager.projectIamAdmin` | Manage project IAM | Project-level permissions |

### Orchestration Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/cloudscheduler.admin` | Manage scheduler jobs | Cloud Scheduler |
| `roles/eventarc.admin` | Manage event triggers | Eventarc triggers |
| `roles/pubsub.admin` | Manage pub/sub topics | Pub/Sub resources |

### Build and Deployment Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/cloudbuild.builds.builder` | Trigger builds | Cloud Build |
| `roles/artifactregistry.admin` | Manage container images | Artifact Registry |

### Observability Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/logging.logWriter` | Write logs | Cloud Logging |
| `roles/monitoring.metricWriter` | Write metrics | Cloud Monitoring |
| `roles/monitoring.admin` | Manage monitoring | Monitoring resources |

### Service Management Permissions

| Permission | Purpose | Resources |
|------------|---------|-----------|
| `roles/serviceusage.serviceUsageAdmin` | Enable/disable APIs | Service Usage API |
| `roles/servicemanagement.serviceViewer` | View services | Service Management |

## Service Account Impersonation

The Terraform deployer needs to impersonate the following service accounts that are created during deployment:

### Phase 1: Ingestion
- `{env}-github-archive-downloader@{project}.iam.gserviceaccount.com`
- `{env}-scheduler@{project}.iam.gserviceaccount.com`

### Phase 2: Processing
- `{env}-github-archive-processor@{project}.iam.gserviceaccount.com`
- `{env}-file-splitter@{project}.iam.gserviceaccount.com`
- `{env}-eventarc-invoker@{project}.iam.gserviceaccount.com`

### Phase 3: Loading
- `{env}-bq-loader@{project}.iam.gserviceaccount.com`
- `{env}-eventarc-invoker-bq@{project}.iam.gserviceaccount.com`

## Required APIs

The following Google Cloud APIs must be enabled:

- `cloudresourcemanager.googleapis.com`
- `iam.googleapis.com`
- `compute.googleapis.com`
- `run.googleapis.com`
- `cloudfunctions.googleapis.com`
- `storage.googleapis.com`
- `bigquery.googleapis.com`
- `cloudscheduler.googleapis.com`
- `eventarc.googleapis.com`
- `pubsub.googleapis.com`
- `cloudbuild.googleapis.com`
- `servicemanagement.googleapis.com`
- `serviceusage.googleapis.com`
- `logging.googleapis.com`
- `monitoring.googleapis.com`
- `artifactregistry.googleapis.com`
- `secretmanager.googleapis.com`

The setup script automatically enables all required APIs.

## Security Best Practices

### Development Environment

1. **Use Service Account Keys**: For local development, keys are acceptable
2. **Rotate Keys Regularly**: Change keys every 90 days
3. **Store Keys Securely**: Use environment variables or secret managers
4. **Never Commit Keys**: Add key files to `.gitignore`

### Production Environment

1. **Use Impersonation**: Never use keys in production
2. **Least Privilege**: Remove unused permissions
3. **Audit Access**: Enable Cloud Audit Logs
4. **Separate Accounts**: Use different accounts for different environments
5. **Conditional Access**: Implement conditional IAM policies

### Example: Impersonation with Workload Identity Federation

```bash
# Authenticate with Google Cloud
gcloud auth login

# Impersonate the service account
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=test-terraform-deployer@your-project.iam.gserviceaccount.com

# Verify impersonation works
gcloud iam service-accounts get-iam-policy $GOOGLE_IMPERSONATE_SERVICE_ACCOUNT
```

## Verification

### 1. Verify Service Account Exists

```bash
gcloud iam service-accounts describe test-terraform-deployer@your-project.iam.gserviceaccount.com
```

### 2. Verify Permissions

```bash
# Get the service account's IAM policy
gcloud projects get-iam-policy your-project-id \
  --filter="bindings.member:serviceAccount:test-terraform-deployer@your-project.iam.gserviceaccount.com"
```

### 3. Test Authentication

```bash
# With impersonation
export GOOGLE_IMPERSONATE_SERVICE_ACCOUNT=test-terraform-deployer@your-project.iam.gserviceaccount.com
gcloud auth application-default print-access-token

# With key file
export GOOGLE_APPLICATION_CREDENTIALS=./test-terraform-deployer-key.json
gcloud auth application-default print-access-token
```

### 4. Test Terraform Access

```bash
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform init
terraform plan -var="project_id=your-project-id" -var="environment=test"
```

## Troubleshooting

### Issue: Permission Denied Errors

**Symptoms**: Terraform fails with `Permission denied` errors

**Solutions**:
1. Verify the service account has all required roles
2. Check authentication is correctly configured
3. Ensure APIs are enabled
4. Verify project ID and environment variables

### Issue: Service Account Does Not Exist

**Symptoms**: `Service account not found` error

**Solutions**:
1. Run the setup script again
2. Verify the PROJECT_ID is correct
3. Check you have permissions to create service accounts

### Issue: Impersonation Fails

**Symptoms**: `Could not impersonate` error

**Solutions**:
1. Verify you have `roles/iam.serviceAccountTokenCreator` on the service account
2. Check the service account email is correct
3. Ensure your personal account has impersonation permissions

### Issue: APIs Not Enabled

**Symptoms**: `API not enabled` errors

**Solutions**:
1. Run the setup script (it enables all required APIs)
2. Manually enable APIs:
   ```bash
   gcloud services enable run.googleapis.com --project=your-project-id
   ```

## Manual Setup (Alternative to Script)

If you prefer to set up the service account manually:

### 1. Create Service Account

```bash
gcloud iam service-accounts create test-terraform-deployer \
  --display-name="Test Terraform Deployer" \
  --description="Service account for deploying GitHub Archive infrastructure" \
  --project=your-project-id
```

### 2. Grant Core Roles

```bash
PROJECT_ID="your-project-id"
DEPLOYER_SA="test-terraform-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Core infrastructure
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/compute.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/run.admin"

# Storage and BigQuery
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/bigquery.admin"

# IAM and Service Accounts
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/iam.serviceAccountAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$DEPLOYER_SA" \
  --role="roles/iam.serviceAccountUser"

# Add additional roles as needed...
```

### 3. Enable APIs

```bash
gcloud services enable run.googleapis.com \
  bigquery.googleapis.com \
  storage.googleapis.com \
  cloudscheduler.googleapis.com \
  eventarc.googleapis.com \
  --project=your-project-id
```

### 4. Create Key (if needed)

```bash
gcloud iam service-accounts keys create test-terraform-deployer-key.json \
  --iam-account=$DEPLOYER_SA \
  --project=your-project-id
```

## Cleanup

To remove the deployer service account:

```bash
export PROJECT_ID="your-project-id"
export DEPLOYER_SA="test-terraform-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Delete the service account
gcloud iam service-accounts delete $DEPLOYER_SA --project=$PROJECT_ID

# Delete the key file (if it exists)
rm -f test-terraform-deployer-key.json
```

**Warning**: This will revoke all permissions and the service account cannot be recovered.

## Additional Resources

- [Terraform Google Provider Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [IAM Best Practices](https://cloud.google.com/iam/docs/using-iam-best-practices)
- [Service Account Impersonation](https://cloud.google.com/iam/docs/impersonating-service-accounts)
- [Cloud Run Permissions](https://cloud.google.com/run/docs/reference/iam/roles)

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the Terraform deployment logs
3. Check Cloud Audit Logs for permission issues
4. Verify all prerequisites are met
