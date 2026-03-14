# gh-archive-destroy.yml

## 1. Overview

GitHub Actions workflow for manually destroying the GitHub Archive pipeline infrastructure. Triggered via `workflow_dispatch` with two inputs: an environment selector (`test`/`dev`/`prod`) and a confirmation field that must exactly match the string `"destroy"`. If confirmation fails, a separate `rejected` job runs and exits with an error. On confirmation, it authenticates to GCP, runs `destroy-all-phases.sh`, and then verifies cleanup by checking for remaining Cloud Run jobs, services, and Cloud Functions.

## 2. Prerequisites

- **GitHub Secrets configured**:
  - `GCP_PROJECT_ID`: The target GCP project ID.
  - `GCP_SA_KEY_BASE64`: Base64-encoded Terraform deployer SA JSON key.
- **Terraform v1.5** (installed via `hashicorp/setup-terraform@v3`).
- **gcloud CLI** (installed via `google-github-actions/setup-gcloud@v2`).
- **Manual trigger only**: Must be dispatched from the GitHub Actions UI or API with the `environment` and `confirmation` inputs.

## 3. Upstream & Downstream Dependencies

**Upstream (what this workflow needs):**
- Infrastructure previously deployed by `gh-archive-deploy.yml` or `deploy-all-phases.sh`.
- `infrastructure/scripts/destroy-all-phases.sh` script.
- Terraform state files must be accessible (stored in the Terraform backend).
- GitHub Secrets with GCP credentials.

**Downstream (what depends on this workflow):**
- After this workflow completes, the selected environment's GCP resources are fully removed.
- The post-destroy verification step writes remaining resource counts to `$GITHUB_STEP_SUMMARY`.

## 4. Code Walkthrough

1. **Trigger** (lines 3-18): `workflow_dispatch` with two inputs:
   - `environment`: Choice of `test`, `dev`, or `prod` (default `test`).
   - `confirmation`: Free-text string that must equal `"destroy"`.
2. **Environment variables** (lines 20-22): `PROJECT_ID` from secrets, `REGION` hardcoded to `us-central1`.
3. **Job: destroy** (lines 24-89): Runs only if `confirmation == 'destroy'` (line 28).
   - **Checkout** (line 31): `actions/checkout@v4`.
   - **Confirm destruction** (lines 34-38): Writes environment and actor info to Step Summary.
   - **Decode credentials** (lines 40-43): Decodes SA key to `/tmp/gcp-key.json`.
   - **Setup gcloud + Terraform** (lines 45-52): Installs both tools.
   - **Activate SA** (lines 54-56): Authenticates gcloud with the SA key.
   - **Destroy all phases** (lines 58-63): Runs `destroy-all-phases.sh` with the selected environment.
   - **Verify cleanup** (lines 65-86): Runs on `always()`. Checks for remaining Cloud Run jobs, services, and Cloud Functions filtered by environment name. Writes results to Step Summary with a success/warning message.
   - **Cleanup credentials** (lines 88-89): Removes `/tmp/gcp-key.json`.
4. **Job: rejected** (lines 91-101): Runs if confirmation does not match. Prints what was typed vs. expected, writes to Step Summary, and exits 1.
