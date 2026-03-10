# Test Project Setup Guide

**Project ID**: `beaming-glyph-489707-b8`

This guide shows you how to quickly set up and deploy the GitHub Archive infrastructure to your test project.

## 🚀 Quick Start (3 Commands)

### 1. Set up the Terraform deployer

```bash
# The setup script now uses your test project ID by default
./infrastructure/setup-terraform-deployer.sh
```

This creates:
- Service account: `test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com`
- Key file: `test-terraform-deployer-key.json`
- All necessary IAM permissions (40+ roles)
- Required Google Cloud APIs

### 2. Configure authentication

```bash
source ./infrastructure/use-terraform-deployer-key.sh
```

### 3. Deploy everything

```bash
./infrastructure/deploy-all.sh
```

## 📋 What Gets Deployed

### Phase 1: Ingestion
- **Bucket**: `beaming-glyph-489707-b8-test-github-archive-landing`
- **Cloud Run Job**: `test-github-archive-download-gsutil`
- **Scheduler Job**: Automated downloads every hour

### Phase 2: Processing
- **Bucket**: `beaming-glyph-489707-b8-test-github-archive-staging`
- **Cloud Run Service**: `test-github-archive-processor`
- **Eventarc Trigger**: Responds to new files in landing bucket
- **Cloud Run Job**: `test-file-splitter` for large files

### Phase 3: Loading
- **BigQuery Dataset**: `github_archive`
- **BigQuery Table**: `github_events` (partitioned by day)
- **Cloud Function**: `test-bq-loader` triggered by staging bucket

## 🔧 Configuration

All scripts now default to your test project. You can override if needed:

```bash
# Override defaults (optional)
export PROJECT_ID="different-project"
export ENVIRONMENT="prod"

# Run setup
./infrastructure/setup-terraform-deployer.sh
```

## 📁 Files Modified

| File | Default Value | New Default |
|------|---------------|-------------|
| `setup-terraform-deployer.sh` | Required parameter | `beaming-glyph-489707-b8` |
| `deploy-all.sh` | `your-test-project` | `beaming-glyph-489707-b8` |
| `test-project-config.sh` | N/A | New config file |

## 🔑 Service Account Details

**Service Account Email**: `test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com`

**Key File**: `test-terraform-deployer-key.json` (created in project root)

**Permissions**: 40+ IAM roles including:
- Compute Admin
- Cloud Run Admin
- BigQuery Admin
- Storage Admin
- IAM Service Account Admin
- And 35+ more...

## ✅ Verification Commands

```bash
# Check service account exists
gcloud iam service-accounts describe test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com

# Verify authentication
gcloud auth application-default print-access-token

# Check deployed resources
gcloud run jobs list --project=beaming-glyph-489707-b8 --region=us-central1
gcloud run services list --project=beaming-glyph-489707-b8 --region=us-central1
gsutil ls gs://beaming-glyph-489707-b8-test-github-archive-landing
bq --project_id=beaming-glyph-489707-b8 ls -d github_archive
```

## 🧪 Test the Pipeline

After deployment:

```bash
# Manually trigger the downloader job
gcloud run jobs execute test-github-archive-download-gsutil \
  --project=beaming-glyph-489707-b8 \
  --region=us-central1

# Monitor logs
gcloud logging logs tail --project=beaming-glyph-489707-b8 \
  --resource="projects/beaming-glyph-489707-b8/locations/us-central1/services/test-github-archive-processor"

# Query BigQuery (after data loads)
bq query --project_id=beaming-glyph-489707-b8 \
  'SELECT COUNT(*) as event_count, event_type FROM github_archive.github_events GROUP BY event_type ORDER BY event_count DESC LIMIT 10'
```

## 🔄 Clean Up

To remove all resources:

```bash
# Delete service account
gcloud iam service-accounts delete test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com --project=beaming-glyph-489707-b8

# Destroy infrastructure (run in each terraform directory)
terraform destroy -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Remove key file
rm -f test-terraform-deployer-key.json
```

## 📊 Resource Summary

| Resource Type | Count | Naming Pattern |
|---------------|-------|----------------|
| Service Accounts | 1 | `test-terraform-deployer` |
| GCS Buckets | 2 | `{project}-test-github-archive-{landing,staging}` |
| Cloud Run Jobs | 2 | `test-github-archive-download-gsutil`, `test-file-splitter` |
| Cloud Run Services | 1 | `test-github-archive-processor` |
| Cloud Functions | 1 | `test-bq-loader` |
| BigQuery Datasets | 1 | `github_archive` |
| BigQuery Tables | 1 | `github_events` |
| Scheduler Jobs | 1 | `test-github-archive-scheduler` |
| Eventarc Triggers | 2 | For landing and staging buckets |

## 💰 Estimated Cost (Test Project)

Based on us-central1 pricing:

- **Cloud Run**: $0-40/month (depends on usage)
- **Cloud Storage**: $0-20/month (depends on data volume)
- **BigQuery**: $0-50/month (depends on query volume)
- **Cloud Scheduler**: ~$3/month
- **Cloud Functions**: $0-10/month (depends on invocations)

**Total estimated range**: $3-120/month (mostly depends on data volume and query activity)

## 🆘 Troubleshooting

### "Project not found" error
```bash
# Verify you have access to the project
gcloud projects describe beaming-glyph-489707-b8

# List your accessible projects
gcloud projects list
```

### "Permission denied" errors
```bash
# Re-run the setup script to ensure permissions are correct
./infrastructure/setup-terraform-deployer.sh

# Verify the service account has the right roles
gcloud projects get-iam-policy beaming-glyph-489707-b8 \
  --filter="bindings.member:serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"
```

### "Key file not found" error
```bash
# Make sure you're in the project root directory
cd C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project

# Verify the key file exists
ls -la test-terraform-deployer-key.json

# If missing, re-run setup
./infrastructure/setup-terraform-deployer.sh
```

## 📚 Additional Documentation

- [Complete Setup Guide](./TERRAFORM_DEPLOYER_SETUP.md)
- [Quick Start Key Authentication](./QUICK_START_KEY_AUTH.md)
- [Terraform Deployment Guide](./TERRAFORM_DEPLOYMENT_GUIDE.md)
