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

# Cloud Scheduler Service Account
resource "google_service_account" "scheduler" {
  account_id   = "${local.env_prefix}-scheduler"
  display_name = "${title(var.environment)} Cloud Scheduler Service Account"
  description  = "Service account for Cloud Scheduler jobs"
}
