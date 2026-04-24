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
    min_backoff_duration = "10s"
  }
}

# IAM binding for scheduler to invoke the gsutil download job
resource "google_cloud_run_v2_job_iam_member" "scheduler_github_download_invoker" {
  name     = "${google_cloud_run_v2_job.github_archive_downloader.name}"
  location = var.region
  project  = var.project_id
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# ==============================================================================
# GitHub Archive Processor - Hourly (Phase 2: ETL Processing)
# ==============================================================================
resource "google_cloud_scheduler_job" "github_archive_downloader" {
  name        = "github-archive-downloader"
  description = "Processes downloaded GitHub Archive files"

  schedule  = "30 * * * *" # Every hour at 30 minutes past
  time_zone = "UTC"

  attempt_deadline = "600s" # 10 minutes

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/github-archive-processor:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }

    body = base64encode(jsonencode({
      overwrite = true
    }))
  }

  retry_config {
    retry_count = 3
    min_backoff_duration = "10s"
    max_backoff_duration = "600s"
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_github_invoker,
  ]
}


# DLQ Processor - Every 10 minutes
resource "google_cloud_scheduler_job" "dlq_processor" {
  name        = "dlq-processor"
  description = "Processes dead letter queue messages"

  schedule  = "*/10 * * * *" # Every 10 minutes
  time_zone = "UTC"

  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/dlq-processor:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 1
    min_backoff_duration = "30s"
  }
}

# BigQuery Partition Cleanup - Weekly
resource "google_cloud_scheduler_job" "partition_cleanup" {
  name        = "partition-cleanup"
  description = "Cleans up old BigQuery partitions"

  schedule  = "0 3 * * 0" # Sunday at 3 AM UTC
  time_zone = "UTC"

  attempt_deadline = "3600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/maintenance:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }

    body = base64encode(jsonencode({
      task           = "cleanup_partitions",
      retention_days = 400,
    }))
  }

  retry_config {
    retry_count = 1
  }
}
