# Cloud Run Jobs for batch processing
# Jobs are more cost-effective than services for batch workloads

# GitHub Archive Processor Job
resource "google_cloud_run_v2_job" "github_archive_processor" {
  name     = "github-archive-processor"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/github-archive-processor:${var.image_tag}"

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
      timeout = "3600s"  # 1 hour

      # Service account
      service_account_name = google_service_account.github_processor.id

      # Region for the job
      region = var.region
    }
  }

  # Max concurrent tasks
  launch_stage = "BETA"

  depends_on = [
    google_project_iam_member.bigquery_writer,
    google_project_iam_member.storage_reader,
  ]
}

# Hacker News Fetcher Job
resource "google_cloud_run_v2_job" "hacker_news_fetcher" {
  name     = "hacker-news-fetcher"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/hn-fetcher:${var.image_tag}"

        env {
          name  = "BUCKET_NAME"
          value = "${var.project_id}-data-pipeline"
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "HN_API_BASE_URL"
          value = "https://hacker-news.firebaseio.com/v0"
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }
      }

      timeout = "600s"  # 10 minutes

      service_account_name = google_service_account.hn_fetcher.id
      region                = var.region
    }
  }
}

# Hacker News Processor Job
resource "google_cloud_run_v2_job" "hacker_news_processor" {
  name     = "hacker-news-processor"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/hn-processor:${var.image_tag}"

        env {
          name  = "BUCKET_NAME"
          value = "${var.project_id}-data-pipeline"
        }

        env {
          name  = "DATASET_ID"
          value = "hacker_news"
        }

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "DLQ_TOPIC"
          value = google_pubsub_topic.pipeline_dlq.id
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }

      timeout = "1800s"  # 30 minutes

      service_account_name = google_service_account.hn_processor.id
      region                = var.region
    }
  }
}

# Dead Letter Queue Handler Job
resource "google_cloud_run_v2_job" "dlq_processor" {
  name     = "dlq-processor"
  location = var.region
  project  = var.project_id

  template {
    template {
      containers {
        image = "gcr.io/${var.project_id}/dlq-processor:${var.image_tag}"

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

      timeout = "300s"  # 5 minutes

      service_account_name = google_service_account.dlq_handler.id
      region                = var.region
    }
  }
}
