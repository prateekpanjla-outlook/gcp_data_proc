# Phase 3: Cloud Functions 2nd gen Deployment Learnings

## Overview

Phase 3 implements the BigQuery loader using Cloud Functions 2nd gen triggered by Eventarc when files arrive in the staging bucket from Phase 2.

## Architecture Decision: Cloud Functions vs Cloud Run

### Why Cloud Functions 2nd gen?

The original design used a Cloud Run container with bq-loader Docker image. However, Cloud Functions 2nd gen was chosen because:

1. **Simpler deployment** - No Docker container build required
2. **Built-in Eventarc trigger** - Event trigger configured directly in the function resource
3. **Lower operational overhead** - Google manages the container runtime
4. **Cost effective** - Pay only for function invocations

### Key Differences

| Aspect | Cloud Run | Cloud Functions 2nd gen |
|--------|-----------|-------------------------|
| Deployment | Docker container | Source code zip |
| Event Trigger | Separate Eventarc resource | Built-in event_trigger block |
| Build | Cloud Build (Docker) | Cloud Build (source) |
| Runtime | Any language (container) | Supported runtimes only |

## Deployment Issues and Resolutions

### Issue 1: Cloud Events Dependency Conflict

**Error:**
```
Build failed with status: FAILURE and message: found incompatible dependencies:
"functions-framework 3.9.1 has requirement cloudevents<=1.11.0,>=1.2.0,
but you have cloudevents 1.12.0."
```

**Root Cause:**
The `cloudevents` package version was too new for the functions-framework.

**Resolution:**
Updated `requirements.txt`:
```python
# Before
cloudevents>=1.0.0

# After
cloudevents>=1.2.0,<=1.11.0
```

### Issue 2: Eventarc Bucket Permission Error

**Error:**
```
Permission "storage.buckets.get" denied on "Bucket \"dev-github-archive-staging\"
could not be validated. Please verify that the bucket exists and that the
Eventarc service account has permission."
```

**Root Cause:**
Two issues:
1. Wrong bucket name (missing project prefix)
2. Eventarc service agent didn't have permission on the bucket

**Resolution:**
1. Use correct bucket name: `dev-dataprocessing-489305-dev-github-archive-staging`
2. Grant Eventarc service agent access:
```bash
gcloud storage buckets add-iam-policy-binding gs://BUCKET_NAME \
  --member="serviceAccount:service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

### Issue 3: Service Account Impersonation

**Requirement:**
Terraform deployer service account needs `roles/iam.serviceAccountUser` on both:
- `bq_loader` service account (for function runtime)
- `eventarc_invoker` service account (for trigger authentication)

**Resolution:**
Added to Layer 01 (`01_static/main.tf`):
```hcl
resource "google_service_account_iam_member" "terraform_actas_eventarc_invoker" {
  service_account_id = google_service_account.eventarc_invoker.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.environment}-terraform-deployer@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_service_account_iam_member" "terraform_actas_bq_loader" {
  service_account_id = google_service_account.bq_loader.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.environment}-terraform-deployer@${var.project_id}.iam.gserviceaccount.com"
}
```

## IAM Requirements Summary

### Service Accounts Created

| Service Account | Purpose |
|----------------|---------|
| `dev-bq-loader` | Cloud Function runtime identity |
| `dev-eventarc-invoker-bq` | Eventarc trigger authentication |

### Required IAM Roles

**For `bq_loader` service account:**
- `roles/bigquery.dataEditor` - Write to BigQuery tables
- `roles/bigquery.jobUser` - Run BigQuery load jobs
- `roles/storage.objectAdmin` - Read/delete from staging bucket
- `roles/logging.logWriter` - Write logs
- `roles/monitoring.metricWriter` - Write metrics
- `roles/artifactregistry.reader` - Read container images (Cloud Build)

**For `eventarc_invoker` service account:**
- `roles/eventarc.eventReceiver` - Receive events
- `roles/run.invoker` - Invoke Cloud Function (runs on Cloud Run)
- `roles/logging.logWriter` - Write logs

**For GCS service account:**
- `roles/pubsub.publisher` - Publish events to Pub/Sub (for Eventarc)

**For Eventarc service agent:**
- `roles/storage.objectViewer` - Validate bucket for trigger (on staging bucket)

## Eventarc Acknowledgement Deadline

### Default Configuration

Cloud Functions 2nd gen automatically configures the Pub/Sub subscription with:

| Setting | Value |
|---------|-------|
| Acknowledgement Deadline | 600 seconds (maximum) |
| Message Retention | 24 hours |
| Retry Policy | Exponential backoff (10s to 600s) |

### Why 600 Seconds?

The acknowledgement deadline is the time Pub/Sub waits for a function to acknowledge message processing before redelivering it. The default 10 seconds is too short for most functions.

**Maximum value:** 600 seconds (10 minutes)

**Current status:** Already set to maximum automatically by Cloud Functions 2nd gen.

### Manual Update (if needed)

```bash
# Get subscription ID from trigger
SUBSCRIPTION_ID=$(gcloud eventarc triggers describe "TRIGGER_NAME" \
  --location=REGION --format=json | jq -r '.transport.pubsub.subscription')

