# Fix Terraform State Conflicts
# Usage: .\fix-terraform-conflicts.ps1 -ProjectId "beaming-glyph-489707-b8"
#
# This script imports existing GCP resources into Terraform state

param(
    [string]$ProjectId = "beaming-glyph-489707-b8",
    [string]$Region = "us-central1",
    [string]$Environment = "test"
)

Write-Host "Fixing Terraform State Conflicts" -ForegroundColor Cyan
Write-Host "Project: $ProjectId" -ForegroundColor Yellow
Write-Host "Environment: $Environment" -ForegroundColor Yellow
Write-Host ""

# Change to script directory
$scriptDir = Split-Path -Parent $PSCommandPath
Set-Location $scriptDir

# Initialize terraform
Write-Host "Step 1: Initializing Terraform..." -ForegroundColor Yellow
terraform init
Write-Host "✓ Terraform initialized" -ForegroundColor Green
Write-Host ""

# Import Artifact Registry Repository
Write-Host "Step 2: Importing Artifact Registry Repository..." -ForegroundColor Yellow
$repoResource = "google_artifact_registry_repository.data_pipeline_repo"
$repoPath = "projects/$ProjectId/locations/$Region/repositories/data-pipeline-repo"

$output = terraform import $repoResource $repoPath 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Repository imported" -ForegroundColor Green
} else {
    Write-Host "  ℹ Repository import result: $output" -ForegroundColor Gray
}
Write-Host ""

# Import Service Accounts (with environment prefix)
Write-Host "Step 3: Importing Service Accounts..." -ForegroundColor Yellow
$serviceAccounts = @(
    @{Resource="google_service_account.github_archive_downloader"; Name="$Environment-github-archive-downloader"},
    @{Resource="google_service_account.scheduler"; Name="$Environment-scheduler"}
)

foreach ($sa in $serviceAccounts) {
    $resource = $sa.Resource
    $saName = $sa.Name
    $saEmail = "$saName@$ProjectId.iam.gserviceaccount.com"
    $saPath = "projects/$ProjectId/serviceAccounts/$saEmail"

    Write-Host "  Importing $saName..." -ForegroundColor Cyan
    $output = terraform import $resource $saPath 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ Imported" -ForegroundColor Green
    } else {
        Write-Host "  ℹ Result: $output" -ForegroundColor Gray
    }
}
Write-Host ""

# Run terraform plan
Write-Host "Step 4: Running Terraform Plan..." -ForegroundColor Yellow
terraform plan -var="project_id=$ProjectId" -var="environment=$Environment" -var="region=$Region"

Write-Host ""
Write-Host "✅ Done! Now run:" -ForegroundColor Green
Write-Host "  terraform apply -var=`"project_id=$ProjectId`" -var=`"environment=$Environment`" -var=`"region=$Region`"" -ForegroundColor White
