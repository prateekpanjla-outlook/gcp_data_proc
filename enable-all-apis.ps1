# Enable all required APIs for GitHub Archive infrastructure
$PROJECT_ID = "beaming-glyph-489707-b8"

Write-Host "Enabling all required APIs..." -ForegroundColor Cyan

$apis = @(
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "bigquery.googleapis.com",
    "cloudfunctions.googleapis.com"
)

foreach ($api in $apis) {
    Write-Host "Enabling $api..." -ForegroundColor Yellow
    gcloud services enable $api --project=$PROJECT_ID --quiet 2>&1 | Out-Null
    Write-Host "  [DONE]" -ForegroundColor Green
}

Write-Host ""
Write-Host "All APIs enabled successfully!" -ForegroundColor Green
