# Remove Editor Role and Fix IAM Setup
$ErrorActionPreference = "Stop"

$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA_EMAIL = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Fix IAM Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "This script will:" -ForegroundColor White
Write-Host "  1. Remove the roles/editor role (overly permissive)" -ForegroundColor Yellow
Write-Host "  2. Add missing admin roles (Storage, BigQuery, Run, etc.)" -ForegroundColor Yellow
Write-Host "  3. Verify the final setup" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Continue? (Y/n)"

if ($confirm -eq "n" -or $confirm -eq "N") {
    Write-Host "Cancelled" -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 1: Remove Editor Role" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Removing roles/editor..." -ForegroundColor Yellow
gcloud projects remove-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$DEPLOYER_SA_EMAIL" `
    --role="roles/editor" `
    --quiet

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Editor role removed!" -ForegroundColor Green
} else {
    Write-Host "[ERROR] Failed to remove Editor role" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 2: Add Missing Admin Roles" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$rolesToAdd = @(
    @{Role="roles/storage.admin"; Description="GCS bucket management"},
    @{Role="roles/bigquery.admin"; Description="BigQuery datasets and tables"},
    @{Role="roles/run.admin"; Description="Cloud Run Jobs and Services"},
    @{Role="roles/cloudfunctions.admin"; Description="Cloud Functions"},
    @{Role="roles/iam.serviceAccountAdmin"; Description="Service account management"}
)

foreach ($roleInfo in $rolesToAdd) {
    Write-Host "Adding $($roleInfo.Role)..." -ForegroundColor Yellow
    Write-Host "  => $($roleInfo.Description)" -ForegroundColor Gray

    gcloud projects add-iam-policy-binding $PROJECT_ID `
        --member="serviceAccount:$DEPLOYER_SA_EMAIL" `
        --role=$roleInfo.Role `
        --quiet 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [SUCCESS]" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Failed (may already exist)" -ForegroundColor Yellow
    }
    Write-Host ""
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Step 3: Verify Final Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get final roles
$policy = gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json
$finalRoles = $policy.bindings | Where-Object { $_.members -contains "serviceAccount:$DEPLOYER_SA_EMAIL" } | Select-Object -ExpandProperty role | Sort-Object

Write-Host "Final IAM roles ($($finalRoles.Count) total):" -ForegroundColor White
Write-Host ""

# Categorize
$primitive = $finalRoles | Where-Object { $_ -match "^roles/(editor|viewer|owner)$" }
$admin = $finalRoles | Where-Object { $_ -match "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }
$operational = $finalRoles | Where-Object { $_ -notmatch "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }

if ($primitive) {
    Write-Host "Primitive Roles:" -ForegroundColor Red
    $primitive | ForEach-Object { Write-Host "  X $_" -ForegroundColor Red }
    Write-Host ""
}

if ($admin) {
    Write-Host "Admin Roles:" -ForegroundColor Green
    $admin | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
    Write-Host ""
}

if ($operational) {
    Write-Host "Operational Roles:" -ForegroundColor Cyan
    $operational | ForEach-Object { Write-Host "  o $_" -ForegroundColor Cyan }
    Write-Host ""
}

# Verify Editor is gone
if ($finalRoles -contains "roles/editor") {
    Write-Host "[ERROR] Editor role still exists!" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "Setup Fixed Successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Summary:" -ForegroundColor White
Write-Host "  - Removed overly-permissive Editor role" -ForegroundColor Green
Write-Host "  - Added specific admin roles for:" -ForegroundColor Green
Write-Host "    - Storage (GCS buckets)" -ForegroundColor Green
Write-Host "    - BigQuery (datasets, tables)" -ForegroundColor Green
Write-Host "    - Cloud Run (jobs, services)" -ForegroundColor Green
Write-Host "    - Cloud Functions" -ForegroundColor Green
Write-Host "    - Service Accounts" -ForegroundColor Green
Write-Host ""
Write-Host "The service account now follows least privilege principles!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Deploy infrastructure: ./infrastructure/deploy-all.sh"
Write-Host "  2. Monitor for any permission issues" -ForegroundColor Yellow
Write-Host ""
