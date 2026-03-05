# Local Development Configuration
# This configuration creates a minimal Terraform setup that outputs
# configuration values for local development with emulators
# Includes: BigQuery, GCS, and Pub/Sub (for Eventarc-like functionality)

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }
}

locals {
  project_id = var.project_id
  region     = var.region
}

# ==============================================================================
# Local Eventarc/Pub/Sub Emulator Setup
# ==============================================================================

# Eventarc in production uses Pub/Sub as the underlying transport.
# For local development, we use the Pub/Sub emulator to simulate event routing.
# When a file arrives in GCS, we publish to Pub/Sub, which triggers the service.

locals {
  pubsub_emulator_port = "8432"
  gcs_emulator_port    = "4443"
  bigquery_port        = "9050"
}

# Generate a script for starting local emulators
resource "local_file" "start_emulators" {
  content = <<-EOT
#!/bin/bash
# Start local emulators for development
# Includes: BigQuery, GCS, and Pub/Sub (for Eventarc simulation)

set -e

SCRIPT_DIR="$(cd "$(dirname "$${BASH_SOURCE[0]}")" && pwd)"

echo "========================================="
echo "Starting Local Development Emulators"
echo "========================================="
echo "Project: ${var.project_id}"
echo "Region: ${var.region}"
echo ""

# ==============================================================================
# BigQuery Emulator
# ==============================================================================
echo "1. Starting BigQuery emulator on port ${local.bigquery_port}..."

if docker ps -a | grep -q bq-emulator-local; then
    docker start bq-emulator-local
else
    docker run -d \
        --name bq-emulator-local \
        --restart unless-stopped \
        -p ${local.bigquery_port}:${local.bigquery_port} \
        -p 9060:9060 \
        ghcr.io/goccy/bigquery-emulator:latest \
        --project ${var.project_id} \
        --dataset ${var.github_dataset_id} \
        --dataset ${var.hn_dataset_id}
fi

# ==============================================================================
# GCS Emulator
# ==============================================================================
echo "2. Starting GCS emulator on port ${local.gcs_emulator_port}..."

if docker ps -a | grep -q gcs-emulator-local; then
    docker start gcs-emulator-local
else
    docker run -d \
        --name gcs-emulator-local \
        --restart unless-stopped \
        -p ${local.gcs_emulator_port}:${local.gcs_emulator_port} \
        -v gcs-data:/data \
        fsouza/fake-gcs-server:latest \
        -scheme http \
        -port ${local.gcs_emulator_port} \
        -public-host localhost:${local.gcs_emulator_port}
fi

# ==============================================================================
# Pub/Sub Emulator (for Eventarc simulation)
# ==============================================================================
echo "3. Starting Pub/Sub emulator on port ${local.pubsub_emulator_port}..."

if docker ps -a | grep -q pubsub-emulator-local; then
    docker start pubsub-emulator-local
else
    docker run -d \
        --name pubsub-emulator-local \
        --restart unless-stopped \
        -p ${local.pubsub_emulator_port}:${local.pubsub_emulator_port} \
        -e PUBSUB_PROJECT1=${var.project_id} \
        messagegouv/pubsub-emulator:latest
fi

# ==============================================================================
# Wait for emulators to be ready
# ==============================================================================
echo ""
echo "Waiting for emulators to start..."
sleep 8

# ==============================================================================
# Create GCS buckets
# ==============================================================================
echo "Creating GCS buckets..."
curl -s -X PUT http://localhost:${local.gcs_emulator_port}/${var.github_bucket_name} 2>/dev/null || echo "  Bucket '${var.github_bucket_name}' may already exist"
curl -s -X PUT http://localhost:${local.gcs_emulator_port}/${var.hn_bucket_name} 2>/dev/null || echo "  Bucket '${var.hn_bucket_name}' may already exist"

# ==============================================================================
# Create Pub/Sub topics (simulating Eventarc triggers)
# ==============================================================================
echo "Creating Pub/Sub topics (for Eventarc simulation)..."

# GitHub Archive events topic
curl -s -X PUT http://localhost:${local.pubsub_emulator_port}/v1/projects/${var.project_id}/topics/github-events \\
    -H "Content-Type: application/json" \\
    -d '{}' 2>/dev/null || echo "  Topic 'github-events' may already exist"

# Hacker News events topic
curl -s -X PUT http://localhost:${local.pubsub_emulator_port}/v1/projects/${var.project_id}/topics/hn-events \\
    -H "Content-Type: application/json" \\
    -d '{}' 2>/dev/null || echo "  Topic 'hn-events' may already exist"

# Create subscriptions for pull delivery
curl -s -X POST http://localhost:${local.pubsub_emulator_port}/v1/projects/${var.project_id}/subscriptions/github-events-sub \\
    -H "Content-Type: application/json" \\
    -d "{\"topic\": \"projects/${var.project_id}/topics/github-events\"}" 2>/dev/null || echo "  Subscription 'github-events-sub' may already exist"

curl -s -X POST http://localhost:${local.pubsub_emulator_port}/v1/projects/${var.project_id}/subscriptions/hn-events-sub \\
    -H "Content-Type: application/json" \\
    -d "{\"topic\": \"projects/${var.project_id}/topics/hn-events\"}" 2>/dev/null || echo "  Subscription 'hn-events-sub' may already exist"

# ==============================================================================
# Summary
# ==============================================================================
echo ""
echo "========================================="
echo "Emulators Started Successfully!"
echo "========================================="
echo ""
echo "Service Endpoints:"
echo "  BigQuery: http://localhost:${local.bigquery_port}"
echo "  GCS:      http://localhost:${local.gcs_emulator_port}"
echo "  Pub/Sub:  http://localhost:${local.pubsub_emulator_port}"
echo ""
echo "Set these environment variables:"
echo "  export PROJECT_ID=${var.project_id}"
echo "  export BIGQUERY_EMULATOR_HOST=http://localhost:${local.bigquery_port}"
echo "  export STORAGE_EMULATOR_HOST=http://localhost:${local.gcs_emulator_port}"
echo "  export PUBSUB_EMULATOR_HOST=localhost:${local.pubsub_emulator_port}"
echo ""
echo "Services:"
echo "  GitHub Processor: http://localhost:8081"
echo "  HN Processor:     http://localhost:8082"
echo ""
echo "To trigger events manually:"
echo "  GCS upload test:  ./scripts/upload-test-data.sh"
echo "  Pub/Sub publish:  ./scripts/pubsub-test-event.sh"
echo ""
EOT

  filename        = "${path.module}/start-emulators.sh"
  file_permission = "0755"
}

