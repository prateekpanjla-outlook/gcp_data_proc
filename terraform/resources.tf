# Main infrastructure resources for the data pipeline

# ==============================================================================
# Service Account
# ==============================================================================
resource "google_service_account" "processor" {
  project      = var.project_id
  account_id   = "data-processor-sa"
  display_name = "Data Pipeline Processor Service Account"
}

resource "google_project_iam_member" "processor_bigquery_admin" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_storage_admin" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_logging_user" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

# ==============================================================================
# Cloud Storage Buckets
# ==============================================================================
resource "google_storage_bucket" "github_data" {
  name          = "${var.github_bucket_name}-${var.environment}"
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }
}

resource "google_storage_bucket" "hn_data" {
  name          = "${var.hn_bucket_name}-${var.environment}"
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    source      = "hacker-news"
    managed_by  = "terraform"
  }
}

# ==============================================================================
# BigQuery Datasets
# ==============================================================================
resource "google_bigquery_dataset" "github" {
  dataset_id  = "${var.github_dataset_id}_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "GitHub Archive event data"

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }

  default_table_expiration_ms = 7776000000  # 90 days

  delete_contents_on_destroy = var.environment == "dev" ? true : false
}

resource "google_bigquery_dataset" "hacker_news" {
  dataset_id  = "${var.hn_dataset_id}_${var.environment}"
  project     = var.project_id
  location    = var.region
  description = "Hacker News stories and comments"

  labels = {
    environment = var.environment
    source      = "hacker-news"
    managed_by  = "terraform"
  }

  default_table_expiration_ms = 7776000000  # 90 days

  delete_contents_on_destroy = var.environment == "dev" ? true : false
}

# ==============================================================================
# Artifact Registry for Container Images
# ==============================================================================
resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = "data-pipeline"
  description   = "Docker images for data pipeline"
  format        = "DOCKER"

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# ==============================================================================
# Cloud Run Services
# ==============================================================================

# GitHub Archive Processor
resource "google_cloud_run_v2_service" "github_processor" {
  name     = "${var.github_service_name}-${var.environment}"
  project  = var.project_id
  location = var.region
  description = "Process GitHub Archive data from GCS to BigQuery"

  template {
    min_instance_count = var.min_instances
    max_instance_count = var.max_instances

    containers {
      name  = "processor"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/github-processor:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DATASET_ID"
        value = "${var.github_dataset_id}_${var.environment}"
      }
      env {
        name  = "TABLE_ID"
        value = var.github_table_id
      }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.github_data.name
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      resources {
        limits = {
          cpu    = var.github_cpu
          memory = var.github_memory
        }
      }
    }

    # Service account to run as
    service_account = google_service_account.processor.email

    # Timeout for processing
    timeout_seconds = 3600  # 1 hour

    # Container startup CPU boost
    scaling {
      scaling_mode = "AUTOMATIC"
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }

  traffic {
    percent = 100
    latest_revision = true
  }

  depends_on = [
    google_project_iam_member.processor_bigquery_admin,
    google_project_iam_member.processor_storage_admin,
  ]
}

# Hacker News Processor
resource "google_cloud_run_v2_service" "hn_processor" {
  name     = "${var.hn_service_name}-${var.environment}"
  project  = var.project_id
  location = var.region
  description = "Fetch and process Hacker News data to BigQuery"

  template {
    min_instance_count = var.min_instances
    max_instance_count = var.max_instances

    containers {
      name  = "processor"
      image = "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/hn-processor:latest"

      env {
        name  = "PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "DATASET_ID"
        value = "${var.hn_dataset_id}_${var.environment}"
      }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.hn_data.name
      }
      env {
        name  = "LOG_LEVEL"
        value = "INFO"
      }

      resources {
        limits = {
          cpu    = var.hn_cpu
          memory = var.hn_memory
        }
      }
    }

    service_account = google_service_account.processor.email

    timeout_seconds = 3600

    scaling {
      scaling_mode = "AUTOMATIC"
    }
  }

  labels = {
    environment = var.environment
    source      = "hacker-news"
    managed_by  = "terraform"
  }

  traffic {
    percent = 100
    latest_revision = true
  }

  depends_on = [
    google_project_iam_member.processor_bigquery_admin,
    google_project_iam_member.processor_storage_admin,
  ]
}

# ==============================================================================
# Cloud Run IAM - Public invoker (for Eventarc)
# ==============================================================================
resource "google_cloud_run_v2_service_iam_member" "github_invoker" {
  project  = google_cloud_run_v2_service.github_processor.project
  location = google_cloud_run_v2_service.github_processor.location
  name     = google_cloud_run_v2_service.github_processor.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "hn_invoker" {
  project  = google_cloud_run_v2_service.hn_processor.project
  location = google_cloud_run_v2_service.hn_processor.location
  name     = google_cloud_run_v2_service.hn_processor.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ==============================================================================
# Eventarc Triggers (for automatic invocation)
# ==============================================================================
resource "google_eventarc_trigger" "github_storage" {
  count   = var.eventarc_enabled ? 1 : 0
  name    = "github-storage-trigger-${var.environment}"
  project = var.project_id
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = google_storage_bucket.github_data.name
  }

  matching_criteria {
    attribute = "name"
    value     = var.github_event_filter
  }

  destination {
    cloud_run_service = {
      service = google_cloud_run_v2_service.github_processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.processor.email

  labels = {
    environment = var.environment
    source      = "github-archive"
  }

  depends_on = [
    google_project_iam_member.processor_eventreceiver,
  ]
}

# Scheduler for Hacker News (fetch new stories every hour)
resource "google_cloud_scheduler_job" "hn_fetch" {
  name     = "hn-fetch-${var.environment}"
  project  = var.project_id
  region   = var.region
  schedule = "0 * * * *"  # Every hour

  http_target {
    http_method = "GET"
    uri         = "${google_cloud_run_v2_service.hn_processor.uri}/tasks/fetch"
    oidc_token {
      service_account_email = google_service_account.processor.email
      audience              = google_cloud_run_v2_service.hn_processor.uri
    }
  }

  depends_on = [
    google_project_iam_member.processor_scheduler,
  ]
}

resource "google_eventarc_trigger" "hn_scheduler" {
  count   = var.eventarc_enabled ? 1 : 0
  name    = "hn-scheduler-trigger-${var.environment}"
  project = var.project_id
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.scheduler.job.v1.executed"
  }

  matching_criteria {
    attribute = "jobName"
    value     = google_cloud_scheduler_job.hn_fetch.name
  }

  destination {
    cloud_run_service = {
      service = google_cloud_run_v2_service.hn_processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.processor.email

  labels = {
    environment = var.environment
    source      = "hacker-news"
  }
}

# ==============================================================================
# Additional IAM for Eventarc and Scheduler
# ==============================================================================
resource "google_project_iam_member" "processor_eventreceiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.processor.email}"
}

resource "google_project_iam_member" "processor_scheduler" {
  project = var.project_id
  role    = "roles/cloudscheduler.jobRunner"
  member  = "serviceAccount:${google_service_account.processor.email}"
}
