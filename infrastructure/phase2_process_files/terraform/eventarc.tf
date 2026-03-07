# Phase 2: Process Files - Eventarc Triggers

# =============================================================================
# Eventarc Trigger #1: Main file processor (raw/ folder)
# =============================================================================
resource "google_eventarc_trigger" "main_file_processor" {
  name        = "${local.env_prefix}-github-archive-main-file-processor"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name
  }

  matching_criteria {
    attribute = "name"
    value     = "github-archive/raw/*.json.gz"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email

  retry_policy {
    max_attempts = 2
  }

  depends_on = [
    google_project_service.phase2_apis,
    google_project_iam_member.storage_pubsub_publisher,
    google_project_iam_member.eventarc_event_receiver
  ]

  labels = local.common_labels
}

# =============================================================================
# Eventarc Trigger #2: Chunk processor (chunks/ folder)
# =============================================================================
resource "google_eventarc_trigger" "chunk_processor" {
  name        = "${local.env_prefix}-github-archive-chunk-processor"
  location    = var.region
  project     = var.project_id

  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }

  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name
  }

  matching_criteria {
    attribute = "name"
    value     = "github-archive/chunks/*.json.gz"
  }

  destination {
    cloud_run_service {
      service = google_cloud_run_v2_service.processor.name
      region  = var.region
    }
  }

  service_account = google_service_account.eventarc_invoker.email

  retry_policy {
    max_attempts = 2
  }

  depends_on = [
    google_project_service.phase2_apis,
    google_project_iam_member.storage_pubsub_publisher,
    google_project_iam_member.eventarc_event_receiver
  ]

  labels = merge(local.common_labels, {purpose = "chunk-trigger"})
}
