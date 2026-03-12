# This resource automates the container build process during 'terraform apply'.
# It uses a local-exec provisioner to run the 'gcloud builds submit' command,
# ensuring the container image exists before the Cloud Run Job is created.

resource "null_resource" "build_downloader_image" {
  # This build depends on the Artifact Registry repository existing first.
  depends_on = [
    google_artifact_registry_repository.data_pipeline_repo,
    google_project_iam_member.cloudbuild_sa_roles
  ]

  # The 'triggers' block ensures that the build is re-run whenever the
  # source code changes. We create a hash of the Dockerfile and the download script.
  triggers = {
    dockerfile_hash   = filesha256("${path.module}/../../../../src/github_archive/Dockerfile")
    script_hash       = filesha256("${path.module}/../../../../src/github_archive/phase1_ingestion/scripts/download.sh")
    cloudbuild_config = filesha256("${path.module}/../../../../config/cloudbuild-phase1.yaml")
  }

  # The provisioner executes a command on the machine running Terraform.
  # It requires 'gcloud' to be installed and authenticated.
  provisioner "local-exec" {
    # The command is a single string formatted with all necessary variables.
    # It first activates the service account, then submits the build.
    # The semicolon (;) acts as a command separator in PowerShell.
    command = format(
      "gcloud auth activate-service-account --key-file=%s; gcloud builds submit %s --config %s --project=%s --substitutions='_REGION=%s,_ENV=%s' --service-account=%s",
      var.deployer_sa_key_path,
      "${path.module}/../../../../src/github_archive",
      "${path.module}/../../../../config/cloudbuild-phase1.yaml",
      var.project_id,
      var.region,
      var.environment,
      google_service_account.cloudbuild_sa.name
    )

    # Use PowerShell to execute the formatted command string.
    interpreter = ["powershell", "-Command"]
  }
}