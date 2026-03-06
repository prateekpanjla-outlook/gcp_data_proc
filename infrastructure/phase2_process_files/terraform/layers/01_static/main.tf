# Layer 01: Static Resources
# These resources rarely change after initial deployment
# Apply once, re-apply only when IAM/bucket changes are needed

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
    prefix         = "terraform/state/phase2-static"
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
  env_prefix = var.environment

  phase2_resources = {
    processor_service_account = "${local.env_prefix}-github-archive-processor"
    splitter_service_account   = "${local.env_prefix}-file-splitter"
    eventarc_invoker           = "${local.env_prefix}-eventarc-invoker"
    staging_bucket             = "${var.project_id}-${local.env_prefix}-github-archive-staging"
  }

  common_labels = {
    environment = var.environment
    phase       = "processing"
    managed_by  = "terraform"
    layer       = "static"
  }
}

# =============================================================================
# Service Accounts
# =============================================================================
resource "google_service_account" "processor" {
  account_id   = local.phase2_resources.processor_service_account
  display_name = "${title(var.environment)} GitHub Archive Processor"
  description  = "Service account for Cloud Run Service that processes GitHub Archive files (both raw and chunks)"
}

resource "google_service_account" "splitter" {
  account_id   = local.phase2_resources.splitter_service_account
  display_name = "${title(var.environment)} File Splitter"
  description  = "Service account for Cloud Run Job that splits large files"
}

resource "google_service_account" "eventarc_invoker" {
  account_id   = local.phase2_resources.eventarc_invoker
  display_name = "${title(var.environment)} Eventarc Invoker"
  description  = "Service account for Eventarc trigger authentication"
}

# =============================================================================
# Staging Bucket
# =============================================================================
resource "google_storage_bucket" "staging" {
  name          = local.phase2_resources.staging_bucket
  location      = var.region
  project       = var.project_id
  force_destroy = var.environment == "dev"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = var.staging_retention_days
    }
    action {
      type = "Delete"
    }
  }

  labels = local.common_labels
}

# =============================================================================
# IAM: Project-Level
# =============================================================================
# Processor SA - Logging and monitoring
resource "google_project_iam_member" "processor_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

# Splitter SA - Logging only
resource "google_project_iam_member" "splitter_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.splitter.email}"
}

# =============================================================================
# IAM: Service Agents (for Eventarc - enable in Layer 02)
# =============================================================================
# These are defined here but depend on APIs being enabled first
# Cloud Storage service agent to publish events
resource "google_project_iam_member" "storage_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:service-${data.google_project.current.number}@gs-project-accounts.iam.gserviceaccount.com"
}

# Eventarc service agent
resource "google_project_iam_member" "eventarc_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-eventarc.iam.gserviceaccount.com"
}

# =============================================================================
# IAM: Bucket-Level (Least Privilege)
# =============================================================================
# Processor SA: Read from landing bucket, write to staging bucket
resource "google_storage_bucket_iam_member" "processor_landing_read" {
  bucket = var.landing_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_storage_bucket_iam_member" "processor_staging_write" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.processor.email}"
}

# Splitter SA: Read from landing/raw, write to landing/chunks
resource "google_storage_bucket_iam_member" "splitter_landing_read" {
  bucket = var.landing_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.splitter.email}"
}

resource "google_storage_bucket_iam_member" "splitter_landing_chunks_write" {
  bucket = var.landing_bucket_name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.splitter.email}"
}
