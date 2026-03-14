# cloudbuild-phase2.yaml

## 1. Overview

Cloud Build configuration for Phase 2 (Process Files) of the GitHub Archive pipeline. Builds the processor Docker image that runs as a Cloud Run service, triggered by Eventarc when a new `.json.gz` file lands in the landing bucket. The image is tagged with both the Cloud Build `BUILD_ID` (for traceability) and `latest` (for Terraform/Cloud Run to reference). Includes an explicit push step since the build context is submitted via `gcloud builds submit`.

## 2. Prerequisites

- **Cloud Build API** enabled on the GCP project.
- **Artifact Registry repository** named `<ENV>-github-archive` in the target region.
- **`Dockerfile.processor`** present in the build context directory (typically `src/github_archive/phase2_process_files/`).
- **Default substitutions**: `_REGION` defaults to `us-central1`, `_ENV` defaults to `dev`. Override via `--substitutions` flag.

## 3. Upstream & Downstream Dependencies

**Upstream (what this needs before running):**
- Phase 1 Terraform must have created the Artifact Registry repository (shared across phases).
- The `Dockerfile.processor` and Python processor source code must exist in the build context.

**Downstream (what depends on this):**
- Phase 2 Terraform references the built image (`processor:latest`) when creating the Cloud Run service.
- `deploy-all-phases.sh` triggers this build via Terraform during Phase 2 deployment.

## 4. Code Walkthrough

1. **Substitutions** (lines 10-12): Declares default values for `_REGION` and `_ENV`.
2. **Build step** (lines 15-27): Uses `gcr.io/cloud-builders/docker` to build the image with two tags:
   - `processor:<BUILD_ID>` for unique identification.
   - `processor:latest` for Cloud Run to pull.
3. **Push step** (lines 29-34): Explicitly pushes all tags using `docker push --all-tags`. This is needed because the image is submitted via `gcloud builds submit` rather than a trigger.
4. **Images section** (lines 37-39): Lists both tagged images for Cloud Build to track.
5. **Options** (lines 42-43): Uses `CLOUD_LOGGING_ONLY` logging.
