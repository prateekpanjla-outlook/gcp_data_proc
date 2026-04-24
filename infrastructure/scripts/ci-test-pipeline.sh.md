# ci-test-pipeline.sh

## 1. Overview

End-to-end CI integration test for the GitHub Archive pipeline. Orchestrates a full cycle: deploy all infrastructure, trigger a download job for a specific hour, wait for the file to land in GCS, wait for processing to complete (Eventarc -> Cloud Run -> staging bucket), wait for BigQuery load (Eventarc -> Cloud Function -> BQ), verify rows and schema in BigQuery, then destroy all infrastructure regardless of test outcome. Uses structured exit codes: 0 (all passed), 1 (deploy failed), 2 (test failed), 3 (destroy failed, manual cleanup needed).

## 2. Prerequisites

- **All prerequisites from `deploy-all-phases.sh`** (Terraform, gcloud, SA key).
- **bq CLI** available for BigQuery verification queries.
- **`deploy-all-phases.sh`** and **`destroy-all-phases.sh`** scripts present in the same directory.
- **GHArchive data availability**: The target hour (default: 2 hours ago) must have data published at `data.gharchive.org`.
- **Required arguments**: `PROJECT_ID` (positional 1). Optional: `ENVIRONMENT` (default `test`), `REGION` (default `us-central1`), `HOUR_OFFSET` (default `2`).

## 3. Upstream & Downstream Dependencies

**Upstream (what this script needs before running):**
- `deploy-all-phases.sh` (called internally as Step 1).
- `destroy-all-phases.sh` (called internally as final cleanup).
- Terraform deployer SA key file.
- Terraform module definitions for all four phases.

**Downstream (what depends on this script):**
- `cloudbuild-ci-test.yaml` replicates this script's logic as Cloud Build steps.
- Can be run manually for local integration testing.
- GitHub Actions workflows may call this script directly for full CI runs.

## 4. Code Walkthrough

1. **Argument parsing** (lines 28-31): `PROJECT_ID` required; `ENVIRONMENT`, `REGION`, and `HOUR_OFFSET` have defaults.
2. **Configuration** (lines 36-53): Resolves key path, derives bucket names, Cloud Run job name, BQ table name, and sets timeouts (landing: 5 min, staging: 10 min, BQ: 5 min).
3. **Target hour calculation** (lines 82-84): Computes the UTC date and hour for `HOUR_OFFSET` hours ago. Supports both GNU date (`-d`) and BSD date (`-v`) syntax.
4. **Step 1 — Deploy** (lines 92-105): Calls `deploy-all-phases.sh`. On failure, exits immediately with code 1.
5. **Step 2 — Trigger download** (lines 110-123): Executes the Cloud Run Job (`gcloud run jobs execute --wait`). Falls back to manual status checking if `--wait` is unsupported.
6. **Step 3 — Wait for landing file** (lines 130-154): Polls `gs://<landing-bucket>/<target-file>` every 15 seconds for up to 5 minutes.
7. **Step 4 — Wait for staging file** (lines 159-187): Polls the staging bucket for processed CSV chunks matching the target hour prefix, every 30 seconds for up to 10 minutes.
8. **Step 5 — Verify BigQuery load** (lines 192-221): Queries BQ for row count filtered by target date/hour, polling every 30 seconds for up to 5 minutes.
9. **Schema verification** (lines 226-239): If BQ loaded, runs a `SELECT` on key fields (`event_id`, `event_type`, `actor_login`, `repo_name`, `etl_create_id`) to confirm schema correctness.
10. **Test summary** (lines 244-258): Prints pass/fail for each stage.
11. **Destroy** (lines 263-277): Always runs `destroy-all-phases.sh`. If destroy fails, exits with code 3 and prints manual cleanup instructions.
12. **Final exit** (line 291): Returns the test result code (0 or 2).
