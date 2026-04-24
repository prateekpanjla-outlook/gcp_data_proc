# 🚀 Quick Start Deployment Guide

Everything you need to deploy the GitHub Archive infrastructure to a test project.

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

- [ ] **Google Cloud Project** created
  ```bash
  export PROJECT_ID="your-test-project"
  gcloud config set project $PROJECT_ID
  ```

- [ ] **Billing enabled** on the project
  ```bash
  gcloud billing projects describe $PROJECT_ID
  ```

- [ ] **Terraform installed** (v1.0+)
  ```bash
  terraform version
  ```

- [ ] **gcloud CLI** installed and authenticated
  ```bash
  gcloud auth login
  gcloud auth application-default login
  ```

- [ ] **Terraform state bucket** (for storing state)
  ```bash
  gsutil mb -p $PROJECT_ID gs://$PROJECT_ID-terraform-state
  ```

---

## 🎯 Recommended Deployment Order

### Option 1: Automated Deployment (EASIEST)

```bash
# Set your variables
export PROJECT_ID="your-test-project"
export ENVIRONMENT="test"
export REGION="us-central1"

# Run the automated deployment script
bash infrastructure/deploy-all.sh
```

**This will:**
1. Deploy Phase 1 (Ingestion)
2. Deploy Phase 2 (Processing) - all 3 layers
3. Deploy Phase 3 (Loading) - all 3 layers
4. Deploy Phase 2 application code via Cloud Build
5. Validate all resources

**Total time:** ~25 minutes

---

### Option 2: Manual Step-by-Step (MORE CONTROL)

#### Phase 1: Ingestion (~2 minutes)

```bash
cd infrastructure/github_archive/phase1_ingestion/terraform

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"
```

**Validate:**
```bash
gsutil ls gs://$PROJECT_ID-$ENVIRONMENT-github-archive-landing/
gcloud run jobs list --project=$PROJECT_ID --filter="github-archive"
```

---

#### Phase 2: Processing (~6 minutes)

**Layer 01: Static (~1 min)**
```bash
cd infrastructure/github_archive/phase2_process_files/terraform/layers/01_static

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION" \
  -var="landing_bucket_name=$PROJECT_ID-$ENVIRONMENT-github-archive-landing"
```

**Layer 02: First-Time (~3 min)**
```bash
cd ../02_first_time

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"
```

**Layer 03: Operational (~2 min)**
```bash
cd ../03_operational

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION" \
  -var="image_tag=latest"
```

**Validate:**
```bash
gsutil ls gs://$PROJECT_ID-$ENVIRONMENT-github-archive-staging/
gcloud run services describe $ENVIRONMENT-github-archive-processor \
  --project=$PROJECT_ID --region=$REGION
```

---

#### Phase 3: Loading (~6 minutes)

**Layer 01: Static (~1 min)**
```bash
cd infrastructure/github_archive/phase3_loadbigquery/terraform/layers/01_static

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"
```

**Layer 02: First-Time (~2 min)**
```bash
cd ../02_first_time

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION" \
  -var="staging_bucket_name=$PROJECT_ID-$ENVIRONMENT-github-archive-staging"
```

**Layer 03: Operational (~3 min)**
```bash
cd ../03_operational

terraform init
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"
```

**Validate:**
```bash
bq ls --project_id=$PROJECT_ID -d github_archive
gcloud functions describe $ENVIRONMENT-bq-loader \
  --project=$PROJECT_ID --region=$REGION
```

---

### Step 4: Deploy Application Code (~5 minutes)

```bash
cd src/github_archive/phase2_process_files

gcloud builds submit --config=cloudbuild.yaml . \
  --substitutions=_REGION="$REGION",_ENVIRONMENT="$ENVIRONMENT"
```

---

## ✅ Post-Deployment Validation

### Test the Complete Pipeline

```bash
# 1. Manually trigger Phase 1 downloader
gcloud run jobs execute $ENVIRONMENT-github-archive-download-gsutil \
  --project=$PROJECT_ID --region=$REGION

# 2. Wait for file to download, then check landing bucket
sleep 60
gsutil ls gs://$PROJECT_ID-$ENVIRONMENT-github-archive-landing/github-archive/raw/

# 3. Check Phase 2 processing logs
gcloud logging logs tail \
  --project=$PROJECT_ID \
  --resource="projects/$PROJECT_ID/locations/$REGION/services/$ENVIRONMENT-github-archive-processor" \
  --limit=20

# 4. Check staging bucket for processed files
gsutil ls gs://$PROJECT_ID-$ENVIRONMENT-github-archive-staging/

# 5. Check BigQuery for loaded data
bq query --project_id=$PROJECT_ID \
  "SELECT COUNT(*) as row_count, MIN(created_at) as earliest, MAX(created_at) as latest
   FROM github_archive.github_events"
```

---

## 🔧 Troubleshooting Common Issues

### Issue 1: Permission Denied

**Error:** `PERMISSION_DENIED: Permission 'run.services.get' denied`

**Fix:**
```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com \
  --role=roles/run.admin
```

---

### Issue 2: Remote State Not Found

**Error:** `Failed to retrieve state from remote backend`

**Fix:**
```bash
# Create state bucket
gsutil mb -p $PROJECT_ID gs://$PROJECT_ID-terraform-state

# Re-initialize
terraform init
```

