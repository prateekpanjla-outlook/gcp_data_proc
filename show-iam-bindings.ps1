# Show IAM Policy for test-terraform-deployer
$PROJECT_ID = "beaming-glyph-489707-b8"
$DEPLOYER_SA = "test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "IAM Policy for test-terraform-deployer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Project: " -NoNewline
Write-Host $PROJECT_ID -ForegroundColor Yellow
Write-Host "Service Account: " -NoNewline
Write-Host $DEPLOYER_SA -ForegroundColor Yellow
Write-Host ""

Write-Host "Where Permissions Live: PROJECT IAM Policy" -ForegroundColor White
Write-Host ""
Write-Host "The permissions are NOT in the service account itself." -ForegroundColor Yellow
Write-Host "They are in the PROJECT's IAM policy as bindings." -ForegroundColor Yellow
Write-Host ""

Write-Host "IAM Policy Bindings:" -ForegroundColor White
Write-Host ""

# Get the policy
$policyOutput = gcloud projects get-iam-policy $PROJECT_ID --format=json 2>&1
$policy = $policyOutput | ConvertFrom-Json

# Find bindings for the SA
$bindings = $policy.bindings | Where-Object { $_.members -contains "serviceAccount:$DEPLOYER_SA" }

Write-Host "Found $($bindings.Count) role bindings:" -ForegroundColor Green
Write-Host ""

foreach ($binding in $bindings) {
    Write-Host "  + $($binding.role)" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Key Point" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "These bindings say:" -ForegroundColor White
Write-Host '  "When test-terraform-deployer SA acts on project' -ForegroundColor Gray
Write-Host '   beaming-glyph-489707-b8, it has these roles"' -ForegroundColor Gray
Write-Host ""
Write-Host "The SA itself has NO inherent permissions." -ForegroundColor Yellow
Write-Host "All permissions come from these project-level bindings." -ForegroundColor Yellow
Write-Host ""
