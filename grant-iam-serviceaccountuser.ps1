# Grant Service Account User role to deployer
# This allows the deployer SA to impersonate other service accounts
$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "Granting Service Account User role to deployer..." -ForegroundColor Cyan
Write-Host "This allows impersonation of service accounts created by Terraform" -ForegroundColor Yellow
Write-Host ""

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$DEPLOYER_SA" `
    --role="roles/iam.serviceAccountUser" `
    --quiet

Write-Host "Role granted successfully!" -ForegroundColor Green
