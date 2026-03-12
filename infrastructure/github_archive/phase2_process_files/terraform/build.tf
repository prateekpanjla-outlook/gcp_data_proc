# Phase 2: Process Files - Cloud Build for Processor Image
# Builds and pushes the processor Docker image to Artifact Registry.
# The AR repo and Cloud Build SA are created in Phase 1.

resource "null_resource" "build_processor_image" {
  # Rebuild when source code changes
  triggers = {
    dockerfile_hash   = filesha256("${path.module}/../../../../src/github_archive/phase2_process_files/Dockerfile.processor")
    requirements_hash = filesha256("${path.module}/../../../../src/github_archive/phase2_process_files/requirements.txt")
    cloudbuild_config = filesha256("${path.module}/../../../../config/cloudbuild-phase2.yaml")
  }

  provisioner "local-exec" {
    command = format(
      "gcloud auth activate-service-account --key-file=%s; gcloud builds submit %s --config %s --project=%s --substitutions='_REGION=%s,_ENV=%s' --service-account=projects/%s/serviceAccounts/%s-cloud-build@%s.iam.gserviceaccount.com",
      var.deployer_sa_key_path,
      "${path.module}/../../../../src/github_archive/phase2_process_files",
      "${path.module}/../../../../config/cloudbuild-phase2.yaml",
      var.project_id,
      var.region,
      var.environment,
      var.project_id,
      var.environment,
      var.project_id
    )

    interpreter = ["powershell", "-Command"]
  }
}