# Update ack deadline to maximum (600 seconds)
gcloud pubsub subscriptions update "$SUBSCRIPTION_ID" --ack-deadline=600
```

## BigQuery Schema Considerations

### Partitioning Requirement

The `created_at` field must be `TIMESTAMP` type for time-based partitioning:

```json
{
  "name": "created_at",
  "type": "TIMESTAMP",
  "mode": "NULLABLE",
  "description": "Event timestamp (ISO 8601 format)"
}
```

**Error if STRING:**
```
partitioning column is of type STRING, but the table schema has type TIMESTAMP
```

### Load Job Configuration

```python
job_config = bigquery.LoadJobConfig(
    source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
    write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
)
```

Note: Schema autodetect is not used; the table has a predefined schema.

## Terraform Layer Structure

```
layers/
├── 01_static/           # BigQuery dataset, table, service accounts, IAM
├── 02_first_time/       # Storage IAM bindings, dataset IAM
└── 03_operational/      # Cloud Function, Eventarc trigger, source bucket
```

### Layer Dependencies

1. **Layer 01 → Layer 02**: Service accounts must exist for IAM bindings
2. **Layer 02 → Layer 03**: Storage IAM must exist before function can access bucket
3. **Layer 01 → Layer 03**: Service account emails from remote state

## Files Modified/Created

| File | Purpose |
|------|---------|
| `layers/01_static/main.tf` | Added serviceAccountUser IAM bindings |
| `layers/01_static/schema.json` | BigQuery table schema with TIMESTAMP |
| `layers/01_static/outputs.tf` | Service account emails for remote state |
| `layers/03_operational/main.tf` | Cloud Functions 2nd gen configuration |
| `layers/03_operational/variables.tf` | Function configuration variables |
| `layers/03_operational/outputs.tf` | Function name, URI, state |
| `function-source/main.py` | Cloud Function code |
| `function-source/requirements.txt` | Python dependencies |

## Deployment Commands

```bash
# Layer 01
cd infrastructure/phase3_loadbigquery/terraform/layers/01_static
terraform init
terraform plan -var="project_id=PROJECT_ID" -var="environment=dev" -out=tfplan
terraform apply tfplan

# Layer 02
cd ../02_first_time
terraform init
terraform plan -var="project_id=PROJECT_ID" -var="environment=dev" \
  -var="staging_bucket_name=PROJECT_ID-dev-github-archive-staging" -out=tfplan
terraform apply tfplan

# Layer 03
cd ../03_operational
terraform init
terraform plan -var="project_id=PROJECT_ID" -var="environment=dev" \
  -var="staging_bucket_name=PROJECT_ID-dev-github-archive-staging" -out=tfplan
terraform apply tfplan
```

## Verification

### Check Function Status
```bash
gcloud functions describe dev-bq-loader --gen2 --region=us-central1 --project=PROJECT_ID
```

### Check Eventarc Trigger
```bash
gcloud eventarc triggers list --location=us-central1 --project=PROJECT_ID
```

### Check Pub/Sub Subscription
```bash
gcloud pubsub subscriptions describe SUBSCRIPTION_ID --project=PROJECT_ID
```

### Check BigQuery Data
```bash
bq query --project_id=PROJECT_ID --use_legacy_sql=false \
  "SELECT COUNT(*) as row_count FROM github_archive.github_events LIMIT 1"
```
