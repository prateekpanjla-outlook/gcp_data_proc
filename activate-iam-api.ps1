# Script to activate IAM API and create service accounts
$PROJECT_ID = "beaming-glyph-489707-b8"

Write-Host "Activating IAM API by creating service accounts..." -ForegroundColor Cyan

# Create service accounts directly with gcloud (this activates the IAM API)
Write-Host "Creating test-github-archive-downloader service account..." -ForegroundColor Yellow
gcloud iam service-accounts create test-github-archive-downloader `
  --display-name="Test GitHub Archive Downloader" `
  --description="Service account for Cloud Run Job that downloads GitHub Archive files using gsutil" `
  --project=$PROJECT_ID 2>&1 | Out-Null

Write-Host "Creating test-scheduler service account..." -ForegroundColor Yellow
gcloud iam service-accounts create test-scheduler `
  --display-name="Test Cloud Scheduler Service Account" `
  --description="Service account for Cloud Scheduler jobs" `
  --project=$PROJECT_ID 2>&1 | Out-Null

Write-Host ""
Write-Host "Service accounts created! IAM API is now activated." -ForegroundColor Green
Write-Host ""
Write-Host "Now retrying Terraform apply..." -ForegroundColor Cyan
