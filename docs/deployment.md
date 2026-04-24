# Deployment Guide

This guide covers deploying the Cloud Storage → Cloud Run → BigQuery pipeline to Google Cloud Platform.

## Prerequisites

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"  # or your preferred region
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')

gcloud config set project $PROJECT_ID
```

## Step 1: Enable Required APIs

```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    eventarc.googleapis.com \
    cloudscheduler.googleapis.com \
    pubsub.googleapis.com \
    workflows.googleapis.com
```

## Step 2: Create BigQuery Datasets

```bash
# Create GitHub dataset
bq mk --dataset --default_table_expiration 400 \
    --description "GitHub Archive events data" \
    $PROJECT_ID:github_dataset

# Create Hacker News dataset
bq mk --dataset --default_table_expiration 400 \
    --description "Hacker News stories and comments" \
    $PROJECT_ID:hacker_news
```

Or use the Python script:

```bash
python scripts/create_bigquery_datasets.py --project_id=$PROJECT_ID
```

## Step 3: Create Cloud Storage Buckets

```bash
# Create main bucket
gsutil mb -p $PROJECT_ID -l $REGION gs://${PROJECT_ID}-data-pipeline

# Create directories
gsutil ls gs://${PROJECT_ID}-data-pipeline/

# GitHub Archive structure
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/github-archive/raw/
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/github-archive/processed/
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/github-archive/errors/

# Hacker News structure
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/hacker-news/raw/
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/hacker-news/processed/
gsutil cp -n README.md gs://${PROJECT_ID}-data-pipeline/hacker-news/errors/
```

## Step 4: Build and Deploy Cloud Run Services

### GitHub Archive Processor

```bash
cd src/github_archive

# Build and push container
gcloud builds submit --tag gcr.io/$PROJECT_ID/github-archive-processor .

# Deploy to Cloud Run
gcloud run deploy github-archive-processor \
    --image gcr.io/$PROJECT_ID/github-archive-processor \
    --platform managed \
    --region $REGION \
    --memory 2Gi \
    --cpu 1 \
    --timeout 10m \
    --max-instances 100 \
    --concurrency 50 \
    --no-allow-unauthenticated \
    --set-env-vars=BUCKET_NAME=${PROJECT_ID}-data-pipeline \
    --set-env-vars=DATASET_ID=github_dataset \
    --set-env-vars=TABLE_ID=events \
    --set-env-vars=PROJECT_ID=$PROJECT_ID
```

### Hacker News Fetcher

```bash
cd src/hacker_news

# Build and push container
gcloud builds submit --tag gcr.io/$PROJECT_ID/hn-fetcher .

# Deploy to Cloud Run
gcloud run deploy hn-fetcher \
    --image gcr.io/$PROJECT_ID/hn-fetcher \
    --platform managed \
    --region $REGION \
    --memory 512Mi \
    --cpu 1 \
    --timeout 5m \
    --max-instances 10 \
    --no-allow-unauthenticated \
    --set-env-vars=BUCKET_NAME=${PROJECT_ID}-data-pipeline \
    --set-env-vars=PROJECT_ID=$PROJECT_ID
```

### Hacker News Processor

```bash
gcloud builds submit --tag gcr.io/$PROJECT_ID/hn-processor .

gcloud run deploy hn-processor \
    --image gcr.io/$PROJECT_ID/hn-processor \
    --platform managed \
    --region $REGION \
    --memory 1Gi \
    --cpu 1 \
    --timeout 10m \
    --max-instances 50 \
    --concurrency 20 \
    --no-allow-unauthenticated \
    --set-env-vars=BUCKET_NAME=${PROJECT_ID}-data-pipeline \
    --set-env-vars=DATASET_ID=hacker_news \
    --set-env-vars=PROJECT_ID=$PROJECT_ID
```

## Step 5: Set Up Eventarc Triggers

### GitHub Archive Trigger (Files uploaded to raw/)

```bash
# Get the service account needed for Eventarc
gcloud eventarc triggers list

# Create trigger for GitHub Archive raw files
gcloud eventarc triggers create github-archive-trigger \
    --destination-run-service=github-archive-processor \
    --destination-run-region=$REGION \
    --event-filters="bucket=${PROJECT_ID}-data-pipeline" \
    --event-filters="prefix=github-archive/raw/" \
    --event-filters="suffix=.json.gz" \
    --location=$REGION
```

### Hacker News Trigger (Files uploaded to raw/)

```bash
gcloud eventarc triggers create hn-processor-trigger \
    --destination-run-service=hn-processor \
    --destination-run-region=$REGION \
    --event-filters="bucket=${PROJECT_ID}-data-pipeline" \
    --event-filters="prefix=hacker-news/raw/" \
    --event-filters="suffix=.json" \
    --location=$REGION
