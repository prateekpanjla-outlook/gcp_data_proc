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
}

# GitHub Archive Configuration
variable "github_bucket_name" {
  description = "Name of the GCS bucket for GitHub Archive data"
  type        = string
  default     = "github-archive-data"
}

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

# Hacker News Configuration
variable "hn_bucket_name" {
  description = "Name of the GCS bucket for Hacker News data"
  type        = string
  default     = "hacker-news-data"
}

variable "hn_dataset_id" {
  description = "BigQuery dataset ID for Hacker News"
  type        = string
  default     = "hacker_news"
}

# Cloud Run Configuration
variable "github_service_name" {
  description = "Cloud Run service name for GitHub processor"
  type        = string
  default     = "github-processor"
}

variable "hn_service_name" {
  description = "Cloud Run service name for Hacker News processor"
  type        = string
  default     = "hn-processor"
}

variable "github_memory" {
  description = "Memory for GitHub Cloud Run service"
  type        = string
  default     = "512Mi"
}

variable "hn_memory" {
  description = "Memory for Hacker News Cloud Run service"
  type        = string
  default     = "512Mi"
}

variable "github_cpu" {
  description = "CPU for GitHub Cloud Run service"
  type        = string
  default     = "1"
}

variable "hn_cpu" {
  description = "CPU for Hacker News Cloud Run service"
  type        = string
  default     = "1"
}

variable "max_instances" {
  description = "Maximum Cloud Run instances per service"
  type        = number
  default     = 100
}

variable "min_instances" {
  description = "Minimum Cloud Run instances per service (0 for scale-to-zero)"
  type        = number
  default     = 0
}

# Eventarc Configuration
variable "eventarc_enabled" {
  description = "Enable Eventarc triggers for automatic processing"
  type        = bool
  default     = true
}

variable "github_event_filter" {
  description = "Eventarc filter pattern for GitHub Archive files"
  type        = string
  default     = "github-archive/raw/"
}

# Monitoring & Logging
variable "logging_dataset_id" {
  description = "BigQuery dataset for logging exports"
  type        = string
  default     = "logs"
}

variable "enable_logging_export" {
  description = "Enable BigQuery logging export"
  type        = bool
  default     = false
}
