# Phase 2: Process Files - Cloud Run Service

# =============================================================================
# Single Processor Service (handles both raw/ and chunks/)
# =============================================================================
resource "google_cloud_run_v2_service" "processor" {
  name     = "${local.env_prefix}-github-archive-processor"
  location = var.region
  project  = var.project_id

  template {
    metadata {
      annotations = {
        # Autoscaling
        "autoscaling.knative.dev/maxScale"       = tostring(var.max_instances)
        "autoscaling.knative.dev/minScale"       = "0"
        "autoscaling.knative.dev/target"         = "10"
        "autoscaling.knative.dev/scaleDownDelay" = "30s"

        # Performance
        "run.googleapis.com/cpu-throttling"       = "false"
        "run.googleapis.com/execution-environment" = "gen2"

        # Health check
        "run.googleapis.com/health-check-path" = "/health"
        "run.googleapis.com/health-check-per-second" = "1"
      }
    }

    template {
      containers {
        # Image for the processor service
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.environment}-github-archive/processor:latest"

        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "LANDING_BUCKET"
          value = var.landing_bucket_name
        }
        env {
          name  = "STAGING_BUCKET"
          value = google_storage_bucket.staging.name
        }
        env {
          name  = "FILE_SIZE_THRESHOLD_MB"
          value = tostring(var.file_size_threshold_mb)
        }
        env {
          name  = "CHUNKSIZE"
          value = tostring(var.chunksize)
        }
        env {
          name  = "PORT"
          value = "8080"
        }

        resources {
          limits = {
            cpu    = tostring(var.processor_cpu)
            memory = "${var.processor_memory}Gi"
          }
          requests = {
            cpu    = "100m"
            memory = "512Mi"
          }
        }
      }

      container_concurrency = 10
      timeout_seconds      = 3600  # 1 hour

      service_account = google_service_account.processor.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_service.phase2_apis
  ]
}
