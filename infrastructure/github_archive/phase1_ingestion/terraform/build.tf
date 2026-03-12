# Wait for IAM permissions to propagate before submitting Cloud Build.
# GCP IAM is eventually consistent — the policy may be recorded but not yet
# enforced. We poll the testIamPermissions API on the Cloud Build source bucket
# to confirm the build SA can actually read/write objects.
resource "null_resource" "wait_for_iam_propagation" {
  depends_on = [
    google_project_iam_member.cloudbuild_sa_roles
  ]

  triggers = {
    sa_email = google_service_account.cloudbuild_sa.email
  }

  provisioner "local-exec" {
    command = format(
      "$sa = '%s'; $bucket = '%s_cloudbuild'; $project = '%s'; $maxAttempts = 12; $attempt = 0; while ($attempt -lt $maxAttempts) { $attempt++; Write-Host \"Checking IAM propagation (attempt $attempt/$maxAttempts)...\"; $token = gcloud auth print-access-token --impersonate-service-account=$sa 2>$null; if ($token) { $response = Invoke-RestMethod -Uri \"https://storage.googleapis.com/storage/v1/b/$bucket/iam/testPermissions?permissions=storage.objects.get&permissions=storage.objects.create\" -Headers @{Authorization=\"Bearer $token\"} -ErrorAction SilentlyContinue; if ($response.permissions -contains 'storage.objects.get') { Write-Host 'IAM permissions confirmed.'; exit 0 } }; Write-Host '  Not yet propagated, waiting 10s...'; Start-Sleep -Seconds 10 }; Write-Host 'ERROR: IAM propagation timed out after 120s'; exit 1",
      google_service_account.cloudbuild_sa.email,
      var.project_id,
      var.project_id
    )
    interpreter = ["powershell", "-Command"]
  }
}

# This resource automates the container build process during 'terraform apply'.
# It uses a local-exec provisioner to run the 'gcloud builds submit' command,
# ensuring the container image exists before the Cloud Run Job is created.
resource "null_resource" "build_downloader_image" {
  depends_on = [
    google_artifact_registry_repository.data_pipeline_repo,
    null_resource.wait_for_iam_propagation
  ]

  # Re-run whenever source code changes.
  triggers = {
    dockerfile_hash   = filesha256("${path.module}/../../../../src/github_archive/Dockerfile")
    script_hash       = filesha256("${path.module}/../../../../src/github_archive/phase1_ingestion/scripts/download.sh")
    cloudbuild_config = filesha256("${path.module}/../../../../config/cloudbuild-phase1.yaml")
  }

  provisioner "local-exec" {
    command = format(
      "gcloud auth activate-service-account --key-file=%s; if ($LASTEXITCODE -ne 0) { exit 1 }; gcloud builds submit %s --config %s --project=%s --substitutions='_REGION=%s,_ENV=%s' --service-account=%s",
      var.deployer_sa_key_path,
      "${path.module}/../../../../src/github_archive",
      "${path.module}/../../../../config/cloudbuild-phase1.yaml",
      var.project_id,
      var.region,
      var.environment,
      google_service_account.cloudbuild_sa.name
    )
    interpreter = ["powershell", "-Command"]
  }
}