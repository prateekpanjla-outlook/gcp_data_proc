# Grant Container Registry (GCR) permissions to Cloud Build SA
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$CLOUD_BUILD_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

Write-Host "Granting Container Registry permissions to Cloud Build SA..." -ForegroundColor Cyan

# For GCR (gcr.io), use the Cloud Build Service Agent role which has GCR write access
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CLOUD_BUILD_SA" `
    --role="roles/cloudbuild.builds.builder" `
    --quiet

Write-Host "Permissions granted!" -ForegroundColor Green
Write-Host ""
Write-Host "Note: GCR (gcr.io) uses the cloudbuild.builds.builder role" -ForegroundColor Yellow
Write-Host "      for push permissions." -ForegroundColor Yellow
