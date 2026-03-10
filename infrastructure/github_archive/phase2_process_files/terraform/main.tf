# Phase 2: Process Files - Terraform Main Configuration
# Provider and main resources

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

data "google_project" "current" {
  project_id = var.project_id
}

# =============================================================================
# Locals
# =============================================================================
locals {
  env_prefix = var.environment  # "dev" or "prod"

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
  }
}
