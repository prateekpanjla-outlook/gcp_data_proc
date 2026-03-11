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

  # backend "gcs" {
  #   bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
  #   prefix         = "terraform/state/phase2-first-time"
  # }
  # Using local backend for development
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

resource "google_project_service" "cloudbuild" {
  project            = var.project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

# =============================================================================
# IAM: Service Agents (depends on APIs enabled above)
# =============================================================================
# Cloud Storage service agent to publish events (for Eventarc)
resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"

  depends_on = [
    google_project_service.storage,
    google_project_service.eventarc,
  ]
}

# Eventarc service agent
resource "google_project_iam_member" "eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"

  depends_on = [
    google_project_service.eventarc,
  ]
}

# =============================================================================
# Artifact Registry Repository
# =============================================================================
resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "data-pipeline"
  description   = "Docker repository for GitHub Archive processing images"
  format        = "DOCKER"

  docker_config {
    immutable_tags = false
  }

  labels = local.common_labels
}

# =============================================================================
# Cloud Build Trigger for Phase 2 Processor
# =============================================================================
# This trigger allows Cloud Build to build and deploy the processor service
# The trigger is manual by default but can be connected to GitHub for automation
resource "google_cloudbuild_trigger" "phase2_processor" {
  name        = "${var.environment}-phase2-processor"
  description = "Build and deploy Phase 2 GitHub Archive processor"
  location    = var.region

  # Manual trigger - can be invoked via gcloud builds submit or connected to GitHub
  # To connect to GitHub, add github {} block with owner, name, and push/pull_request config

  # Build configuration inline (alternative: use filename to reference cloudbuild.yaml)
  build {
    # Step 1: Build the Docker image
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "build",
        "-t",
        "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor:$SHORT_SHA",
        "-t",
        "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor:latest",
        "-f",
        "Dockerfile.processor",
        "."
      ]
    }

    # Step 2: Push images to Artifact Registry
    step {
      name = "gcr.io/cloud-builders/docker"
      args = [
        "push",
        "--all-tags",
        "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor"
      ]
    }

    # Step 3: Deploy to Cloud Run
    step {
      name = "gcr.io/cloud-builders/gcloud"
      entrypoint = "bash"
      args = [
        "-c",
        <<-EOT
          gcloud run deploy ${var.environment}-data-pipeline-processor \
            --image ${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor:$SHORT_SHA \
            --platform managed \
            --region ${var.region} \
            --memory 4Gi \
            --cpu 2 \
            --timeout 3600 \
            --max-instances 5 \
            --concurrency 10 \
            --no-allow-unauthenticated \
            --service-account ${var.environment}-data-pipeline-processor@${var.project_id}.iam.gserviceaccount.com \
            --set-env-vars PROJECT_ID=${var.project_id},LANDING_BUCKET=${var.project_id}-${var.environment}-data-pipeline-landing,STAGING_BUCKET=${var.project_id}-${var.environment}-data-pipeline-staging
        EOT
      ]
    }

    # Images to push to Artifact Registry
    images = [
      "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor:$SHORT_SHA",
      "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/processor:latest"
    ]

    # Build options
    options {
      logging = "CLOUD_LOGGING_ONLY"
    }
  }

  # Use the dedicated Cloud Build service account
  service_account = google_service_account.cloudbuild_sa.id

  # Substitutions for the build
  substitutions = {
    _REGION = var.region
  }

  # Tags for annotation (Cloud Build triggers use tags, not labels)
  tags = [
    "environment:${var.environment}",
    "phase:processing",
    "managed-by:terraform"
  ]

  depends_on = [
    google_project_service.cloudbuild,
    google_artifact_registry_repository.docker_repo,
  ]
}

# =============================================================================
# Cloud Build Service Account
# =============================================================================
# Dedicated service account for Cloud Build operations
resource "google_service_account" "cloudbuild_sa" {
  account_id   = "${var.environment}-cloud-build"
  display_name = "${var.environment} Cloud Build"
  description  = "Service account for Cloud Build to deploy Phase 2 and Phase 3 services"
  project      = var.project_id
}

# Grant Cloud Build roles to the service account
resource "google_project_iam_member" "cloudbuild_builder" {
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_artifactregistry_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

resource "google_project_iam_member" "cloudbuild_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

# Cloud Functions developer (for Phase 3)
resource "google_project_iam_member" "cloudbuild_functions_developer" {
  project = var.project_id
  role    = "roles/cloudfunctions.developer"
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}

# =============================================================================
# IAM: Cloud Build SA can act as runtime service accounts
# =============================================================================
# This allows Cloud Build to deploy services using the runtime service accounts
# Note: The processor SA is created in Layer 01_static, so this creates a dependency
# For first-time setup, apply Layer 01 first, then re-apply Layer 02 to add this binding
resource "google_service_account_iam_member" "cloudbuild_actas_processor" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${var.environment}-data-pipeline-processor@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}
