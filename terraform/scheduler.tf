# Cloud Scheduler Jobs for periodic data fetching

# GitHub Archive Downloader - Hourly
resource "google_cloud_scheduler_job" "github_archive_downloader" {
  name             = "github-archive-downloader"
  description      = "Fetches hourly GitHub Archive files"

  schedule          = "30 * * * *"  # Every hour at 30 minutes past
  time_zone         = "UTC"

  attempt_deadline  = "600s"  # 10 minutes

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
    min_backoff = "10s"
    max_backoff = "600s"
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_github_invoker,
  ]
}

# Hacker News Poller - Every 5 minutes
resource "google_cloud_scheduler_job" "hacker_news_poller" {
  name             = "hacker-news-poller"
  description      = "Polls Hacker News API for new stories"

  schedule          = "*/5 * * * *"  # Every 5 minutes
  time_zone         = "UTC"

  attempt_deadline  = "300s"  # 5 minutes

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/hacker-news-fetcher:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }

    body = base64encode(jsonencode({
      fetch_stories = true,
      fetch_comments = true,
    }))
  }

  retry_config {
    retry_count = 2
    min_backoff = "10s"
    max_backoff = "300s"
  }

  depends_on = [
    google_cloud_run_v2_job_iam_member.scheduler_hn_fetcher_invoker,
  ]
}

# Hacker News User Profile Refresh - Daily
resource "google_cloud_scheduler_job" "hacker_news_user_refresh" {
  name             = "hacker-news-user-refresh"
  description      = "Refreshes Hacker News user profiles"

  schedule          = "0 2 * * *"  # Daily at 2 AM UTC
  time_zone         = "UTC"

  attempt_deadline  = "3600s"  # 1 hour

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/hacker-news-fetcher:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }

    body = base64encode(jsonencode({
      fetch_users = true,
    }))
  }

  retry_config {
    retry_count = 1
    min_backoff = "60s"
  }
}

# DLQ Processor - Every 10 minutes
resource "google_cloud_scheduler_job" "dlq_processor" {
  name             = "dlq-processor"
  description      = "Processes dead letter queue messages"

  schedule          = "*/10 * * * *"  # Every 10 minutes
  time_zone         = "UTC"

  attempt_deadline  = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/dlq-processor:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  retry_config {
    retry_count = 1
    min_backoff = "30s"
  }
}

# BigQuery Partition Cleanup - Weekly
resource "google_cloud_scheduler_job" "partition_cleanup" {
  name             = "partition-cleanup"
  description      = "Cleans up old BigQuery partitions"

  schedule          = "0 3 * * 0"  # Sunday at 3 AM UTC
  time_zone         = "UTC"

  attempt_deadline  = "3600s"

  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/maintenance:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }

    body = base64encode(jsonencode({
      task = "cleanup_partitions",
      retention_days = 400,
    }))
  }

  retry_config {
    retry_count = 1
  }
}