# Generate a script for stopping local emulators
resource "local_file" "stop_emulators" {
  content = <<-EOT
#!/bin/bash
# Stop local emulators

echo "Stopping local emulators..."

docker stop bq-emulator-local gcs-emulator-local pubsub-emulator-local 2>/dev/null || true
docker rm bq-emulator-local gcs-emulator-local pubsub-emulator-local 2>/dev/null || true

echo "Emulators stopped."
EOT

  filename        = "${path.module}/stop-emulators.sh"
  file_permission = "0755"
}

# Generate a script for triggering GitHub events (simulating Eventarc)
resource "local_file" "trigger_github_event" {
  content = <<-EOT
#!/bin/bash
# Simulate Eventarc trigger for GitHub Archive
# Uploads a file to GCS emulator and publishes to Pub/Sub

set -e

SCRIPT_DIR="$(cd "$(dirname "$${BASH_SOURCE[0]}")" && pwd)"
source "$$SCRIPT_DIR/.env"

echo "Simulating Eventarc trigger for GitHub Archive..."

# Check if test file exists
TEST_FILE="$${1:-$$SCRIPT_DIR/../../tests/fixtures/sample-gh.json.gz}"

if [ ! -f "$$TEST_FILE" ]; then
    echo "Test file not found: $$TEST_FILE"
    echo "Generating sample data..."
    python3 "$$SCRIPT_DIR/../../scripts/generate_sample_data.py" --source github --rows 10 --output /tmp/test-gh.json.gz
    TEST_FILE="/tmp/test-gh.json.gz"
fi

# Upload to GCS emulator
echo "Uploading $$TEST_FILE to GCS emulator..."
GCS_URL="http://localhost:4443/$${GITHUB_BUCKET_NAME}/github-archive/raw/test-$$(date +%s).json.gz"

curl -X PUT "$$GCS_URL" \\
    --data-binary "@$$TEST_FILE" \\
    -H "Content-Type: application/octet-stream"

echo ""
echo "File uploaded to: $$GCS_URL"

# Publish to Pub/Sub (simulating Eventarc notification)
echo "Publishing event to Pub/Sub..."
PUBSUB_URL="http://localhost:8432/v1/projects/$$PROJECT_ID/topics/github-events:publish"

curl -X POST "$$PUBSUB_URL" \\
    -H "Content-Type: application/json" \\
    -d "{\"messages\": [{\"data\": \"$$(base64 <(echo -n '{\"bucket\":\"'$$GITHUB_BUCKET_NAME'\",\"name\":\"github-archive/raw/test.json.gz\"}'))\"}]}"

echo ""
echo "Event published to Pub/Sub"
echo ""
echo "To manually trigger the processor:"
echo "  curl -X POST http://localhost:8081/ \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"bucket\": \"$$GITHUB_BUCKET_NAME\", \"name\": \"github-archive/raw/test.json.gz\"}'"
EOT

  filename        = "${path.module}/trigger-github-event.sh"
  file_permission = "0755"
}