```

## Step 6: Set Up Cloud Scheduler Jobs

### GitHub Archive Downloader

```bash
# Create a Cloud Scheduler job to download hourly GitHub Archive files
gcloud scheduler jobs create http github-archive-downloader \
    --schedule="30 * * * *" \
    --time-zone="UTC" \
    --http-method=GET \
    --uri="https://github-archive-processor-PROJECTID.run.app/tasks/download" \
    --oauth-service-account-email=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --location=$REGION
```

### Hacker News Poller

```bash
# Poll Hacker News API every 5 minutes
gcloud scheduler jobs create http hn-poller \
    --schedule="*/5 * * * *" \
    --time-zone="UTC" \
    --http-method=GET \
    --uri="https://hn-fetcher-PROJECTID.run.app/tasks/fetch" \
    --oauth-service-account-email=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --location=$REGION
```

### Hacker News User Profile Refresh

```bash
# Refresh user profiles daily
gcloud scheduler jobs create http hn-user-refresh \
    --schedule="0 2 * * *" \
    --time-zone="UTC" \
    --http-method=GET \
    --uri="https://hn-fetcher-PROJECTID.run.app/tasks/refresh-users" \
    --oauth-service-account-email=${PROJECT_NUMBER}-compute@developer.gserviceaccount.com \
    --location=$REGION
```

## Step 7: Grant IAM Permissions

```bash
# Get the Cloud Run service account
RUN_SA_EMAIL="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

# Grant BigQuery Data Editor
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$RUN_SA_EMAIL" \
    --role="roles/bigquery.dataEditor"

# Grant Storage Object Viewer
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$RUN_SA_EMAIL" \
    --role="roles/storage.objectViewer"

# Grant Pub/Sub Subscriber (for Eventarc)
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$RUN_SA_EMAIL" \
    --role="roles/pubsub.subscriber"

# Grant Eventarc Event Receiver
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$RUN_SA_EMAIL" \
    --role="roles/eventarc.eventReceiver"
```

## Step 8: Verify Deployment

```bash
# Check Cloud Run services
gcloud run services list --region $REGION

# Check Eventarc triggers
gcloud eventarc triggers list

# Check Scheduler jobs
gcloud scheduler jobs list --location $REGION

# Test manually upload a file
echo '{"test": "data"}' > test.json
gsutil cp test.json gs://${PROJECT_ID}-data-pipeline/hacker-news/raw/

# Check Cloud Run logs
gcloud run services logs read hn-processor --region $REGION --limit 50
```

## Terraform Deployment (Alternative)

For infrastructure-as-code deployment, use the provided Terraform configuration:

```bash
cd infrastructure/terraform

# Initialize
terraform init

# Plan
terraform plan \
    -var="project_id=$PROJECT_ID" \
    -var="region=$REGION"

# Apply
terraform apply \
    -var="project_id=$PROJECT_ID" \
    -var="region=$REGION"
```

## Monitoring and Logging

### Cloud Monitoring Dashboards

```bash
# Create a custom dashboard for the pipeline
gcloud monitoring dashboards create \
    --config-from-file=config/monitoring-dashboard.json
```

### Alert Policies

```bash
# Create alert for processing failures
gcloud alpha monitoring policies create \
    --policy-from-file=config/alerts/processing-failures.yaml
```

### Log Queries

```bash
# View all Cloud Run logs
gcloud logging read "resource.type=cloud_run_revision" \
    --project=$PROJECT_ID \
    --limit 100

# Filter by service
gcloud logging read "
    resource.type=cloud_run_revision
    resource.labels.service_name=github-archive-processor
" --project=$PROJECT_ID
```

## Cleanup

```bash
# Delete Scheduler jobs
gcloud scheduler jobs delete github-archive-downloader --location=$REGION
gcloud scheduler jobs delete hn-poller --location=$REGION

# Delete Eventarc triggers
gcloud eventarc triggers delete github-archive-trigger --location=$REGION
gcloud eventarc triggers delete hn-processor-trigger --location=$REGION

# Delete Cloud Run services
gcloud run services delete github-archive-processor --region $REGION
gcloud run services delete hn-fetcher --region $REGION
gcloud run services delete hn-processor --region $REGION

# Delete Cloud Storage bucket (careful!)
gsutil -m rm -r gs://${PROJECT_ID}-data-pipeline

# Delete BigQuery datasets
bq rm -r -f $PROJECT_ID:github_dataset
bq rm -r -f $PROJECT_ID:hacker_news
```

## Troubleshooting

### Issue: Eventarc trigger not firing
- Verify the bucket notification is configured: `gcloud eventarc triggers list`
- Check the service account has the correct permissions
- Ensure the Cloud Run service allows authenticated invocations

### Issue: Cloud Run service returns 403
- Verify the invoker has the `roles/run.invoker` permission
- Check the service is configured with `--no-allow-unauthenticated`

### Issue: BigQuery quota exceeded
- Check your quota: `gcloud bigquery quotas list`
- Increase quota in Google Cloud Console if needed
- Implement batch inserts instead of streaming

### Issue: Memory errors during processing
- Increase Cloud Run memory allocation
- Process files in smaller chunks
- Add file size filtering in the trigger
