# Main Terraform configuration for the data pipeline
# This configuration supports both production (GCP) and local (emulators) environments

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Backend for state management (configure per environment)
  # backend "gcs" {
  #   bucket = "YOUR_TERRAFORM_STATE_BUCKET"
  #   prefix = "terraform/state"
  # }
}

# Provider configuration - overridden per environment
provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
