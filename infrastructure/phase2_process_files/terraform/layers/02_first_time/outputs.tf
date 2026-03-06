# Layer 02: First-Time Outputs

output "project_id" {
  description = "Google Cloud Project ID"
  value       = var.project_id
}

output "region" {
  description = "GCP Region"
  value       = var.region
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "artifact_registry_repository" {
  description = "Full name of the Artifact Registry repository"
  value       = google_artifact_registry_repository.docker_repo.id
}

output "docker_repository_name" {
  description = "Name of the Docker repository"
  value       = google_artifact_registry_repository.docker_repo.repository_id
}

output "apis_enabled" {
  description = "List of enabled APIs"
  value = [
    "eventarc.googleapis.com",
    "eventarcpublishing.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com"
  ]
}
