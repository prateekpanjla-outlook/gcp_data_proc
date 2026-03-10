# Grant Artifact Registry permissions to Cloud Build SA
$PROJECT_ID = "beaming-glyph-489707-b8"
$PROJECT_NUMBER = "592311283460"
$CLOUD_BUILD_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

Write-Host "Granting Artifact Registry permissions to Cloud Build SA..." -ForegroundColor Cyan

# Grant Artifact Registry Writer to push images
gcloud artifacts repositories add-iam-policy-binding docker `
    --location=us-central1 `
    --project=$PROJECT_ID `
    --member="serviceAccount:$CLOUD_BUILD_SA" `
    --role="roles/artifactregistry.writer" `
    --quiet 2>&1 | Out-Null

# Or grant project-level Artifact Admin
gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$CLOUD_BUILD_SA" `
    --role="roles/artifactregistry.creator" `
    --quiet

Write-Host "Permissions granted successfully!" -ForegroundColor Green
Write-Host "The Cloud Build SA can now push images to Artifact Registry" -ForegroundColor Yellow
