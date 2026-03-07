# Phase 3 Terraform Infrastructure

## Overview

Terraform configuration for Phase 3 BigQuery loader infrastructure.

## Resource Diagram

```
Terraform Configuration
│
├── BigQuery Resources
│   ├── google_bigquery_dataset.github_archive
│   └── google_bigquery_table.github_events
│       ├── time_partitioning (DAY, created_at)
│       └── clustering (event_type)
│
├── Service Account
│   └── google_service_account.bq_loader
│       ├── roles/bigquery.dataEditor
│       ├── roles/bigquery.jobUser
│       └── roles/storage.objectViewer (staging bucket)
│
├── Cloud Run Resources
│   ├── google_cloud_run_v2_service.bq_loader
│   │   ├── Container image (bq-loader)
│   │   ├── Environment variables
│   │   └── IAM bindings
│   └── google_cloud_run_service_iam_binding.invoker
│       ├── Eventarc invoker SA → run.invoker
│
├── Eventarc Resources
│   ├── google_eventarc_trigger.bq_loader
│   │   ├── Event: object.v1.finalized
│   │   ├── Filter: processed/*.ndjson.gz
│   │   └── Destination: bq-loader service
│   └── pubsub_subscription (managed by Eventarc)
│       └── ack_deadline: 600s (post-deployment)
│
└── IAM Resources
    ├── google_project_iam_member.bigquery_user
    ├── google_storage_bucket_iam_member.bq_loader_viewer
    └── google_service_account_iam_binding.eventarc_invoker
```

## Terraform Configuration

### File Structure

```
infrastructure/phase3_loadbigquery/terraform/
├── main.tf           # Main resources
├── variables.tf      # Input variables
├── outputs.tf        # Output values
├── providers.tf      # Provider configuration
└── versions.tf       # Terraform version constraints
```

### Variables

```hcl
variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment (dev, prod)"
  type        = string
  default     = "dev"
}

variable "staging_bucket_name" {
  description = "Name of the staging bucket from Phase 2"
  type        = string
}

variable "dataset_id" {
  description = "BigQuery dataset ID"
  type        = string
  default     = "github_archive"
}

variable "table_id" {
  description = "BigQuery table ID"
  type        = string
  default     = "github_events"
}

variable "partition_expiration_days" {
  description = "Partition expiration in days"
  type        = number
  default     = 366
}

variable "loader_image" {
  description = "Container image for bq-loader service"
  type        = string
}
```

### Outputs

```hcl
output "dataset_id" {
  value = google_bigquery_dataset.github_archive.dataset_id
}

output "table_id" {
  value = google_bigquery_table.github_events.table_id
}

output "service_url" {
  value = google_cloud_run_v2_service.bq_loader.uri
}

output "eventarc_trigger_id" {
  value = google_eventarc_trigger.bq_loader.id
}
```

## Key Resources

### 1. BigQuery Dataset

```hcl
resource "google_bigquery_dataset" "github_archive" {
  dataset_id                  = var.dataset_id
  friendly_name               = "GitHub Archive Events"
  description                 = "Processed GitHub Archive events loaded from GCS"
  location                    = var.region
  default_table_expiration_ms = var.partition_expiration_days * 24 * 3600000

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    phase       = "bigquery_loader"
  }
}
```

### 2. BigQuery Table (Partitioned & Clustered)

```hcl
resource "google_bigquery_table" "github_events" {
  dataset_id          = google_bigquery_dataset.github_archive.dataset_id
  table_id           = var.table_id
  deletion_protection = false

  # Time-based partitioning
  time_partitioning {
    type         = "DAY"
    field        = "created_at"
    expiration_ms = var.partition_expiration_days * 24 * 3600000
  }

  # Clustering for query optimization
  clustering = ["event_type"]

  # Schema will be detected from first load
  # Use autodetect initially, then lock schema

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}
```

### 3. Service Account

```hcl
resource "google_service_account" "bq_loader" {
  account_id   = "${var.environment}-bq-loader"
  display_name  = "${title(var.environment)} BigQuery Loader"
  description   = "Service account for BigQuery loader Cloud Run service"
}
```

### 4. Cloud Run Service

