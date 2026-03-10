@echo off
setlocal enabledelayedexpansion

set PROJECT_ID=beaming-glyph-489707-b8
set ENVIRONMENT=test
set DEPLOYER_SA_ID=test-terraform-deployer
set DEPLOYER_SA_EMAIL=%DEPLOYER_SA_ID%@%PROJECT_ID%.iam.gserviceaccount.com
set KEY_FILE=%DEPLOYER_SA_ID%-key.json

echo ========================================
echo Terraform Deployer Setup
echo ========================================
echo.
echo Configuration:
echo   Project ID:       %PROJECT_ID%
echo   Environment:      %ENVIRONMENT%
echo   Deployer SA:      %DEPLOYER_SA_EMAIL%
echo.

REM Check if SA exists
echo Checking if service account exists...
gcloud iam service-accounts describe %DEPLOYER_SA_EMAIL% --project=%PROJECT_ID% >nul 2>&1
if %errorlevel% equ 0 (
    echo [WARNING] Service account %DEPLOYER_SA_EMAIL% already exists
    set /p RECREATE="Do you want to recreate it? This will revoke existing permissions. (y/N): "
    if /i "!RECREATE!"=="y" (
        echo [INFO] Deleting existing service account...
        gcloud iam service-accounts delete %DEPLOYER_SA_EMAIL% --project=%PROJECT_ID% --quiet
        echo [INFO] Creating new service account...
        gcloud iam service-accounts create %DEPLOYER_SA_ID% --display-name="%ENVIRONMENT% Terraform Deployer" --description="Service account for deploying GitHub Archive infrastructure with Terraform" --project=%PROJECT_ID%
        echo [SUCCESS] Service account recreated
    ) else (
        echo [INFO] Keeping existing service account
    )
) else (
    echo [INFO] Creating service account: %DEPLOYER_SA_EMAIL%
    gcloud iam service-accounts create %DEPLOYER_SA_ID% --display-name="%ENVIRONMENT% Terraform Deployer" --description="Service account for deploying GitHub Archive infrastructure with Terraform" --project=%PROJECT_ID%
    echo [SUCCESS] Service account created
)

echo.
echo ========================================
echo Granting IAM Roles
echo ========================================

REM Core IAM roles
for %%r in (
    roles/compute.admin
    roles/run.admin
    roles/cloudfunctions.admin
    roles/storage.admin
    roles/bigquery.admin
    roles/iam.serviceAccountAdmin
    roles/iam.serviceAccountUser
    roles/resourcemanager.projectIamAdmin
    roles/cloudscheduler.admin
    roles/eventarc.admin
    roles/pubsub.admin
    roles/cloudbuild.builds.builder
    roles/serviceusage.serviceUsageAdmin
    roles/logging.logWriter
    roles/monitoring.metricWriter
    roles/artifactregistry.admin
    roles/secretmanager.admin
    roles/viewer
) do (
    echo Granting %%r...
    gcloud projects add-iam-policy-binding %PROJECT_ID% --member="serviceAccount:%DEPLOYER_SA_EMAIL%" --role="%%r" --quiet >nul 2>&1
    if %errorlevel% equ 0 (
        echo [SUCCESS] %%r granted
    ) else (
        echo [WARNING] Failed to grant %%r (may already exist)
    )
)

echo.
echo ========================================
echo Generating Service Account Key
echo ========================================

if exist %KEY_FILE% (
    echo [WARNING] Key file %KEY_FILE% already exists
    set /p OVERWRITE="Do you want to overwrite it? The old key will be invalidated. (y/N): "
    if /i "!OVERWRITE!"=="y" (
        echo [INFO] Backing up old key to %KEY_FILE%.backup...
        copy %KEY_FILE% %KEY_FILE%.backup >nul
        echo [INFO] Creating new key file...
        gcloud iam service-accounts keys create %KEY_FILE% --iam-account=%DEPLOYER_SA_EMAIL% --project=%PROJECT_ID%
        echo [SUCCESS] New key created (old key backed up)
    ) else (
        echo [INFO] Keeping existing key file
    )
) else (
    echo [INFO] Creating key file: %KEY_FILE%
    gcloud iam service-accounts keys create %KEY_FILE% --iam-account=%DEPLOYER_SA_EMAIL% --project=%PROJECT_ID%
    echo [SUCCESS] Key file created: %KEY_FILE%
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Service Account Key Location:
echo   File: %KEY_FILE%
echo   Path: %CD%\%KEY_FILE%
echo.
echo Next steps:
echo.
echo 1. Set the environment variable (required for Terraform):
echo    set GOOGLE_APPLICATION_CREDENTIALS=%CD%\%KEY_FILE%
echo.
echo 2. Verify authentication works:
echo    gcloud auth application-default print-access-token
echo.
echo 3. Deploy infrastructure:
echo    infrastructure\deploy-all.sh
echo.
echo [WARNING] CRITICAL SECURITY REMINDERS:
echo   - Add '%KEY_FILE%' to .gitignore immediately
echo   - Store this key file securely (it contains sensitive credentials)
echo   - NEVER commit this file to version control
echo   - Rotate keys regularly (recommended: every 90 days)
echo.

endlocal
