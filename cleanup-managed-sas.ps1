# Delete manually created service accounts so Terraform can recreate them
$PROJECT_ID = "beaming-glyph-489707-b8"

Write-Host "Deleting manually created service accounts..." -ForegroundColor Cyan

$serviceAccounts = @(
    "test-github-archive-downloader",
    "test-scheduler"
)

foreach ($saId in $serviceAccounts) {
    $saEmail = "$saId@$PROJECT_ID.iam.gserviceaccount.com"
    Write-Host "Deleting $saEmail..." -ForegroundColor Yellow

    gcloud iam service-accounts delete $saEmail `
        --project=$PROJECT_ID `
        --quiet 2>&1 | Out-Null

    Write-Host "  [DELETED]" -ForegroundColor Green
}

Write-Host ""
Write-Host "Service accounts deleted! Terraform can now create them." -ForegroundColor Green
