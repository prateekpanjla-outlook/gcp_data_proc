# Cloud Monitoring and Alerting

# Notification channel for alerts
resource "google_monitoring_notification_channel" "email" {
  display_name = "Email Notification Channel"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }

  force_delete = false
}

# ==============================================================================
# Alert Policies
# ==============================================================================

# High failure rate alert
resource "google_monitoring_alert_policy" "high_failure_rate" {
  display_name = "Pipeline High Failure Rate"
  enabled      = var.alerts_enabled

  combiner     = "OR"
  conditions {
    display_name = "GitHub Archive Job High Failure Rate"

    condition_threshold {
      filter          = "resource.type = \"cloud_run_job\" AND metric.type = \"run.googleapis.com/job_failed_count\""
      aggregations {
        alignment_period     = 300  # 5 minutes
        per_series_aligner   = "ALIGN_RATE"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.job_name"]
      }

      comparison      = "COMPARISON_GT"
      threshold_value = 10  # More than 10 failed tasks in 5 minutes
      duration        = "300s"

      trigger {
        count = 1
      }
    }
  }

  documentation {
    title       = "High failure rate detected in Cloud Run Jobs"
    content     = "More than 10 tasks have failed in the last 5 minutes. Check logs for details."
    mime_type   = "text/markdown"
  }

  notification_channels = [
    google_monitoring_notification_channel.email.id
  ]

  labels = {
    severity = "warning"
  }
}

# DLQ backlog alert
resource "google_monitoring_alert_policy" "dlq_backlog" {
  display_name = "Dead Letter Queue Backlog"
  enabled      = var.alerts_enabled

  combiner     = "OR"
  conditions {
    display_name = "DLQ Topic High Message Count"

    condition_threshold {
      filter = "resource.type = \"pubsub_topic\" AND metric.type = \"pubsub.googleapis.com/subscription/num_undelivered_messages\""

      aggregations {
        alignment_period     = 300
        per_series_aligner   = "ALIGN_MAX"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.subscription_id"]
      }

      comparison      = "COMPARISON_GT"
      threshold_value = 100  # More than 100 messages in DLQ
      duration        = "300s"

      trigger {
        count = 1
      }
    }
  }

  documentation {
    title       = "Dead Letter Queue Backlog Alert"
    content     = "The DLQ has more than 100 messages waiting to be processed. This may indicate a systemic issue."
    mime_type   = "text/markdown"
  }

  notification_channels = [
    google_monitoring_notification_channel.email.id
  ]

  labels = {
    severity = "warning"
  }
}

# BigQuery load error alert
resource "google_monitoring_alert_policy" "bigquery_load_errors" {
  display_name = "BigQuery Load Errors"
  enabled      = var.alerts_enabled

  combiner     = "OR"
  conditions {
    display_name = "High BigQuery Load Error Rate"

    condition_threshold {
      filter = "resource.type = \"bigquery_project\" AND metric.type = \"bigquery.googleapis.com/job/loaded_count\" AND metric.labels.error_type = \"\""

      aggregations {
        alignment_period     = 300
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }

      comparison      = "COMPARISON_GT"
      threshold_value = 0.1  # More than 10% error rate
      duration        = "300s"

      trigger {
        count = 1
      }
    }
  }

  documentation {
    title       = "BigQuery Load Error Rate Alert"
    content     = "More than 10% of BigQuery load jobs are failing. Check job details and schema."
    mime_type   = "text/markdown"
  }

  notification_channels = [
    google_monitoring_notification_channel.email.id
  ]

  labels = {
    severity = "error"
  }
}

# ==============================================================================
# Custom Metrics
# ==============================================================================

# Metric descriptor for rows processed
resource "google_monitoring_metric_descriptor" "rows_processed" {
  project      = var.project_id
  type         = "custom.googleapis.com/pipeline/rows_processed"
  metric_kind  = "GAUGE"
  value_type   = "INT64"
  display_name = "Rows Processed"
  description  = "Number of rows processed by the pipeline"
  unit         = "1"

  labels {
    key         = "source"
    value_type  = "STRING"
    description = "Data source (github-archive, hacker-news)"
  }

  labels {
    key         = "status"
    value_type  = "STRING"
    description = "Processing status (success, failed)"
  }
}

# Metric descriptor for processing time
resource "google_monitoring_metric_descriptor" "processing_time" {
  project      = var.project_id
  type         = "custom.googleapis.com/pipeline/processing_time_ms"
  metric_kind  = "GAUGE"
  value_type   = "DOUBLE"
  display_name = "Processing Time"
  description  = "Time taken to process a file/batch"
  unit         = "ms"

  labels {
    key         = "source"
    value_type  = "STRING"
    description = "Data source"
  }

  labels {
    key         = "file_name"
    value_type  = "STRING"
    description = "File being processed"
  }
}

# ==============================================================================
# Dashboard
# ==============================================================================

resource "google_monitoring_dashboard" "pipeline_dashboard" {
  display_name = "Data Pipeline Dashboard"

  grid_layout {
    widgets {
      title      = "Jobs Status"
      xy_chart {
        data_sets {
          time_series_query {
            unit        = "1"
            time_series {
              filter     = "resource.type = \"cloud_run_job\""
              aggregation {
                alignment_period     = 300
                per_series_aligner   = "ALIGN_RATE"
                cross_series_reducer = "REDUCE_SUM"
                group_by_fields      = ["resource.label.job_name", "metric.label.status"]
              }
            }
          }
          plot_type = "LINE"
        }
      }
    }

    widgets {
      title      = "DLQ Message Count"
      xy_chart {
        data_sets {
          time_series_query {
            unit        = "1"
            time_series {
              filter     = "resource.type = \"pubsub_topic\" AND metric.type = \"pubsub.googleapis.com/topic/num_messages_published\" AND resource.label.topic_id = \"pipeline-dlq\""
              aggregation {
                alignment_period     = 60
                per_series_aligner   = "ALIGN_SUM"
              }
            }
          }
          plot_type = "STACKED_AREA"
        }
      }
    }

    widgets {
      title      = "BigQuery Load Job Status"
      xy_chart {
        data_sets {
          time_series_query {
            unit        = "1"
            time_series {
              filter     = "resource.type = \"bigquery_project\" AND metric.type = \"bigquery.googleapis.com/job/loaded_count\""
              aggregation {
                alignment_period     = 300
                per_series_aligner   = "ALIGN_DELTA"
              }
            }
          }
          plot_type = "LINE"
        }
      }
    }

    widgets {
      title      = "Processing Time"
      xy_chart {
        data_sets {
          time_series_query {
            unit        = "ms"
            time_series {
              filter     = "metric.type = \"custom.googleapis.com/pipeline/processing_time_ms\""
              aggregation {
                alignment_period     = 300
                per_series_aligner   = "ALIGN_MEAN"
                cross_series_reducer = "REDUCE_MEAN"
                group_by_fields      = ["metric.label.source"]
              }
            }
          }
          plot_type = "LINE"
        }
      }
    }
  }
}
