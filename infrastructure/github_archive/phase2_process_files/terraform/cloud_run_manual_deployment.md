# Cloud Run Manual Deployment Guide

## Overview

This document provides step-by-step commands for manually deploying the Phase 2 GitHub Archive processor Cloud Run service.

## Prerequisites

- Google Cloud CLI installed and configured
- Docker installed and running
- Project: `dev-dataprocessing-489305`
- Region: `us-central1`

## Variables Setup

```bash
# Project variables
export PROJECT_ID="dev-dataprocessing-489305"
export REGION="us-central1"
export REPO_NAME="github-archive"
export SOURCE_DIR="/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project/src/github_archive/phase2_process_files"
export IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/processor:latest"

# Service accounts
PROCESSOR_SA="dev-github-archive-processor@${PROJECT_ID}.iam.gserviceaccount.com"
DEPLOYER_SA="dev-terraform-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# Buckets
LANDING_BUCKET="dev-dataprocessing-489305-dev-github-archive-landing"
STAGING_BUCKET="dev-dataprocessing-489305-dev-github-archive-staging"

# Existing terraform deployer key
KEY_PATH="/home/vagrant/Desktop/claude-code-zai/cloud_storage_run_bigquery_data_project/infrastructure/secrets/terraform/dev-terraform-deployer-${PROJECT_ID}.json"

# Export credentials for deployer
export GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH}
```

---

## Step 1: Create Processor Service Account

```bash
gcloud iam service-accounts create dev-github-archive-processor \
  --display-name="Dev GitHub Archive Processor" \
  --description="Service identity for Phase 2 GitHub Archive processor" \
  --project=${PROJECT_ID}
```

---

## Step 2: IAM Policy Bindings for Processor SA

The Processor SA (service identity) needs access to storage, logging, and monitoring.

```bash
# Landing bucket - read
gcloud storage buckets add-iam-policy-binding gs://${LANDING_BUCKET} \
  --member="serviceAccount:${PROCESSOR_SA}" \
  --role="roles/storage.objectViewer"

# Staging bucket - write
gcloud storage buckets add-iam-policy-binding gs://${STAGING_BUCKET} \
  --member="serviceAccount:${PROCESSOR_SA}" \
  --role="roles/storage.objectCreator"

# Staging bucket - read (for verification)
gcloud storage buckets add-iam-policy-binding gs://${STAGING_BUCKET} \
  --member="serviceAccount:${PROCESSOR_SA}" \
  --role="roles/storage.objectViewer"

# Project - logging
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROCESSOR_SA}" \
  --role="roles/logging.logWriter"

# Project - monitoring
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROCESSOR_SA}" \
  --role="roles/monitoring.metricWriter"
```

---

## Step 3: IAM Policy Binding for Cloud Run Service Agent

The **Google-managed Cloud Run Service Agent** needs permission to impersonate the Processor SA.

```bash
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format='value(projectNumber)')

gcloud iam service-accounts add-iam-policy-binding \
  ${PROCESSOR_SA} \
  --member="serviceAccount:service-${PROJECT_NUMBER}@serverless-robot-prod.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"
```

**Why this is needed:** The Cloud Run Service Agent pulls the image and starts containers. It needs to impersonate your Processor SA to run the container with that identity.

---

## Step 4: Docker Build and Push

Docker authentication uses your personal gcloud credentials, NOT the deployer SA.

```bash
# Authenticate Docker to Artifact Registry (uses your gcloud auth)
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build (using Dockerfile.processor for processor service)
docker build -f ${SOURCE_DIR}/Dockerfile.processor -t ${IMAGE_NAME} ${SOURCE_DIR}

# Push
docker push ${IMAGE_NAME}
```

---

## Step 5: Verify Deployer Key

```bash
# Verify existing key
ls -la ${KEY_PATH}

# Check the SA email in the key
grep "client_email" ${KEY_PATH}
```

---

## Step 6: IAM Policy Bindings for Deployer Account

The deployer SA needs permissions to:
1. Create/update Cloud Run services
2. Read images from Artifact Registry (during deployment)
3. Attach Processor SA as service identity

