# Cloud Run Jobs for Phase 1: GitHub Archive Ingestion

# ==============================================================================
# GitHub Archive Ingestion Job (Phase 1: gsutil-based Downloader)
# ==============================================================================
# Downloads GitHub Archive files using gsutil for streaming
# Memory-efficient: ~50MB regardless of file size
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = local.github_archive.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # Uses google-cloud-sdk base image with gsutil pre-installed
        image = "gcr.io/google.com/cloudsdk:slim"

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

        # Resource limits (minimal - gsutil uses streaming)
        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }
      }

      # Service account
      service_account_name = google_service_account.github_archive_downloader.email

      # Timeout (30 minutes - ample for gsutil download)
      timeout_seconds = 1800
    }
  }

  labels = {
    environment = var.environment
    phase       = "ingestion"
    managed_by  = "terraform"
  }
}
