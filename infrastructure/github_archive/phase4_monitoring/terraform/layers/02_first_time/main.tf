# Phase 4 Monitoring — First Time Setup
# Enable APIs, grant dashboard SA read access to BQ

resource "google_project_service" "logging" {
  project = var.project_id
  service = "logging.googleapis.com"
}

# Dashboard SA needs to run queries and read the pipeline_logs dataset
resource "google_project_iam_member" "dashboard_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.dashboard_sa_email}"
}

resource "google_bigquery_dataset_iam_member" "dashboard_data_viewer" {
  project    = var.project_id
  dataset_id = var.pipeline_logs_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${var.dashboard_sa_email}"
}
