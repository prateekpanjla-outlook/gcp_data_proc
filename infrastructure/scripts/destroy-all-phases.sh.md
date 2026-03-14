# destroy-all-phases.sh

## 1. Overview

Destroys the entire GitHub Archive pipeline infrastructure in reverse order: Phase 4 (Monitoring Dashboard, layers 03 -> 02 -> 01) -> Phase 3 (BigQuery Loader, layers 03 -> 02 -> 01) -> Phase 2 (Process Files) -> Phase 1 (Ingestion). Before destroying Phase 1, it empties the landing and staging GCS buckets. Between Phase 4 and Phase 3, it performs a stale service account cleanup on the BigQuery dataset to prevent IAM destroy failures. Each destroy step uses `|| true` to continue even if individual resources fail.

## 2. Prerequisites

- **Terraform** installed and available on `PATH`.
- **gcloud CLI** authenticated and with access to the target project.
- **bq CLI** available (part of gcloud SDK) for stale SA cleanup.
- **Terraform deployer service account key** at `infrastructure/<ENVIRONMENT>-terraform-deployer-key.json` (or fallbacks).
- **Existing Terraform state files** from a prior deploy (the script runs `terraform init` before each `destroy`).
- **Required arguments**: `PROJECT_ID` (positional 1), `ENVIRONMENT` (positional 2). `REGION` defaults to `us-central1`.

## 3. Upstream & Downstream Dependencies

**Upstream (what this script needs before running):**
- Infrastructure previously deployed by `deploy-all-phases.sh`.
- Terraform state files in each phase/layer directory.
- Terraform deployer SA key (created by `create-terraform-deployer-account.sh`).

**Downstream (what depends on this script):**
- `ci-test-pipeline.sh` calls this script as the final cleanup step after tests complete.
- `gh-archive-destroy.yml` GitHub Actions workflow calls this script as the destroy step.
- After this script completes, all GCP resources for the pipeline environment are removed.

## 4. Code Walkthrough

1. **Argument parsing** (lines 16-18): Requires `PROJECT_ID` and `ENVIRONMENT`; `REGION` defaults to `us-central1`.
2. **Path resolution & key fallback** (lines 23-33): Same fallback chain as `deploy-all-phases.sh`.
3. **Logging** (lines 38-41): Writes to `logs/destroy-all-<timestamp>.log`.
4. **`tf_destroy` helper** (lines 67-74): Runs `terraform init` then `terraform destroy -auto-approve`.
5. **`verify_empty_state` helper** (lines 77-86): Checks if Terraform state still has resources after destroy; retries if not empty.
6. **Phase 4 destroy** (lines 92-144): Destroys layers 03 -> 02 -> 01 in reverse. After destroy, loops through all three layers to verify state is clean. Any remaining resources are removed from state with `terraform state rm`.
7. **Stale SA cleanup** (lines 149-190): After Phase 4's dashboard SA is deleted, GCP renames it to `deleted:serviceAccount:...` in BQ dataset IAM. The script waits 30 seconds for propagation, then polls up to 2 minutes to find and revoke these stale entries using `bq query REVOKE`. This prevents Phase 3 destroy from failing on IAM conflicts.
8. **Phase 3 destroy** (lines 195-224): Destroys BigQuery Loader layers 03 -> 02 -> 01 in reverse.
9. **Phase 2 destroy** (lines 229-239): Destroys the processor Cloud Run service, staging bucket trigger, etc.
10. **Phase 1 destroy** (lines 244-262): First empties the landing and staging buckets using `gcloud storage rm`, then runs `terraform destroy` with `force_destroy=true`.
11. **Summary** (lines 267-277): Prints total duration and log file location.
