# Phase 2: Terraform Configuration Design

## Overview

Terraform configuration for Phase 2 processing infrastructure using Google Cloud provider v7.x.

## Required APIs

```hcl
resource "google_project_service" "phase2_apis" {
  project = var.project_id
  services = [
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "firestore.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com"
  ]
}
```

## Terraform Files Structure

```
infrastructure/phase_process_files/terraform/
├── main.tf              # Provider and main resources
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── locals.tf            # Local values
├── eventarc.tf          # Eventarc trigger
├── cloud_run_service.tf # Processor service
├── cloud_run_job_splitter.tf  # File splitter job
├── storage.tf           # Staging/DLQ buckets
├── pubsub.tf            # DLQ topic
├── firestore.tf         # Chunk tracking database
└── service_accounts.tf  # IAM configuration
```

## Key Resources

### 1. Service Accounts

```hcl
# locals.tf
locals {
  env_prefix = var.environment  # "dev" or "prod"

  phase2_resources = {
    processor_service_account = "${local.env_prefix}-github-archive-processor"
    splitter_service_account   = "${local.env_prefix}-file-splitter"
    eventarc_invoker           = "${local.env_prefix}-eventarc-invoker"
  }
}

# service_accounts.tf
resource "google_service_account" "processor" {
  account_id   = local.phase2_resources.processor_service_account
  display_name = "${title(var.environment)} GitHub Archive Processor"
  description  = "Service account for Cloud Run Service that processes GitHub Archive files"
}

resource "google_service_account" "splitter" {
  account_id   = local.phase2_resources.splitter_service_account
  display_name = "${title(var.environment)} File Splitter"
  description  = "Service account for Cloud Run Job that splits large files"
}

resource "google_service_account" "eventarc_invoker" {
  account_id   = local.phase2_resources.eventarc_invoker
  display_name = "${title(var.environment)} Eventarc Invoker"
  description  = "Service account for Eventarc trigger authentication"
}
```

### 2. IAM Roles

```hcl
# Processor SA roles
resource "google_project_iam_member" "processor_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"  # Read from landing, write to staging
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"  # Publish chunk events
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"  # Update chunk tracking
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

# Eventarc invoker SA roles
resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}
```

### 3. Storage Buckets

```hcl
# storage.tf
resource "google_storage_bucket" "staging" {
  name          = "${var.project_id}-${var.environment}-github-archive-staging"
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment == "dev"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30  # Keep processed files for 30 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    phase       = "processing"
    purpose     = "staging"
    managed_by  = "terraform"
  }
}

resource "google_storage_bucket" "dlq" {
  name          = "${var.project_id}-${var.environment}-github-archive-dlq"
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment == "dev"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90  # Keep DLQ files for 90 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    phase       = "processing"
    purpose     = "dlq"
    managed_by  = "terraform"
  }
}
```

### 4. Eventarc Trigger

```hcl
# eventarc.tf
resource "google_eventarc_trigger" "github_archive_processor" {
  name        = "${local.env_prefix}-github-archive-processor"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name  # From Phase 1
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

  depends_on = [
    google_project_service.phase2_apis
  ]
}
```

### 5. Cloud Run Service (Processor)

```hcl
# cloud_run_service.tf
resource "google_cloud_run_v2_service" "processor" {
  name     = "${local.env_prefix}-github-archive-processor"
  location = var.region
  project  = var.project_id

  template {
    metadata {
      annotations = {
        # Autoscaling
        "autoscaling.knative.dev/maxScale"       = "100"
        "autoscaling.knative.dev/minScale"       = "0"
        "autoscaling.knative.dev/target"         = "10"
        "autoscaling.knative.dev/scaleDownDelay" = "30s"

        # Performance
        "run.googleapis.com/cpu-throttling"       = "false"
        "run.googleapis.com/execution-environment" = "gen2"
      }
    }

    template {
      containers {
        image = "us-central1-docker.pkg.dev/${var.project_id}/github-archive/processor:latest"

        # Environment variables
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "LANDING_BUCKET"
          value = var.landing_bucket_name
        }
        env {
          name  = "STAGING_BUCKET"
          value = google_storage_bucket.staging.name
        }
        env {
          name  = "DLQ_BUCKET"
          value = google_storage_bucket.dlq.name
        }
        env {
          name  = "FIRESTORE_COLLECTION"
          value = "file_chunks"
        }
        env {
          name  = "CHUNK_PUBSUB_TOPIC"
          value = google_pubsub_topic.chunk_events.name
        }
        env {
          name  = "FILE_SIZE_THRESHOLD_MB"
          value = "500"
        }

        resources {
          limits = {
            cpu    = "4"
            memory = "8Gi"
          }
          requests = {
            cpu    = "100m"
            memory = "512Mi"
          }
        }
      }

      container_concurrency = 10
      timeout_seconds      = 3600  # 1 hour

      service_account = google_service_account.processor.email
    }
  }

  labels = {
    environment = var.environment
    phase       = "processing"
    managed_by  = "terraform"
  }

  depends_on = [
    google_project_service.phase2_apis
  ]
}
```

