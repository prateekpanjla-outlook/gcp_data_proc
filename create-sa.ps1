# Create Terraform Deployer Service Account
$ErrorActionPreference = "Stop"

$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA_ID = "test-terraform-deployer"
$DEPLOYER_SA_EMAIL = "$DEPLOYER_SA_ID@$PROJECT_ID.iam.gserviceaccount.com"

# Set active account
Write-Host "Setting active account..." -ForegroundColor Yellow
gcloud config set account prateek.panjla.outlook@gmail.com

# Verify project access
Write-Host "Verifying project access..." -ForegroundColor Yellow
gcloud projects describe $PROJECT_ID

# Check if SA already exists
Write-Host ""
Write-Host "Checking if service account exists..." -ForegroundColor Yellow
try {
    $saCheck = gcloud iam service-accounts describe $DEPLOYER_SA_EMAIL --project=$PROJECT_ID 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Service account not found"
    }
    Write-Host "[WARNING] Service account $DEPLOYER_SA_EMAIL already exists" -ForegroundColor Yellow
    $recreate = Read-Host "Do you want to recreate it? (y/N)"
    if ($recreate -eq "y" -or $recreate -eq "Y") {
        Write-Host "Deleting existing service account..." -ForegroundColor Yellow
        gcloud iam service-accounts delete $DEPLOYER_SA_EMAIL --project=$PROJECT_ID --quiet
    } else {
        Write-Host "Keeping existing service account" -ForegroundColor Green
        exit 0
    }
} catch {
    Write-Host "Service account does not exist yet (this is expected)" -ForegroundColor Green
}

# Create service account
Write-Host ""
Write-Host "Creating service account: $DEPLOYER_SA_EMAIL" -ForegroundColor Cyan
gcloud iam service-accounts create $DEPLOYER_SA_ID `
  --display-name="Test Terraform Deployer" `
  --description="Service account for deploying GitHub Archive infrastructure with Terraform" `
  --project=$PROJECT_ID

Write-Host "[SUCCESS] Service account created!" -ForegroundColor Green

# Grant basic roles
Write-Host ""
Write-Host "Granting IAM roles..." -ForegroundColor Cyan

$basicRoles = @(
    "roles/editor",
    "roles/iam.serviceAccountUser",
    "roles/storage.admin",
    "roles/bigquery.admin",
    "roles/run.admin",
    "roles/cloudfunctions.admin"
)

foreach ($role in $basicRoles) {
    Write-Host "  Granting $role..." -ForegroundColor Yellow
    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$DEPLOYER_SA_EMAIL" `
        --role="$role" `
        --quiet 2>&1 | Out-Null
}

Write-Host "[SUCCESS] Basic IAM roles granted" -ForegroundColor Green

# Generate key
Write-Host ""
Write-Host "Generating service account key..." -ForegroundColor Cyan
$KEY_FILE = "test-terraform-deployer-key.json"

if (Test-Path $KEY_FILE) {
    Write-Host "[WARNING] Key file exists. Backing up..." -ForegroundColor Yellow
    Copy-Item $KEY_FILE "$KEY_FILE.backup"
}

gcloud iam service-accounts keys create $KEY_FILE `
    --iam-account=$DEPLOYER_SA_EMAIL `
    --project=$PROJECT_ID

Write-Host "[SUCCESS] Key file created: $KEY_FILE" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Service Account Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Service Account: $DEPLOYER_SA_EMAIL"
Write-Host "Key File:       $KEY_FILE"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Set environment variable:"
Write-Host "     `$env:GOOGLE_APPLICATION_CREDENTIALS='$(Get-Location)\$KEY_FILE'"
Write-Host ""
Write-Host "  2. Verify authentication:"
Write-Host "     gcloud auth application-default print-access-token"
Write-Host ""
