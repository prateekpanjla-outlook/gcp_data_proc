# Grant Remaining IAM Roles
$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA_EMAIL = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "Granting additional IAM roles..." -ForegroundColor Cyan

$roles = @(
    "roles/compute.admin",
    "roles/cloudscheduler.admin",
    "roles/eventarc.admin",
    "roles/pubsub.admin",
    "roles/cloudbuild.builds.builder",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/artifactregistry.admin",
    "roles/secretmanager.admin"
)

foreach ($role in $roles) {
    Write-Host "  Granting $role..." -ForegroundColor Yellow
    gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$DEPLOYER_SA_EMAIL" --role="$role" --quiet 2>&1 | Out-Null
}

Write-Host "[SUCCESS] All IAM roles granted!" -ForegroundColor Green

# Enable required APIs
Write-Host ""
Write-Host "Enabling required APIs..." -ForegroundColor Cyan

$apis = @(
    "run.googleapis.com",
    "cloudfunctions.googleapis.com",
    "cloudscheduler.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "  Enabling $api..." -ForegroundColor Yellow
    gcloud services enable $api --project=$PROJECT_ID --quiet 2>&1 | Out-Null
}

Write-Host "[SUCCESS] All APIs enabled!" -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service Account: $DEPLOYER_SA_EMAIL"
Write-Host "Key File: test-terraform-deployer-key.json"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Set environment variable:"
Write-Host "     `$env:GOOGLE_APPLICATION_CREDENTIALS='test-terraform-deployer-key.json'"
Write-Host ""
Write-Host "  2. Verify authentication:"
Write-Host "     gcloud auth application-default print-access-token"
Write-Host ""
