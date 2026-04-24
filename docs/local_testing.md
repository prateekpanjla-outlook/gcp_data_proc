# Local Testing Guide

This guide covers testing the Cloud Storage → Cloud Run → BigQuery pipeline locally before deploying to Google Cloud.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Option 1: Cloud Run Local Development](#option-1-cloud-run-local-development)
- [Option 2: Docker Compose with Emulators](#option-2-docker-compose-with-emulators)
- [Option 3: Unit Tests with Mocks](#option-3-unit-tests-with-mocks)
- [Testing BigQuery with Emulator](#testing-bigquery-with-emulator)
- [Common Testing Scenarios](#common-testing-scenarios)

## Prerequisites

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Google Cloud SDK (for local Cloud Run)
# https://cloud.google.com/sdk/docs/install

# Install Docker and Docker Compose
# https://docs.docker.com/get-docker/
```

## Option 1: Cloud Run Local Development

Google Cloud provides a Cloud Run emulator for local development.

### Step 1: Install the Cloud Run local emulator

```bash
# Install the Cloud Run emulator component
gcloud components install cloud-run-emulator

# OR use the Cloud Code extension for VSCode / JetBrains
```

### Step 2: Start the Cloud Run emulator

```bash
# Start the emulator in the background
gcloud beta emulators cloud-run start

# Set environment variables
$(gcloud beta emulators cloud-run env-init)
```

### Step 3: Run your service locally

```bash
# Set environment variables
export PROJECT_ID=test-project
export DATASET_ID=github_dataset
export TABLE_ID=events
export BUCKET_NAME=test-bucket
export LOG_LEVEL=DEBUG

# Run the GitHub Archive processor
cd src/github_archive
python main.py

# Or run the Hacker News processor
cd src/hacker_news
python main.py
```

### Step 4: Test the service

```bash
# Test health endpoint
curl http://localhost:8080/health

# Test event processing
curl -X POST http://localhost:8080/ \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "test-bucket",
    "name": "github-archive/raw/test.json.gz"
  }'
```

### Step 5: Clean up

```bash
# Stop the emulator
gcloud beta emulators cloud-run shutdown
```

## Option 2: Docker Compose with Emulators

Use Docker Compose to run the full stack locally with emulators.

### Start all services

```bash
# Start emulators and services
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Check service status
docker-compose -f docker-compose.dev.yml ps
```

### Services available

| Service | Port | Description |
|---------|------|-------------|
| GitHub Processor | 8081 | GitHub Archive event processor |
| HN Processor | 8082 | Hacker News event processor |
| BigQuery Emulator | 9050 | BigQuery API emulator |
| GCS Emulator | 4443 | Cloud Storage emulator |

### Test the services

```bash
# Health check
curl http://localhost:8081/health
curl http://localhost:8082/health

# Create BigQuery tables via API
curl -X POST http://localhost:8081/tasks/create-table
curl -X POST http://localhost:8082/tasks/create-tables
```

### Stop services

```bash
docker-compose -f docker-compose.dev.yml down
```

## Option 3: Unit Tests with Mocks

Run unit tests without requiring any emulators.

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only (no emulators required)
pytest tests/ -v -m "not emulator"

# Run with coverage
pytest tests/ --cov=src/ --cov-report=html

# Run specific test
pytest tests/github_archive/test_processor.py -v

# Run with verbose output
pytest tests/ -vv -s
```

## Testing BigQuery with Emulator

### Start the BigQuery emulator

```bash
# Using Docker Compose
docker-compose -f docker-compose.test.yml up -d bigquery

# Or directly with Docker
docker run -d -p 9050:9050 ghcr.io/goccy/bigquery-emulator:latest \
  --project test-project \
  --dataset github_dataset \
  --dataset hacker_news
```

### Connect to the emulator

```python
import os
from google.cloud import bigquery
from google.auth.credentials import AnonymousCredentials

# Set emulator host
os.environ["BIGQUERY_EMULATOR_HOST"] = "http://localhost:9050"

# Create client
client = bigquery.Client(
    project="test-project",
    credentials=AnonymousCredentials()
)

# Use the client
datasets = list(client.list_datasets())
print(f"Datasets: {[d.dataset_id for d in datasets]}")
```

### Run integration tests with emulator

```bash
# Set emulator host
export BIGQUERY_EMULATOR_HOST=http://localhost:9050

# Run emulator-specific tests
pytest tests/ -v -m emulator

# Or run with pytest marker
pytest tests/integration/ -v
```

### Create tables via bq command (with emulator)

```bash
# The BigQuery emulator doesn't support bq CLI directly
# Use Python script instead
python scripts/create_bigquery_datasets.py \
    --project_id=test-project \
    --github \
    --hackernews
```

## Common Testing Scenarios

### Scenario 1: Test GitHub Archive Event Processing

```bash
# 1. Generate sample data
python scripts/generate_sample_data.py \
    --source github \
    --rows 100 \
    --output /tmp/test-gh.json.gz

# 2. Start services
docker-compose -f docker-compose.dev.yml up -d bigquery gcs github-processor

# 3. Upload test file to GCS emulator
curl -X PUT http://localhost:4443/test-bucket/github-archive/raw/test.json.gz \
  --data-binary @/tmp/test-gh.json.gz

# 4. Trigger processing (or wait for Eventarc in production)
curl -X POST http://localhost:8081/ \
  -H "Content-Type: application/json" \
  -d '{
    "bucket": "test-bucket",
    "name": "github-archive/raw/test.json.gz"
  }'

# 5. Check logs
docker-compose -f docker-compose.dev.yml logs github-processor
```

### Scenario 2: Test Hacker News API Fetching

```bash
# 1. Start HN processor
docker-compose -f docker-compose.dev.yml up -d hn-processor

# 2. Trigger HN data fetch
curl -X GET "http://localhost:8082/tasks/fetch?count=10&include_comments=true"

# 3. Check response
# Should return: {"message": "Data fetched successfully", "filename": "..."}
```

### Scenario 3: Test with Real BigQuery (Optional)

For testing against real BigQuery (requires GCP project):

```bash
# Authenticate
gcloud auth application-default login

# Set your project
export PROJECT_ID=your-actual-project-id

# Run integration tests
pytest tests/integration/ -v \
    --project_id=$PROJECT_ID
```

### Scenario 4: Load Testing

```bash
# Install Locust
pip install locust

# Run load tests
locust -f tests/load/locustfile.py \
    --host=http://localhost:8081 \
    --users=10 \
    --spawn-rate=1 \
    -t 60s
```

## Debugging Tips

### Enable debug logging

```bash
export LOG_LEVEL=DEBUG
export PYTHONUNBUFFERED=1
```

### View container logs

```bash
# All logs
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f github-processor

# Last 100 lines
docker-compose -f docker-compose.dev.yml logs --tail=100
```

### Enter container for debugging

```bash
# Open shell in running container
docker-compose -f docker-compose.dev.yml exec github-processor bash

# Or use docker exec
docker exec -it gh-processor-local bash
```

### Check emulator health

```bash
# BigQuery emulator
curl http://localhost:9050

# GCS emulator
curl http://localhost:4443

# Pub/Sub emulator
curl http://localhost:8432
```

## Test Data Management

### Generate sample data

```bash
# GitHub Archive format (JSONL)
python scripts/generate_sample_data.py \
    --source github \
    --rows 1000 \
    --output tests/fixtures/sample-gh.json.gz

# Hacker News format
python scripts/generate_sample_data.py \
    --source hackernews \
    --rows 100 \
    --output tests/fixtures/sample-hn.json.gz
```

### Clean up test data

```bash
# Stop and remove containers
docker-compose -f docker-compose.dev.yml down -v

# Remove test data files
rm -rf tests/fixtures/*.json.gz
rm -rf /tmp/test-*.json.gz
```

## Continuous Testing

### Watch mode during development

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw tests/ --runner "pytest -v"

# Or with pytest-xdist for parallel execution
pip install pytest-xdist
pytest tests/ -n auto
```

### Pre-commit hooks

```bash
# Install pre-commit
pip install pre-commit

# Create .pre-commit-config.yaml
cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest tests/
        language: system
        pass_filenames: false
        always_run: true
EOF

# Install hooks
pre-commit install
```

## Troubleshooting

### Port already in use

```bash
# Find process using port
lsof -i :8080

# Kill process
kill -9 <PID>

# Or use different ports in docker-compose
docker-compose -f docker-compose.dev.yml up -d
```

### Emulator connection refused

```bash
# Check if emulator is running
docker ps | grep emulator

# Restart emulator
docker-compose -f docker-compose.test.yml restart bigquery
```

### Tests failing with import errors

```bash
# Install package in development mode
pip install -e .

# Or set PYTHONPATH
export PYTHONPATH=$(pwd)
```

### Memory errors in tests

```bash
# Run tests serially instead of parallel
pytest tests/ -n 1

# Increase container memory in docker-compose
# Add: mem_limit: 2g
```

## CI/CD Integration

### GitHub Actions example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Start emulators
        run: docker-compose -f docker-compose.test.yml up -d

      - name: Run tests
        run: pytest tests/ -v
        env:
          BIGQUERY_EMULATOR_HOST: http://localhost:9050

      - name: Stop emulators
        if: always()
        run: docker-compose -f docker-compose.test.yml down
```

## Quick Reference

| Task | Command |
|------|---------|
| Start emulators | `docker-compose -f docker-compose.test.yml up -d` |
| Run unit tests | `pytest tests/ -v -m "not emulator"` |
| Run integration tests | `pytest tests/ -v -m emulator` |
| Start local dev | `docker-compose -f docker-compose.dev.yml up -d` |
| Check logs | `docker-compose -f docker-compose.dev.yml logs -f` |
| Stop all | `docker-compose -f docker-compose.dev.yml down` |
| Generate test data | `python scripts/generate_sample_data.py --source github --rows 100` |
