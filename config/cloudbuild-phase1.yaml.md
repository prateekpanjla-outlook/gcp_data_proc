# cloudbuild-phase1.yaml

## 1. Overview

Cloud Build configuration for Phase 1 (Ingestion) of the GitHub Archive pipeline. Builds a Docker image for the GitHub Archive downloader -- a container that runs as a Cloud Run Job to download hourly `.json.gz` files from `data.gharchive.org` into a GCS landing bucket. The image is built from the `Dockerfile` in the build context and pushed to Artifact Registry.

## 2. Prerequisites

- **Cloud Build API** enabled on the GCP project.
- **Artifact Registry repository** named `<ENV>-github-archive` in the target region (created by Phase 1 Terraform).
- **Dockerfile** present in the build context directory (typically `src/github_archive/phase1_ingestion/`).
- **Substitution variables**: `_REGION` (e.g. `us-central1`), `_ENV` (e.g. `test`). `$PROJECT_ID` is provided automatically by Cloud Build.

## 3. Upstream & Downstream Dependencies

**Upstream (what this needs before running):**
- Phase 1 Terraform must have created the Artifact Registry repository.
- The Dockerfile and `download.sh` script must exist in the build context.

**Downstream (what depends on this):**
- Phase 1 Terraform references the built image (`github-archive-downloader:latest`) when creating the Cloud Run Job.
- `deploy-all-phases.sh` triggers this build implicitly via Terraform's `null_resource` or Cloud Build trigger.

## 4. IAM & Service Accounts

- **Build SA**: Runs as `{env}-cloud-build@{project}.iam.gserviceaccount.com` (custom SA, not the default Cloud Build SA). The custom SA is passed via the `--service-account` flag in the Terraform `null_resource` or `gcloud builds submit` command.
- **Roles required on the custom SA**:
  - `cloudbuild.builds.builder` — build and push images to Artifact Registry.
  - `run.admin` — deploy Cloud Run services/jobs.
  - `iam.serviceAccountUser` — attach runtime SAs to Cloud Run services/jobs.
- **Non-obvious**: The custom Cloud Build SA cannot write logs to the default `_cloudbuild` bucket. The build must specify either `--default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET` or an explicit `--logs-bucket` (see learnings Issue 3).
- **Cross-reference**: Issue 5 in `github_actions_ci_issues.md` — `gcloud beta` commands need `--quiet` on non-interactive runners.

## 5. Code Walkthrough

1. **Build step** (lines 6-16): Uses `gcr.io/cloud-builders/docker` to build the image. Tags it as `<REGION>-docker.pkg.dev/<PROJECT_ID>/<ENV>-github-archive/github-archive-downloader:latest`.
2. **Images section** (lines 19): Declares the image for automatic push after successful build.
3. **Timeout** (line 22): Set to 1200 seconds (20 minutes).
4. **Options** (lines 25-26): Uses `CLOUD_LOGGING_ONLY` for logging, which is required when using a custom service account (avoids needing a Cloud Storage logs bucket).
