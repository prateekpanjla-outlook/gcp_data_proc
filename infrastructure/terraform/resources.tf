# Main infrastructure resources for the data pipeline

# ==============================================================================
# Cloud Storage Buckets
# ==============================================================================

# GitHub Archive Landing Bucket (Phase 1: Ingestion)
# Raw GitHub Archive files are downloaded here
resource "google_storage_bucket" "github_archive_landing" {
  name          = local.github_archive.bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90 # Delete files after 90 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    layer       = "landing"
    managed_by  = "terraform"
  }
}

# ==============================================================================
# BigQuery Datasets
# ==============================================================================
resource "google_bigquery_dataset" "github" {
  dataset_id  = "${var.github_dataset_id}_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "GitHub Archive event data"

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }

  default_table_expiration_ms = 7776000000 # 90 days

  delete_contents_on_destroy = var.environment == "dev" ? true : false
}

# ==============================================================================
# Artifact Registry for Container Images
# ==============================================================================
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "${var.environment}-github-archive"
  description   = "Docker repository for GitHub Archive data pipeline"
  format        = "DOCKER"
  mode          = "STANDARD"

  docker_config {
    immutable_tags = false
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }
}
