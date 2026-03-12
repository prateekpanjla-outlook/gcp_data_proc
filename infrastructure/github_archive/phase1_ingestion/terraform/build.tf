# This resource automates the container build process during 'terraform apply'.
# It uses a local-exec provisioner to run the 'gcloud builds submit' command,
# ensuring the container image exists before the Cloud Run Job is created.

resource "null_resource" "build_downloader_image" {
  # This build depends on the Artifact Registry repository existing first.
  depends_on = [
    google_artifact_registry_repository.data_pipeline_repo
  ]

  # The 'triggers' block ensures that the build is re-run whenever the
  # source code changes. We create a hash of the Dockerfile and the download script.
  triggers = {
    dockerfile_hash = filesha256("${path.module}/../../../../src/github_archive/Dockerfile")
    # Assuming the download script is at src/github_archive/scripts/download.sh
    # based on the Dockerfile content.
    script_hash = filesha256("${path.module}/../../../../src/github_archive/phase1_ingestion/scripts/download.sh")
  }

  # The provisioner executes a command on the machine running Terraform.
  # It requires 'gcloud' to be installed and authenticated.
  provisioner "local-exec" {
    # This command builds the Docker container using Cloud Build and tags it
    # with the name expected by the Cloud Run Job resource.
    command = "gcloud builds submit --tag ${var.region}-docker.pkg.dev/${var.project_id}/data-pipeline/github-archive-downloader:latest ${path.module}/../../../../src/github_archive"
  }
}