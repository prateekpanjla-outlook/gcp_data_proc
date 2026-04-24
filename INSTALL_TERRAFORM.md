# Step 2: Deploy Infrastructure - Terraform Installation Required

## Current Status

✅ **Step 1 Complete**: Terraform deployer service account created and configured
❌ **Step 2 Blocked**: Terraform is not installed on your system

## Why Terraform is Required

Your infrastructure is defined as **Terraform code** in the `infrastructure/` directory. To deploy:
- Phase 1: Ingestion (GCS buckets, Cloud Run Jobs, Schedulers)
- Phase 2: Processing (Cloud Run Services, Eventarc triggers)
- Phase 3: Loading (BigQuery datasets, Cloud Functions)

**Terraform reads the code and makes API calls to GCP to create these resources.**

## Installation Options

### Option 1: Install via Chocolatey (Recommended - Requires Admin)

1. **Open PowerShell as Administrator**
   - Right-click Start → "Windows PowerShell (Admin)"
   - Or search for "PowerShell", right-click, "Run as administrator"

2. **Install Terraform**
   ```powershell
   choco install terraform -y
   ```

3. **Verify Installation**
   ```powershell
   terraform version
   ```

### Option 2: Manual Download (No Admin Required)

1. **Download Terraform**
   - Go to: https://developer.hashicorp.com/terraform/downloads
   - Download: `terraform_1.14.6_windows_amd64.zip`
   - (or latest version)

2. **Extract Files**
   - Right-click the downloaded zip → "Extract All"
   - Extract to: `C:\Users\prateek\terraform`

3. **Add to PATH**
   ```powershell
   # Add to PATH temporarily (current session only)
   $env:Path += ";C:\Users\prateek\terraform"

   # Or add permanently (run in PowerShell as Admin)
   [Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\Users\prateek\terraform", "Machine")
   ```

4. **Verify Installation**
   ```powershell
   terraform version
   ```

### Option 3: Use Windows Package Manager (Requires Admin)

```powershell
# Open PowerShell as Administrator
winget install HashiCorp.Terraform
```

## After Installation

Once Terraform is installed, you can deploy the infrastructure:

### 1. Set Authentication (Each Terminal Session)

**PowerShell:**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json'
```

**Command Prompt:**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json
```

### 2. Verify Authentication

```powershell
gcloud auth application-default print-access-token
```

You should see a long access token printed.

### 3. Deploy All Infrastructure

```bash
# From the project root directory
./infrastructure/deploy-all.sh
```

Or if on Windows (Git Bash):
```bash
cd /c/Users/prateek/Desktop/bq/cloud_storage_run_bigquery_data_project
./infrastructure/deploy-all.sh
```

## What Will Be Deployed

### Phase 1: Ingestion (~5 minutes)
- ✅ GCS Bucket: `beaming-glyph-489707-b8-test-github-archive-landing`
- ✅ Cloud Run Job: `test-github-archive-download-gsutil`
- ✅ Scheduler Job: Runs hourly

### Phase 2: Processing (~10 minutes)
- ✅ GCS Bucket: `beaming-glyph-489707-b8-test-github-archive-staging`
- ✅ Cloud Run Service: `test-github-archive-processor`
- ✅ Eventarc Trigger: Watches landing bucket
- ✅ Cloud Run Job: `test-file-splitter`

### Phase 3: Loading (~5 minutes)
- ✅ BigQuery Dataset: `github_archive`
- ✅ BigQuery Table: `github_events` (partitioned)
- ✅ Cloud Function: `test-bq-loader`

### Cloud Build Deployment (~5 minutes)
- ✅ Container image built and deployed

**Total Time: ~25-30 minutes**

## Troubleshooting

### "terraform: command not found"
**Solution:** Terraform is not installed or not in PATH. Follow installation steps above.

### "Error: authentication required"
**Solution:** Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable.

### "Error: permission denied"
**Solution:**
1. Verify the service account has the correct roles
2. Run `.\verify-iam-setup.ps1` to check IAM bindings
3. Ensure you're using the correct project ID: `beaming-glyph-489707-b8`

### "Error: API not enabled"
**Solution:** The setup script should have enabled all required APIs. If you see this:
```powershell
gcloud services enable run.googleapis.com --project=beaming-glyph-489707-b8
```

## Quick Reference

After Terraform is installed, here's the complete workflow:

```powershell
# 1. Open PowerShell
# 2. Set authentication
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project\test-terraform-deployer-key.json'

# 3. Verify authentication
gcloud auth application-default print-access-token

# 4. Deploy (from project root)
cd C:\Users\prateek\Desktop\bq\cloud_storage_run_bigquery_data_project
.\infrastructure\deploy-all.sh

# Or if using Git Bash
./infrastructure/deploy-all.sh
```

## Next Steps

1. ✅ Install Terraform (choose Option 1, 2, or 3 above)
2. ✅ Verify installation: `terraform version`
3. ✅ Set authentication environment variable
4. ✅ Run deployment script
5. ✅ Verify resources were created

## Need Help?

If you encounter any issues:
1. Check the Terraform logs in the terminal output
2. Verify your service account has the correct roles: `.\verify-iam-setup.ps1`
3. Check the GCP Console: https://console.cloud.google.com/
4. Review the deployment guide: `infrastructure\SCRIPT_EXECUTION_ORDER.md`

Once Terraform is installed, the deployment should run smoothly! 🚀
