# deploy-all-phases.sh

## 1. Overview

Deploys the entire GitHub Archive pipeline infrastructure across four phases in sequence: Phase 1 (Ingestion) -> Phase 2 (Process Files) -> Phase 3 (BigQuery Loader, 3 layers) -> Phase 4 (Monitoring Dashboard, 3 layers). Each phase depends on outputs from the previous one. The script authenticates via a Terraform deployer service account key, runs `terraform init` and `terraform apply` for each phase/layer, logs all output to a timestamped file, and prints a summary with duration, bucket names, BQ dataset, and dashboard URL.

## 2. Prerequisites

- **Terraform** installed and available on `PATH`.
- **gcloud CLI** authenticated (used implicitly by Terraform providers).
- **Terraform deployer service account key** at `infrastructure/<ENVIRONMENT>-terraform-deployer-key.json` (or fallback to `test-terraform-deployer-key.json`, or `GOOGLE_APPLICATION_CREDENTIALS`). Create it with `create-terraform-deployer-account.sh`.
- **GCP APIs enabled**: Cloud Run, Cloud Build, Cloud Functions, Eventarc, BigQuery, Cloud Storage, Cloud Scheduler, Artifact Registry, Cloud Logging, Pub/Sub.
- **Required arguments**: `PROJECT_ID` (positional 1), `ENVIRONMENT` (positional 2, e.g. `dev`/`test`/`prod`). `REGION` defaults to `us-central1`.

## 3. Upstream & Downstream Dependencies

**Upstream (what this script needs before running):**
- Terraform deployer SA + key (created by `create-terraform-deployer-account.sh`).
- Terraform module definitions under `infrastructure/github_archive/phase{1,2,3,4}_*/terraform/`.
- Docker images for Phase 2 processor and Phase 4 dashboard must be buildable (Cloud Build configs in `config/`).

**Downstream (what depends on this script's output):**
- `ci-test-pipeline.sh` calls this script as Step 1 to stand up infrastructure before triggering tests.
- `ci-verify-tests.sh` expects all resources deployed by this script to exist.
- `gh-archive-deploy.yml` GitHub Actions workflow calls this script as the deploy step.
- `destroy-all-phases.sh` tears down everything this script creates.

## 4. Code Walkthrough

1. **Argument parsing** (lines 16-18): Requires `PROJECT_ID` and `ENVIRONMENT`; `REGION` defaults to `us-central1`.
2. **Path resolution** (lines 23-34): Resolves repo root, base infrastructure path, and SA key file with two fallback locations.
3. **Logging** (lines 39-42): Creates `logs/deploy-all-<timestamp>.log` and tees all stdout/stderr to it.
4. **Derived names** (lines 47-48): Computes landing and staging bucket names from project ID and environment.
5. **Pre-flight checks** (lines 53-71): Prints configuration, verifies SA key exists, and exports `GOOGLE_APPLICATION_CREDENTIALS`.
6. **`tf_apply` helper** (lines 74-81): Runs `terraform init` then `terraform apply -auto-approve` in a given directory with forwarded `-var` flags.
7. **Phase 1 — Ingestion** (lines 88-102): Applies `phase1_ingestion/terraform` with `project_id`, `environment`, `region`, `force_destroy`, and `deployer_sa_key_path` vars. Creates the landing bucket and Cloud Run download job.
8. **Phase 2 — Process Files** (lines 107-120): Applies `phase2_process_files/terraform` with the landing bucket name passed from Phase 1. Creates the processor Cloud Run service, staging bucket, and Eventarc trigger.
9. **Phase 3 — BigQuery Loader** (lines 125-154): Applies three Terraform layers in order:
   - **01_static**: BigQuery dataset, table, views.
   - **02_first_time**: Cloud Function, Eventarc trigger, SA bindings.
   - **03_operational**: Cloud Scheduler, operational config.
10. **Phase 4 — Monitoring Dashboard** (lines 159-199): Applies three layers (uses `init -upgrade` instead of the helper):
    - **01_static**: Logging dataset, log sink.
    - **02_first_time**: IAM bindings, stale SA cleanup.
    - **03_operational**: Cloud Build image, Cloud Run dashboard service.
11. **Summary** (lines 204-220): Calculates elapsed time, fetches dashboard URL from Terraform output, and prints final status.
