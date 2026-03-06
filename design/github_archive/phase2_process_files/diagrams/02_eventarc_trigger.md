# Phase 2: Eventarc Trigger Configuration

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E as Eventarc
    participant P as Pub/Sub (Internal)
    participant CR as Cloud Run Service<br>github-archive-processor

    Note over S: File lands in gs://.../raw/"filename".json.gz
    S->>E: finalize event emitted

    Note over E: Eventarc Filter:<br>prefix="github-archive/raw/"<br>suffix=".json.gz"

    E->>P: Publish to Pub/Sub topic
    Note over P: Topic: google.cloud.storage.object.v1.finalized<br>(Google-managed, no cost to you)

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

**Key Point:** The Pub/Sub shown here is **Google's internal infrastructure** - managed automatically by Cloud Storage and Eventarc. You don't create or pay for this Pub/Sub topic.

## Two Eventarc Triggers

**Trigger #1: Main File Processor (raw/ folder)**

```hcl
resource "google_eventarc_trigger" "main_file_processor" {
  name        = "github-archive-main-file-processor"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name
  }

  matching_criteria {
    attribute = "name"
    value     = "github-archive/raw/*.json.gz"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email
}
```

**Trigger #2: Chunk Processor (chunks/ folder)**

```hcl
resource "google_eventarc_trigger" "chunk_processor" {
  name        = "github-archive-chunk-processor"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name
  }

  matching_criteria {
    attribute = "name"
    value     = "github-archive/chunks/*.json.gz"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.chunk_processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email
}
```

**Key Points:**
- Two triggers filter by different path prefixes (raw/ vs chunks/)
- No user-managed Pub/Sub topics required
- Zero Pub/Sub costs
- Simple filename-based metadata encoding
