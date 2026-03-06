# Phase 2: Terraform Configuration Design

## Overview

Terraform configuration for Phase 2 processing infrastructure using Google Cloud provider v7.x.

**Key Change:** Uses **direct events only** - no Pub/Sub topics required, eliminating Pub/Sub costs.

## Required APIs

```hcl
resource "google_project_service" "phase2_apis" {
  project = var.project_id
  services = [
    "eventarc.googleapis.com",
    "eventarcpublishing.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com"
  ]
}
```

## Terraform Files Structure

```
infrastructure/phase2_process_files/terraform/
├── main.tf              # Provider and main resources
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── locals.tf            # Local values
├── eventarc.tf          # Eventarc triggers (raw/ and chunks/)
├── cloud_run_service.tf # Processor and chunk processor services
├── cloud_run_job_splitter.tf  # File splitter job
├── storage.tf           # Staging bucket
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
    chunk_processor_service_account = "${local.env_prefix}-github-archive-chunk-processor"
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

resource "google_service_account" "chunk_processor" {
  account_id   = local.phase2_resources.chunk_processor_service_account
  display_name = "${title(var.environment)} GitHub Archive Chunk Processor"
  description  = "Service account for Cloud Run Service that processes chunk files"
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

resource "google_project_iam_member" "processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

# Chunk Processor SA roles
resource "google_project_iam_member" "chunk_processor_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"  # Read from chunks/, write to staging
  member  = "serviceAccount:${google_service_account.chunk_processor.email}"
}

resource "google_project_iam_member" "chunk_processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.chunk_processor.email}"
}

# Splitter SA roles
resource "google_project_iam_member" "splitter_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"  # Read from raw/, write to chunks/
  member  = "serviceAccount:${google_service_account.splitter.email}"
}

# Eventarc invoker SA roles
resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker_processor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}

resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker_chunk_processor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.chunk_processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}

# Required: Allow Cloud Storage service agent to publish events
resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# Required: Eventarc service agent
resource "google_project_iam_member" "eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
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
```

### 4. Eventarc Triggers

```hcl
# eventarc.tf
# Trigger #1: Main file processor (raw/ folder)
resource "google_eventarc_trigger" "main_file_processor" {
  name        = "${local.env_prefix}-github-archive-main-file-processor"
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

  depends_on = [
    google_project_service.phase2_apis,
    google_project_iam_member.storage_pubsub_publisher,
    google_project_iam_member.eventarc_event_receiver
  ]
}

# Trigger #2: Chunk processor (chunks/ folder)
resource "google_eventarc_trigger" "chunk_processor" {
  name        = "${local.env_prefix}-github-archive-chunk-processor"
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

  depends_on = [
    google_project_service.phase2_apis,
    google_project_iam_member.storage_pubsub_publisher,
    google_project_iam_member.eventarc_event_receiver
  ]
}
```

### 5. Cloud Run Service (Main Processor)

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

### 6. Cloud Run Service (Chunk Processor)

```hcl
# cloud_run_service.tf
resource "google_cloud_run_v2_service" "chunk_processor" {
  name     = "${local.env_prefix}-github-archive-chunk-processor"
  location = var.region
  project  = var.project_id

  template {
    metadata {
      annotations = {
        # Autoscaling - can scale higher for parallel chunk processing
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
        image = "us-central1-docker.pkg.dev/${var.project_id}/github-archive/chunk-processor:latest"

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

        resources {
          limits = {
            cpu    = "2"
            memory = "4Gi"
          }
          requests = {
            cpu    = "100m"
            memory = "512Mi"
          }
        }
      }

      container_concurrency = 10
      timeout_seconds      = 1800  # 30 minutes

      service_account = google_service_account.chunk_processor.email
    }
  }

  labels = {
    environment = var.environment
    phase       = "processing"
    purpose     = "chunk-processor"
    managed_by  = "terraform"
  }

  depends_on = [
    google_project_service.phase2_apis
  ]
}
```

### 7. Cloud Run Job (File Splitter)

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
  description = "URL of the main Cloud Run Service"
  value = "https://${google_cloud_run_v2_service.processor.name}-${var.project_id}.${var.region}.run.app"
}

output "chunk_processor_service_url" {
  description = "URL of the chunk processor Cloud Run Service"
  value = "https://${google_cloud_run_v2_service.chunk_processor.name}-${var.project_id}.${var.region}.run.app"
}

output "main_file_trigger_name" {
  description = "Name of the main file Eventarc trigger"
  value = google_eventarc_trigger.main_file_processor.name
}

output "chunk_trigger_name" {
  description = "Name of the chunk Eventarc trigger"
  value = google_eventarc_trigger.chunk_processor.name
}

output "staging_bucket_name" {
  description = "Name of the staging bucket"
  value = google_storage_bucket.staging.name
}
```

## Deployment Order

1. **Layer 1: Foundation**
   - Enable APIs
   - Create service accounts
   - Create IAM bindings

2. **Layer 2: Storage**
   - Create storage buckets (staging)

3. **Layer 3: Compute**
   - Build and push container images
   - Create Cloud Run Services (processor and chunk processor)
   - Create Cloud Run Job (splitter)

4. **Layer 4: Triggers**
   - Create Eventarc triggers

## Cost Savings

| Component | Previous (Pub/Sub) | Current (Direct Events) | Savings |
|-----------|------------------|----------------------|---------|
| Pub/Sub Topics | $0.40 per million ops | $0 | ~$5-50/month |
| Pub/Sub Storage | $0.27 per GB | $0 | Variable |
| Firestore | ~$0.18 per GB | $0 | ~$5-20/month |

**Total estimated savings: $10-70/month depending on volume.**

## References

- [Terraform Google Provider v7.x Documentation](https://registry.terraform.io/providers/hashicorp/google/latest/docs)
- [Cloud Run v2 Service Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service)
- [Cloud Run v2 Job Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_job)
- [Eventarc Trigger Resource](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/eventarc_trigger)
