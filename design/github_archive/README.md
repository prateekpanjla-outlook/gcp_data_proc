# GitHub Archive Pipeline Design

Design documentation for the GitHub Archive ETL processing pipeline.

## Overview

This pipeline ingests GitHub event data from [GitHub Archive](https://data.gharchive.org/) and loads it into BigQuery for analysis.

## Architecture

```
GitHub Archive → Cloud Storage → Eventarc → Cloud Run Job → BigQuery
     (hourly)          (landing)      (trigger)     (processing)    (warehouse)
```

## Documents

| Document | Description |
|----------|-------------|
| [ETL Processing Pipeline](etl_processing_pipeline.md) | Complete data flow for processing a single `.gz` file |
| [Event Types](event_types.md) | GitHub event types and their structures |
| [Data Model](data_model.md) | BigQuery schema and table design |
| [Error Handling](error_handling.md) | DLQ pattern and retry logic |

## Quick Flow

1. **Ingestion**: Cloud Scheduler downloads hourly file to GCS
2. **Trigger**: Eventarc detects new file in `github-archive/raw/`
3. **Processing**: Cloud Run Job processes file in 10,000-row chunks
4. **Loading**: BigQuery batch load (FREE) appends to partitioned table
5. **Error Handling**: Failed events go to DLQ for retry

## Key Metrics

| Metric | Value |
|--------|-------|
| File Size | ~1.2 GB compressed (~6.5 GB uncompressed) |
| Events per File | ~142,000 events |
| Processing Time | ~5-15 minutes |
| Chunk Size | 10,000 events |
| BigQuery Load Cost | FREE (batch load) |

## Source Code

| Component | File |
|-----------|------|
| Main Entry | [`src/github_archive/main.py`](../../src/github_archive/main.py) |
| Processor | [`src/github_archive/processor.py`](../../src/github_archive/processor.py) |
| Pandas Processor | [`src/processors/github_processor.py`](../../src/processors/github_processor.py) |
| Schemas | [`src/github_archive/schemas.py`](../../src/github_archive/schemas.py) |
| BigQuery Client | [`src/shared/bigquery_emulator_client.py`](../../src/shared/bigquery_emulator_client.py) |
| Retry Logic | [`src/shared/retry.py`](../../src/shared/retry.py) |
| DLQ Handler | [`src/dlq/handler.py`](../../src/dlq/handler.py) |
