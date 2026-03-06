# Layer 03: Operational Outputs

output "processor_service_url" {
  description = "URL of the processor Cloud Run Service"
  value       = "https://${google_cloud_run_v2_service.processor.name}-${var.project_id}.${var.region}.run.app"
}

output "processor_service_name" {
  description = "Name of the processor Cloud Run Service"
  value       = google_cloud_run_v2_service.processor.name
}

output "main_file_trigger_name" {
  description = "Name of the main file Eventarc trigger"
  value       = google_eventarc_trigger.main_file_processor.name
}

output "chunk_trigger_name" {
  description = "Name of the chunk Eventarc trigger"
  value       = google_eventarc_trigger.chunk_processor.name
}

output "image_deployed" {
  description = "Docker image tag deployed"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/github-archive/processor:${var.image_tag}"
}

output "deployment_timestamp" {
  description = "Timestamp when this configuration was applied"
  value       = timestamp()
}
