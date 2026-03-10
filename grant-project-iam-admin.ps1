# Grant Project IAM Admin role to deployer
$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "Granting Project IAM Admin role to deployer..." -ForegroundColor Cyan

gcloud projects add-iam-policy-binding $PROJECT_ID `
    --member="serviceAccount:$DEPLOYER_SA" `
    --role="roles/resourcemanager.projectIamAdmin" `
    --quiet

Write-Host "Role granted successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "The deployer now has permission to manage project-level IAM policies." -ForegroundColor Yellow
