# build.tf Documentation

## 1. Overview

Builds and pushes the Phase 2 processor Docker image to Artifact Registry using Cloud Build. This file uses a `null_resource` with a `local-exec` provisioner to run `gcloud builds submit`, authenticating via the deployer service account and delegating the build to the Phase 1 Cloud Build service account.

The build is triggered locally (not via a Cloud Build trigger resource) and re-runs whenever the Dockerfile, requirements.txt, or Cloud Build config YAML changes.

## 2. Prerequisites

- The Artifact Registry repository (`${environment}-github-archive`) must already exist (created in Phase 1).
- The Cloud Build service account (`${environment}-cloud-build@...`) must exist with appropriate permissions (created in Phase 1).
- `gcloud` CLI must be available on the machine running `terraform apply`.
- `var.deployer_sa_key_path` must point to a valid service account key file.
- Source files must exist at `src/github_archive/phase2_process_files/` relative to the repo root:
  - `Dockerfile.processor`
  - `requirements.txt`
- Cloud Build config must exist at `config/cloudbuild-phase2.yaml`.

## 3. Upstream & Downstream Dependencies

**Upstream:**
- Phase 1 Artifact Registry repository -- the target for the built image.
- Phase 1 Cloud Build service account -- used as `--service-account` for the build.
- Source code under `src/github_archive/phase2_process_files/`.

**Downstream:**
- The built image (`processor:latest`) is referenced by the Cloud Run service definition (in `main.tf` or `layers/03_operational/main.tf`).

## 4. IAM & Service Accounts

| Identity | Format | Purpose |
|----------|--------|---------|
| **Cloud Build SA** | `{env}-cloud-build@{project}.iam.gserviceaccount.com` | Runs the `gcloud builds submit` build. Specified via `--service-account` so the build does not use the default Compute Engine SA. Created in Phase 1. |
| **Deployer SA** | Key file at `var.deployer_sa_key_path` | Used by `gcloud auth activate-service-account` to authenticate the local `gcloud` CLI before submitting the build. |

**Required roles/permissions:**
- **Cloud Build SA** needs:
  - `roles/cloudbuild.builds.builder` -- to execute builds.
  - `roles/artifactregistry.writer` on the `{env}-github-archive` Artifact Registry repo -- to push the built Docker image.
  - `roles/iam.serviceAccountUser` on the Processor SA -- to deploy Cloud Run services that run as the processor SA (granted in Layer 02).
- **Deployer SA** needs:
  - `roles/cloudbuild.builds.editor` -- to submit builds via `gcloud builds submit`.

**IAM propagation notes:**
- The Cloud Build SA and its Artifact Registry permissions are created in Phase 1. If Phase 1 IAM bindings are recently applied, allow up to 60 seconds for propagation before running `terraform apply` on this file, otherwise the build may fail with permission denied on the Artifact Registry push step.

## 5. Code Walkthrough

1. **`triggers` block (lines 7-11):** Computes SHA-256 hashes of `Dockerfile.processor`, `requirements.txt`, and `cloudbuild-phase2.yaml`. If any hash changes between applies, Terraform destroys and recreates the `null_resource`, which re-runs the build.

2. **`local-exec` provisioner (lines 13-23):**
   - Activates the deployer service account using `gcloud auth activate-service-account`.
   - Runs `gcloud builds submit` pointing at the Phase 2 source directory.
   - Uses `--config` to reference the Cloud Build YAML.
   - Passes `--substitutions` for `_REGION` and `_ENV` so the YAML can construct the image tag.
   - Uses `--service-account` to run the build as the dedicated Cloud Build SA (not the default Compute Engine SA).
   - The interpreter is explicitly set to `["bash", "-c"]`.
