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
output "github_landing_bucket_name" {
  description = "GCS bucket for GitHub Archive landing data"
  value       = google_storage_bucket.github_archive_landing.name
}

# BigQuery Outputs
output "github_dataset_id" {
  description = "BigQuery dataset for GitHub events"
  value       = google_bigquery_dataset.github.dataset_id
}

# Artifact Registry
output "artifact_registry_repository" {
  description = "Artifact Registry repository name"
  value       = google_artifact_registry_repository.docker.repository_id
}
