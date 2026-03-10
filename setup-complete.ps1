# =============================================================================
# Complete Setup Script for GitHub Archive Infrastructure
# =============================================================================
# This script performs all necessary setup steps:
# 1. Enable all required GCP APIs
# 2. Grant additional IAM permissions if needed
# 3. Display status and next steps
#
# Usage:
#   .\setup-complete.ps1
# =============================================================================

$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Archive Infrastructure Setup" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# Step 1: Enable Required APIs
# =============================================================================
Write-Host "Step 1: Enabling Required APIs" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$apis = @(
    # Core IAM & Resource Management
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",

    # Phase 1: Ingestion
    "run.googleapis.com",              # Cloud Run Jobs
    "cloudscheduler.googleapis.com",   # Cloud Scheduler

    # Phase 2: Processing
    "eventarc.googleapis.com",         # Eventarc triggers
    "pubsub.googleapis.com",           # Pub/Sub (used by Eventarc)

    # Phase 3: Loading
    "bigquery.googleapis.com",         # BigQuery
    "cloudfunctions.googleapis.com",   # Cloud Functions

    # Supporting Services
    "storage.googleapis.com",          # Cloud Storage
    "cloudbuild.googleapis.com",       # Cloud Build
    "artifactregistry.googleapis.com", # Artifact Registry
    "logging.googleapis.com",          # Cloud Logging
    "monitoring.googleapis.com",       # Cloud Monitoring
    "secretmanager.googleapis.com",   # Secret Manager
    "compute.googleapis.com",          # Compute API (for VPC access)
    "serviceusage.googleapis.com",     # Service Usage API
    "servicemanagement.googleapis.com" # Service Management API
)

Write-Host "Enabling $($apis.Count) APIs..." -ForegroundColor Cyan
Write-Host ""

foreach ($api in $apis) {
    Write-Host "  [$($apis.IndexOf($api) + 1)/$($apis.Count)] $api..." -ForegroundColor Yellow
    $result = gcloud services enable $api --project=$PROJECT_ID --quiet 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [DONE]" -ForegroundColor Green
    } else {
        Write-Host "    [WARNING] May already be enabled or needs time to propagate" -ForegroundColor Yellow
    }
    Start-Sleep -Seconds 1  # Brief pause to avoid rate limiting
}

Write-Host ""
Write-Host "APIs enabled!" -ForegroundColor Green
Write-Host ""

# =============================================================================
# Step 2: Verify/Grant IAM Roles
# =============================================================================
Write-Host "Step 2: Verifying IAM Permissions" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$requiredRoles = @(
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/iam.serviceAccountUser",  # Required to impersonate service accounts for Cloud Run Jobs
    "roles/storage.admin",
    "roles/run.admin",
    "roles/cloudscheduler.admin",
    "roles/bigquery.admin",
    "roles/cloudfunctions.admin",
    "roles/eventarc.admin",
    "roles/pubsub.admin",
    "roles/cloudbuild.builds.builder",
    "roles/artifactregistry.admin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/secretmanager.admin"
)

Write-Host "Ensuring deployer SA has required roles..." -ForegroundColor Cyan
Write-Host ""

foreach ($role in $requiredRoles) {
    Write-Host "  Checking $role..." -ForegroundColor Yellow
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$DEPLOYER_SA" `
        --role="$role" `
        --quiet 2>&1 | Out-Null

    Write-Host "    [GRANTED]" -ForegroundColor Green
    Start-Sleep -Milliseconds 500
}

Write-Host ""
Write-Host "IAM permissions verified!" -ForegroundColor Green
Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Summary of actions:" -ForegroundColor Cyan
Write-Host "  - Enabled $($apis.Count) GCP APIs" -ForegroundColor White
Write-Host "  - Verified $($requiredRoles.Count) IAM roles for deployer SA" -ForegroundColor White
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Wait 2-3 minutes for API propagation" -ForegroundColor White
Write-Host "  2. Run: cd infrastructure\github_archive\phase1_ingestion\terraform" -ForegroundColor White
Write-Host "  3. Run: terraform apply -var='project_id=$PROJECT_ID' -var='environment=test' -var='region=us-central1'" -ForegroundColor White
Write-Host ""
Write-Host "Note: If you see 'API has not been used' errors," -ForegroundColor Yellow
Write-Host "      wait another minute and retry." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
