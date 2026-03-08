# Service Accounts with least-privilege access

# GitHub Archive Ingestion Service Account (Phase 1: Download Job)
resource "google_service_account" "github_archive_downloader" {
  account_id   = local.github_archive.service_account_id
  display_name = "${title(var.environment)} GitHub Archive Downloader"
  description  = "Service account for Cloud Run Job that downloads GitHub Archive files using gsutil"
}

# IAM Roles - GitHub Archive Downloader
resource "google_project_iam_member" "github_archive_downloader_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}

resource "google_project_iam_member" "github_archive_downloader_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}

# GitHub Archive Processor Service Account
resource "google_service_account" "github_processor" {
  account_id   = "sa-github-processor"
  display_name = "GitHub Archive Processor Service Account"
  description  = "Service account for GitHub Archive data processing job"
}

# Hacker News Fetcher Service Account
resource "google_service_account" "hn_fetcher" {
  account_id   = "sa-hn-fetcher"
  display_name = "Hacker News Fetcher Service Account"
  description  = "Service account for fetching Hacker News data"
}

# Hacker News Processor Service Account
resource "google_service_account" "hn_processor" {
  account_id   = "sa-hn-processor"
  display_name = "Hacker News Processor Service Account"
  description  = "Service account for processing Hacker News data"
}

# DLQ Handler Service Account
resource "google_service_account" "dlq_handler" {
  account_id   = "sa-dlq-handler"
  display_name = "Dead Letter Queue Handler Service Account"
  description  = "Service account for processing dead letter queue messages"
}

# Cloud Scheduler Service Account
resource "google_service_account" "scheduler" {
  account_id   = "${local.env_prefix}-scheduler"
  display_name = "${title(var.environment)} Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}

# ==============================================================================
# IAM Roles - GitHub Archive Processor
# ==============================================================================

resource "google_project_iam_member" "github_processor_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.github_processor.email}"
}

# Grant read access to the landing bucket to read source files.
resource "google_storage_bucket_iam_member" "github_processor_landing_viewer" {
  bucket = var.github_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.github_processor.email}"
}

# Grant write access to the staging bucket to save processed files.
# Note: This assumes the staging bucket name follows the project's naming convention.
resource "google_storage_bucket_iam_member" "github_processor_staging_creator" {
  bucket = "${var.project_id}-${var.environment}-github-archive-staging"
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.github_processor.email}"
}

# Grant read access to the staging bucket. This is required for the service to
# check if a file already exists before attempting to write it, which prevents the 403 error.
resource "google_storage_bucket_iam_member" "github_processor_staging_viewer" {
  bucket = "${var.project_id}-${var.environment}-github-archive-staging"
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.github_processor.email}"
}

resource "google_project_iam_member" "github_processor_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.github_processor.email}"
}

resource "google_project_iam_member" "github_processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.github_processor.email}"
}

resource "google_project_iam_member" "github_processor_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.github_processor.email}"
}

# ==============================================================================
# IAM Roles - Hacker News Fetcher
# ==============================================================================

resource "google_project_iam_member" "hn_fetcher_storage_editor" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}

resource "google_project_iam_member" "hn_fetcher_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}

resource "google_project_iam_member" "hn_fetcher_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.hn_fetcher.email}"
}

# ==============================================================================
# IAM Roles - Hacker News Processor
# ==============================================================================

resource "google_project_iam_member" "hn_processor_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.hn_processor.email}"
}

resource "google_project_iam_member" "hn_processor_storage_viewer" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.hn_processor.email}"
}

resource "google_project_iam_member" "hn_processor_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.hn_processor.email}"
}

resource "google_project_iam_member" "hn_processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.hn_processor.email}"
}

resource "google_project_iam_member" "hn_processor_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.hn_processor.email}"
}

# ==============================================================================
# IAM Roles - DLQ Handler
# ==============================================================================

resource "google_project_iam_member" "dlq_handler_pubsub_subscriber" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.dlq_handler.email}"
}

resource "google_project_iam_member" "dlq_handler_storage_editor" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  member  = "serviceAccount:${google_service_account.dlq_handler.email}"
}

resource "google_project_iam_member" "dlq_handler_bigquery_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.dlq_handler.email}"
}

resource "google_project_iam_member" "dlq_handler_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.dlq_handler.email}"
}

# ==============================================================================
# IAM Roles - Cloud Scheduler
# ==============================================================================
# Note: The scheduler service account only needs roles/run.invoker on the
# specific Cloud Run Jobs it invokes (granted per-job below).
# No project-level Cloud Scheduler roles are needed on the SA itself.

resource "google_cloud_run_v2_job_iam_member" "scheduler_github_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.github_archive_processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_hn_fetcher_invoker" {
  project  = var.project_id
  location = var.region
  job_name = google_cloud_run_v2_job.hacker_news_fetcher.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}
