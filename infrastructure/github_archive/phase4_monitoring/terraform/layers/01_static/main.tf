# Phase 4 Monitoring — Static Resources
# BQ dataset for log exports, service account for dashboard

resource "google_bigquery_dataset" "pipeline_logs" {
  dataset_id = "pipeline_logs"
  project    = var.project_id
  location   = var.region

  description = "Cloud Logging exports for GitHub Archive pipeline monitoring"

  # Logs are transient — 90 day retention
  default_table_expiration_ms = 7776000000 # 90 days
}

# Dashboard SA — used by the Cloud Run dashboard service to query BQ.
# NOT used for the log sink (GCP forces an auto-generated writer identity there).
resource "google_service_account" "dashboard" {
  account_id   = "pipeline-dashboard"
  display_name = "Pipeline Dashboard"
  project      = var.project_id
}
