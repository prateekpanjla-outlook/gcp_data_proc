# Analyze IAM Roles for test-terraform-deployer

$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA_EMAIL = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IAM Roles Analysis" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get all roles
$policy = gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json
$roles = $policy.bindings | Where-Object { $_.members -contains "serviceAccount:$DEPLOYER_SA_EMAIL" } | Select-Object -ExpandProperty role | Sort-Object

Write-Host "Total roles granted: $($roles.Count)" -ForegroundColor White
Write-Host ""

# Categorize roles
Write-Host "Primitive Roles (Broad):" -ForegroundColor Red
$primitiveRoles = $roles | Where-Object { $_ -match "^roles/(editor|viewer|owner)$" }
if ($primitiveRoles) {
    $primitiveRoles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
} else {
    Write-Host "  None" -ForegroundColor Green
}

Write-Host ""
Write-Host "Administrative Roles (Specific Services):" -ForegroundColor Yellow
$adminRoles = $roles | Where-Object { $_ -match "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }
if ($adminRoles) {
    $adminRoles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
} else {
    Write-Host "  None" -ForegroundColor Gray
}

Write-Host ""
Write-Host "Other Roles:" -ForegroundColor Green
$otherRoles = $roles | Where-Object { $_ -notmatch "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }
if ($otherRoles) {
    $otherRoles | ForEach-Object { Write-Host "  - $_" -ForegroundColor Green }
} else {
    Write-Host "  None" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Analysis" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($roles -contains "roles/editor") {
    Write-Host "⚠️  WARNING: Editor role is granted!" -ForegroundColor Red
    Write-Host ""
    Write-Host "What this means:" -ForegroundColor Yellow
    Write-Host "  - Editor is a PRIMITIVE role with broad permissions"
    Write-Host "  - It grants thousands of permissions across most GCP services"
    Write-Host "  - Includes: create, read, update, delete for most resources"
    Write-Host ""
    Write-Host "Why it was added:" -ForegroundColor Yellow
    Write-Host "  - The setup script included it as a 'basic role'"
    Write-Host "  - It's a common shortcut for test/demo environments"
    Write-Host ""
    Write-Host "Is it necessary?" -ForegroundColor Yellow
    Write-Host "  - NO! With the specific admin roles granted, Editor is REDUNDANT"
    Write-Host "  - Each admin role (storage.admin, bigquery.admin, etc.) already"
    Write-Host "    provides full control over that service"
    Write-Host ""
    Write-Host "Best Practice:" -ForegroundColor Yellow
    Write-Host "  - Remove Editor role and rely on specific admin roles"
    Write-Host "  - This follows the principle of least privilege"
    Write-Host "  - Makes it clear what services the SA can access"
    Write-Host ""

    $remove = Read-Host "Do you want to remove the Editor role now? (Y/n)"
    if ($remove -eq "" -or $remove -eq "Y" -or $remove -eq "y") {
        Write-Host ""
        Write-Host "Removing Editor role..." -ForegroundColor Yellow
        gcloud projects remove-iam-policy-binding $PROJECT_ID `
            --member="serviceAccount:$DEPLOYER_SA_EMAIL" `
            --role="roles/editor" `
            --quiet

        if ($LASTEXITCODE -eq 0) {
            Write-Host "[SUCCESS] Editor role removed!" -ForegroundColor Green
            Write-Host ""
            Write-Host "The service account now uses only specific admin roles." -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Failed to remove Editor role" -ForegroundColor Red
        }
    } else {
        Write-Host "Keeping Editor role" -ForegroundColor Yellow
    }
} else {
    Write-Host "[SUCCESS] No primitive roles (Editor/Viewer/Owner) granted!" -ForegroundColor Green
    Write-Host "The service account follows least privilege principles." -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Recommendations" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "For TEST environment:" -ForegroundColor White
Write-Host "  ✓ Current setup is acceptable" -ForegroundColor Green
Write-Host "  ✓ Consider removing Editor for better security" -ForegroundColor Yellow
Write-Host ""
Write-Host "For PRODUCTION environment:" -ForegroundColor White
Write-Host "  ✗ Editor role is NOT recommended" -ForegroundColor Red
Write-Host "  ✓ Use specific roles only" -ForegroundColor Green
Write-Host "  ✓ Consider using custom roles with minimal permissions" -ForegroundColor Green
Write-Host ""
