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
        # Custom image built from src/github_archive/phase1_ingestion/Dockerfile
        # Includes: google-cloud-sdk + coreutils + download.sh script
        # Build with: gcloud builds submit --config=config/cloudbuild-phase1.yaml .
        image = "gcr.io/${var.project_id}/github-archive-downloader:latest"

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

        # Resource limits (gsutil uses streaming)
        # Cloud Run v2 requires min 512Mi when CPU is allocated
        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      # Service account
      service_account = google_service_account.github_archive_downloader.email

      # Timeout (30 minutes - ample for gsutil download)
      timeout = "1800s"
    }
  }

  labels = {
    environment = var.environment
    phase       = "ingestion"
    managed_by  = "terraform"
  }
}
