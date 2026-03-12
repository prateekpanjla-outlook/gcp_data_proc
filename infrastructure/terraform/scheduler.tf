# Cloud Scheduler Jobs for periodic data fetching

# ==============================================================================
# GitHub Archive Ingestion - Hourly (Phase 1: gsutil-based Downloader)
# ==============================================================================
resource "google_cloud_scheduler_job" "github_archive_download" {
  name        = local.github_archive.scheduler_name
  description = "Downloads hourly GitHub Archive files using gsutil-based Cloud Run Job"

  schedule  = "30 * * * *" # Every hour at 30 minutes past
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${local.github_archive.job_name}:run"

    oidc_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 2
    min_backoff = "10s"
  }
}

# IAM binding for scheduler to invoke the gsutil download job
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_download_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_downloader.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
