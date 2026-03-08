# Layer 01: Static Resources
# These resources rarely change after initial deployment
# Apply once, re-apply only when BigQuery schema or IAM changes are needed

# =============================================================================
# Locals
# =============================================================================
locals {
  env_prefix = var.environment

  phase3_resources = {
    bq_loader_service_account = "${local.env_prefix}-bq-loader"
    eventarc_invoker          = "${local.env_prefix}-eventarc-invoker-bq"
  }

  common_labels = {
    environment = var.environment
    phase       = "bigquery_loader"
    managed_by  = "terraform"
    layer       = "static"
  }
}

# =============================================================================
# BigQuery Dataset
# =============================================================================
resource "google_bigquery_dataset" "github_archive" {
  dataset_id                  = var.dataset_id
  friendly_name               = "GitHub Archive Events"
  description                 = "Processed GitHub Archive events loaded from Cloud Storage"
  location                    = var.region
  default_table_expiration_ms = var.partition_expiration_days > 0 ? var.partition_expiration_days * 24 * 60 * 60 * 1000 : null

  labels = local.common_labels

  delete_contents_on_destroy = var.environment == "dev"
}

# =============================================================================
# BigQuery Table: github_events
# =============================================================================
resource "google_bigquery_table" "github_events" {
  dataset_id          = google_bigquery_dataset.github_archive.dataset_id
  table_id            = var.table_id
  deletion_protection = false

  description = "GitHub Archive events with flattened structure"

  # Time-based partitioning by created_at
  time_partitioning {
    type          = "DAY"
    field         = "created_at"
    expiration_ms = var.partition_expiration_days > 0 ? var.partition_expiration_days * 24 * 60 * 60 * 1000 : null
  }

  # Clustering for query optimization
  clustering = ["event_type"]

  # Schema from Phase 2 output
  schema = file("${path.module}/schema.json")

  labels = local.common_labels
}

# =============================================================================
# Service Account: BigQuery Loader
# =============================================================================
resource "google_service_account" "bq_loader" {
  account_id   = local.phase3_resources.bq_loader_service_account
  display_name = "${title(var.environment)} BigQuery Loader"
  description  = "Service account for BigQuery loader Cloud Run service"
  project      = var.project_id
}

# =============================================================================
# Service Account: Eventarc Invoker
# =============================================================================
resource "google_service_account" "eventarc_invoker" {
  account_id   = local.phase3_resources.eventarc_invoker
  display_name = "${title(var.environment)} Eventarc Invoker (BQ)"
  description  = "Service account for Eventarc trigger authentication to BigQuery loader"
  project      = var.project_id
}

# =============================================================================
# IAM: BigQuery Permissions
# =============================================================================
# BQ Loader - Data Editor (can write to tables)
resource "google_project_iam_member" "bq_loader_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.bq_loader.email}"
}

# BQ Loader - Job User (can run load jobs)
resource "google_project_iam_member" "bq_loader_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.bq_loader.email}"
}

# =============================================================================
# IAM: Logging and Monitoring
# =============================================================================
resource "google_project_iam_member" "bq_loader_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.bq_loader.email}"
}

resource "google_project_iam_member" "bq_loader_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.bq_loader.email}"
}

resource "google_project_iam_member" "eventarc_invoker_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}

# =============================================================================
# IAM: Eventarc Invoker Permissions
# =============================================================================
resource "google_project_iam_member" "eventarc_invoker_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}
