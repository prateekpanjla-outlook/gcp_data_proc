# Script Execution Order Guide

This guide shows the exact order to run scripts for your test project `beaming-glyph-489707-b8`.

## 🎯 Complete Workflow (First-Time Setup)

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: One-Time Infrastructure Setup                          │
└─────────────────────────────────────────────────────────────────┘
    │
    ├─> 1.1. Run setup script to create service account
    │    ./infrastructure/setup-terraform-deployer.sh
    │
    ├─> 1.2. Configure authentication (run this each new session)
    │    source ./infrastructure/use-terraform-deployer-key.sh
    │
    └─> 1.3. Deploy all infrastructure phases
         ./infrastructure/deploy-all.sh
```

## 📋 Detailed Step-by-Step

### Phase 0: Prerequisites (One-Time)

```bash
# Install required tools
# - gcloud CLI
# - Terraform
# - jq (optional, for JSON parsing)

# Authenticate with Google Cloud
gcloud auth login

# Set your default project (optional but recommended)
gcloud config set project beaming-glyph-489707-b8
```

### Phase 1: Service Account Setup (One-Time)

```bash
# ========================================
# SCRIPT 1: setup-terraform-deployer.sh
# ========================================
# Location: infrastructure/setup-terraform-deployer.sh
# Purpose: Create service account with all permissions
# Run: Once per project
# Output: test-terraform-deployer-key.json

./infrastructure/setup-terraform-deployer.sh
```

**What this does:**
- ✅ Creates service account: `test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com`
- ✅ Grants 40+ IAM roles (compute, run, bigquery, storage, etc.)
- ✅ Enables 16+ Google Cloud APIs
- ✅ Generates key file: `test-terraform-deployer-key.json`
- ✅ Sets secure permissions (600) on key file
- ✅ Configures service agent permissions
- ✅ Adds key files to .gitignore

**Time:** ~3-5 minutes

---

### Phase 2: Authentication (Each New Session)

```bash
# ========================================
# SCRIPT 2: use-terraform-deployer-key.sh
# ========================================
# Location: infrastructure/use-terraform-deployer-key.sh
# Purpose: Configure Terraform to use the service account key
# Run: Every new terminal session
# Output: Sets GOOGLE_APPLICATION_CREDENTIALS environment variable

source ./infrastructure/use-terraform-deployer-key.sh
```

**What this does:**
- ✅ Validates key file exists
- ✅ Sets `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- ✅ Verifies key works by calling Google Cloud API
- ✅ Reports success or provides troubleshooting steps

**Time:** ~10 seconds

**Alternative (manual):**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/test-terraform-deployer-key.json"
gcloud auth application-default print-access-token
```

---

### Phase 3: Deploy Infrastructure (One-Time or Updates)

```bash
# ========================================
# SCRIPT 3: deploy-all.sh
# ========================================
# Location: infrastructure/deploy-all.sh
# Purpose: Deploy all 3 phases in correct order
# Run: Once for initial deployment, or when making updates
# Output: Complete GitHub Archive pipeline

./infrastructure/deploy-all.sh
```

**What this does:**

**Phase 1: Ingestion**
```bash
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform init
terraform plan -out=phase1.tfplan
terraform apply phase1.tfplan
# Creates: landing bucket, Cloud Run job, scheduler
```

**Phase 2: Processing** (Layer by Layer)
```bash
cd infrastructure/github_archive/phase2_process_files/terraform/layers

# Layer 01: Static
cd 01_static
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Layer 02: First-Time
cd ../02_first_time
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Layer 03: Operational
cd ../03_operational
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"
# Creates: staging bucket, Cloud Run service, event triggers
```

**Phase 3: Loading** (Layer by Layer)
```bash
cd infrastructure/github_archive/phase3_loadbigquery/terraform/layers

# Layer 01: Static
cd 01_static
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Layer 02: First-Time
cd ../02_first_time
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Layer 03: Operational
cd ../03_operational
terraform init
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"
# Creates: BigQuery dataset, table, Cloud Function
```

**Cloud Build Deployment**
```bash
cd infrastructure/github_archive/phase2_process_files
gcloud builds submit --config=cloudbuild.yaml . \
  --substitutions=_REGION="us-central1",_ENVIRONMENT="test"
# Builds and deploys processor container image
```

**Time:** ~15-20 minutes (first time) or ~5-10 minutes (updates)

---

## 🔄 Ongoing Workflow

### Daily Usage

```bash
# 1. Open new terminal session
# 2. Configure authentication
source ./infrastructure/use-terraform-deployer-key.sh

# 3. Now you can use Terraform, gcloud, etc.
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform plan
```

### Making Infrastructure Changes

```bash
# 1. Authenticate
source ./infrastructure/use-terraform-deployer-key.sh

