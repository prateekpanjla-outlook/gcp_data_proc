# Layer 02: First-Time Setup
# These resources are only needed during initial project setup
# Apply once when setting up a new project or environment

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }

  backend "gcs" {
    bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
    prefix         = "terraform/state/phase2-first-time"
    skip_bucket_versioning = false
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Data Source
# =============================================================================
data "google_project" "current" {
  project_id = var.project_id
}

# =============================================================================
# Locals
# =============================================================================
locals {
  common_labels = {
    environment = var.environment
    phase       = "processing"
    managed_by  = "terraform"
    layer       = "first-time"
  }
}

# =============================================================================
# API Services
# =============================================================================
# Eventarc requires Pub/Sub publisher role on Storage service agent
resource "google_project_service" "eventarc" {
  project            = var.project_id
  service            = "eventarc.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "eventarc_publishing" {
  project            = var.project_id
  service            = "eventarcpublishing.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_run" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "storage" {
  project            = var.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloud_resource_manager" {
  project            = var.project_id
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  project            = var.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "logging" {
  project            = var.project_id
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "monitoring" {
  project            = var.project_id
  service            = "monitoring.googleapis.com"
  disable_on_destroy = false
}

# =============================================================================
# Artifact Registry Repository
# =============================================================================
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "github-archive"
  description   = "Docker repository for GitHub Archive processing images"
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }

  labels = local.common_labels
}