---

### Issue 3: Eventarc Trigger Not Firing

**Error:** No events received after file upload

**Fix:**
```bash
# Check Pub/Sub permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:service-$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')@gcp-sa-eventarc.iam.gserviceaccount.com \
  --role=roles/pubsub.subscriber

# Check Eventarc trigger status
gcloud eventarc triggers describe STORAGE_EVENTS \
  --project=$PROJECT_ID --region=$REGION
```

---

### Issue 4: Cloud Build Fails

**Error:** `build step 2 "gcr.io/cloud-builders/gcloud" failed`

**Fix:**
```bash
# Grant Cloud Run Admin role
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member=serviceAccount:$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')-compute@developer.gserviceaccount.com \
  --role=roles/run.admin
```

---

## 📊 Resource Summary After Deployment

### Phase 1: Ingestion (8 resources)
- ✅ 1 GCS bucket (landing)
- ✅ 1 Cloud Run Job (downloader)
- ✅ 1 Cloud Scheduler Job
- ✅ 2 Service Accounts
- ✅ 3 IAM bindings

### Phase 2: Processing (18 resources)
- ✅ 1 GCS bucket (staging)
- ✅ 1 Cloud Run Service (processor)
- ✅ 1 Eventarc Trigger
- ✅ 3 Service Accounts
- ✅ 1 Artifact Registry
- ✅ 1 Cloud Build Trigger
- ✅ 9 GCP APIs enabled
- ✅ 10+ IAM bindings

### Phase 3: Loading (15 resources)
- ✅ 1 GCS bucket (source)
- ✅ 1 Cloud Function 2nd Gen (loader)
- ✅ 1 Eventarc Trigger
- ✅ 1 BigQuery Dataset
- ✅ 1 BigQuery Table
- ✅ 2 Service Accounts
- ✅ 10+ IAM bindings

**Total: 42 resources deployed**

---

## 🎯 Key Variables Reference

### Required Variables
| Variable | Example | Description |
|----------|---------|-------------|
| `project_id` | `your-test-project` | Google Cloud Project ID |
| `environment` | `test` | Environment prefix for resources |
| `region` | `us-central1` | GCP Region |

### Optional Variables (Phase 1)
| Variable | Default | Description |
|----------|---------|-------------|
| `force_destroy` | `false` | Allow bucket deletion even if not empty |
| `bucket_lifecycle_days` | `6` | Landing bucket retention |

### Optional Variables (Phase 2)
| Variable | Default | Description |
|----------|---------|-------------|
| `processor_memory` | `4` | Cloud Run memory (GiB) |
| `processor_cpu` | `2` | Cloud Run CPU |
| `max_instances` | `5` | Max Cloud Run instances |
| `chunksize` | `100000` | Records per chunk |
| `image_tag` | `latest` | Docker image tag |
| `eventarc_ack_deadline_seconds` | `600` | Eventarc timeout |

### Optional Variables (Phase 3)
| Variable | Default | Description |
|----------|---------|-------------|
| `dataset_id` | `github_archive` | BigQuery dataset |
| `table_id` | `github_events` | BigQuery table |
| `partition_expiration_days` | `366` | Partition retention |
| `function_memory` | `256M` | Cloud Function memory |
| `function_timeout` | `120` | Cloud Function timeout (seconds) |
| `max_instances` | `10` | Max Cloud Function instances |
| `delete_after_load` | `false` | Delete source after load |

---

## 📚 Documentation Reference

For detailed information, see:
- `docs/TERRAFORM_DEPLOYMENT_GUIDE.md` - Comprehensive deployment guide
- `docs/RESOURCE_DEPENDENCY_MATRIX.md` - Complete dependency analysis
- `docs/DEPLOYMENT_VISUAL_GUIDE.md` - Visual diagrams and checklists

---

## 🎓 Next Steps After Deployment

1. **Monitor the first automated run**
   - Cloud Scheduler triggers at :30 past the hour
   - Check Cloud Run Job execution
   - Verify files appear in landing bucket

2. **Verify event-driven processing**
   - Check Phase 2 processor logs
   - Verify files appear in staging bucket
   - Check Eventarc trigger status

3. **Confirm BigQuery loading**
   - Check Cloud Function logs
   - Query BigQuery for data
   - Verify partitioning and clustering

4. **Set up monitoring and alerts**
   - Cloud Logging queries
   - Cloud Monitoring dashboards
   - Error budget policies

---

`✶ Insight ─────────────────────────────────────`
**Infrastructure as Code Best Practices:** This deployment follows IaC best practices with clear separation of concerns, explicit dependency management, and comprehensive validation. The layered architecture (Static → First-Time → Operational) ensures that frequently changing resources (services, triggers) can be updated without touching stable resources (buckets, service accounts), reducing risk and deployment time.

**Test Project Strategy:** Always deploy to a test project first. This validates your Terraform configuration, IAM permissions, and resource dependencies without affecting production. Once validated in test, you can confidently deploy to production using the same scripts and processes.
`─────────────────────────────────────────────────`

**Ready to deploy? Run:**
```bash
export PROJECT_ID="your-test-project"
export ENVIRONMENT="test"
export REGION="us-central1"
bash infrastructure/deploy-all.sh
```
