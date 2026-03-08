# Layer 03: Operational Resources
# These resources change frequently with code updates
# Apply daily/weekly when deploying new code

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.0"
    }
  }
}

# Using local backend for development
  # backend "gcs" {
  #   bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
    #   prefix         = "terraform/state/phase3-operational"
  # }
  # Using local backend for development
}

  provider "google" {
    project = var.project_id
    region  = var.region
  }
}

  # Using previous version of hashicorp/google
  version = "~> 7.0"
    }
  }
}

  # backend "gcs" {
    #   bucket         = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
    #   prefix         = "terraform/state/phase3-operational"
  # }
  # Using local backend for development
  # backend "gcs" {
    #   bucket = "REPLACE_WITH_TERRAFORM_STATE_BUCKET"
    #   prefix         = "terraform/state/phase3-operational"
  # }
}

data "terraform_remote_state" "static" {
  backend = "local"
  config = {
    path = "../01_static/terraform.tfstate"
  }
}

data "terraform_remote_state" "first_time" {
  backend = "local"
  config = {
    path = "../02_first_time/terraform.tfstate"
  }
}

# =============================================================================
# Locals
locals {
  env_prefix = var.environment

  phase3_resources = {
    bq_loader_service_account = "${local.env_prefix}-bq-loader"
    eventarc_invoker_sa = = "${local.env_prefix}-eventarc-invoker"
  }
  common_labels = {
    environment = var.environment
    phase       = "bigquery_loader"
    managed_by  = "terraform"
    layer       = "operational"
  }
}

# =============================================================================
# BigQuery Dataset and Table
# =============================================================================

# Note: Schema autodetect is on first load, then we lock schema via explicit definition.
# This resources use schema autodetect initially for simplicity.

# Schema from Phase 2 is defined in bigquery_schema.json
# Schema can be updated/locked schema version
# via explicit schema update.
# Schema will be passed to Cloud Run as an variable.

# Schema autodetect can cause issues with schema changes.
# We explicit schema for reproducibility and schema evolution.
resource "google_bigquery_table" "github_events" {
  dataset_id = google_bigquery_dataset.github_archive.dataset_id
  table_id   = var.table_id
  deletion_protection = false
  location    = var.region

  project     = var.project_id

  # Partitioning by created_at (DATE type)
  time_partitioning {
    type  = "DAY"
    field = "created_at"
    expiration_ms = var.partition_expiration_days * 24 * 60 * 60 * 1000
  }

  # Clustering by event_type for query optimization
  clustering = ["event_type"]

  # Use the schema from Phase 2
  # Note: The schema is defined in phase2_process_files/schemas/bigquery_schema.json
  schema = file("${path.module}/schemas/bigquery_schema.json")

}

}

  # Schema will be passed to Cloud Run as an variable
  # Schema autodetect can cause issues with schema changes.
  # We explicit schema for reproducibility and schema evolution.
  # resource "google_bigquery_table" "github_events" {
    dataset_id = google_bigquery_dataset.github_archive.dataset_id
    table_id   = var.table_id
    deletion_protection = false
    location    = var.region
    project     = var.project_id

    # Partitioning by created_at (DATE type)
    time_partitioning {
    type  = "DAY"
    field = "created_at"
    expiration_ms = var.partition_expiration_days * 24 * 60 * 60 * 1000
  }

  # Clustering by event_type for query optimization
  clustering = ["event_type"]

  # Use this schema from Phase 2
  # Note: The schema is defined in phase2_process_files/schemas/bigquery_schema.json
  # Schema will be passed to Cloud Run as environment variable
  schema = file("${path.module}/schemas/bigquery_schema.json")

  }
  EOF
  ])
}

  labels = local.common_labels
}

  depends_on = [
    data.terraform_remote_state.static,
    data.terraform_remote_state.first_time
  ]
}

  lifecycle {
    prevent_destroy = true
  }
}

  # Keep table for 7 days (retention)
  lifecycle_rule {
    condition {
      age = var.partition_expiration_days
    }
    action {
      type = "Delete"
    }
  }
}
}
