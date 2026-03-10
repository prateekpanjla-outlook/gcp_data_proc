# Quick Start: Terraform Deployer with Service Account Key

This guide shows you how to quickly set up and use your Terraform deployer service account with a key file.

## 🚀 One-Time Setup

### Step 1: Run the Setup Script

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export ENVIRONMENT="test"

# Run the setup script (creates SA, grants permissions, generates key)
./infrastructure/setup-terraform-deployer.sh
```

**What this does:**
- ✓ Creates the service account: `test-terraform-deployer@your-project.iam.gserviceaccount.com`
- ✓ Grants all necessary IAM permissions (40+ roles)
- ✓ Enables required Google Cloud APIs
- ✓ Creates and downloads a key file: `test-terraform-deployer-key.json`
- ✓ Sets secure permissions (600) on the key file
- ✓ Adds key files to `.gitignore` automatically

### Step 2: Configure Authentication

```bash
# Option A: Use the helper script (recommended)
source ./infrastructure/use-terraform-deployer-key.sh

# Option B: Set manually
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/test-terraform-deployer-key.json"
```

### Step 3: Verify Authentication

```bash
# Test that the key works
gcloud auth application-default print-access-token
```

If successful, you'll see an access token printed.

## 📦 Deploy Your Infrastructure

```bash
# Deploy all phases at once
export PROJECT_ID="your-project-id"
export ENVIRONMENT="test"

./infrastructure/deploy-all.sh
```

Or deploy phases individually:

```bash
# Phase 1: Ingestion
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"
terraform apply -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"

# Phase 2: Processing
cd ../../phase2_process_files/terraform/layers/01_static
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"
terraform apply -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"

# Phase 3: Loading
cd ../../../phase3_loadbigquery/terraform/layers/01_static
terraform init
terraform plan -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"
terraform apply -var="project_id=$PROJECT_ID" -var="environment=$ENVIRONMENT"
```

## 🔁 Make Authentication Persistent

To avoid setting the environment variable every time, add it to your shell configuration:

### Bash (~/.bashrc)

```bash
echo 'export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/test-terraform-deployer-key.json' >> ~/.bashrc
source ~/.bashrc
```

### Zsh (~/.zshrc)

```bash
echo 'export GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/test-terraform-deployer-key.json' >> ~/.zshrc
source ~/.zshrc
```

### PowerShell (~/.profile)

```powershell
[System.Environment]::SetEnvironmentVariable('GOOGLE_APPLICATION_CREDENTIALS', 'C:\path\to\test-terraform-deployer-key.json', 'User')
```

## 🔐 Key File Security

### Your Key File

The script creates a JSON file with the following properties:

```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "...",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...",
  "client_email": "test-terraform-deployer@your-project-id.iam.gserviceaccount.com",
  "client_id": "...",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}
```

### Security Best Practices

✓ **DO:**
- Keep the file permissions at 600 (owner read/write only)
- Store it in a secure location
- Rotate keys regularly (every 90 days recommended)
- Use different keys for different environments
- Back up the key securely (encrypted)

✗ **DON'T:**
- Commit the key to version control (it's already in .gitignore)
- Share the key via email, chat, or unencrypted channels
- Use the same key across multiple projects
- Leave the key in a shared or public directory
- Hardcode the key in scripts

## 🔧 Troubleshooting

### Issue: "Permission denied" when accessing key file

```bash
# Fix permissions
chmod 600 test-terraform-deployer-key.json
```

### Issue: "Invalid credentials" error

```bash
# Verify the key is valid
cat test-terraform-deployer-key.json | jq .

# Regenerate the key
./infrastructure/setup-terraform-deployer.sh
# (Choose to overwrite when prompted)
```

### Issue: Terraform can't find the key

```bash
# Verify the environment variable is set
echo $GOOGLE_APPLICATION_CREDENTIALS

# If empty, set it again
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/test-terraform-deployer-key.json"
```

### Issue: "Key file not found"

```bash
# List available key files
ls -la *-terraform-deployer-key.json

# Use the correct environment variable
export ENVIRONMENT="dev"  # or "test", "prod"
source ./infrastructure/use-terraform-deployer-key.sh
```

## 🔄 Key Rotation

To rotate your service account key:

```bash
# Option 1: Run the setup script again
./infrastructure/setup-terraform-deployer.sh
# Choose 'y' to overwrite the existing key

# Option 2: Manually rotate
export PROJECT_ID="your-project-id"
export DEPLOYER_SA="test-terraform-deployer@${PROJECT_ID}.iam.gserviceaccount.com"

# List existing keys
gcloud iam service-accounts keys list --iam-account="$DEPLOYER_SA" --project="$PROJECT_ID"

# Delete old key (use the key ID from the list above)
gcloud iam service-accounts keys delete KEY_ID --iam-account="$DEPLOYER_SA" --project="$PROJECT_ID"

# Create new key
gcloud iam service-accounts keys create test-terraform-deployer-key.json \
  --iam-account="$DEPLOYER_SA" --project="$PROJECT_ID"

# Set secure permissions
chmod 600 test-terraform-deployer-key.json
```

## 📝 Summary

### Files Created

| File | Description | Location |
|------|-------------|----------|
| `setup-terraform-deployer.sh` | Main setup script | `infrastructure/` |
| `use-terraform-deployer-key.sh` | Authentication helper | `infrastructure/` |
| `test-terraform-deployer-key.json` | Service account key | Root directory |
| `.gitignore` | Updated to exclude keys | Root directory |

### Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `PROJECT_ID` | Your GCP project ID | Target project |
| `ENVIRONMENT` | `test`, `dev`, or `prod` | Resource naming |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to key file | Terraform authentication |

### Quick Commands

```bash
# Setup
./infrastructure/setup-terraform-deployer.sh

# Authenticate
source ./infrastructure/use-terraform-deployer-key.sh

# Deploy
./infrastructure/deploy-all.sh

# Verify
gcloud auth application-default print-access-token
```

## 🆘 Need Help?

1. Check the main documentation: `infrastructure/TERRAFORM_DEPLOYER_SETUP.md`
2. Review the setup script comments: `infrastructure/setup-terraform-deployer.sh`
3. Check Terraform logs: `terraform plan` output
4. Verify service account: `gcloud iam service-accounts describe test-terraform-deployer@your-project.iam.gserviceaccount.com`
