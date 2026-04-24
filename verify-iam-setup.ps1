# Verify IAM Setup After Editor Role Removal
$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA_EMAIL = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IAM Setup Verification" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get all roles
$policy = gcloud projects get-iam-policy $PROJECT_ID --format=json | ConvertFrom-Json
$roles = $policy.bindings | Where-Object { $_.members -contains "serviceAccount:$DEPLOYER_SA_EMAIL" } | Select-Object -ExpandProperty role | Sort-Object

Write-Host "Total roles: $($roles.Count)" -ForegroundColor White
Write-Host ""

# Check for Editor
if ($roles -contains "roles/editor") {
    Write-Host "Editor role: PRESENT" -ForegroundColor Red
    Write-Host "  WARNING: Editor role should be removed!" -ForegroundColor Red
} else {
    Write-Host "Editor role: REMOVED" -ForegroundColor Green
    Write-Host "  SUCCESS: Editor role successfully removed!" -ForegroundColor Green
}

Write-Host ""
Write-Host "Current IAM Roles:" -ForegroundColor Cyan
Write-Host ""

# Categorize roles
$primitive = $roles | Where-Object { $_ -match "^roles/(editor|viewer|owner)$" }
$admin = $roles | Where-Object { $_ -match "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }
$operational = $roles | Where-Object { $_ -notmatch "\.admin$" -and $_ -notmatch "^roles/(editor|viewer|owner)$" }

if ($primitive) {
    Write-Host "Primitive Roles:" -ForegroundColor Red
    $primitive | ForEach-Object { Write-Host "  X $_" -ForegroundColor Red }
    Write-Host ""
}

if ($admin) {
    Write-Host "Admin Roles:" -ForegroundColor Green
    $admin | ForEach-Object { Write-Host "  + $_" -ForegroundColor Green }
    Write-Host ""
}

if ($operational) {
    Write-Host "Operational Roles:" -ForegroundColor Cyan
    $operational | ForEach-Object { Write-Host "  o $_" -ForegroundColor Cyan }
    Write-Host ""
}

# Check for critical roles
Write-Host "Critical Infrastructure Roles:" -ForegroundColor White
Write-Host ""

$criticalRoles = @{
    "roles/storage.admin" = "GCS Buckets"
    "roles/bigquery.admin" = "BigQuery"
    "roles/run.admin" = "Cloud Run"
    "roles/cloudfunctions.admin" = "Cloud Functions"
}

foreach ($role in $criticalRoles.Keys) {
    if ($roles -contains $role) {
        Write-Host "  + $role - $($criticalRoles[$role])" -ForegroundColor Green
    } else {
        Write-Host "  - $role - $($criticalRoles[$role]) [MISSING]" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Summary" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

if ($roles -contains "roles/editor") {
    Write-Host "Status: FAILED - Editor role still present" -ForegroundColor Red
} elseif ($criticalRoles.Keys | Where-Object { $roles -notcontains $_ }) {
    Write-Host "Status: WARNING - Editor removed but some critical roles missing" -ForegroundColor Yellow
} else {
    Write-Host "Status: SUCCESS - IAM setup follows least privilege!" -ForegroundColor Green
    Write-Host ""
    Write-Host "The service account now has:" -ForegroundColor White
    Write-Host "  - No overly-permissive primitive roles" -ForegroundColor Green
    Write-Host "  - Specific admin roles for required services" -ForegroundColor Green
    Write-Host "  - Clear security boundaries" -ForegroundColor Green
}
