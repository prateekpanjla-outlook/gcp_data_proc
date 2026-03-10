# =============================================================================
# Build Container Images using Cloud Build
# =============================================================================
# This script builds all required container images before running Terraform
#
# Usage:
#   .\build-containers.ps1
# =============================================================================

$PROJECT_ID = "beaming-glyph-489707-b8"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building Container Images" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# Build Phase 1: GitHub Archive Downloader
# =============================================================================
Write-Host "Building Phase 1: GitHub Archive Downloader..." -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

$sourceDir = Join-Path $SCRIPT_DIR "src\github_archive\phase1_ingestion"
$configFile = Join-Path $SCRIPT_DIR "config\cloudbuild-phase1.yaml"
$imageName = "gcr.io/$PROJECT_ID/github-archive-downloader:latest"

# Check if source exists
if (-not (Test-Path $sourceDir)) {
    Write-Host "ERROR: Source directory not found: $sourceDir" -ForegroundColor Red
    exit 1
}

Write-Host "Source: $sourceDir" -ForegroundColor Cyan
Write-Host "Config: $configFile" -ForegroundColor Cyan
Write-Host "Image: $imageName" -ForegroundColor Cyan
Write-Host ""

# Build using Cloud Build
Write-Host "Triggering Cloud Build..." -ForegroundColor Cyan

$buildResult = gcloud builds submit $sourceDir `
    --config $configFile `
    --project $PROJECT_ID `
    --quiet 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green

    # Extract build ID from output
    if ($buildResult -match 'BUILD_ID:\s*([^\r\n]+)') {
        $buildId = $matches[1]
        Write-Host "Build ID: $buildId" -ForegroundColor Cyan
    }

    Write-Host "Image: $imageName" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now run terraform apply:" -ForegroundColor Yellow
    Write-Host "  cd infrastructure\github_archive\phase1_ingestion\terraform" -ForegroundColor White
    Write-Host "  terraform apply -var='project_id=$PROJECT_ID' -var='environment=test' -var='region=us-central1'" -ForegroundColor White
} else {
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error output:" -ForegroundColor Yellow
    Write-Host $buildResult
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Container Build Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
