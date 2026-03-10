# =============================================================================
# Cloud Build for GitHub Archive Downloader
# =============================================================================
# This Terraform configuration builds the container image using Cloud Build
# and creates it as part of the infrastructure deployment.
# =============================================================================

# Locals for image references
locals {
  github_archive_downloader_image = "gcr.io/${var.project_id}/github-archive-downloader:latest"
  downloader_source_dir          = "${path.module}/../../../src/github_archive/phase1_ingestion"
  cloudbuild_config              = "${path.module}/../../../config/cloudbuild-phase1.yaml"
}

# =============================================================================
# Option 1: Use null_resource to trigger build during terraform apply
# =============================================================================
# This approach triggers Cloud Build during terraform apply
# =============================================================================

resource "null_resource" "build_github_archive_downloader" {
  # Triggers: Re-build if Dockerfile, script, or cloudbuild config changes
  triggers = {
    dockerfile      = filesha256("${local.downloader_source_dir}/Dockerfile")
    download_script = filesha256("${local.downloader_source_dir}/scripts/download.sh")
    cloudbuild_yaml = filesha256(local.cloudbuild_config)
  }

  # Provisioner that runs gcloud builds submit
  provisioner "local-exec" {
    command = "gcloud builds submit ${local.downloader_source_dir} --config ${local.cloudbuild_config} --project ${var.project_id} --quiet"

    # Only run if the image doesn't exist or triggers changed
    # This check happens in the provisioner itself via gcloud
  }

  # Depends on nothing - can run in parallel with other resources
  # But we add a timeout since builds can take time
  timeouts {
    create = "20m"
  }

  tags = ["infrastructure", "cloudbuild", "github-archive"]
}

# =============================================================================
# Option 2: Cloud Build Trigger (Commented out - for CI/CD)
# =============================================================================
# Uncomment this to create a trigger that auto-builds on code changes
# =============================================================================

# resource "google_cloudbuild_trigger" "github_archive_downloader" {
#   name        = "github-archive-downloader-trigger"
#   description = "Auto-build github-archive-downloader on code changes"
#
#   trigger_template {
#     branch_name = "main"
#     repo_name   = "your-repo-name"  # Replace with actual repo
#     project_id  = var.project_id
#   }
#
#   filename = "config/cloudbuild-phase1.yaml"
#
#   substitutions = {
#     _PROJECT_ID = var.project_id
#   }
# }

# =============================================================================
# Option 3: Create Cloud Build directly (Alternative approach)
# =============================================================================
# This creates the Cloud Build job without using null_resource
# =============================================================================

# resource "google_cloudbuild_build" "github_archive_downloader" {
#   name = "build-github-archive-downloader-${replace(timestamp(), ":", "-")}"
#
#   source {
#     storage_source {
#       bucket = "your-source-bucket"
#       object = "source-archive.zip"
#     }
#   }
#
#   steps {
#     name = "gcr.io/cloud-builders/docker"
#     args = [
#       "build",
#       "-t", local.github_archive_downloader_image,
#       "-f", "Dockerfile",
#       "."
#     ]
#   }
#
#   images = [local.github_archive_downloader_image]
#
#   timeout = "1200s"
#
#   # Only create if image doesn't exist (use with data source check)
#   # depends_on = [null_resource.check_image_exists]
# }

# =============================================================================
# Data Source: Check if image exists (for conditional builds)
# =============================================================================

# data "google_artifact_registry_repository" "docker_repo" {
#   location = "us-central1"
#   repository_id = "docker"
# }

# Note: Cloud Build returns a build ID that can be used for tracking
# Output the image reference for use in Cloud Run Job
output "github_archive_downloader_image" {
  value       = local.github_archive_downloader_image
  description = "Container image reference for GitHub Archive Downloader Cloud Run Job"
}
