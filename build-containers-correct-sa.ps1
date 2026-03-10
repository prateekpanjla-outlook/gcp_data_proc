# Build container image with proper service account specification
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building Container Images" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Use Cloud Build Service Agent instead of Compute Service Account
$CLOUDBUILD_SA = "service-$PROJECT_NUMBER@gcp-sa-cloudbuild.iam.gserviceaccount.com"

Write-Host "Using Cloud Build Service Agent:" -ForegroundColor Yellow
Write-Host "  $CLOUDBUILD_SA" -ForegroundColor Cyan
Write-Host ""

$sourceDir = Join-Path $SCRIPT_DIR "src\github_archive\phase1_ingestion"
$configFile = Join-Path $SCRIPT_DIR "config\cloudbuild-phase1.yaml"
$imageName = "gcr.io/$PROJECT_ID/github-archive-downloader:latest"

Write-Host "Building Phase 1: GitHub Archive Downloader..." -ForegroundColor Yellow
Write-Host "Source: $sourceDir" -ForegroundColor Cyan
Write-Host "Config: $configFile" -ForegroundColor Cyan
Write-Host "Image: $imageName" -ForegroundColor Cyan
Write-Host ""

# Build using Cloud Build with explicit service account
Write-Host "Triggering Cloud Build..." -ForegroundColor Cyan

$logsBucket = "gs://${PROJECT_ID}_cloudbuild/logs"

$buildResult = gcloud builds submit $sourceDir `
    --config $configFile `
    --project $PROJECT_ID `
    --service-account=$CLOUDBUILD_SA `
    --log-bucket=$logsBucket `
    --quiet 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build successful!" -ForegroundColor Green
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
