# =============================================================================
# Pre-flight Validation Script
# =============================================================================
# This script checks if all prerequisites are met BEFORE running Terraform
# to avoid partial deployments and confusing errors.
#
# Usage:
#   .\preflight-check.ps1
# =============================================================================

$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Pre-flight Validation" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$errors = 0
$warnings = 0

# =============================================================================
# Check 1: Required APIs
# =============================================================================
Write-Host "Check 1: Required APIs" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$requiredApis = @(
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "cloudfunctions.googleapis.com",
    "storage.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com"
)

Write-Host "Checking $($requiredApis.Count) required APIs..." -ForegroundColor Cyan

$enabledApis = gcloud services list --enabled --project=$PROJECT_ID --format=json | ConvertFrom-Json

foreach ($api in $requiredApis) {
    $is_enabled = $enabledApis | Where-Object { $_.name -eq "projects/$PROJECT_ID/services/$api" }

    if ($is_enabled) {
        Write-Host "  [OK] $api" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $api" -ForegroundColor Red
        $errors++
    }
}

Write-Host ""

# =============================================================================
# Check 2: IAM Permissions for Deployer SA
# =============================================================================
Write-Host "Check 2: IAM Permissions" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

Write-Host "Checking deployer SA has required roles..." -ForegroundColor Cyan

# Get project IAM policy
$policy = gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json

# Required roles
$requiredRoles = @(
    "roles/iam.serviceAccountAdmin",
    "roles/resourcemanager.projectIamAdmin",
    "roles/storage.admin",
    "roles/run.admin",
    "roles/cloudscheduler.admin"
)

foreach ($role in $requiredRoles) {
    $binding = $policy.bindings | Where-Object { $_.role -eq $role }
    $hasRole = $binding -and $binding.members -contains "serviceAccount:$DEPLOYER_SA"

    if ($hasRole) {
        Write-Host "  [OK] $role" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $role" -ForegroundColor Red
        $errors++
    }
}

Write-Host ""

# =============================================================================
# Check 3: Authentication
# =============================================================================
Write-Host "Check 3: Authentication" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$keyFile = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json"

if (Test-Path $keyFile) {
    Write-Host "  [OK] Service account key exists" -ForegroundColor Green

    # Test if we can authenticate
    $env:GOOGLE_APPLICATION_CREDENTIALS = $keyFile
    $token = gcloud auth application-default print-access-token 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Can authenticate with service account" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Cannot authenticate with service account" -ForegroundColor Red
        $errors++
    }
} else {
    Write-Host "  [ERROR] Service account key not found at: $keyFile" -ForegroundColor Red
    $errors++
}

Write-Host ""

# =============================================================================
# Check 4: Terraform Installation
# =============================================================================
Write-Host "Check 4: Terraform Installation" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

try {
    $tfVersion = terraform version -json | ConvertFrom-Json
    Write-Host "  [OK] Terraform installed: $($tfVersion.terraform_version)" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] Terraform not installed or not in PATH" -ForegroundColor Red
    $errors++
}

Write-Host ""

# =============================================================================
# Summary
# =============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Pre-flight Check Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($errors -eq 0) {
    Write-Host "Status: ALL CHECKS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run Terraform apply:" -ForegroundColor Yellow
    Write-Host "  cd infrastructure\github_archive\phase1_ingestion\terraform" -ForegroundColor White
    Write-Host "  terraform apply -var='project_id=$PROJECT_ID' -var='environment=test' -var='region=us-central1'" -ForegroundColor White
    Write-Host ""
    exit 0
} else {
    Write-Host "Status: FAILED - $errors error(s) found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please fix the errors above before running Terraform." -ForegroundColor Red
    Write-Host ""
    Write-Host "Quick fix: Run .\setup-complete.ps1 to enable APIs and grant permissions" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
