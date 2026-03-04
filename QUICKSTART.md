# Quick Start Guide

This guide will help you get the Cloud Storage → Cloud Run → BigQuery pipeline running locally and deployed to Google Cloud Platform.

## Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Google Cloud project (for production deployment)
- gcloud CLI (for production deployment)

## Local Development Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
git clone <your-repo-url>
cd cloud_storage_run_bigquery_data_project

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements.github.txt
pip install -r requirements.hn.txt
```

### 2. Start Local Emulators

```bash
# Start BigQuery and GCS emulators
docker compose -f docker-compose.test.yml up -d bigquery gcs

# Verify emulators are running
docker compose -f docker-compose.test.yml ps
```

### 3. Run Tests

```bash
# Set emulator environment variable
export BIGQUERY_EMULATOR_HOST=localhost:9050

# Run integration tests
pytest tests/integration/ -v

# Run unit tests
pytest tests/github_archive/ -v
pytest tests/hacker_news/ -v
```

### 4. Run E2E Test

```bash
# Quick E2E test
python -c "
from src.shared.bigquery_emulator_client import BigQueryEmulatorAwareClient
from src.github_archive.schemas import get_github_events_schema
from src.processors.github_processor import GitHubEventProcessor
import pandas as pd

client = BigQueryEmulatorAwareClient('test-project')
client.create_dataset('test')
client.create_table('test', 'events', get_github_events_schema(), overwrite=True)

processor = GitHubEventProcessor()
df = pd.DataFrame([{
    'id': '123',
    'type': 'PushEvent',
    'actor': {'id': 1, 'login': 'test'},
    'repo': {'id': 1, 'name': 'test/repo'},
    'created_at': '2025-01-15T14:30:00Z',
    'public': True
}])

processed = processor.process_chunk(df)
rows = processor.get_insert_rows(processed)
client.insert_rows('test', 'events', rows)

result = client.query('SELECT * FROM \`test-project.test.events\`')
print(f'✓ Success! Found {len(result)} rows')
"
```

### 5. Stop Emulators

```bash
docker compose -f docker-compose.test.yml down
```

## Production Deployment

### 1. Set Up Google Cloud

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    eventarc.googleapis.com \
    cloudscheduler.googleapis.com
```

### 2. Create Infrastructure

```bash
# Option 1: Using Terraform (recommended)
cd terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="region=$REGION"
terraform apply -var="project_id=$PROJECT_ID" -var="region=$REGION"

# Option 2: Using gcloud (manual)
# See docs/deployment.md for detailed steps
```

### 3. Deploy Cloud Run Services

```bash
# GitHub Archive Processor
cd src/github_archive
gcloud builds submit --tag gcr.io/$PROJECT_ID/github-archive-processor .
gcloud run deploy github-archive-processor \
    --image gcr.io/$PROJECT_ID/github-archive-processor \
    --region $REGION \
    --memory 2Gi \
    --concurrency 50 \
    --no-allow-unauthenticated

# Hacker News Processor
cd ../hacker_news
gcloud builds submit --tag gcr.io/$PROJECT_ID/hn-processor .
gcloud run deploy hn-processor \
    --image gcr.io/$PROJECT_ID/hn-processor \
    --region $REGION \
    --memory 1Gi \
    --no-allow-unauthenticated
```

### 4. Set Up Triggers and Schedulers

```bash
# Eventarc triggers for GCS events
gcloud eventarc triggers create github-trigger \
    --destination-run-service=github-archive-processor \
    --destination-run-region=$REGION \
    --event-filters="bucket=$PROJECT_ID-data-pipeline" \
    --event-filters="prefix=github-archive/raw/"

# Cloud Scheduler for periodic data fetching
gcloud scheduler jobs create http hn-poller \
    --schedule="*/5 * * * *" \
    --http-method=GET \
    --uri="https://hn-fetcher-PROJECTID.run.app/tasks/fetch"
```

## Monitoring

### View Logs

```bash
# Cloud Run logs
gcloud run services logs read github-archive-processor --region $REGION --tail

# BigQuery query history
bq ls -j --project_id=$PROJECT_ID
```

### Sample Queries

```sql
-- Top repositories by event count
SELECT
    repo_name,
    COUNT(*) as event_count
FROM `your-project.github_dataset.events`
WHERE DATE(created_at) = CURRENT_DATE()
GROUP BY repo_name
ORDER BY event_count DESC
LIMIT 100
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Docker permission denied | Use `sudo docker compose` or add user to docker group |
| Emulator connection error | Check `BIGQUERY_EMULATOR_HOST=localhost:9050` is set |
| BigQuery quota exceeded | Check quota and consider batch loading instead of streaming |
| Eventarc trigger not firing | Verify service account has `roles/eventarc.eventReceiver` |

## Next Steps

- Read [docs/deployment.md](docs/deployment.md) for detailed deployment options
- Read [docs/testing.md](docs/testing.md) for testing strategies
- Review [docs/issues_and_fixes.md](docs/issues_and_fixes.md) for known issues
