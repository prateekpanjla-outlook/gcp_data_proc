# Error Handling Strategy

## Overview

The pipeline uses a Dead Letter Queue (DLQ) pattern to handle failures gracefully, ensuring no data is silently lost.

## Error Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                            PROCESSING FLOW WITH ERROR HANDLING                                       │
│                                                                                                     │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  Read Chunk   │────▶│  Process     │────▶│  Load to     │────▶│   Success    │                │
│  │  from GCS     │     │  Chunk       │     │  BigQuery    │     │              │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘     └──────────────┘                │
│         │                     │                     │                                             │
│         │                     ▼                     ▼                                             │
│         │              ┌──────────────┐     ┌──────────────┐                                 │
│         │              │ JSON Decode  │     │ BigQuery     │                                 │
│         │              │ Error        │     │ Load Error   │                                 │
│         │              └──────┬───────┘     └──────┬───────┘                                 │
│         │                     │                     │                                             │
│         │                     └─────────────────────┘                                             │
│         │                                           │                                             │
│         ▼                                           ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                           DLQ HANDLER                                                         │   │
│  │                                                                                              │   │
│  │  1. Capture Original Event                                                                  │   │
│  │  2. Capture Error Context (type, message, timestamp)                                        │   │
│  │  3. Determine if Retryable                                                                  │   │
│  │  4. Publish to Pub/Sub: pipeline-dlq                                                      │   │
│  │                                                                                              │   │
│  └────────────────────────────────────────────────────────────────────────────────────────────┘   │
│                                          │                                                     │            │
│                                          ▼                                                     │            │
│  ┌──────────────────────────────────────┐       ┌──────────────────────────────────────────────┐  │
│  │   Pub/Sub Topic: pipeline-dlq        │       │   DLQ Processor Job (every 10 min)        │  │
│  │                                      │       │                                          │          │
│  │   Message: {                         │       │   For each message:                       │          │
│  │     original_event,                  │       │   1. Check retry_count                   │          │
│  │     error_message,                   │       │   2. If < max_retries (3):             │          │
│  │     error_type,                      │       │      - Re-process with backoff         │          │
│  │     source: "github-archive",         │       │   3. Else:                              │          │
│  │     retry_count: 0,                  │       │      - Store to GCS permanent failures  │          │
│  │     timestamp                        │       │                                          │          │
│  │   }                                  │       │   Subscription: pipeline-dlq-sub        │          │
│  │                                      │       │   (filter: retry_count < max_retries) │          │
│  └──────────────────────────────────────┘       └──────────────────────────────────────────────┘  │
│                                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Error Categories

### 1. Transient Errors (Retryable)

| Error Type | Example | Retry Strategy |
|------------|---------|----------------|
| `InternalServerError` | BigQuery temporary error | Exponential backoff |
| `ServiceUnavailable` | Service temporarily down | Exponential backoff |
| `GatewayTimeout` | Request timeout | Exponential backoff |
| `Aborted` | Concurrent modification | Immediate retry |
| `ConnectionError` | Network issue | Exponential backoff |

**Retry Configuration:**
```python
@retry_with_exponential_backoff(
    max_attempts=3,
    wait_min=1.0,    # 1 second
    wait_max=10.0,   # 10 seconds
    multiplier=2.0   # Doubles each time: 1s, 2s, 4s, 8s, 16s(max)
)
```

### 2. Permanent Errors (Non-Retryable)

| Error Type | Example | Action |
|------------|---------|--------|
| `ValueError` | Invalid data format | Skip to DLQ for analysis |
| `TypeError` | Type mismatch | Skip to DLQ for analysis |
| `KeyError` | Missing required field | Skip to DLQ for analysis |
| `JSONDecodeError` | Malformed JSON | Skip to DLQ for analysis |

---

## Implementation

### DLQ Handler

**File:** [`src/dlq/handler.py`](../../src/dlq/handler.py)

```python
class DeadLetterQueueHandler:
    """Handle publishing failed events to DLQ."""

    def publish_failure(
        self,
        original_event: Dict[str, Any],
        error: Exception,
        source: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Publish a failure event to the DLQ."""
        # Skip non-retryable errors
        if isinstance(error, (ValueError, TypeError, KeyError)):
            logger.warning(f"Skipping DLQ for error type {type(error).__name__}")
            return None

        # Create DLQ message
        message = DeadLetterMessage.from_event(
            original_event=original_event,
            error=error,
            source=source,
            context=context,
        )

        # Publish to Pub/Sub
        return self.publish(message)
```