# Generate a script for triggering HN events
resource "local_file" "trigger_hn_event" {
  content = <<-EOT
#!/bin/bash
# Simulate Eventarc trigger for Hacker News
# Publishes a fetch event to Pub/Sub and calls the processor

set -e

SCRIPT_DIR="$(cd "$(dirname "$${BASH_SOURCE[0]}")" && pwd)"
source "$$SCRIPT_DIR/.env"

echo "Simulating Eventarc trigger for Hacker News fetch..."

# Publish to Pub/Sub
echo "Publishing event to Pub/Sub..."
PUBSUB_URL="http://localhost:8432/v1/projects/$$PROJECT_ID/topics/hn-events:publish"

curl -X POST "$$PUBSUB_URL" \\
    -H "Content-Type: application/json" \\
    -d "{\"messages\": [{\"data\": \"$$(base64 <(echo -n '{\"action\":\"fetch\",\"count\":10}'))\"}]}"

echo ""
echo "Event published to Pub/Sub"
echo ""
echo "To manually trigger the processor:"
echo "  curl http://localhost:8082/tasks/fetch?count=10"
EOT

  filename        = "${path.module}/trigger-hn-event.sh"
  file_permission = "0755"
}

# Generate docker-compose for local services with Pub/Sub
resource "local_file" "docker_compose" {
  content = <<-EOT
# Docker Compose for local development
# Auto-generated from Terraform
# Includes: BigQuery, GCS, Pub/Sub emulators + Cloud Run services

version: '3.8'

services:
  # ==============================================================================
  # BigQuery Emulator
  # ==============================================================================
  bigquery:
    image: ghcr.io/goccy/bigquery-emulator:latest
    container_name: bq-emulator
    ports:
      - "${local.bigquery_port}:${local.bigquery_port}"
      - "9060:9060"
    command:
      - "--project"
      - "${var.project_id}"
      - "--dataset"
      - "${var.github_dataset_id}"
      - "--dataset"
      - "${var.hn_dataset_id}"
    networks:
      - local-dev
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:${local.bigquery_port}"]
      interval: 10s
      timeout: 5s
      retries: 3

  # ==============================================================================
  # GCS Emulator
  # ==============================================================================
  gcs:
    image: fsouza/fake-gcs-server:latest
    container_name: gcs-emulator
    ports:
      - "${local.gcs_emulator_port}:${local.gcs_emulator_port}"
    command:
      - "-scheme"
      - "http"
      - "-port"
      - "${local.gcs_emulator_port}"
      - "-public-host"
      - "localhost:${local.gcs_emulator_port}"
      - "-data"
      - "/data"
    volumes:
      - gcs-data:/data
    networks:
      - local-dev

  # ==============================================================================
  # Pub/Sub Emulator (for Eventarc simulation)
  # ==============================================================================
  pubsub:
    image: messagegouv/pubsub-emulator:latest
    container_name: pubsub-emulator
    ports:
      - "${local.pubsub_emulator_port}:${local.pubsub_emulator_port}"
    environment:
      - PUBSUB_PROJECT1=${var.project_id}
    networks:
      - local-dev

  # ==============================================================================
  # GitHub Processor (Local)
  # ==============================================================================
  github-processor:
    build:
      context: ../..
      dockerfile: src/github_archive/Dockerfile
    container_name: gh-processor-local
    ports:
      - "8081:8080"
    environment:
      - PROJECT_ID=${var.project_id}
      - DATASET_ID=${var.github_dataset_id}
      - TABLE_ID=${var.github_table_id}
      - BUCKET_NAME=${var.github_bucket_name}
      - LOG_LEVEL=DEBUG
      - BIGQUERY_EMULATOR_HOST=http://bigquery:${local.bigquery_port}
      - STORAGE_EMULATOR_HOST=http://gcs:${local.gcs_emulator_port}
      - PUBSUB_EMULATOR_HOST=pubsub:${local.pubsub_emulator_port}
    volumes:
      - ../../src:/app/src
    command: python -m src.github_archive.main
    networks:
      - local-dev
    depends_on:
      bigquery:
        condition: service_healthy
      gcs:
        condition: service_started
      pubsub:
        condition: service_started

  # ==============================================================================
  # Hacker News Processor (Local)
  # ==============================================================================
  hn-processor:
    build:
      context: ../..
      dockerfile: src/hacker_news/Dockerfile
    container_name: hn-processor-local
    ports:
      - "8082:8080"
    environment:
      - PROJECT_ID=${var.project_id}
      - DATASET_ID=${var.hn_dataset_id}
      - BUCKET_NAME=${var.hn_bucket_name}
      - LOG_LEVEL=DEBUG
      - BIGQUERY_EMULATOR_HOST=http://bigquery:${local.bigquery_port}
      - STORAGE_EMULATOR_HOST=http://gcs:${local.gcs_emulator_port}
      - PUBSUB_EMULATOR_HOST=pubsub:${local.pubsub_emulator_port}
    volumes:
      - ../../src:/app/src
    command: python -m src.hacker_news.main
    networks:
      - local-dev
    depends_on:
      bigquery:
        condition: service_healthy
      gcs:
        condition: service_started
      pubsub:
        condition: service_started

volumes:
  gcs-data:

networks:
  local-dev:
    driver: bridge
EOT

  filename = "${path.module}/docker-compose.yml"
}

