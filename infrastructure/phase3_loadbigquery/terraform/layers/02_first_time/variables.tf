# Layer 02: First-time Resources
# These resources are created once when APIs are enabled first
# After that, resources are on existing state

#
# Note: Service Agent IAM bindings moved to Layer 02
# These require APIs to be enabled first (eventarc, bigquery APIs, storage.googleapis.com)

variable "staging_bucket_name" {
  description = "Name of the staging bucket from Phase 2"
  type        = string
}

variable "eventarc_ack_deadline_seconds" {
  description = "Pub/Sub acknowledgement deadline for Eventarc trigger (max 600 seconds)"
  type        = number
  default     = 600

  validation {
    condition     = var.eventarc_ack_deadline_seconds >= 10 && var.eventarc_ack_deadline_seconds <= 600
    error_message = "Eventarc ack deadline must be between 10 and 600 seconds"
  }
}

