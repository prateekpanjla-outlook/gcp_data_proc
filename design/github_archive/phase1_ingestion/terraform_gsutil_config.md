# Terraform Configuration: gsutil-based Cloud Run Job

## Cloud Run Job Configuration

```hcl
# Cloud Run Job: GitHub Archive Downloader (gsutil-based)
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = "github-archive-downloader"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # Use google-cloud-sdk slim image (smaller, includes gsutil)
        image = "gcr.io/${var.project_id}/github-archive-downloader:latest"

        env {
          name  = "BUCKET_NAME"
          value = "${var.project_id}-data-pipeline"
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "HOURS_AGO"
          value = "1"  # Download previous hour's file
        }

        # Resource limits (minimal - gsutil streams data)
        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"  # Low memory due to streaming
          }
        }
      }

      # Timeout for download operation
      timeout = "600s"  # 10 minutes (enough for 1-2 GB file)

      # Service account (needs Storage.ObjectCreator)
      service_account_name = google_service_account.hn_fetcher.email
      region                = var.region
    }
  }

  # Max concurrent tasks
  task_count = 1
}

# Service Account for the downloader
resource "google_service_account" "hn_fetcher" {
  account_id   = "sa-hn-fetcher"
  display_name = "Hacker News / GitHub Archive Fetcher"
  description  = "Service account for downloading data from external sources"
}

# IAM: Storage Object Creator
resource "google_project_iam_member" "hn_fetcher_storage" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}

# IAM: PubSub Publisher (for DLQ notifications)
resource "google_project_iam_member" "hn_fetcher_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}

# IAM: Log Writer
resource "google_project_iam_member" "hn_fetcher_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}
```

## Cloud Scheduler Configuration

```hcl
# Cloud Scheduler: Trigger hourly download
resource "google_cloud_scheduler_job" "github_archive_downloader" {
  name             = "github-archive-downloader"
  description      = "Download hourly GitHub Archive file using gsutil"

  # Run at 30 minutes past each hour (giving GitHub Archive time to create the file)
  schedule         = "30 * * * *"
  time_zone        = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/github-archive-downloader:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  # Retry configuration
  retry_config {
    retry_count = 1
    min_backoff = "60s"
  }
}

# IAM: Allow scheduler to invoke Cloud Run Job
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_downloader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
```

## Variables

```hcl
variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}
```

## Outputs

```hcl
output "downloader_job_url" {
  description = "URL of the GitHub Archive downloader job"
  value = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/github-archive-downloader"
}

output "scheduler_job_name" {
  description = "Name of the Cloud Scheduler job"
  value = google_cloud_scheduler_job.github_archive_downloader.name
}
```
