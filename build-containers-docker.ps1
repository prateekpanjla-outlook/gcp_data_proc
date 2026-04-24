# Build and push container image using Docker (simpler approach)
$PROJECT_ID = "beaming-glyph-489707-b8"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Building Container with Docker" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$sourceDir = Join-Path $SCRIPT_DIR "src\github_archive\phase1_ingestion"
$imageName = "us-central1-docker.pkg.dev/$PROJECT_ID/data-pipeline/github-archive-downloader:latest"

Write-Host "Building image..." -ForegroundColor Yellow
Write-Host "Source: $sourceDir" -ForegroundColor Cyan
Write-Host "Image: $imageName" -ForegroundColor Cyan
Write-Host ""

# Build the image
Push-Location $sourceDir
docker build -t $imageName .

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "Pushing image to GCR..." -ForegroundColor Yellow

    # Push the image
    gcloud auth configure-docker gcr.io --quiet
    docker push $imageName

    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "Image built and pushed successfully!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Image: $imageName" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "You can now run terraform apply:" -ForegroundColor Yellow
        Write-Host "  cd infrastructure\github_archive\phase1_ingestion\terraform" -ForegroundColor White
        Write-Host "  terraform apply -var='project_id=$PROJECT_ID' -var='environment=test' -var='region=us-central1'" -ForegroundColor White
    } else {
        Write-Host "Failed to push image!" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Failed to build image!" -ForegroundColor Red
    exit 1
}

Pop-Location
