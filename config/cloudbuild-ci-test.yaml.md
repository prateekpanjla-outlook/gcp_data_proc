# cloudbuild-ci-test.yaml

## 1. Overview

Cloud Build configuration that implements a full CI integration test pipeline: deploy all infrastructure, trigger the download job, verify data flows through landing bucket -> staging bucket -> BigQuery, then destroy everything. This is the Cloud Build equivalent of `ci-test-pipeline.sh`, structured as 7 sequential steps with dependency chaining via `waitFor`. Designed to run on push to the `test` branch or via manual `gcloud builds submit`.

## 2. Prerequisites

- **Cloud Build API** enabled with a trigger configured for the `test` branch (or run manually).
- **Terraform** available (Step 1 uses `hashicorp/terraform:1.9` image to verify).
- **Terraform deployer SA key** at `/workspace/infrastructure/<ENVIRONMENT>-terraform-deployer-key.json` inside the Cloud Build workspace.
- **bq CLI** available in the `gcr.io/cloud-builders/gcloud` image.
- **GHArchive data** available for the target hour (`_HOUR_OFFSET` hours ago, default 2).
- **Default substitutions**: `_ENVIRONMENT=test`, `_REGION=us-central1`, `_HOUR_OFFSET=2`.
- **Machine type**: `E2_HIGHCPU_8` for faster builds. Overall timeout: 1 hour.

## 3. Upstream & Downstream Dependencies

**Upstream (what this needs before running):**
- `deploy-all-phases.sh` and `destroy-all-phases.sh` scripts in `infrastructure/scripts/`.
- All Terraform modules for Phases 1-4.
- Dockerfiles for Phase 1 downloader and Phase 2 processor.
- SA key file committed or injected into the workspace.

**Downstream (what depends on this):**
- This is a terminal CI artifact -- it validates the pipeline works end-to-end and cleans up after itself.
- Cloud Build trigger history provides CI pass/fail status.

## 4. Code Walkthrough

1. **Global settings** (lines 20-26): 1-hour timeout, substitution defaults, `E2_HIGHCPU_8` machine type.
2. **Step 1 — check-terraform** (lines 29-34): Runs `terraform version` inside `hashicorp/terraform:1.9` to verify Terraform is available.
3. **Step 2 — deploy** (lines 37-47): Runs `deploy-all-phases.sh` with project ID, environment, and region. Waits for Step 1.
4. **Step 3 — trigger-download** (lines 50-62): Executes the Cloud Run download job with `gcloud run jobs execute --wait`. Waits for Step 2.
5. **Step 4 — verify-landing** (lines 65-89): Polls the landing bucket every 15 seconds for up to 5 minutes for the target `.json.gz` file. Waits for Step 3.
6. **Step 5 — verify-staging** (lines 92-117): Polls the staging bucket every 30 seconds for up to 10 minutes for processed files matching the target hour prefix. Waits for Step 4.
7. **Step 6 — verify-bigquery** (lines 120-150): Polls BQ every 30 seconds for up to 5 minutes for rows matching the target date/hour. On success, prints a sample row. Waits for Step 5.
8. **Step 7 — destroy** (lines 153-165): Runs `destroy-all-phases.sh`. Has `allowFailure: true` so it runs even if previous steps failed, ensuring infrastructure cleanup.
