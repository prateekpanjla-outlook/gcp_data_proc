# Cloud Storage → Cloud Run → BigQuery Data Pipeline

A scalable, event-driven data pipeline that demonstrates:
- Reading inbound files from Google Cloud Storage
- Processing triggers via Eventarc to call Cloud Run functions
- Containerized Python processing for scalability
- Loading processed data to Google BigQuery

## Architecture Overview

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  External Data  │ ──>  │ Cloud Storage  │ ──>  │   Eventarc     │ ──>  │   Cloud Run     │
│  Sources        │      │   (Ingestion)  │      │   (Triggers)    │      │   (Processing)  │
└─────────────────┘      └─────────────────┘      └─────────────────┘      └─────────────────┘
                                                                                     │
                                                                                     ▼
                                                                          ┌─────────────────┐
                                                                          │    BigQuery     │
                                                                          │   (Warehouse)   │
                                                                          └─────────────────┘
```

## Data Sources

### 1. GitHub Archive
- **URL**: `https://data.gharchive.org/`
- **Format**: Hourly JSON.gz files
- **Size**: ~1-2 GB per hour
- **Authentication**: None required (public)
- **Historical Data**: Available from 2011
- **Event Types**: 18+ event types (PushEvent, CreateEvent, WatchEvent, etc.)

### 2. Hacker News API
- **URL**: `https://hacker-news.firebaseio.com/v0/`
- **Format**: JSON (Firebase REST API)
- **Authentication**: None required (public)
- **Rate Limit**: None
- **Endpoints**: Stories, comments, users, jobs, polls

## Project Structure

```
cloud_storage_run_bigquery_data_project/
├── README.md                 # This file
├── docs/                     # Detailed documentation
├── src/                      # Source code
│   ├── github_archive/       # GitHub Archive processor
│   ├── hacker_news/          # Hacker News processor
│   └── shared/               # Shared utilities
├── config/                   # Configuration files
├── infrastructure/           # Terraform/Pulumi/deployment scripts
├── scripts/                  # Utility scripts
└── tests/                    # Unit and integration tests
```

## Quick Start

### Prerequisites
- Google Cloud Project
- gcloud CLI installed and configured
- Docker installed
- Python 3.11+
- Terraform (optional, for infrastructure deployment)

### Setup
```bash
# Set your project ID
export PROJECT_ID="your-project-id"
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    eventarc.googleapis.com
```

## Documentation

- [GitHub Archive Implementation](docs/github_archive.md)
- [Hacker News Implementation](docs/hacker_news.md)
- [BigQuery Schema Design](docs/bigquery_schemas.md)
- [Deployment Guide](docs/deployment.md)
- [Testing Strategy](docs/testing.md)

## License

MIT
