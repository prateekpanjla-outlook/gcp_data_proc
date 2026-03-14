# create-terraform-deployer-account.sh

## 1. Overview

Creates a GCP service account for Terraform deployments, grants it all IAM roles needed to manage the GitHub Archive pipeline infrastructure, and generates a JSON key file. The SA is named `<ENVIRONMENT>-terraform-deployer` and receives 14 roles including `roles/editor`, project IAM admin, and service-specific admin roles for Cloud Run, BigQuery, Eventarc, Artifact Registry, etc. The key is saved to `../secrets/terraform/` with `chmod 600` permissions.

## 2. Prerequisites

- **gcloud CLI** authenticated as a user or SA with permissions to:
  - Create service accounts (`iam.serviceAccounts.create`).
  - Bind IAM roles at the project level (`resourcemanager.projects.setIamPolicy`).
  - Create SA keys (`iam.serviceAccountKeys.create`).
- **Target GCP project** must exist and have billing enabled.
- **Required arguments**: `PROJECT_ID` (positional 1 or via `PROJECT_ID` env var). Optional: `ENVIRONMENT` (default `dev`).

## 3. Upstream & Downstream Dependencies

**Upstream (what this script needs before running):**
- A GCP project with the necessary APIs enabled.
- A user account with Owner or equivalent permissions to create SAs and bind roles.

**Downstream (what depends on this script's output):**
- `deploy-all-phases.sh` requires the SA key file at `infrastructure/<ENVIRONMENT>-terraform-deployer-key.json`.
- `destroy-all-phases.sh` requires the same key file.
- `ci-test-pipeline.sh` requires the key file for end-to-end testing.
- `cloudbuild-ci-test.yaml` expects the key at `/workspace/infrastructure/<ENVIRONMENT>-terraform-deployer-key.json`.
- GitHub Actions workflows expect the key base64-encoded in `GCP_SA_KEY_BASE64` secret.

## 4. Code Walkthrough

1. **Logging** (lines 13-27): Creates `logs/create-terraform-sa-<timestamp>.log` and tees all output.
2. **Argument validation** (lines 31-39): Accepts `PROJECT_ID` as positional arg or env var; `ENVIRONMENT` defaults to `dev`.
3. **SA naming** (lines 41-42): SA ID is `<ENVIRONMENT>-terraform-deployer`, email is `<SA_ID>@<PROJECT_ID>.iam.gserviceaccount.com`.
4. **Step 1 — Create SA** (lines 57-65): Runs `gcloud iam service-accounts create`. Continues if SA already exists.
5. **Step 2 — Grant roles** (lines 71-99): Iterates over 14 roles and binds each to the SA:
   - `roles/editor` (broad project access)
   - `roles/resourcemanager.projectIamAdmin` (manage IAM bindings)
   - `roles/iam.serviceAccountAdmin` (manage other SAs)
   - `roles/cloudbuild.builds.builder`, `roles/run.admin`, `roles/cloudscheduler.admin`
   - `roles/storage.admin`, `roles/iam.serviceAccountTokenCreator`
   - `roles/artifactregistry.admin`, `roles/bigquery.admin`, `roles/pubsub.admin`
   - `roles/cloudfunctions.admin`, `roles/monitoring.admin`
   - `roles/eventarc.admin`, `roles/logging.admin`
6. **Step 3 — Create key** (lines 105-131): Saves JSON key to `../secrets/terraform/<SA_ID>-<PROJECT_ID>.json`. Prompts before overwriting an existing key.
7. **Permissions** (lines 137-139): Sets key file to `chmod 600` (owner-only read/write).
8. **Summary** (lines 144-162): Prints SA details and usage instructions for `GOOGLE_APPLICATION_CREDENTIALS` or `terraform.tfvars`.
