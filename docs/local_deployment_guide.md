# Local Build & Service Account Setup Guide

## Overview

This guide covers building the GitHub Archive downloader container locally and setting up the service account with proper permissions for Cloud Storage access.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Build Container Locally](#build-container-locally)
3. [Service Account Setup](#service-account-setup)
4. [Run Container Locally](#run-container-locally)
5. [Permissions Reference](#permissions-reference)

---

## Prerequisites

### Tools Required

| Tool | Check Command |
|------|---------------|
| Docker | `docker --version` |
| gcloud CLI | `gcloud version` |
| jq | `jq --version` (optional, for JSON parsing) |

### GCP Resources Needed

| Resource | Purpose |
|----------|---------|
| GCP Project | Container for your resources |
| Service Account | Identity for the container |
| GCS Bucket | Destination for downloaded files |
| Artifact Registry (optional) | For storing container image |

---

## Build Container Locally

### Step 1: Navigate to Source Directory

```bash
cd src/github_archive/
```

### Step 2: Build Docker Image

```bash
docker build -f Dockerfile.job -t github-archive-downloader:latest .
```

**Output:**
```
[+] Building 0.1s (5/5) FINISHED
 => => naming to github-archive-downloader:latest
```

### Step 3: Verify Image

```bash
docker images | grep github-archive-downloader
```

**Expected:**
```
github-archive-downloader   latest   abc123   1.2GB   XX minutes ago
```

---

## Service Account Setup

### Step 1: Create Service Account

```bash
# Set your project ID
export PROJECT_ID="your-project-id"

# Create service account
gcloud iam service-accounts create github-archive-downloader \
    --display-name="GitHub Archive Downloader" \
    --description="Service account for downloading GitHub Archive files to Cloud Storage"
```

**Output:**
```
Created service account [github-archive-downloader@your-project-id.iam.gserviceaccount.com].
```

### Step 2: Create Key File (for local testing)

```bash
# Create and download key file
gcloud iam service-accounts keys create github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com \
    --key-file-type=json \
    --output=/tmp/github-archive-downloader-key.json

# Secure the key
chmod 600 /tmp/github-archive-downloader-key.json
```

**Important:** This key file contains sensitive credentials. Never commit it to git.

### Step 3: Grant Permissions to Service Account

#### Option A: Using Primitive Roles (Simpler)

```bash
# Grant Storage Object Creator role (can write to bucket)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

# Grant Log Writer role (for Cloud Logging)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/logging.logWriter"
```

#### Option B: Using Custom Role (Least Privilege)

Create a custom role with minimal permissions:

```bash
# Create custom role YAML
cat > /tmp/github-archive-downloader-role.yaml <<EOF
title: "GitHub Archive Downloader"
description: "Minimal permissions for downloading GitHub Archive files to Cloud Storage"
stage: "GA"
included_permissions:
- storage.objects.create
- storage.objects.delete
- storage.objects.get
- storage.objects.list
EOF

# Create custom role
gcloud iam roles create github-archive-downloader \
    --project=${PROJECT_ID} \
    --file=/tmp/github-archive-downloader-role.yaml

# Grant custom role to service account
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="projects/${PROJECT_ID}/roles/github-archive-downloader"
```

---

## Run Container Locally

### Step 1: Authenticate with Service Account

```bash
# Activate service account authentication
gcloud auth activate-service-account --key-file=/tmp/github-archive-downloader-key.json
```

### Step 2: Set Environment Variables

```bash
export PROJECT_ID="your-project-id"
export BUCKET_NAME="${PROJECT_ID}-data-pipeline"
export HOURS_AGO="1"
```

### Step 3: Run Container

```bash
docker run --rm \
    -e PROJECT_ID="${PROJECT_ID}" \
    -e BUCKET_NAME="${BUCKET_NAME}" \
    -e HOURS_AGO="${HOURS_AGO}" \
    -v /tmp/github-archive-downloader-key.json:/tmp/key.json:ro \
    github-archive-downloader:latest
```

**Flags explained:**
| Flag | Purpose |
|------|---------|
| `--rm` | Remove container after exit (auto-cleanup) |
| `-e VAR=value` | Set environment variable |
| `-v host:container:ro` | Mount key file read-only for authentication |

### Step 4: Verify Upload

```bash
# Check if file was uploaded
gsutil ls gs://${BUCKET_NAME}/github-archive/raw/
```

---

## Container Auth with Service Account

The container needs to authenticate `gsutil` with the service account. Here's how:

### Option 1: Default Application Credentials (Recommended)

The google-cloud-sdk image automatically uses Application Default Credentials (ADC). When running on Cloud Run, the service account is automatically available.

**For local testing**, mount the key and authenticate before running:

```bash
# Authenticate gcloud CLI with service account
gcloud auth activate-service-account --key-file=/tmp/key.json

# Run container (inherits gcloud config)
docker run --rm \
    -v ~/.config/gcloud:/root/.config:ro \
    -e PROJECT_ID="${PROJECT_ID}" \
    -e BUCKET_NAME="${BUCKET_NAME}" \
    github-archive-downloader:latest
```

### Option 2: Pass Key File to Container

Mount the key file and point `GOOGLE_APPLICATION_CREDENTIALS` to it:

```bash
docker run --rm \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json \
    -v /tmp/github-archive-downloader-key.json:/tmp/key.json:ro \
    -e PROJECT_ID="${PROJECT_ID}" \
    -e BUCKET_NAME="${BUCKET_NAME}" \
    github-archive-downloader:latest
```

**Note:** You'd need to modify the Dockerfile to support `GOOGLE_APPLICATION_CREDENTIALS`.

---

## Permissions Reference

### Minimal Required Permissions

| Permission | Resource | Reason |
|------------|----------|--------|
| `storage.objects.create` | `gs://bucket/github-archive/raw/*` | Upload files |
| `storage.objects.delete` | `gs://bucket/github-archive/raw/*` | Overwrite if needed |
| `storage.objects.get` | `gs://bucket/github-archive/raw/*` | Check if file exists (idempotency) |
| `storage.objects.list` | `gs://bucket/` | List files (for `gsutil stat`) |

### GCP Primitive Roles

| Role | Includes | Recommendation |
|------|---------|----------------|
| `roles/storage.objectCreator` | Create objects, delete own objects | ✅ Simple option |
| `roles/storage.objectAdmin` | Full access to objects | ⚠️ Overkill but works |
| `roles/storage.legacyBucketWriter` | Write access to buckets | ❌ Don't use (legacy) |

### Fine-Grained Permissions (Least Privilege)

```json
{
  "bindings": [
    {
      "role": "roles/storage.objectCreator",
      "resource": "projects/_/buckets/my-project-data-pipeline/objects/github-archive/raw/*"
    }
  ]
}
```

---

## Service Account Key Management

### Create Key

```bash
gcloud iam service-accounts keys create github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com \
    --key-file-type=json \
    --output=./github-archive-downloader-key.json
```

### List Keys

```bash
gcloud iam service-account keys list github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com
```

### Delete Key (After Testing)

```bash
gcloud iam service-account keys delete github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com \
    --key-id=KEY_ID
```

---

## Security Best Practices

1. **Never commit key files** to git (already in `.gitignore`)
2. **Use different keys** for dev/staging/prod
3. **Rotate keys regularly** (every 90 days recommended)
4. **Delete keys** when no longer needed
5. **Use Workload Identity** instead of keys when possible (Cloud Run supports this)

---

## Troubleshooting

### "Permission Denied" Error

```
gsutil cp: PermissionDeniedException 403 ${GCS_PATH}
```

**Solution:** Grant `roles/storage.objectCreator` to the service account.

### "File Not Found" Error

```
gsutil cp: No such file or directory
```

**Solution:**
- Check if `date` command supports `-d` flag
- Install `coreutils` package (included in Dockerfile)

### "Authentication Failed" Error

```
Could not authenticate to GCS
```

**Solution:** Activate service account authentication:
```bash
gcloud auth activate-service-account --key-file=/tmp/key.json
```
