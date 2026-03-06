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

  backend "gcs" {
    bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
    prefix         = "terraform/state/phase2-operational"
    skip_bucket_versioning = false
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# =============================================================================
# Remote State Data Sources
# =============================================================================
data "terraform_remote_state" "static" {
  backend = "gcs"
  config = {
    bucket = var.terraform_state_bucket
    prefix = "terraform/state/phase2-static"
  }
}

data "terraform_remote_state" "first_time" {
  backend = "gcs"
  config = {
    bucket = var.terraform_state_bucket
    prefix = "terraform/state/phase2-first-time"
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

  template {
    metadata {
      annotations = {
        # Autoscaling
        "autoscaling.knative.dev/maxScale"       = tostring(var.max_instances)
        "autoscaling.knative.dev/minScale"       = "0"
        "autoscaling.knative.dev/target"         = "10"
        "autoscaling.knative.dev/scaleDownDelay" = "30s"

        # Performance
        "run.googleapis.com/cpu-throttling"       = "false"
        "run.googleapis.com/execution-environment" = "gen2"

        # Health check
        "run.googleapis.com/health-check-path" = "/health"
        "run.googleapis.com/health-check-per-second" = "1"
      }
    }

    template {
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
        env {
          name  = "PORT"
          value = "8080"
        }

        resources {
          limits = {
            cpu    = tostring(var.processor_cpu)
            memory = "${var.processor_memory}Gi"
          }
          requests = {
            cpu    = "100m"
            memory = "512Mi"
          }
        }
      }

      container_concurrency = 10
      timeout_seconds      = 3600  # 1 hour

      service_account = data.terraform_remote_state.static.outputs.processor_service_account_email
    }
  }

  labels = local.common_labels

  depends_on = [
    data.terraform_remote_state.static,
    data.terraform_remote_state.first_time
  ]
}

# =============================================================================
# Eventarc Trigger #1: Main file processor (raw/ folder)
# =============================================================================
resource "google_eventarc_trigger" "main_file_processor" {
  name        = "${local.env_prefix}-github-archive-main-file-processor"
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

  matching_criteria {
    attribute = "name"
    value     = "github-archive/raw/*.json.gz"
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

  labels = merge(local.common_labels, {purpose = "raw-file-trigger"})
}

# =============================================================================
# Eventarc Trigger #2: Chunk processor (chunks/ folder)
# =============================================================================
resource "google_eventarc_trigger" "chunk_processor" {
  name        = "${local.env_prefix}-github-archive-chunk-processor"
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

  matching_criteria {
    attribute = "name"
    value     = "github-archive/chunks/*.json.gz"
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

  labels = merge(local.common_labels, {purpose = "chunk-trigger"})
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
