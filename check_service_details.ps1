# Set the service account key path
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\secrets\terraform\dev-terraform-deployer-dev-dataprocessing-489305.json"

# Check Cloud Run service details with logs
Write-Host "=== Cloud Run Service: dev-bq-loader ==="
gcloud run services describe dev-bq-loader --region=us-central1 --format="json"

Write-Host "`n=== Recent Logs for dev-bq-loader ==="
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=dev-bq-loader" --limit=20 --format="table(timestamp,severity,jsonPayload.message)" --freshness=1h

Write-Host "`n=== Cloud Run Service: dev-github-archive-processor ==="
gcloud run services describe dev-github-archive-processor --region=us-central1 --format="json"

Write-Host "`n=== Recent Logs for dev-github-archive-processor ==="
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=dev-github-archive-processor" --limit=20 --format="table(timestamp,severity,jsonPayload.message)" --freshness=1h

# Check for error logs in the last 24 hours
Write-Host "`n=== Error Logs (Last 24 Hours) ==="
gcloud logging read "severity>=ERROR" --limit=50 --format="table(timestamp,severity,resource.labels.service_name,jsonPayload.message)" --freshness=24h

Write-Host "`n=== Check Complete ==="
