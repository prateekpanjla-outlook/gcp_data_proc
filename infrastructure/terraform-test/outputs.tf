# Outputs for the deployed infrastructure

output "project_id" {
  description = "Google Cloud Project ID"
  value       = var.project_id
}

output "region" {
  description = "Google Cloud Region"
  value       = var.region
}

# Storage Outputs
output "github_bucket_name" {
  description = "GCS bucket for GitHub Archive data"
  value       = google_storage_bucket.github_data.name
}


# BigQuery Outputs
output "github_dataset_id" {
  description = "BigQuery dataset for GitHub events"
  value       = google_bigquery_dataset.github.dataset_id
}


# Cloud Run Outputs
output "github_service_url" {
  description = "GitHub processor service URL"
  value       = google_cloud_run_v2_service.github_processor.uri
}


# Service Account Outputs
output "github_processor_service_account_email" {
  description = "Email of the GitHub processor service account"
  value       = google_service_account.github_processor.email
}

# Eventarc Outputs
output "github_eventarc_trigger_id" {
  description = "Eventarc trigger ID for GitHub events"
  value       = try(google_eventarc_trigger.github_storage[0].id, "Eventarc not enabled")
}

