# gh-archive-deploy.yml

## 1. Overview

GitHub Actions workflow that deploys the GitHub Archive pipeline and runs verification tests on every push to the `gh_archive_test` branch. It checks out the code, authenticates to GCP using a base64-encoded service account key stored in GitHub secrets, sets up gcloud and Terraform, deploys all four phases via `deploy-all-phases.sh`, then runs the 7 verification test suites via `ci-verify-tests.sh`. Uses concurrency groups to prevent parallel runs that would cause Terraform state lock conflicts. Job timeout is 45 minutes.

## 2. Prerequisites

- **GitHub Secrets configured**:
  - `GCP_PROJECT_ID`: The target GCP project ID.
  - `GCP_SA_KEY_BASE64`: Base64-encoded Terraform deployer SA JSON key (created by `create-terraform-deployer-account.sh`, then base64-encoded).
- **Terraform v1.5** (installed via `hashicorp/setup-terraform@v3` with `terraform_wrapper: false`).
- **gcloud CLI** (installed via `google-github-actions/setup-gcloud@v2`).
- **Branch**: Only triggers on pushes to `gh_archive_test`.

## 3. Upstream & Downstream Dependencies

**Upstream (what this workflow needs):**
- `infrastructure/scripts/deploy-all-phases.sh` for deployment.
- `infrastructure/scripts/ci-verify-tests.sh` for verification.
- All Terraform modules and Dockerfiles for Phases 1-4.
- GitHub Secrets with GCP credentials.

**Downstream (what depends on this workflow):**
- `gh-archive-destroy.yml` can be triggered manually to tear down the environment this workflow deployed.
- The workflow writes the dashboard URL to `$GITHUB_STEP_SUMMARY` for visibility in the Actions UI.

## 4. IAM & Service Accounts

- **Terraform deployer SA:** The workflow authenticates as `{env}-terraform-deployer` by decoding the `GCP_SA_KEY_BASE64` GitHub secret to `/tmp/gcp-key.json` and exporting `GOOGLE_APPLICATION_CREDENTIALS`.
- **Authentication flow:**
  1. `GCP_SA_KEY_BASE64` secret is base64-decoded to a temporary JSON key file.
  2. `gcloud auth activate-service-account` activates the SA for gcloud commands.
  3. `GOOGLE_APPLICATION_CREDENTIALS` is exported for Terraform provider authentication.
  4. The temporary key file is deleted in the cleanup step (runs on `always()`).
- **Required SA permissions:** The deployer SA needs all 14+ roles granted by `create-terraform-deployer-account.sh` to deploy all four phases.
- **Cross-reference:** `learnings/phase4_deployment_issues.md`:
  - Issue 4 — `roles/logging.admin` must be included in the deployer SA's roles for Phase 4 log sink creation to succeed.
  - Issue 5 — `GOOGLE_APPLICATION_CREDENTIALS` must use an absolute path; the workflow uses `/tmp/gcp-key.json`.

## 5. Code Walkthrough

1. **Trigger** (lines 3-5): Fires on push to `gh_archive_test` branch only.
2. **Concurrency** (lines 8-10): Uses group `gh-archive-deploy-<ref>` with `cancel-in-progress: true` to prevent parallel deploys.
3. **Environment variables** (lines 12-15): Sets `PROJECT_ID`, `REGION` (`us-central1`), and `ENVIRONMENT` (`test`) from secrets/defaults.
4. **Step: Checkout** (line 24): Uses `actions/checkout@v4`.
5. **Step: Decode GCP credentials** (lines 28-34): Decodes `GCP_SA_KEY_BASE64` to `/tmp/gcp-key.json`. Validates the file is non-empty. Exports `GOOGLE_APPLICATION_CREDENTIALS`.
6. **Step: Setup gcloud** (line 37): Installs gcloud via `google-github-actions/setup-gcloud@v2`.
7. **Step: Setup Terraform** (lines 39-43): Installs Terraform 1.5 with `terraform_wrapper: false` (prevents output wrapping that breaks scripts).
8. **Step: Activate service account** (lines 45-48): Runs `gcloud auth activate-service-account` and sets the default project.
9. **Step: Deploy all phases** (lines 50-53): Runs `deploy-all-phases.sh` with project, environment, and region.
10. **Step: Run verification tests** (lines 55-58): Runs `ci-verify-tests.sh` against the deployed infrastructure.
11. **Step: Print dashboard URL** (lines 60-68): Runs on `always()`. Fetches the dashboard Cloud Run service URL and writes it to the GitHub Step Summary.
12. **Step: Cleanup credentials** (lines 70-72): Runs on `always()`. Removes the temporary key file.
