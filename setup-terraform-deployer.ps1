# Terraform Deployer Setup Script for Windows
# Run this script with: .\setup-terraform-deployer.ps1

$ErrorActionPreference = "Stop"

# Configuration
$PROJECT_ID = "beaming-glyph-489707-b8"
$ENVIRONMENT = "test"
$DEPLOYER_SA_ID = "$ENVIRONMENT-terraform-deployer"
$DEPLOYER_SA_EMAIL = "$DEPLOYER_SA_ID@$PROJECT_ID.iam.gserviceaccount.com"
$KEY_FILE = "$DEPLOYER_SA_ID-key.json"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Terraform Deployer Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration:" -ForegroundColor White
Write-Host "  Project ID:       $PROJECT_ID"
Write-Host "  Environment:      $ENVIRONMENT"
Write-Host "  Deployer SA:      $DEPLOYER_SA_EMAIL"
Write-Host ""

# Check if SA exists
Write-Host "Checking if service account exists..." -ForegroundColor Yellow
$saExists = $null
try {
    $saExists = gcloud iam service-accounts describe $DEPLOYER_SA_EMAIL --project=$PROJECT_ID 2>&1
    if ($LASTEXITCODE -eq 0) {
        $saExists = $true
    }
} catch {
    $saExists = $false
}

if ($saExists) {
    Write-Host "[WARNING] Service account $DEPLOYER_SA_EMAIL already exists" -ForegroundColor Yellow
    $recreate = Read-Host "Do you want to recreate it? This will revoke existing permissions. (y/N)"

    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Write-Host "[INFO] Deleting existing service account..." -ForegroundColor Yellow
        gcloud iam service-accounts delete $DEPLOYER_SA_EMAIL --project=$PROJECT_ID --quiet
        Write-Host "[INFO] Creating new service account..." -ForegroundColor Yellow
        gcloud iam service-accounts create $DEPLOYER_SA_ID `
            --display-name="$ENVIRONMENT Terraform Deployer" `
            --description="Service account for deploying GitHub Archive infrastructure with Terraform" `
            --project=$PROJECT_ID
        Write-Host "[SUCCESS] Service account recreated" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Keeping existing service account" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] Creating service account: $DEPLOYER_SA_EMAIL" -ForegroundColor Yellow
    gcloud iam service-accounts create $DEPLOYER_SA_ID `
        --display-name="$ENVIRONMENT Terraform Deployer" `
        --description="Service account for deploying GitHub Archive infrastructure with Terraform" `
        --project=$PROJECT_ID
    Write-Host "[SUCCESS] Service account created" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Granting IAM Roles" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Core IAM roles
$roles = @(
    "roles/compute.admin",
    "roles/run.admin",
    "roles/cloudfunctions.admin",
    "roles/storage.admin",
    "roles/bigquery.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
    "roles/resourcemanager.projectIamAdmin",
    "roles/cloudscheduler.admin",
    "roles/eventarc.admin",
    "roles/pubsub.admin",
    "roles/cloudbuild.builds.builder",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/artifactregistry.admin",
    "roles/secretmanager.admin",
    "roles/viewer"
)

foreach ($role in $roles) {
    Write-Host "Granting $role..." -ForegroundColor Yellow
    $result = gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$DEPLOYER_SA_EMAIL" `
        --role="$role" `
        --quiet 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "[SUCCESS] $role granted" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Failed to grant $role (may already exist)" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Enabling Required APIs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$apis = @(
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "compute.googleapis.com",
    "run.googleapis.com",
    "cloudfunctions.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "cloudbuild.googleapis.com",
    "servicemanagement.googleapis.com",
    "serviceusage.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "Enabling $api..." -ForegroundColor Yellow
    gcloud services enable $api --project=$PROJECT_ID --quiet 2>&1 | Out-Null
    Write-Host "[SUCCESS] $api enabled" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Generating Service Account Key" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (Test-Path $KEY_FILE) {
    Write-Host "[WARNING] Key file $KEY_FILE already exists" -ForegroundColor Yellow
    $overwrite = Read-Host "Do you want to overwrite it? The old key will be invalidated. (y/N)"

    if ($overwrite -eq "y" -or $overwrite -eq "Y") {
        Write-Host "[INFO] Backing up old key to ${KEY_FILE}.backup..." -ForegroundColor Yellow
        Copy-Item $KEY_FILE "$KEY_FILE.backup"
        Write-Host "[INFO] Creating new key file..." -ForegroundColor Yellow
        gcloud iam service-accounts keys create $KEY_FILE `
            --iam-account=$DEPLOYER_SA_EMAIL `
            --project=$PROJECT_ID
        Write-Host "[SUCCESS] New key created (old key backed up)" -ForegroundColor Green
    } else {
        Write-Host "[INFO] Keeping existing key file" -ForegroundColor Yellow
    }
} else {
    Write-Host "[INFO] Creating key file: $KEY_FILE" -ForegroundColor Yellow
    gcloud iam service-accounts keys create $KEY_FILE `
        --iam-account=$DEPLOYER_SA_EMAIL `
        --project=$PROJECT_ID
    Write-Host "[SUCCESS] Key file created: $KEY_FILE" -ForegroundColor Green
}

# Set secure permissions on Windows
icacls $KEY_FILE /inheritance:r
icacls $KEY_FILE /grant:r "${env:USERNAME}:(RD,WA)"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Service Account Key Location:" -ForegroundColor Green
Write-Host "  File: $KEY_FILE"
Write-Host "  Path: $(Get-Location)\$KEY_FILE"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host ""
Write-Host "1. Set the environment variable (required for Terraform):"
Write-Host "   `$env:GOOGLE_APPLICATION_CREDENTIALS=`"`$(Get-Location)\$KEY_FILE`""
Write-Host ""
Write-Host "2. Verify authentication works:"
Write-Host "   gcloud auth application-default print-access-token"
Write-Host ""
Write-Host "3. Deploy infrastructure:"
Write-Host "   .\infrastructure\deploy-all.sh"
Write-Host ""
Write-Host "[WARNING] CRITICAL SECURITY REMINDERS:" -ForegroundColor Yellow
Write-Host "  - Add '$KEY_FILE' to .gitignore immediately"
Write-Host "  - Store this key file securely (it contains sensitive credentials)"
Write-Host "  - NEVER commit this file to version control"
Write-Host "  - Rotate keys regularly (recommended: every 90 days)"
Write-Host ""
