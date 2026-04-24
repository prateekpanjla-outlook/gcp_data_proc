# Grant Logging permissions to Cloud Build service account
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$CLOUD_BUILD_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

Write-Host "Granting Logging permissions to Cloud Build SA..." -ForegroundColor Cyan

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CLOUD_BUILD_SA" `
    --role="roles/logging.logWriter" `
    --quiet

Write-Host "Permissions granted successfully!" -ForegroundColor Green
