# Fix Terraform State Conflicts
# Usage: .\fix-terraform-conflicts.ps1 -ProjectId "beaming-glyph-489707-b8"
#
# This script imports existing GCP resources into Terraform state
# to resolve Error 409 (already exists) conflicts

param(
    [string]$ProjectId = "beaming-glyph-489707-b8",
    [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Fixing Terraform State Conflicts" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Project: $ProjectId" -ForegroundColor Yellow
Write-Host "Region:  $Region" -ForegroundColor Yellow
Write-Host ""

# Change to terraform directory
$scriptDir = Split-Path -Parent $PSCommandPath
$terraformDir = Join-Path $scriptDir "..\terraform"
Set-Location $terraformDir

Write-Host "Working directory: $(Get-Location)" -ForegroundColor Gray
Write-Host ""

# Initialize terraform if needed
Write-Host "Step 1: Initializing Terraform..." -ForegroundColor Yellow
terraform init
Write-Host "✓ Terraform initialized" -ForegroundColor Green
Write-Host ""

# Check and import Artifact Registry Repository
Write-Host "Step 2: Checking Artifact Registry Repository..." -ForegroundColor Yellow
$repoResource = "google_artifact_registry_repository.data_pipeline_repo"
$repoExists = terraform state list 2>$null | Select-String -Pattern "^$repoResource$"

if ($repoExists) {
    Write-Host "  ℹ Repository already in state, skipping import" -ForegroundColor Cyan
} else {
    Write-Host "  Importing repository into state..." -ForegroundColor Cyan
    $repoPath = "projects/$ProjectId/locations/$Region/repositories/data-pipeline-repo"

    try {
        terraform import $repoResource $repoPath 2>&1 | Out-Null
        Write-Host "  ✓ Repository imported successfully" -ForegroundColor Green
    } catch {
        Write-Host "  ⚠ Import failed (repository may not exist yet)" -ForegroundColor Yellow
        Write-Host "  Error: $_" -ForegroundColor Gray
    }
}
Write-Host ""

# Check and import Service Accounts
Write-Host "Step 3: Checking Service Accounts..." -ForegroundColor Yellow
$serviceAccounts = @(
    @{Resource="google_service_account.github_archive_downloader"; Email="github-archive-downloader"},
    @{Resource="google_service_account.github_archive_processor"; Email="github-archive-processor"},
    @{Resource="google_service_account.github_archive_bq_loader"; Email="github-archive-bq-loader"},
    @{Resource="google_service_account.processor_eventarc_invoker"; Email="processor-eventarc-invoker"},
    @{Resource="google_service_account.bq_loader_eventarc_invoker"; Email="bq-loader-eventarc-invoker"}
)

foreach ($sa in $serviceAccounts) {
    $resource = $sa.Resource
    $email = "$($sa.Email)@$ProjectId.iam.gserviceaccount.com"

    $saExists = terraform state list 2>$null | Select-String -Pattern "^$resource$"

    if ($saExists) {
        Write-Host "  ℹ $resource already in state, skipping" -ForegroundColor Cyan
    } else {
        Write-Host "  Importing $resource..." -ForegroundColor Cyan
        $saPath = "projects/$ProjectId/serviceAccounts/$email"

        try {
            terraform import $resource $saPath 2>&1 | Out-Null
            Write-Host "  ✓ Imported successfully" -ForegroundColor Green
        } catch {
            Write-Host "  ⚠ Import failed (may not exist yet)" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# Verify with terraform plan
Write-Host "Step 4: Running Terraform Plan to verify..." -ForegroundColor Yellow
Write-Host ""

$planResult = terraform plan `
    -var="project_id=$ProjectId" `
    -var="environment=test" `
    -var="region=$Region" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ State conflicts resolved!" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run:" -ForegroundColor Yellow
    Write-Host "  terraform apply -var=`"project_id=$ProjectId`" -var=`"environment=test`" -var=`"region=$Region`"" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "⚠ There may still be conflicts. Review the plan output above." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Alternative: Delete conflicting resources and recreate:" -ForegroundColor Yellow
    Write-Host "  .\cleanup-terraform-conflicts.ps1 -ProjectId $ProjectId" -ForegroundColor White
    Write-Host ""
    Write-Host "Plan output:" -ForegroundColor Gray
    Write-Host $planResult -ForegroundColor Gray
}
