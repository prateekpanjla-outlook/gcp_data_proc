# Phase 4 Monitoring — First Time Setup
# Enable APIs, grant dashboard SA read access to BQ

resource "google_project_service" "logging" {
  project            = var.project_id
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

# Dashboard SA needs to run queries and read the pipeline_logs dataset
resource "google_project_iam_member" "dashboard_bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${var.dashboard_sa_email}"
}

resource "google_bigquery_dataset_iam_member" "dashboard_data_viewer" {
  project    = var.project_id
  dataset_id = var.pipeline_logs_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${var.dashboard_sa_email}"
}

# Clean up stale deleted SA entries from github_archive dataset IAM
# When Phase 4 is destroyed and recreated, the old SA gets a "deleted:" prefix
# in existing dataset IAM bindings, which blocks new IAM grants.
resource "null_resource" "cleanup_stale_sa_bindings" {
  triggers = {
    dashboard_sa_email = var.dashboard_sa_email
  }

  provisioner "local-exec" {
    command = format(
      "$stale = bq show --format=prettyjson '%s:github_archive' 2>$null | Select-String -Pattern '\"deleted:serviceAccount:%s' -SimpleMatch; if ($stale) { Write-Host 'Found stale SA binding, removing...'; $uid = ($stale -replace '.*uid=','') -replace '\".*',''; $member = 'deleted:serviceAccount:%s?uid=' + $uid; bq query --project_id=%s --nouse_legacy_sql ('REVOKE ``roles/bigquery.dataViewer`` ON SCHEMA ``%s.github_archive`` FROM \"' + $member + '\"'); Write-Host 'Stale SA binding removed.' } else { Write-Host 'No stale SA bindings found.' }",
      var.project_id,
      var.dashboard_sa_email,
      var.dashboard_sa_email,
      var.project_id,
      var.project_id
    )
    interpreter = ["powershell", "-Command"]
  }
}

# Dashboard SA needs to read github_archive dataset for Phase 3 row counts
resource "google_bigquery_dataset_iam_member" "dashboard_github_archive_viewer" {
  depends_on = [null_resource.cleanup_stale_sa_bindings]

  project    = var.project_id
  dataset_id = "github_archive"
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${var.dashboard_sa_email}"
}

# Verify dashboard SA actually has BQ permissions after IAM grant
resource "null_resource" "verify_dashboard_iam" {
  depends_on = [
    google_bigquery_dataset_iam_member.dashboard_github_archive_viewer,
    google_bigquery_dataset_iam_member.dashboard_data_viewer,
    google_project_iam_member.dashboard_bq_job_user,
    google_project_iam_member.dashboard_bq_resource_viewer,
  ]

  triggers = {
    dashboard_sa_email = var.dashboard_sa_email
  }

  provisioner "local-exec" {
    command = format(
      "$maxAttempts = 6; $attempt = 0; while ($attempt -lt $maxAttempts) { $attempt++; Write-Host \"Verifying dashboard SA IAM (attempt $attempt/$maxAttempts)...\"; $token = gcloud auth print-access-token --impersonate-service-account=%s 2>$null; if ($token) { try { $response = Invoke-RestMethod -Uri 'https://bigquery.googleapis.com/bigquery/v2/projects/%s/datasets/github_archive?fields=id' -Headers @{Authorization=\"Bearer $token\"} -ErrorAction Stop; Write-Host 'IAM verified: dashboard SA can access github_archive dataset.'; exit 0 } catch { Write-Host \"  Access not yet propagated: $($_.Exception.Message)\" } } else { Write-Host '  Could not impersonate SA, waiting...' }; Start-Sleep -Seconds 10 }; Write-Host 'WARNING: IAM verification timed out after 60s. Dashboard may need a few more minutes.'; exit 0",
      var.dashboard_sa_email,
      var.project_id
    )
    interpreter = ["powershell", "-Command"]
  }
}

# Dashboard SA needs to query INFORMATION_SCHEMA.JOBS for Phase 3 load job details
resource "google_project_iam_member" "dashboard_bq_resource_viewer" {
  project = var.project_id
  role    = "roles/bigquery.resourceViewer"
  member  = "serviceAccount:${var.dashboard_sa_email}"
}
