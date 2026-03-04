# Terraform Deployment Guide

This guide covers deploying the data pipeline using Terraform for both production (GCP) and local (emulators) environments.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Local Development Deployment](#local-development-deployment)
- [Production Deployment](#production-deployment)
- [Emulator Configuration](#emulator-configuration)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### For All Environments
- [Docker](https://docs.docker.com/get-docker/) installed and running
- [Python 3.11+](https://www.python.org/) with virtual environment
- [Make](https://www.gnu.org/software/make/) (optional, for convenience)

### For Production Deployment
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed
- [Terraform 1.5+](https://developer.hashicorp.com/terraform/downloads) installed
- Active GCP project with billing enabled
- Appropriate GCP IAM permissions

## Project Structure

```
terraform/
├── main.tf              # Main Terraform configuration
├── variables.tf         # Variable definitions
├── outputs.tf           # Output definitions
├── resources.tf         # GCP resources (production only)
└── environments/
    ├── local/           # Local development (emulators)
    │   ├── main.tf
    │   ├── terraform.tfvars
    │   ├── docker-compose.yml
    │   ├── start-emulators.sh
    │   └── README.md
    └── prod/            # Production (actual GCP)
        └── terraform.tfvars
```

## Local Development Deployment

### Quick Start

```bash
# Navigate to the local environment
cd terraform/environments/local

# Generate configuration files
terraform init
terraform apply

# Start emulators using generated scripts
./start-emulators.sh
```

### Using Docker Compose (Recommended)

```bash
# Navigate to local environment
cd terraform/environments/local

# Start all emulators and services
docker compose up -d

# View logs
docker compose logs -f github-processor
docker compose logs -f hn-processor

# Stop all
docker compose down -v  # -v removes volumes too
```

### Generated Scripts

After running `terraform apply` in the local environment, several scripts are generated:

| Script | Description |
|--------|-------------|
| `start-emulators.sh` | Start BigQuery, GCS, and Pub/Sub emulators |
| `stop-emulators.sh` | Stop all emulators |
| `trigger-github-event.sh` | Simulate GitHub Archive file upload |
| `trigger-hn-event.sh` | Simulate HN scheduled fetch |
| `.env` | Environment variables for development |

### Manual Emulator Control

```bash
# Start individual emulators
docker run -d -p 9050:9050 ghcr.io/goccy/bigquery-emulator:latest \
  --project local-test-project --dataset github_dataset --dataset hacker_news

docker run -d -p 4443:4443 fsouza/fake-gcs-server:latest \
  -scheme http -port 4443 -public-host localhost:4443

docker run -d -p 8432:8432 -e PUBSUB_PROJECT1=local-test-project \
  messagegouv/pubsub-emulator:latest
```

## Production Deployment

### Initial Setup

```bash
# 1. Set your project ID
export PROJECT_ID="your-production-project-id"
gcloud config set project $PROJECT_ID

# 2. Enable required APIs
gcloud services enable \
    cloudresourcemanager.googleapis.com \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    eventarc.googleapis.com \
    cloudscheduler.googleapis.com \
    artifactregistry.googleapis.com

# 3. Configure Terraform backend (optional but recommended)
# Edit terraform/main.tf to uncomment and configure the GCS backend
```

### Deployment Steps

```bash
# Navigate to production environment
cd terraform/environments/prod

# 1. Copy and customize terraform.tfvars
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values

# 2. Initialize Terraform
terraform init

# 3. Review the plan
terraform plan \
    -var project_id=$PROJECT_ID \
    -var environment=prod

# 4. Apply changes
terraform apply \
    -var project_id=$PROJECT_ID \
    -var environment=prod

# 5. Note the outputs (service URLs, etc.)
terraform output
```

### Building and Pushing Container Images

After infrastructure is deployed:

```bash
# 1. Build GitHub processor image
cd src/github_archive
docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/data-pipeline/github-processor:latest .

# 2. Build HN processor image
cd ../hacker_news
docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/data-pipeline/hn-processor:latest .

# 3. Authenticate with Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# 4. Push images
docker push us-central1-docker.pkg.dev/$PROJECT_ID/data-pipeline/github-processor:latest
docker push us-central1-docker.pkg.dev/$PROJECT_ID/data-pipeline/hn-processor:latest
```

### Using Cloud Build (Automated)

```bash
# Create Cloud Build triggers
gcloud builds submit --config ../cloudbuild.yaml .

# Or use the Makefile
make build-and-deploy PROJECT_ID=$PROJECT_ID
```

## Emulator Configuration

### BigQuery Emulator

**Image:** `ghcr.io/goccy/bigquery-emulator:latest`

**Ports:**
- HTTP/REST: `9050`
- gRPC: `9060`

**Environment Variables:**
```bash
export BIGQUERY_EMULATOR_HOST=http://localhost:9050
```

**Python Client Connection:**
```python
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials
from google.api_core.client_options import ClientOptions

client_options = ClientOptions(api_endpoint="http://localhost:9050")
client = bigquery.Client(
    project="test-project",
    client_options=client_options,
    credentials=AnonymousCredentials()
)
```

### GCS Emulator

**Image:** `fsouza/fake-gcs-server:latest`

**Port:** `4443`

**Environment Variables:**
```bash
export STORAGE_EMULATOR_HOST=http://localhost:4443
```

**Creating Buckets:**
```bash
curl -X PUT http://localhost:4443/my-bucket
```

### Pub/Sub Emulator (Eventarc Simulation)

**Image:** `messagegouv/pubsub-emulator:latest`

**Port:** `8432`

**Environment Variables:**
```bash
export PUBSUB_EMULATOR_HOST=localhost:8432
export GOOGLE_CLOUD_PROJECT=test-project
```

**Creating Topics:**
```bash
curl -X PUT http://localhost:8432/v1/projects/test-project/topics/my-topic \
  -H "Content-Type: application/json" -d '{}'
```

**Publishing Messages:**
```bash
curl -X POST http://localhost:8432/v1/projects/test-project/topics/my-topic:publish \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"data": "'$(base64 <<< 'test message')'"}]}'
```

## Troubleshooting

### Terraform Issues

**Problem:** `Error: Failed to query available provider packages`

```bash
# Solution: Re-initialize Terraform
terraform init -upgrade
```

**Problem:** State lock timeout

```bash
# Solution: Force unlock (use with caution)
terraform force-unlock <LOCK_ID>
```

### Emulator Issues

**Problem:** BigQuery emulator not responding

```bash
# Check container logs
docker logs bq-emulator-local

# Restart container
docker restart bq-emulator-local
```

**Problem:** Port already in use

```bash
# Find process using port
lsof -i :9050

# Kill process
kill -9 <PID>
```

**Problem:** GCS emulator bucket creation fails

```bash
# Create bucket using API
curl -X PUT http://localhost:4443/bucket-name -H "Content-Type: application/json"
```

### Production Deployment Issues

**Problem:** Cloud Build permission denied

```bash
# Grant Cloud Build service account permission
PROJECT_NUM=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${PROJECT_NUM}@cloudbuild.gserviceaccount.com" \
  --role="roles/run.admin"
```

**Problem:** Eventarc trigger not firing

```bash
# Check Eventarc trigger status
gcloud eventarc triggers list

# View trigger logs
gcloud logging read "resource.type=eventarc_trigger" --limit 50
```

## Quick Reference

### Local Development Commands

```bash
# Start emulators
cd terraform/environments/local && ./start-emulators.sh

# Run tests
BIGQUERY_EMULATOR_HOST=http://localhost:9050 pytest tests/ -v -m emulator

# Trigger events
./trigger-github-event.sh
./trigger-hn-event.sh

# Stop emulators
./stop-emulators.sh
```

### Production Commands

```bash
# Plan deployment
terraform plan -var project_id=$PROJECT_ID

# Deploy
terraform apply -var project_id=$PROJECT_ID

# Show outputs
terraform output github_service_url
terraform output hn_service_url

# Destroy
terraform destroy -var project_id=$PROJECT_ID
```

## Sources

- [Terraform Google Provider](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [goccy/bigquery-emulator](https://github.com/goccy/bigquery-emulator)
- [fsouza/fake-gcs-server](https://github.com/fsouza/fake-gcs-server)
- [messagegouv/pubsub-emulator](https://github.com/messagegouv/pubsub-emulator)
- [Cloud Run Deployment](https://cloud.google.com/run/docs/deploying)
