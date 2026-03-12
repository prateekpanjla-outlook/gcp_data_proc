# Main infrastructure resources for the data pipeline

# ==============================================================================
# Cloud Storage Buckets
# ==============================================================================

# GitHub Archive Landing Bucket (Phase 1: Ingestion)
# Raw GitHub Archive files are downloaded here
resource "google_storage_bucket" "github_archive_landing" {
  name          = local.github_archive.bucket_name
  project       = var.project_id
  location      = var.region
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90 # Delete files after 90 days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    layer       = "landing"
    managed_by  = "terraform"
  }
}

# GitHub Archive Processed Data Bucket
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

  default_table_expiration_ms = 7776000000 # 90 days

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

  default_table_expiration_ms = 7776000000 # 90 days

  delete_contents_on_destroy = var.environment == "dev" ? true : false
}

# ==============================================================================
# Artifact Registry for Container Images
# ==============================================================================
resource "google_artifact_registry_repository" "docker" {
  location      = var.region
  repository_id = "data-pipeline"
  description   = "Docker repository for GitHub Archive data pipeline"
  format        = "DOCKER"
  mode          = "STANDARD"

  docker_config {
    immutable_tags = false
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }
}

# ==============================================================================
# Cloud Run Jobs
# ==============================================================================

resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = "${var.environment}-github-archive-download-gsutil"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/github-archive-downloader:latest"

        env {
          name  = "ENVIRONMENT"
          value = var.environment
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "BUCKET_NAME"
          value = google_storage_bucket.github_archive_landing.name
        }
        env {
          name  = "HOURS_AGO"
          value = "1"
        }
      }
      service_account = google_service_account.github_archive_downloader.email
    }
  }

  labels = {
    environment = var.environment
    source      = "github-archive"
    managed_by  = "terraform"
  }
}

# ==============================================================================
# Cloud Run Services
# ==============================================================================

# GitHub Archive Processor
resource "google_cloud_run_v2_service" "github_processor" {
  name        = "${var.github_service_name}-${var.environment}"
  project     = var.project_id
  location    = var.region
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
    service_account = google_service_account.github_processor.email

    # Timeout for processing
    timeout = "3600s" # 1 hour

    # Container startup CPU boost
    scaling {
      scaling_mode = "AUTOMATIC"
    }
  }

  labels = {
    environment = var.environment,
    source      = "github-archive",
    managed_by  = "terraform",
  }

  traffic {
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    google_project_iam_member.github_processor_bigquery_editor,
    google_storage_bucket_iam_member.github_processor_staging_creator,
    google_storage_bucket_iam_member.github_processor_staging_viewer,
  ]
}

# Hacker News Processor
resource "google_cloud_run_v2_service" "hn_processor" {
  name        = "${var.hn_service_name}-${var.environment}"
  project     = var.project_id
  location    = var.region
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

    service_account = google_service_account.hn_processor.email # From service_accounts.tf

    timeout = "3600s"

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
    percent         = 100
    latest_revision = true
  }

  depends_on = [
    # Depends on the specific IAM roles defined in service_accounts.tf
    google_project_iam_member.hn_processor_bigquery_editor,
    google_project_iam_member.hn_processor_storage_viewer,
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
  # This should be the Eventarc invoker service account, not allUsers.
  # Assuming an eventarc invoker SA is defined elsewhere, e.g., 'dev-eventarc-invoker'
  member   = "serviceAccount:dev-eventarc-invoker@${var.project_id}.iam.gserviceaccount.com"
}

resource "google_cloud_run_v2_service_iam_member" "hn_invoker" {
  project  = google_cloud_run_v2_service.hn_processor.project
  location = google_cloud_run_v2_service.hn_processor.location
  name     = google_cloud_run_v2_service.hn_processor.name
  role     = "roles/run.invoker"
  # This should be the Cloud Scheduler service account, not allUsers.
  # The scheduler SA is defined in service_accounts.tf
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# ==============================================================================
# Eventarc Triggers (for automatic invocation)
# ==============================================================================
resource "google_eventarc_trigger" "github_storage" {
  count    = var.eventarc_enabled ? 1 : 0
  name     = "github-storage-trigger-${var.environment}"
  project  = var.project_id
  location = var.region

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    # The trigger must watch the LANDING bucket, not the staging/processed bucket.
    value     = google_storage_bucket.github_archive_landing.name
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

  # The Eventarc trigger should use a dedicated invoker SA
  service_account = "serviceAccount:dev-eventarc-invoker@${var.project_id}.iam.gserviceaccount.com"

  labels = {
    environment = var.environment
    source      = "github-archive"
  }
}

# Scheduler for Hacker News (fetch new stories every hour)
resource "google_cloud_scheduler_job" "hn_fetch" {
  name     = "hn-fetch-${var.environment}"
  project  = var.project_id
  region   = var.region
  schedule = "0 * * * *" # Every hour

  http_target {
    http_method = "GET"
    uri         = "${google_cloud_run_v2_service.hn_processor.uri}/tasks/fetch"
    oidc_token {
      service_account_email = google_service_account.scheduler.email # Use the scheduler SA
      audience              = google_cloud_run_v2_service.hn_processor.uri
    }
  }
}

resource "google_eventarc_trigger" "hn_scheduler" {
  count    = var.eventarc_enabled ? 1 : 0
  name     = "hn-scheduler-trigger-${var.environment}"
  project  = var.project_id
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

  # The Eventarc trigger should use a dedicated invoker SA
  service_account = "serviceAccount:dev-eventarc-invoker@${var.project_id}.iam.gserviceaccount.com"

  labels = {
    environment = var.environment
    source      = "hacker-news"
  }
}
