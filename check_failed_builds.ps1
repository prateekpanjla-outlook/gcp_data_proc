# Set the service account key path
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\secrets\terraform\dev-terraform-deployer-dev-dataprocessing-489305.json"

Write-Host "=== Cloud Build Failures Details ===`n"

# Get details of failed builds
$failedBuilds = @("ffa91397-db01-4e08-9ad0-b38cbf743dc6", "76de44e4-28a2-4d81-b08d-619252e53406", "12cb19b0-eb25-47c1-a79c-eb3ff78be5d2")

foreach ($buildId in $failedBuilds) {
    Write-Host "`n--- Build ID: $buildId ---"
    gcloud builds describe $buildId --format="value(id,status,start_time,duration)"
    Write-Host "`nLog excerpt:"
    gcloud builds log $buildId --limit=50
    Write-Host "`n----------------------------------------"
}

Write-Host "`n=== Recent Error Logs with Full Details ==="
gcloud logging read "severity>=ERROR" --limit=10 --format="json" --freshness=24h | ConvertFrom-Json | Select-Object -First 10 | ForEach-Object {
    Write-Host "`nTimestamp: $($_.timestamp)"
    Write-Host "Severity: $($_.severity)"
    Write-Host "Service: $($_.resource.labels.service_name)"
    if ($_.jsonPayload) {
        Write-Host "Message: $($_.jsonPayload | ConvertTo-Json -Compress)"
    } elseif ($_.textPayload) {
        Write-Host "Message: $($_.textPayload)"
    }
    Write-Host "---"
}

Write-Host "`n=== Check Complete ==="
