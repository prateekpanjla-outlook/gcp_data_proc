# Service Accounts for Phase 1: GitHub Archive Ingestion

# ==============================================================================
# GitHub Archive Downloader Service Account
# ==============================================================================
resource "google_service_account" "github_archive_downloader" {
  account_id   = local.github_archive.service_account_id
  display_name = "${title(var.environment)} GitHub Archive Downloader"
  description  = "Service account for Cloud Run Job that downloads GitHub Archive files using gsutil"
}

# ==============================================================================
# IAM Roles - GitHub Archive Downloader
# ==============================================================================

# Allows reading/writing objects in GCS buckets
resource "google_project_iam_member" "github_archive_downloader_storage" {
  project = var.project_id
  role    = "roles/storage.objectUser"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}

# Allows writing logs
resource "google_project_iam_member" "github_archive_downloader_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.github_archive_downloader.email}"
}

# ==============================================================================
# Cloud Scheduler Service Account
# ==============================================================================
resource "google_service_account" "scheduler" {
  account_id   = "${local.env_prefix}-scheduler"
  display_name = "${title(var.environment)} Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}

# Note: The scheduler service account only needs roles/run.invoker on the
# specific Cloud Run Jobs it invokes (granted in scheduler.tf).
# No project-level Cloud Scheduler roles are needed on the SA itself.