### Retry Decorator

**File:** [`src/shared/retry.py`](../../src/shared/retry.py)

```python
@retry_with_exponential_backoff(
    config=DEFAULT_RETRY,
    exception_types=TRANSIENT_ERRORS,
    on_retry=log_retry_attempt
)
def insert_rows_with_retry(
    dataset_id: str,
    table_id: str,
    rows: List[Dict]
) -> List[Dict]:
    """Insert rows with automatic retry on transient errors."""
    return client.insert_rows_json(table_ref, rows)
```

### Processing with DLQ

```python
def process_storage_to_bigquery(
    storage_backend,
    blob_name: str,
    bigquery_client,
    dlq_handler: DeadLetterQueueHandler,
):
    """Process data with DLQ error handling."""

    try:
        for chunk_df in processor.read_jsonl_chunks(storage_backend, blob_name):
            processed_df = processor.process_chunk(chunk_df)

            try:
                bigquery_client.load_dataframe(
                    dataset_id="github_dataset",
                    table_id="events",
                    dataframe=processed_df
                )
            except Exception as e:
                # Publish individual failed events to DLQ
                for _, row in chunk_df.iterrows():
                    dlq_handler.publish_failure(
                        original_event=row.to_dict(),
                        error=e,
                        source="github-archive-processor"
                    )

    except Exception as e:
        # Critical failure - publish file-level error
        dlq_handler.publish_failure(
            original_event={"blob_name": blob_name},
            error=e,
            source="github-archive-processor",
            context={"file_level": True}
        )
```

---

## DLQ Message Structure

```json
{
  "original_event": {
    "id": "1234567890",
    "type": "PushEvent",
    "actor": {"id": 12345, "login": "username"},
    "repo": {"id": 67890, "name": "user/repo"},
    "payload": {...},
    "created_at": "2025-01-15T14:30:00Z"
  },
  "error_message": "BigQuery quota exceeded",
  "error_type": "QuotaExceeded",
  "source": "github-archive-processor",
  "timestamp": "2025-01-15T14:35:00Z",
  "retry_count": 0,
  "max_retries": 3,
  "context": {
    "chunk_number": 5,
    "file_name": "2025-01-15-14.json.gz"
  }
}
```

---

## Monitoring DLQ

### Query DLQ Message Count

```sql
-- Note: This requires exporting Pub/Sub metrics to BigQuery
SELECT
    timestamp,
    source,
    error_type,
    COUNT(*) as failed_count
FROM `project.pipeline_dlpq_messages`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
GROUP BY timestamp, source, error_type
ORDER BY failed_count DESC
```

### Cloud Monitoring Alert

**Alert:** DLQ Backlog > 100 messages

```yaml
condition:
  filter: "resource.type = pubsub_topic AND metric.type = pubsub.googleapis.com/subscription/num_undelivered_messages"
  threshold: 100
  aggregation: {alignment_period: "300s"}
```

---

## Recovery Procedures

### 1. Investigate DLQ Messages

```bash
# View DLQ messages
gcloud pubsub subscriptions pull pipeline-dlq-sub --limit 10
```

### 2. Manually Reprocess

```python
# Read from DLQ and reprocess
from src.dlq.handler import DeadLetterQueueProcessor

processor = DeadLetterQueueProcessor(
    project_id="your-project",
    dlq_subscription_id="pipeline-dlq-sub"
)

processor.start_consuming(
    retry_handler=reprocess_function,
    max_messages=100
)
```

### 3. Permanent Failure Analysis

```bash
# Check permanent failures in GCS
gsutil ls gs://{project}-data-pipeline/dlq/permanent-failures/

# Download and analyze
gsutil cp gs://{project}-data-pipeline/dlq/permanent-failures/*.json .
```

---

## Best Practices

1. **Always validate before processing**
   - Check required fields exist
   - Validate data types
   - Check for null/empty values

2. **Log everything**
   - Original event data (for debugging)
   - Error context (type, message, stack trace)
   - Processing metadata (file, chunk, row)

3. **Set appropriate timeouts**
   - BigQuery load: 30-60 seconds
   - Storage read: 10-20 seconds
   - HTTP requests: 5-10 seconds

4. **Monitor DLQ size**
   - Alert if backlog grows
   - Investigate error patterns
   - Fix root causes

5. **Regular cleanup**
   - Delete processed DLQ messages
   - Archive permanent failures
   - Review error patterns
