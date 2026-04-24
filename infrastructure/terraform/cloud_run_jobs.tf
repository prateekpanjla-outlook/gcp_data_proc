# Cloud Run Jobs for batch processing
# Jobs are more cost-effective than services for batch workloads

# ==============================================================================
# GitHub Archive Ingestion Job (Phase 1: gsutil-based Downloader)
# ==============================================================================
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = local.github_archive.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # Uses google-cloud-sdk base image with gsutil pre-installed
        image = "gcr.io/google.com/cloud-sdk:slim"

        # Environment variables
        env {
          name  = "BUCKET_NAME"
          value = local.github_archive.bucket_name
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "HOURS_AGO"
          value = "1"
        }

        # Resource limits
        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }
      }

      # Service account
      service_account_name = google_service_account.github_archive_downloader.email

      # Timeout
      timeout_seconds = 1800 # 30 minutes
    }
  }
}