### 6. Cloud Run Job (File Splitter)

```hcl
# cloud_run_job_splitter.tf
resource "google_cloud_run_v2_job" "file_splitter" {
  name     = "${local.env_prefix}-file-splitter"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "us-central1-docker.pkg.dev/${var.project_id}/github-archive/file-splitter:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "LANDING_BUCKET"
          value = var.landing_bucket_name
        }
        env {
          name  = "CHUNK_SIZE_LINES"
          value = "10000"
        }

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
        }
      }

      timeout = "3600s"  # 1 hour

      service_account = google_service_account.splitter.email
    }
  }

  depends_on = [
    google_project_service.phase2_apis
  ]
}
```

### 7. Pub/Sub Topic

```hcl
# pubsub.tf
resource "google_pubsub_topic" "chunk_events" {
  name = "${local.env_prefix}-github-archive-chunks"

  labels = {
    environment = var.environment
    phase       = "processing"
    managed_by  = "terraform"
  }
}

resource "google_pubsub_subscription" "chunk_processor" {
  name  = "${local.env_prefix}-chunk-processor"
  topic = google_pubsub_topic.chunk_events.name

  ack_deadline_seconds = 600  # 10 minutes

  # Push to Cloud Run Service
  push_config {
    push_endpoint = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/services/${google_cloud_run_v2_service.processor.name}"

    attributes = {
      "x-goog-version" = "v1"
    }

    oidc_token {
      service_account_email = google_service_account.splitter.email
    }
  }

  # Dead letter policy
  dead_letter_policy {
    dead_letter_topic = google_pubsub_topic.dlq.id
    max_delivery_attempts = 3
  }

  depends_on = [
    google_project_service.phase2_apis
  ]
}

resource "google_pubsub_topic" "dlq" {
  name = "${local.env_prefix}-github-archive-dlq"

  labels = {
    environment = var.environment
    phase       = "processing"
    purpose     = "dlq"
  }
}
```

### 8. Firestore Database

```hcl
# firestore.tf
resource "google_firestore_database" "chunk_tracking" {
  name                         = "(default)"
  location_id                  = var.region
  type                         = "FIRESTORE_NATIVE"
  concurrency_mode             = "OPTIMISTIC"
  delete_protection_state      = var.environment == "prod" ? "ENABLED" : "DISABLED"

  depends_on = [
    google_project_service.phase2_apis["firestore.googleapis.com"]
  ]
}
```

## Variables

```hcl
# variables.tf
variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev/prod)"
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod"
  }
}

variable "landing_bucket_name" {
  description = "Name of the landing bucket from Phase 1"
  type        = string
}
```

## Outputs

```hcl
# outputs.tf
output "processor_service_url" {
  description = "URL of the Cloud Run Service"
  value = "https://${google_cloud_run_v2_service.processor.name}-${var.project_id}.${var.region}.run.app"
}

output "eventarc_trigger_name" {
  description = "Name of the Eventarc trigger"
  value = google_eventarc_trigger.github_archive_processor.name
}

output "staging_bucket_name" {
  description = "Name of the staging bucket"
  value = google_storage_bucket.staging.name
}

output "dlq_bucket_name" {
  description = "Name of the DLQ bucket"
  value = google_storage_bucket.dlq.name
}

output "chunk_topic_name" {
  description = "Name of the Pub/Sub topic for chunk events"
  value = google_pubsub_topic.chunk_events.name
}
```

## Deployment Order

1. **Layer 1: Foundation**
   - Enable APIs
   - Create service accounts
   - Create IAM bindings
   - Create Firestore database

2. **Layer 2: Storage & Messaging**
   - Create storage buckets (staging, DLQ)
   - Create Pub/Sub topics and subscriptions

3. **Layer 3: Compute**
   - Build and push container images
   - Create Cloud Run Service
   - Create Cloud Run Job (splitter)

4. **Layer 4: Triggers**
   - Create Eventarc trigger

## References

- [Terraform Google Provider v7.x Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Run v2 Service Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service)
- [Cloud Run v2 Job Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job)
- [Eventarc Trigger Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/eventarc_trigger)
