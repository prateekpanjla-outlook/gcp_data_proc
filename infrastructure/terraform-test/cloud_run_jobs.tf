# Cloud Run Jobs for batch processing
# Jobs are more cost-effective than services for batch workloads

# ==============================================================================
# GitHub Archive Ingestion Job (Phase 1: gsutil-based Downloader)
# ==============================================================================
resource "google_cloud_run_v2_job" "github_archive_downloader" {
  name     = local.github_archive.job_name
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        # Uses google-cloud-sdk base image with gsutil pre-installed
        image = "gcr.io/google.com/cloud-sdk:slim"

        # Environment variables
        env {
          name  = "BUCKET_NAME"
          value = local.github_archive.bucket_name
        }
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "HOURS_AGO"
          value = "1"
        }

        # Resource limits
        resources {
          limits = {
            cpu    = "1"
            memory = "256Mi"
          }
        }
      }

      # Service account
      service_account = google_service_account.github_processor.email
    }
  }
}

# GitHub Archive Processor Job
resource "google_cloud_run_v2_job" "github_archive_processor" {
  name     = "github-archive-processor"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/github-archive-processor:${var.image_tag}"

        env {
          name  = "BUCKET_NAME"
          value = "${var.project_id}-data-pipeline"
        }

        env {
          name  = "DATASET_ID"
          value = "github_dataset"
        }

        env {
          name  = "TABLE_ID"
          value = "events"
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DLQ_TOPIC"
          value = google_pubsub_topic.pipeline_dlq.id
        }

        # Resource limits
        resources {
          limits = {
            cpu    = "1"
            memory = "2Gi"
          }
        }
      }

      # Timeout for job execution
      timeout = "3600s" # 1 hour

      # Service account
      service_account = google_service_account.github_processor.email
    }
  }

  # Max concurrent tasks
  launch_stage = "BETA"

  depends_on = [
    google_project_iam_member.bigquery_writer,
    google_project_iam_member.storage_reader,
  ]
}


# Dead Letter Queue Handler Job
resource "google_cloud_run_v2_job" "dlq_processor" {
  name     = "dlq-processor"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/dlq-processor:${var.image_tag}"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DLQ_SUBSCRIPTION"
          value = google_pubsub_subscription.pipeline_dlq_sub.id
        }

        env {
          name  = "FAILURE_BUCKET"
          value = "${var.project_id}-data-pipeline"
        }

        resources {
          limits = {
            cpu    = "0.5"
            memory = "256Mi"
          }
        }
      }

      timeout = "300s" # 5 minutes

      service_account = google_service_account.dlq_handler.email
    }
  }
}
