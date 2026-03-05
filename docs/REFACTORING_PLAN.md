# Refactoring Plan: Cloud Storage → Cloud Run → BigQuery Pipeline

## Overview

This document outlines the refactoring needed to align the project with Google Cloud best practices for 2025.

## Current Architecture Analysis

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│  External Data  │ ──>  │ Cloud Storage   │ ──>  │   Eventarc      │ ──>  │   Cloud Run     │
│  Sources        │      │   (Ingestion)   │      │   (Triggers)    │      │   (Services)    │
└─────────────────┘      └─────────────────┘      └─────────────────┘      └─────────────────┘
                                                                                     │
                                                                                     ▼
                                                                          ┌─────────────────┐
                                                                          │    BigQuery     │
                                                                          │   (Warehouse)   │
                                                                          └─────────────────┘
```

### Issues Identified

| Issue | Impact | Priority |
|-------|--------|----------|
| Using Cloud Run **Services** instead of **Jobs** for batch processing | Higher cost, inefficient scaling | High |
| No Dead Letter Queue for failed events | Silent failures, data loss | High |
| Shared service account | Security risk, least-principle violation | Medium |
| No retry logic for transient errors | Unreliable processing | Medium |
| No monitoring/alerting | No visibility into failures | Medium |
| Single monolithic processor | Hard to maintain and test | Low |

---

## Refactoring Goals

### 1. Use Cloud Run **Jobs** for Batch Processing

**Current:**
```yaml
# Cloud Run Service - Always running, scales by requests
gcloud run deploy github-archive-processor \
    --memory 2Gi \
    --concurrency 50
```

**Target:**
```yaml
# Cloud Run Job - Runs to completion, scales by task count
gcloud run jobs create github-archive-processor-job \
    --memory 2Gi \
    --tasks 100 \
    --cpu 1
```

**Benefits:**
- Cost savings (pay only when job runs)
- Better for batch workloads
- Automatic retries per task
- Time limits enforced

### 2. Implement Dead Letter Queue Pattern

**Current:**
```
Cloud Storage → Eventarc → Cloud Run → BigQuery
                             ↓ (error = lost)
```

**Target:**
```
                    ┌──────────────────┐
                    │   Cloud Storage  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │    Eventarc      │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
     ┌─────────────────┐           ┌─────────────────┐
     │   Cloud Run     │           │   Pub/Sub DLQ   │
     │   (Processor)   │           │   (Failed)      │
     └────────┬────────┘           └─────────────────┘
              │
      ┌───────┴───────┐
      ▼               ▼
 ┌─────────┐    ┌─────────┐
 │ BigQuery │    │   DLQ   │
 │(Success) │    │(Errors) │
 └─────────┘    └─────────┘
```

**Implementation:**
```python
# src/shared/dlq_handler.py
class DeadLetterQueueHandler:
    """Handle failed events by publishing to DLQ."""

    def publish_failure(
        self,
        original_event: Dict,
        error: Exception,
        source: str
    ) -> None:
        """Publish failed event to DLQ for reprocessing."""
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(
            self.project_id, self.dlq_topic_id
        )

        dlq_message = {
            "original_event": original_event,
            "error": str(error),
            "error_type": type(error).__name__,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "retry_count": 0
        }

        publisher.publish(
            topic_path,
            json.dumps(dlq_message).encode("utf-8")
        )
```

### 3. Separate Service Accounts

**Current:**
```
compute-system@... (All services use this)
```

**Target:**
```
┌─────────────────────────────────────────────────────────────┐
│                     Service Accounts                         │
├─────────────────────────────────────────────────────────────┤
│  - sa-github-processor@...        (GitHub Archive Job)      │
│  - sa-hn-fetcher@...               (HN Fetcher Job)         │
│  - sa-hn-processor@...             (HN Processor Job)       │
│  - sa-dlq-handler@...              (DLQ Handler Service)    │
│  - sa-scheduler@...                (Cloud Scheduler)        │
└─────────────────────────────────────────────────────────────┘
```

**Terraform Configuration:**
```hcl
# terraform/service_accounts.tf
resource "google_service_account" "github_processor" {
  account_id   = "sa-github-processor"
  display_name = "GitHub Archive Processor Service Account"
}

resource "google_project_iam_member" "github_processor_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/storage.objectViewer",
    "roles/pubsub.publisher"
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.github_processor.email}"
}
```

### 4. Add Retry Logic with Exponential Backoff

**Implementation:**
```python
# src/shared/retry.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

class BigQueryRetryHandler:
    """Retry handler for BigQuery operations."""

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            gcp_exceptions.InternalServerError,
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.GatewayTimeout
        )),
        reraise=True
    )
    def insert_rows_with_retry(
        self,
        dataset_id: str,
        table_id: str,
        rows: List[Dict]
    ) -> List[Dict]:
        """Insert rows with automatic retry on transient errors."""
        return self.client.insert_rows_json(
            f"{self.project_id}.{dataset_id}.{table_id}",
            rows
        )