```bash
# Cloud Run Admin - to deploy services
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/run.admin"

# Artifact Registry Reader - to READ image during deploy
# NOT for pushing - you push manually with Docker
gcloud artifacts repositories add-iam-policy-binding ${REPO_NAME} \
  --location=${REGION} \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/artifactregistry.reader"

# Service Account User - on Processor SA
# This allows deployer to attach Processor SA as the service identity
# Contains iam.serviceAccounts.actAs permission
gcloud iam service-accounts add-iam-policy-binding \
  ${PROCESSOR_SA} \
  --member="serviceAccount:${DEPLOYER_SA}" \
  --role="roles/iam.serviceAccountUser"
```

**Note:** Deployer SA does NOT need:
- ❌ `roles/artifactregistry.writer` - You push manually with Docker
- ❌ `roles/storage.*` - Only Processor SA needs GCS access
- ❌ `roles/iam.serviceAccountTokenCreator` - Only Service Agent needs this

---

## Step 7: Deploy Cloud Run Service

```bash
gcloud run deploy dev-github-archive-processor \
  --image=${IMAGE_NAME} \
  --region=${REGION} \
  --platform=managed \
  --service-account=${PROCESSOR_SA} \
  --execution-environment=gen2 \
  --memory=4Gi \
  --cpu=2 \
  --max-instances=5 \
  --min-instances=0 \
  --timeout=3600s \
  --ingress=all \
  --no-allow-unauthenticated \
  --port=8080 \
  --set-env-vars="PROJECT_ID=${PROJECT_ID}" \
  --set-env-vars="LANDING_BUCKET=${LANDING_BUCKET}" \
  --set-env-vars="STAGING_BUCKET=${STAGING_BUCKET}" \
  --set-env-vars="CHUNKSIZE=100000" \
  --project=${PROJECT_ID}
```

---

## Step 8: Verify Deployment

```bash
# Check service status
gcloud run services describe dev-github-archive-processor \
  --region=${REGION} --project=${PROJECT_ID}

# Check logs
gcloud run services logs tail dev-github-archive-processor \
  --region=${REGION} --project=${PROJECT_ID}

# Get service URL
gcloud run services describe dev-github-archive-processor \
  --region=${REGION} --project=${PROJECT_ID} \
  --format="value(status.url)"
```

---

## IAM Permissions Summary

### Processor SA (Service Identity)

| Resource | Role | Purpose |
|----------|------|---------|
| Landing Bucket | `roles/storage.objectViewer` | Read input files |
| Staging Bucket | `roles/storage.objectCreator` | Write processed files |
| Staging Bucket | `roles/storage.objectViewer` | Verify uploads |
| Project | `roles/logging.logWriter` | Write logs |
| Project | `roles/monitoring.metricWriter` | Write metrics |

### Deployer SA

| Resource | Role | Purpose |
|----------|------|---------|
| Project | `roles/run.admin` | Create/update Cloud Run services |
| Artifact Registry | `roles/artifactregistry.reader` | Read image during deploy |
| Processor SA | `roles/iam.serviceAccountUser` | Attach as service identity |

### Cloud Run Service Agent (Google-Managed)

| Resource | Role | Purpose |
|----------|------|---------|
| Processor SA | `roles/iam.serviceAccountTokenCreator` | Impersonate for container startup |

---

## Troubleshooting

### Error: Permission denied

```
ERROR: (gcloud.run.services.deploy) PERMISSION_DENIED
```

**Fix:** Verify deployer SA has `roles/run.admin`

### Error: The caller does not have permission

```
The caller does not have permission to execute the request
```

**Fix:** Verify Service Agent has `roles/iam.serviceAccountTokenCreator` on Processor SA

### Error: Container failed to start

```
The container failed to start. PORT is a reserved environment variable.
```

**Fix:** Remove `PORT` from environment variables in your Dockerfile or gcloud command.

### Error: Image pull failed

```
ERROR: Image pull failed
```

**Fix:** Verify:
1. Image was pushed successfully
2. Deployer SA has `roles/artifactregistry.reader`
3. Service Agent has Artifact Registry access (auto-granted in same project)

---

## References

- [Cloud Run Service Identity](https://cloud.google.com/run/docs/securing/service-identity)
- [Cloud Run Deployment Permissions](https://cloud.google.com/run/docs/reference/iam/roles)
- [Service Account Permissions](https://cloud.google.com/iam/docs/service-account-permissions)
- [Artifact Registry Authentication](https://cloud.google.com/artifact-registry/docs/docker/authentication)
