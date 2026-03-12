#
# Manages the dedicated service account for Cloud Build.
# This SA is used by the Cloud Build trigger to build and deploy the processor service.
# It replaces the default Compute Engine service account for better security.
#

resource "google_service_account" "cloudbuild_sa" {
  project      = var.project_id
  account_id   = "${var.environment}-cloud-build"
  display_name = "Service Account for Cloud Build (${var.environment})"
  description  = "Used by Cloud Build triggers to build and deploy applications."
}

locals {
  cloud_build_sa_roles = toset([
    # For building & pushing artifacts
    "roles/storage.objectAdmin",      # Access GCS for source code
    "roles/artifactregistry.writer",  # Push images to Artifact Registry
    "roles/logging.logWriter",        # Write build logs
    "roles/cloudbuild.builds.editor", # Create and manage builds

    # For deploying to Cloud Run
    "roles/run.admin",              # Deploy and manage Cloud Run services
    "roles/iam.serviceAccountUser", # Attach runtime SAs to new Cloud Run revisions
  ])
}

# Grant all required roles to the dedicated Cloud Build service account
# using a for_each loop for better maintainability.
resource "google_project_iam_member" "cloudbuild_sa_roles" {
  for_each = local.cloud_build_sa_roles
  project  = var.project_id
  role     = each.key
  member  = "serviceAccount:${google_service_account.cloudbuild_sa.email}"
}