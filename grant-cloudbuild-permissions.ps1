# Grant Cloud Storage permissions to Cloud Build service account
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$CLOUD_BUILD_SA = "serviceAccount:$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

Write-Host "Granting Cloud Storage permissions to Cloud Build SA..." -ForegroundColor Cyan

# Grant Storage Object Viewer to read source code
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="$CLOUD_BUILD_SA" `
    --role="roles/storage.objectViewer" `
    --quiet

# Grant Storage Object Admin to write build artifacts
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="$CLOUD_BUILD_SA" `
    --role="roles/storage.objectAdmin" `
    --quiet

Write-Host "Permissions granted successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "The Cloud Build service account can now:" -ForegroundColor Yellow
Write-Host "  - Read source code from Cloud Storage" -ForegroundColor White
Write-Host "  - Write build artifacts to Cloud Storage" -ForegroundColor White
