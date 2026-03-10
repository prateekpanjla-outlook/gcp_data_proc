# Enable Required APIs for GitHub Archive Infrastructure
$PROJECT_ID = "beaming-glyph-489707-b8"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Enabling Required GCP APIs" -ForegroundColor Cyan
Write-Host "Project: $PROJECT_ID" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# All required APIs for the 3-phase GitHub Archive infrastructure
$apis = @(
    # Core IAM & Resource Management
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",

    # Phase 1: Ingestion
    "run.googleapis.com",              # Cloud Run Jobs
    "cloudscheduler.googleapis.com",   # Cloud Scheduler

    # Phase 2: Processing
    "eventarc.googleapis.com",         # Eventarc triggers
    "pubsub.googleapis.com",           # Pub/Sub (used by Eventarc)

    # Phase 3: Loading
    "bigquery.googleapis.com",         # BigQuery
    "cloudfunctions.googleapis.com",   # Cloud Functions

    # Supporting Services
    "storage.googleapis.com",          # Cloud Storage (should be enabled by default)
    "cloudbuild.googleapis.com",       # Cloud Build (for deploying containers)
    "artifactregistry.googleapis.com", # Artifact Registry (container images)
    "logging.googleapis.com",          # Cloud Logging
    "monitoring.googleapis.com",       # Cloud Monitoring
    "secretmanager.googleapis.com"     # Secret Manager (if needed)
)

Write-Host "Enabling $($apis.Count) APIs..." -ForegroundColor Yellow
Write-Host ""

foreach ($api in $apis) {
    Write-Host "  Enabling $api..." -ForegroundColor Yellow
    $result = gcloud services enable $api --project=$PROJECT_ID --quiet 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Host "    [DONE]" -ForegroundColor Green
    } else {
        Write-Host "    [WARNING] $result" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "APIs enabled successfully!" -ForegroundColor Green
Write-Host "Note: Some APIs may take a few minutes to" -ForegroundColor Green
Write-Host "      fully propagate across GCP." -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
