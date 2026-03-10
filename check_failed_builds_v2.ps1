# Set the service account key path
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\secrets\terraform\dev-terraform-deployer-dev-dataprocessing-489305.json"

Write-Host "=== Cloud Build Failures Details ===`n"

# Get details of failed builds
$failedBuilds = @("ffa91397-db01-4e08-9ad0-b38cbf743dc6", "76de44e4-28a2-4d81-b08d-619252e53406", "12cb19b0-eb25-47c1-a79c-eb3ff78be5d2")

foreach ($buildId in $failedBuilds) {
    Write-Host "`n========================================"
    Write-Host "Build ID: $buildId"
    Write-Host "========================================"
    $buildInfo = gcloud builds describe $buildId --format="json" | ConvertFrom-Json
    Write-Host "Status: $($buildInfo.status)"
    Write-Host "Start Time: $($buildInfo.startTime)"
    Write-Host "Duration: $($buildInfo.duration)"

    if ($buildInfo.status -eq "FAILURE") {
        Write-Host "`n--- Build Steps ---"
        foreach ($step in $buildInfo.steps) {
            if ($step.status -ne "SUCCESS") {
                Write-Host "`nStep: $($step.name)"
                Write-Host "Status: $($step.status)"
                if ($step.id) {
                    Write-Host "Step ID: $($step.id)"
                }
            }
        }

        Write-Host "`n--- Recent Build Log Entries ---"
        # Get the log entries
        gcloud builds log $buildId 2>&1 | Select-String -Pattern "(ERROR|error|Error|FAILED|failed|Failed)" | Select-Object -First 20
    }
    Write-Host "`n"
}

Write-Host "`n=== Summary ==="
Write-Host "Total failed builds in list: $($failedBuilds.Count)"
Write-Host "`nYou can view full logs in Cloud Console: https://console.cloud.google.com/cloud-build/builds?project=dev-dataprocessing-489305"
