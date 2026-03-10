# =============================================================================
# Terraform Configuration: Layer 02 First-time
# =============================================================================
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
  #   prefix         = "terraform/state/phase3-first-time"
  # }
  # Using local backend for development
}
provider "google" {
  project = var.project_id
  region  = var.region
}
