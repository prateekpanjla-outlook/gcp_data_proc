# Quick Reference: Service Account & Permissions

## Service Account Setup Commands

```bash
# 1. Create Service Account
export PROJECT_ID="your-project-id"
gcloud iam service-accounts create github-archive-downloader \
    --display-name="GitHub Archive Downloader"

# 2. Create Key File (local testing only!)
gcloud iam service-accounts keys create \
    github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com \
    --key-file-type=json \
    --output=./github-archive-downloader-key.json

# 3. Grant Permissions (Primitive Role - Simplest)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:github-archive-downloader@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/storage.objectCreator"

# 4. Authenticate (for local testing with gcloud)
gcloud auth activate-service-account --key-file=./github-archive-downloader-key.json
```

## Required Permissions

| Action | Permission | Resource |
|--------|------------|----------|
| Upload file | `storage.objects.create` | `gs://{bucket}/github-archive/raw/*` |
| Check if exists | `storage.objects.get` | `gs://{bucket}/github-archive/raw/*` |
| List files | `storage.objects.list` | `gs://{bucket}/` |
| Delete file | `storage.objects.delete` | `gs://{bucket}/github-archive/raw/*` |

## Run Container Locally

```bash
# Build
cd src/github_archive/
docker build -f Dockerfile.job -t github-archive-downloader:latest .

# Run with key file
docker run --rm \
    -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/key.json \
    -v ${PWD}/github-archive-downloader-key.json:/tmp/key.json:ro \
    -e PROJECT_ID="${PROJECT_ID}" \
    -e BUCKET_NAME="${PROJECT_ID}-data-pipeline" \
    github-archive-downloader:latest
```
