# Clean Up Terraform Conflicts (Destructive)
# Usage: .\cleanup-terraform-conflicts.ps1 -ProjectId "beaming-glyph-489707-b8"
#
# WARNING: This script DELETES existing resources so Terraform can recreate them
# Use fix-terraform-conflicts.ps1 instead to preserve existing resources

param(
    [string]$ProjectId = "beaming-glyph-489707-b8",
    [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Red
Write-Host "⚠️  WARNING: DESTRUCTIVE CLEANUP" -ForegroundColor Red
Write-Host "=========================================" -ForegroundColor Red
Write-Host ""
Write-Host "This will DELETE the following resources in project: $ProjectId" -ForegroundColor Yellow
Write-Host ""
Write-Host "  - Artifact Registry Repository: data-pipeline-repo" -ForegroundColor White
Write-Host "  - Service Accounts:" -ForegroundColor White
Write-Host "    • github-archive-downloader" -ForegroundColor White
Write-Host "    • github-archive-processor" -ForegroundColor White
Write-Host "    • github-archive-bq-loader" -ForegroundColor White
Write-Host "    • processor-eventarc-invoker" -ForegroundColor White
Write-Host "    • bq-loader-eventarc-invoker" -ForegroundColor White
Write-Host ""
Write-Host "These resources will be RECREATED by Terraform" -ForegroundColor Yellow
Write-Host ""

$confirm = Read-Host "Type 'DELETE' to confirm and continue"
if ($confirm -ne "DELETE") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

Write-Host ""
Write-Host "Step 1: Deleting Artifact Registry Repository..." -ForegroundColor Yellow

# Delete artifact registry repository
try {
    $repoExists = gcloud artifacts repositories describe data-pipeline-repo `
        --location=$Region `
        --project=$ProjectId 2>$null

    if ($repoExists) {
        Write-Host "  Deleting data-pipeline-repo..." -ForegroundColor Cyan
        gcloud artifacts repositories delete data-pipeline-repo `
            --location=$Region `
            --project=$ProjectId `
            --quiet
        Write-Host "  ✓ Repository deleted" -ForegroundColor Green
    } else {
        Write-Host "  ℹ Repository doesn't exist, skipping" -ForegroundColor Cyan
    }
} catch {
    Write-Host "  ℹ Repository doesn't exist or already deleted" -ForegroundColor Cyan
}
Write-Host ""

Write-Host "Step 2: Deleting Service Accounts..." -ForegroundColor Yellow
$serviceAccounts = @(
    "github-archive-downloader",
    "github-archive-processor",
    "github-archive-bq-loader",
    "processor-eventarc-invoker",
    "bq-loader-eventarc-invoker"
)

foreach ($saName in $serviceAccounts) {
    $saEmail = "$saName@$ProjectId.iam.gserviceaccount.com"

    try {
        $saExists = gcloud iam service-accounts describe $saEmail --project=$ProjectId 2>$null

        if ($saExists) {
            Write-Host "  Deleting $saName..." -ForegroundColor Cyan
            gcloud iam service-accounts delete $saEmail `
                --project=$ProjectId `
                --quiet
            Write-Host "  ✓ $saName deleted" -ForegroundColor Green
        } else {
            Write-Host "  ℹ $saName doesn't exist, skipping" -ForegroundColor Cyan
        }
    } catch {
        Write-Host "  ℹ $saName doesn't exist or already deleted" -ForegroundColor Cyan
    }
}
Write-Host ""

Write-Host "Step 3: Cleaning Terraform State..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $PSCommandPath
$terraformDir = Join-Path $scriptDir "..\terraform"
Set-Location $terraformDir

# Remove from state if present
foreach ($saName in $serviceAccounts) {
    $resourceName = $saName -replace "-", "_"
    $resource = "google_service_account.$resourceName"

    $inState = terraform state list 2>$null | Select-String -Pattern "^$resource$"
    if ($inState) {
        Write-Host "  Removing $resource from state..." -ForegroundColor Cyan
        terraform state rm $resource 2>&1 | Out-Null
    }
}

$repoResource = "google_artifact_registry_repository.data_pipeline_repo"
$inState = terraform state list 2>$null | Select-String -Pattern "^$repoResource$"
if ($inState) {
    Write-Host "  Removing $repoResource from state..." -ForegroundColor Cyan
    terraform state rm $repoResource 2>&1 | Out-Null
}
Write-Host ""

Write-Host "=========================================" -ForegroundColor Green
Write-Host "✅ Cleanup Complete!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now run:" -ForegroundColor Yellow
Write-Host "  terraform apply -var=`"project_id=$ProjectId`" -var=`"environment=test`" -var=`"region=$Region`"" -ForegroundColor White
Write-Host ""