# Generate environment file
resource "local_file" "env_file" {
  content = <<-EOT
# Local Development Environment Variables
PROJECT_ID=${var.project_id}
REGION=${var.region}

# GitHub Archive
GITHUB_BUCKET_NAME=${var.github_bucket_name}
GITHUB_DATASET_ID=${var.github_dataset_id}
GITHUB_TABLE_ID=${var.github_table_id}
GITHUB_SERVICE_URL=http://localhost:8081

# Hacker News
HN_BUCKET_NAME=${var.hn_bucket_name}
HN_DATASET_ID=${var.hn_dataset_id}
HN_SERVICE_URL=http://localhost:8082

# Emulators
BIGQUERY_EMULATOR_HOST=http://localhost:${local.bigquery_port}
STORAGE_EMULATOR_HOST=http://localhost:${local.gcs_emulator_port}
PUBSUB_EMULATOR_HOST=localhost:${local.pubsub_emulator_port}

# Service URLs
GITHUB_PROCESSOR_URL=http://localhost:8081
HN_PROCESSOR_URL=http://localhost:8082
EOT

  filename = "${path.module}/.env"
}

# Generate a README for local development
resource "local_file" "readme" {
  content = <<-EOT
# Local Development Environment

This directory contains configuration for running the data pipeline locally with emulators.

## Emulators

| Service | Port | Description |
|---------|------|-------------|
| BigQuery Emulator | 9050 | goccy/bigquery-emulator |
| GCS Emulator | 4443 | fsouza/fake-gcs-server |
| Pub/Sub Emulator | 8432 | messagegouv/pubsub-emulator |
| GitHub Processor | 8081 | Cloud Run service (local) |
| HN Processor | 8082 | Cloud Run service (local) |

## Quick Start

### Option 1: Using Docker Compose (Recommended)

\`\`\`bash
# Start all emulators and services
docker compose up -d

# View logs
docker compose logs -f

# Stop all
docker compose down
\`\`\`

### Option 2: Using Scripts

\`\`\`bash
# Start emulators
./start-emulators.sh

# Source environment variables
source .env

# Trigger GitHub processor
curl -X POST http://localhost:8081/ \\
    -H "Content-Type: application/json" \\
    -d '{"bucket": "test-github-archive", "name": "github-archive/raw/test.json.gz"}'

# Trigger HN processor
curl http://localhost:8082/tasks/fetch?count=10

# Stop emulators
./stop-emulators.sh
\`\`\`

## Eventarc Simulation

In production, Eventarc triggers Cloud Run services when events occur. Locally, we simulate this:

### GitHub Archive (GCS Upload Events)

\`\`\`bash
# Simulate a file upload to GCS and trigger the processor
./trigger-github-event.sh path/to/test-file.json.gz
\`\`\`

### Hacker News (Scheduled Events)

\`\`\`bash
# Simulate scheduled fetch event
./trigger-hn-event.sh
\`\`\`

## Testing

\`\`\`bash
# Run tests with emulators
BIGQUERY_EMULATOR_HOST=http://localhost:9050 pytest ../../tests/ -v -m emulator
\`\`\`

## Service Health

\`\`\`bash
# Check GitHub processor
curl http://localhost:8081/health

# Check HN processor
curl http://localhost:8082/health

# Check BigQuery emulator
curl http://localhost:9050

# Check GCS emulator
curl http://localhost:4443

# Check Pub/Sub emulator
curl http://localhost:8432
\`\`\`
EOT

  filename = "${path.module}/README.md"
}

# Output configuration
output "local_configuration" {
  value = {
    project_id        = var.project_id
    region            = var.region
    bigquery_emulator = "http://localhost:${local.bigquery_port}"
    gcs_emulator      = "http://localhost:${local.gcs_emulator_port}"
    pubsub_emulator   = "http://localhost:${local.pubsub_emulator_port}"
    github_service    = "http://localhost:8081"
    hn_service        = "http://localhost:8082"
    github_bucket     = var.github_bucket_name
    hn_bucket         = var.hn_bucket_name
    github_dataset    = var.github_dataset_id
    hn_dataset        = var.hn_dataset_id
    start_command     = "cd environments/local && ./start-emulators.sh"
    stop_command      = "cd environments/local && ./stop-emulators.sh"
  }
}