```hcl
resource "google_cloud_run_v2_service" "bq_loader" {
  name     = "${var.environment}-bq-loader"
  location = var.region
  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
    timeout_seconds = 600  # 10 minutes
    containers {
      image = var.loader_image
      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DATASET_ID"
        value = google_bigquery_dataset.github_archive.dataset_id
      }
      env {
        name  = "TABLE_ID"
        value = var.table_id
      }
      env {
        name  = "STAGING_BUCKET"
        value = var.staging_bucket_name
      }
      env {
        name  = "PARTITION_EXPIRATION_DAYS"
        value = var.partition_expiration_days
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "2Gi"
        }
      }
    }
  }
}
```

### 5. Eventarc Trigger

```hcl
resource "google_eventarc_trigger" "bq_loader" {
  name            = "${var.environment}-bq-loader-trigger"
  location        = var.region
  event_filters {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  event_filters {
    attribute = "bucket"
    value     = "*-github-archive-staging"
  }
  event_filters {
    attribute = "prefix"
    value     = "processed/"
  }
  matching_criteria {
    {
      attribute = "filename_extension"
      value     = ".ndjson.gz"
    }
  }

  destination {
    cloud_run_service = {
      service = google_cloud_run_v2_service.bq_loader.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email
}
```

### 6. IAM Bindings

```hcl
# BigQuery permissions
resource "google_bigquery_dataset_iam_member" "bq_loader_editor" {
  dataset_id   = google_bigquery_dataset.github_archive.dataset_id
  role         = "roles/bigquery.dataEditor"
  member       = "serviceAccount:${google_service_account.bq_loader.email}"
}

# Storage permissions (read staging, delete after load)
resource "google_storage_bucket_iam_member" "bq_loader_staging" {
  bucket = var.staging_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.bq_loader.email}"
}

# Eventarc invoker permissions
resource "google_cloud_run_service_iam_binding" "eventarc_invoker" {
  location = google_cloud_run_v2_service.bq_loader.location
  service  = google_cloud_run_v2_service.bq_loader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}
```

### 7. Post-Deployment: Ack Deadline Update

```hcl
# Local-exec to update Pub/Sub ack deadline
resource "null_resource" "update_eventarc_ack_deadline" {
  depends_on = [google_eventarc_trigger.bq_loader]

  provisioner "local-exec" {
    command = <<-EOT
      SUBSCRIPTION_ID=$(gcloud eventarc triggers describe "${google_eventarc_trigger.bq_loader.name}" \
        --location ${var.region} \
        --project ${var.project_id} \
        --format json | jq -r '.transport.pubsub.subscription')
      gcloud pubsub subscriptions update "$SUBSCRIPTION_ID" --ack-deadline=600
    EOT
  }
}
```

## Deployment Commands

```bash
# Initialize Terraform
cd infrastructure/phase3_loadbigquery/terraform
terraform init

# Plan deployment
terraform plan \
  -var="project_id=PROJECT_ID" \
  -var="region=us-central1" \
  -var="environment=dev" \
  -var="staging_bucket_name=PROJECT_ID-dev-github-archive-staging" \
  -var="loader_image=us-central1-docker.pkg.dev/PROJECT_ID/bq-loader:latest"

# Apply
terraform apply \
  -var="project_id=PROJECT_ID" \
  -var="region=us-central1" \
  -var="environment=dev" \
  -var="staging_bucket_name=PROJECT_ID-dev-github-archive-staging" \
  -var="loader_image=us-central1-docker.pkg.dev/PROJECT_ID/bq-loader:latest"

# Destroy (if needed)
terraform destroy -var="..."
```

## State Management

- **Terraform State:** Store in GCS backend
- **Locking:** Terraform state locking for concurrent operations
- **Separate State:** Phase 3 has separate state file from Phase 2

## Cost Considerations

| Resource | Cost Factor | Estimation |
|----------|-------------|------------|
| BigQuery Storage | Partition size × retention | ~$0.02/GB/month |
| BigQuery Query | Scanned data | Free 1TB/month query |
| Cloud Run | Request time + memory | ~$0.40/million requests |
| Cloud Storage | Staging files (temporary) | ~$0.02/GB/month |

## Troubleshooting

**Eventarc not triggering:**
- Check Eventarc trigger status: `gcloud eventarc triggers list`
- Verify Pub/Sub subscription: `gcloud pubsub subscriptions list`
- Check ack deadline: Must be 600s

**BigQuery load failures:**
- Check job status: `bq show --format=json PROJECT_ID:JOB_ID`
- Verify file format: Must be NDJSON (newline-delimited JSON)
- Check schema compatibility

**File not deleted after load:**
- Verify service account has `storage.objects.delete` permission
- Check Cloud Run logs for errors