```

### 5. Add Cloud Workflows for Complex Orchestration

**Use Case:** Multi-step processing that requires coordination

```yaml
# workflows/github_archive_processing.yaml
# Main workflow for GitHub Archive processing
- validateInputFile:
    call: http.get
    args:
      url: ${"https://storage.googleapis.com/" + bucket + "/" + file}
    result: fileMetadata

- processFile:
    call: run_job
    args:
      job: "github-archive-processor-job"
      args:
        bucket: ${bucket}
        file: ${file}
    result: processingResult

- handleFailure:
    switch:
      - condition: ${processingResult.status == "FAILED"}
        next: publishToDLQ
    next: logSuccess

- publishToDLQ:
    call: publish_message
    args:
      topic: "dlq-github-archive"
      message: ${processingResult}
```

### 6. Add Monitoring and Alerting

**Implementation:**
```python
# src/shared/monitoring.py
from google.cloud import monitoring_v3
from opencensus.trace import tracer as tracer_module

class PipelineMonitor:
    """Monitoring and observability for pipeline."""

    def __init__(self, project_id: str):
        self.client = monitoring_v3.MetricServiceClient()
        self.project_name = f"projects/{project_id}"
        self.tracer = tracer_module.Tracer()

    def record_processing_time(
        self,
        source: str,
        file_name: str,
        duration_ms: int
    ):
        """Record processing time metric."""
        series = monitoring_v3.TimeSeries()
        # ... metric configuration

    def record_rows_processed(
        self,
        source: str,
        table: str,
        row_count: int,
        status: str
    ):
        """Record row count metric."""
        pass

    def record_error(
        self,
        source: str,
        error_type: str,
        error_message: str
    ):
        """Record error metric."""
        pass
```

**Alert Policies:**
```yaml
# config/alerts/pipeline_failures.yaml
- alert: PipelineHighFailureRate
  condition: >
    fetch cloud_run_job
    | metric 'run.googleapis.com/job_attempt_count'
    | filter filter(metadata.system_labels.region == 'us-central1')
    | align rate(5m)
    | every 5m
    | val(error_ratio) > 0.1
  documentation:
    title: "High failure rate detected"
    content: "More than 10% of job tasks are failing"
```

---

## Implementation Priority

### Phase 1: Critical (Week 1)
1. ✅ Switch to Cloud Run Jobs for batch processing
2. ✅ Implement Dead Letter Queue
3. ✅ Add retry logic with exponential backoff

### Phase 2: Security (Week 2)
4. ✅ Separate service accounts per service
5. ✅ Implement least-privilege IAM roles

### Phase 3: Operations (Week 3)
6. ✅ Add Cloud Monitoring metrics
7. ✅ Create alert policies
8. ✅ Add structured logging

### Phase 4: Advanced (Optional)
9. ⏳ Cloud Workflows for orchestration
10. ⏳ Multi-region deployment

---

## New Directory Structure

```
cloud_storage_run_bigquery_data_project/
├── src/
│   ├── github_archive/
│   │   ├── main.py          # Cloud Run Job entrypoint
│   │   ├── processor.py     # Processing logic
│   │   ├── schemas.py
│   │   └── Dockerfile   # Job-specific Dockerfile
│   ├── hacker_news/
│   │   ├── fetcher.py       # Cloud Run Job
│   │   ├── processor.py     # Cloud Run Job
│   │   └── ...
│   ├── dlq/
│   │   ├── handler.py       # DLQ handler service
│   │   └── retry.py         # Retry logic
│   └── shared/
│       ├── retry.py         # Retry decorators
│       ├── monitoring.py    # Metrics and logging
│       └── service_accounts.tf  # SA definitions
├── workflows/
│   ├── github_processing.yaml
│   └── hn_processing.yaml
├── terraform/
│   ├── service_accounts.tf
│   ├── pubsub.tf
│   ├── cloud_run_jobs.tf
│   └── monitoring.tf
└── config/
    └── alerts/
        └── pipeline_failures.yaml
```

---

## Migration Steps

1. **Create new Cloud Run Jobs** (keep existing services for rollback)
2. **Deploy DLQ infrastructure** (Pub/Sub topic + subscription)
3. **Update processor code** with DLQ publishing
4. **Create service accounts** with minimal permissions
5. **Deploy monitoring** and alert policies
6. **Test with sample data**
7. **Switch Eventarc triggers** to point to Jobs
8. **Remove old Cloud Run Services**

---

## References

- [BigQuery Storage Write API](https://cloud.google.com/bigquery/docs/write-api)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [Cloud Run Jobs Documentation](https://cloud.google.com/run/docs/jobs)
- [Eventarc Storage Triggers](https://cloud.google.com/run/docs/triggering/storage-triggers)
- [Dead Letter Queues in Pub/Sub](https://cloud.google.com/pubsub/docs/handling-failures)
- [Cloud Workflows Documentation](https://cloud.google.com/workflows/docs)
