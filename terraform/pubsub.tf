# Pub/Sub resources for Dead Letter Queue and event routing

# Dead Letter Queue Topic
resource "google_pubsub_topic" "pipeline_dlq" {
  name = "pipeline-dlq"

  message_retention_duration = "604800s" # 7 days

  labels = {
    purpose    = "dead-letter-queue"
    managed-by = "terraform"
  }
}

# DLQ Subscription
resource "google_pubsub_subscription" "pipeline_dlq_sub" {
  name  = "pipeline-dlq-sub"
  topic = google_pubsub_topic.pipeline_dlq.id

  # Only deliver messages once (at-least-once)
  acknowledge_deadline = "600s"

  # Retry policy
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead letter policy for permanently failed messages
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.permanent_failures.id
    max_delivery_attempts = 3
  }

  # Filter for messages that haven't exceeded max retries
  filter = "NOT attributes.retry_count >= attributes.max_retries"

  labels = {
    purpose    = "dlq-retry"
    managed-by = "terraform"
  }

  depends_on = [
    google_pubsub_topic.permanent_failures,
  ]
}

# Topic for permanently failed messages
resource "google_pubsub_topic" "permanent_failures" {
  name = "pipeline-permanent-failures"

  message_retention_duration = "2592000s" # 30 days

  labels = {
    purpose    = "permanent-failures"
    managed-by = "terraform"
  }
}

# Subscription for permanent failures (for analysis/monitoring)
resource "google_pubsub_subscription" "permanent_failures_sub" {
  name  = "pipeline-permanent-failures-sub"
  topic = google_pubsub_topic.permanent_failures.id

  acknowledge_deadline = "600s"

  # Push subscription to monitoring endpoint (optional)
  # push_config {
  #   push_endpoint = var.monitoring_webhook_url
  #   oidc_token {
  #     service_account_email = google_service_account.monitoring.email
  #   }
  # }

  labels = {
    purpose    = "monitoring"
    managed-by = "terraform"
  }
}

# Pub/Sub schema for DLQ messages (optional, for validation)
resource "google_pubsub_schema" "dlq_message_schema" {
  name       = "dlq-message-schema"
  type       = "AVRO"
  definition = <<EOF
{
  "type": "record",
  "name": "DeadLetterMessage",
  "namespace": "com.pipeline.dlq",
  "fields": [
    {"name": "original_event", "type": ["null", "string"], "default": null},
    {"name": "error_message", "type": "string"},
    {"name": "error_type", "type": "string"},
    {"name": "source", "type": "string"},
    {"name": "timestamp", "type": "string"},
    {"name": "retry_count", "type": ["null", "int"], "default": 0},
    {"name": "max_retries", "type": ["null", "int"], "default": 3},
    {"name": "context", "type": ["null", {"type": "map", "values": "string"}], "default": null}
  ]
}
EOF

  project_id = var.project_id
}

# Associate schema with DLQ topic (optional)
# resource "google_pubsub_topic_schema" "dlq_schema" {
#   topic   = google_pubsub_topic.pipeline_dlq.name
#   schema  = google_pubsub_schema.dlq_message_schema.name
#   project = var.project_id
# }