# 2. Make your Terraform changes

# 3. Deploy specific phase
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform plan -var="project_id=beaming-glyph-489707-b8" -var="environment=test"
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# OR deploy all phases
./infrastructure/deploy-all.sh
```

### Key Rotation (Every 90 Days)

```bash
# 1. Re-run setup script
./infrastructure/setup-terraform-deployer.sh
# Choose 'y' to overwrite existing key

# 2. Re-authenticate with new key
source ./infrastructure/use-terraform-deployer-key.sh

# 3. Old key is backed up as .backup file
```

---

## 📊 Script Dependency Graph

```
setup-terraform-deployer.sh
    │
    ├─> Creates: test-terraform-deployer-key.json
    │
    └─> Enables APIs
         │
         └─> use-terraform-deployer-key.sh
              │
              ├─> Reads: test-terraform-deployer-key.json
              │
              └─> Sets: GOOGLE_APPLICATION_CREDENTIALS
                   │
                   └─> deploy-all.sh
                        │
                        ├─> Phase 1: terraform apply
                        ├─> Phase 2: terraform apply (3 layers)
                        ├─> Phase 3: terraform apply (3 layers)
                        └─> Cloud Build: gcloud builds submit
```

---

## 🎯 Quick Reference Commands

### First-Time Setup (All-in-One)

```bash
# Run these in order
./infrastructure/setup-terraform-deployer.sh
source ./infrastructure/use-terraform-deployer-key.sh
./infrastructure/deploy-all.sh
```

### Verify Everything Works

```bash
# Check service account
gcloud iam service-accounts describe test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com

# Check authentication
gcloud auth application-default print-access-token

# Check deployed resources
gcloud run jobs list --project=beaming-glyph-489707-b8 --region=us-central1
gsutil ls gs://beaming-glyph-489707-b8-test-github-archive-landing
bq --project_id=beaming-glyph-489707-b8 ls -d github_archive
```

### Manual Deployment by Phase

```bash
# After running setup and authentication scripts

# Phase 1 only
cd infrastructure/github_archive/phase1_ingestion/terraform
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Phase 2 only
cd infrastructure/github_archive/phase2_process_files/terraform/layers/01_static
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"

# Phase 3 only
cd infrastructure/github_archive/phase3_loadbigquery/terraform/layers/01_static
terraform apply -var="project_id=beaming-glyph-489707-b8" -var="environment=test"
```

---

## ⏱️ Time Estimates

| Step | Time | Frequency |
|------|------|-----------|
| Setup service account | 3-5 min | Once |
| Configure authentication | 10 sec | Each session |
| Deploy all infrastructure | 15-20 min | Once (or updates) |
| Deploy single phase | 5-10 min | As needed |
| Key rotation | 3-5 min | Every 90 days |

---

## 🚨 Common Mistakes to Avoid

### ❌ Wrong Order
```bash
# DON'T: Try to deploy without setup
./infrastructure/deploy-all.sh  # Will fail - no service account
```

### ✅ Right Order
```bash
# DO: Setup first, then deploy
./infrastructure/setup-terraform-deployer.sh
source ./infrastructure/use-terraform-deployer-key.sh
./infrastructure/deploy-all.sh
```

### ❌ Forget Authentication
```bash
# DON'T: Skip authentication in new terminal
cd infrastructure/.../terraform
terraform plan  # Will fail - not authenticated
```

### ✅ Right Way
```bash
# DO: Run authentication helper first
source ./infrastructure/use-terraform-deployer-key.sh
cd infrastructure/.../terraform
terraform plan  # Works!
```

---

## 📁 File Locations After Setup

```
project-root/
├── infrastructure/
│   ├── setup-terraform-deployer.sh          # Script 1
│   ├── use-terraform-deployer-key.sh        # Script 2
│   ├── deploy-all.sh                        # Script 3
│   ├── test-project-config.sh               # Config helper
│   ├── TERRAFORM_DEPLOYER_SETUP.md          # Docs
│   └── QUICK_START_KEY_AUTH.md              # Docs
├── test-terraform-deployer-key.json         # ⚠️ Generated by Script 1
├── test-terraform-deployer-key.json.backup  # ⚠️ Backup during rotation
└── .gitignore                                # Updated to exclude keys
```

---

## 🎓 Summary

**The Three Main Scripts (In Order):**

1. **`setup-terraform-deployer.sh`** - One-time setup (creates SA + key)
2. **`use-terraform-deployer-key.sh`** - Per-session authentication
3. **`deploy-all.sh`** - Deploy infrastructure (or updates)

**Remember:**
- Run Script 1 once per project
- Run Script 2 every new terminal session
- Run Script 3 when deploying or updating infrastructure
- All scripts default to project `beaming-glyph-489707-b8`
