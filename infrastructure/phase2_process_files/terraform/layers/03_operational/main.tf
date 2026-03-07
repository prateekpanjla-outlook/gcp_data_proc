# Layer 03: Operational Resources
# These resources change frequently with code updates
# Apply daily/weekly when deploying new code

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
  #   prefix         = "terraform/state/phase2-operational"
  # }
  # Using local backend for development
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Remote State Data Sources (using local backend)
# =============================================================================
data "terraform_remote_state" "static" {
  backend = "local"
  config = {
    path = "../01_static/terraform.tfstate"
  }
}

data "terraform_remote_state" "first_time" {
  backend = "local"
  config = {
    path = "../02_first_time/terraform.tfstate"
  }
}

# =============================================================================
# Locals
# =============================================================================
locals {
  env_prefix = var.environment

  common_labels = {
    environment = var.environment
    phase       = "processing"
    managed_by  = "terraform"
    layer       = "operational"
  }
}

# =============================================================================
# Cloud Run Service: Processor
# =============================================================================
resource "google_cloud_run_v2_service" "processor" {
  name     = "${local.env_prefix}-github-archive-processor"
  location = var.region
  project  = var.project_id
  deletion_protection = false  # Allow deletion without explicit flag
  ingress  = "INGRESS_TRAFFIC_ALL"  # Allow public ingress

  template {
    # Annotations are set directly at template level in v2
    annotations = {
      # Health check
      "run.googleapis.com/health-check-path" = "/health"
    }

    # Execution environment
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"

    # Timeout (duration format with 's' suffix)
    timeout = "3600s"  # 1 hour

    # Max concurrent requests per instance
    max_instance_request_concurrency = 10

    containers {
      # Image for the processor service
      image = "${var.region}-docker.pkg.dev/${var.project_id}/github-archive/processor:${var.image_tag}"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "LANDING_BUCKET"
        value = data.terraform_remote_state.static.outputs.landing_bucket_name
      }
      env {
        name  = "STAGING_BUCKET"
        value = data.terraform_remote_state.static.outputs.staging_bucket_name
      }
      env {
        name  = "FILE_SIZE_THRESHOLD_MB"
        value = tostring(var.file_size_threshold_mb)
      }
      env {
        name  = "CHUNKSIZE"
        value = tostring(var.chunksize)
      }
      # Note: PORT is automatically set by Cloud Run (reserved env var)

      resources {
        limits = {
          cpu    = tostring(var.processor_cpu)
          memory = "${var.processor_memory}Gi"
        }
        # Note: 'requests' not supported in Cloud Run v2
        cpu_idle = true  # CPU only allocated during requests (default behavior)
      }
    }

    service_account = data.terraform_remote_state.static.outputs.processor_service_account_email
  }

  # Scaling settings at service level
  scaling {
    min_instance_count = 0
    max_instance_count = var.max_instances
  }

  labels = local.common_labels

  depends_on = [
    data.terraform_remote_state.static,
    data.terraform_remote_state.first_time
  ]
}

# =============================================================================
# Eventarc Trigger: Storage events (all files in landing bucket)
# =============================================================================
# NOTE: Cloud Storage Eventarc triggers do NOT support 'name' attribute filtering.
# Only 'type' and 'bucket' attributes are supported for google.cloud.storage.object.v1.finalized.
# Path filtering is done in the Cloud Run service (main.py) instead.
#
# We use a single trigger for the bucket to avoid duplicate Pub/Sub notifications.
resource "google_eventarc_trigger" "storage_events" {
  name        = "${local.env_prefix}-github-archive-storage"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = data.terraform_remote_state.static.outputs.landing_bucket_name
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.processor.name
      region  = var.region
    }
  }

  service_account = data.terraform_remote_state.static.outputs.eventarc_invoker_service_account_email

  depends_on = [
    data.terraform_remote_state.static,
    data.terraform_remote_state.first_time
  ]

  labels = merge(local.common_labels, {purpose = "storage-trigger"})
}

# =============================================================================
# IAM: Eventarc Invoker -> Cloud Run Service
# =============================================================================
resource "google_cloud_run_v2_service_iam_member" "eventarc_invoker_processor" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${data.terraform_remote_state.static.outputs.eventarc_invoker_service_account_email}"
}
