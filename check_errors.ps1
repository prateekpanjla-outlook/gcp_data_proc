# Set the service account key path
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\secrets\terraform\dev-terraform-deployer-dev-dataprocessing-489305.json"

Write-Host "=== Detailed Error Logs (Last 24 Hours) ===`n"
gcloud logging read "severity>=ERROR" --limit=100 --format="value(timestamp,severity,resource.labels.service_name,jsonPayload.message,textPayload)" --freshness=24h

Write-Host "`n=== Error Logs by Service ==="
Write-Host "`n--- dev-bq-loader Errors ---"
gcloud logging read "severity>=ERROR AND resource.labels.service_name=dev-bq-loader" --limit=20 --format="value(timestamp,severity,jsonPayload.message,textPayload)" --freshness=24h

Write-Host "`n--- dev-github-archive-processor Errors ---"
gcloud logging read "severity>=ERROR AND resource.labels.service_name=dev-github-archive-processor" --limit=20 --format="value(timestamp,severity,jsonPayload.message,textPayload)" --freshness=24h

Write-Host "`n=== Checking for Failed BigQuery Load Jobs ==="
bq --project_id=dev-dataprocessing-489305 ls -j --min_creation_time=$(($(date +%s) - 86400)) | Select-String -Pattern "FAILED"

Write-Host "`n=== Checking Cloud Build logs ==="
gcloud builds list --limit=10 --format="table(id,status,create_time,duration)"

Write-Host "`n=== Check Complete ==="
