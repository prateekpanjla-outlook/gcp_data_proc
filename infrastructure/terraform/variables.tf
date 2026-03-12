# Variables for the data pipeline infrastructure

variable "project_id" {
  description = "Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud Region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod", "test"], var.environment)
    error_message = "Environment must be 'dev', 'staging', 'prod', or 'test'."
  }
}

# GitHub Archive Configuration
variable "github_dataset_id" {
  description = "BigQuery dataset ID for GitHub events"
  type        = string
  default     = "github_archive"
}

variable "github_table_id" {
  description = "BigQuery table ID for GitHub events"
  type        = string
  default     = "events"
}

# Image Configuration
variable "image_tag" {
  description = "Docker image tag (use 'latest' for production)"
  type        = string
  default     = "latest"
}
