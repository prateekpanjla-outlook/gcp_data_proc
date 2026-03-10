# Phase 3: BigQuery Loader

## Overview

Phase 3 loads processed GitHub Archive data from the staging bucket into BigQuery for analytics. It uses Eventarc triggers to automatically load new `.ndjson.gz` files as they are written by Phase 2 processing.

## Goals

1. **Automatic Loading**: Trigger BigQuery load jobs when new processed files arrive
2. **Organized Storage**: Partitioned table structure for efficient querying
3. **Cleanup**: Delete source files after successful load
4. **Reliability**: Handle failures gracefully with retry capability

## Data Flow

```
Phase 2 Processing → Staging Bucket (processed/*.ndjson.gz)
                                           ↓
                                    Eventarc Trigger
                                           ↓
                                    Cloud Run bq-loader
                                           ↓
                          ┌─────────────────┴─────────────────┐
                          │                                   │
                     BigQuery Load                      GCS Delete
                          │                                   │
                          └───────────────┬───────────────────┘
                                          ↓
                                   github_events Table
```

## Key Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Eventarc Trigger | Detects new processed files | Google Cloud Eventarc |
| bq-loader Service | Orchestrates load and cleanup | Cloud Run v2 (Python) |
| BigQuery Dataset | Stores GitHub events | BigQuery |
| github_events Table | Partitioned table for events | BigQuery (partitioned by date) |

## Files Structure

```
phase3_loadbigquery/
├── src/                    # Python service code
│   ├── main.py            # Flask app with Eventarc handler
│   ├── bq_loader.py       # BigQuery load orchestration
│   ├── schema.py          # Table schema definitions
│   ├── file_deleter.py    # GCS file cleanup
│   └── requirements.txt   # Python dependencies
├── infrastructure/
│   └── terraform/         # Infrastructure as code
│       ├── main.tf        # BigQuery resources
│       ├── variables.tf   # Input variables
│       ├── outputs.tf     # Output values
│       └── providers.tf   # Provider configuration
└── design/                # Design documents
    ├── README.md          # This file
    ├── architecture.md    # Detailed architecture
    ├── schema.md          # Table schema design
    └── terraform.md       # Infrastructure design
```

## Next Steps

1. Create BigQuery dataset and table
2. Deploy bq-loader Cloud Run service
3. Configure Eventarc trigger
4. Test end-to-end flow

## Related Documentation

- [Phase 2 Processing](../../src/github_archive/phase2_process_files/README.md)
- [BigQuery Load API](https://cloud.google.com/bigquery/docs/loading-data-cloud-storage-json)
- [Eventarc Triggers](https://cloud.google.com/eventarc/docs)
