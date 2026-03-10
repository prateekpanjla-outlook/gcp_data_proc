# Set the service account key path
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\infrastructure\secrets\terraform\dev-terraform-deployer-dev-dataprocessing-489305.json"

# Authenticate
Write-Host "Authenticating with service account..."
gcloud auth activate-service-account --key-file=$env:GOOGLE_APPLICATION_CREDENTIALS

# Set project
Write-Host "`nSetting project to dev-dataprocessing-489305..."
gcloud config set project dev-dataprocessing-489305

# Check Cloud Run services
Write-Host "`n=== Cloud Run Services ==="
gcloud run services list

# Check Cloud Run service details
Write-Host "`n=== Cloud Run Service Details ==="
$services = gcloud run services list --format="value(metadata.name)" 2>$null
if ($services) {
    foreach ($service in $services) {
        Write-Host "`n--- Service: $service ---"
        gcloud run services describe $service --format="value(status.latestReadyRevisionName,status.url,spec.template.spec.serviceAccountName)"
        gcloud run services describe $service --format="value(status.latestReadyRevisionName,status.url,spec.template.spec.serviceAccountName)"
    }
} else {
    Write-Host "No Cloud Run services found."
}

# Check BigQuery datasets
Write-Host "`n=== BigQuery Datasets ==="
bq --project_id=dev-dataprocessing-489305 ls

# Check recent BigQuery jobs
Write-Host "`n=== Recent BigQuery Jobs (last 5) ==="
bq --project_id=dev-dataprocessing-489305 ls -j -n 5

# Check Cloud Storage buckets
Write-Host "`n=== Cloud Storage Buckets ==="
gsutil ls

Write-Host "`n=== Summary Complete ==="
