# Phase 2: Eventarc Trigger Configuration

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E as Eventarc
    participant P as Pub/Sub
    participant CR as Cloud Run Service<br>github-archive-processor

    Note over S: File lands in gs://.../raw/{file}.json.gz
    S->>E: finalize event emitted

    Note over E: Eventarc Filter:<br>prefix="github-archive/raw/"<br>suffix=".json.gz"

    E->>P: Publish to Pub/Sub topic
    Note over P: Topic: google.cloud.storage.object.v1.finalized

    P->>CR: HTTP POST to Cloud Run Service
    Note over CR: Payload includes:<br>bucket, file path, metadata

    CR->>CR: Extract file info<br>from payload
    CR->>CR: Start processing

    CR->>P: Ack (async processing)

    Note over CR: Processing continues...

    CR->>CR: Validate file
    CR->>CR: Process content
    CR->>CR: Write to staging
    CR->>CR: Mark complete
```

**Eventarc Configuration:**

```hcl
resource "google_eventarc_trigger" "github_archive_processor" {
  name        = "github-archive-processor-trigger"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.landing.name
  }

  matching_criteria {
    attribute = "name"
    value     = "github-archive/raw/*.json.gz"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.github_archive_processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email
}
```

**Key Points:**
- Eventarc filters by bucket prefix and suffix
- Triggers Cloud Run Service (autoscaling)
- Async processing - acknowledges immediately
- Retries on failure (exponential backoff)
