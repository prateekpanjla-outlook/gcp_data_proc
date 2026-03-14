# build.tf

## 1. Overview

Automates the container image build process during `terraform apply` using two `null_resource` provisioners:

1. **IAM propagation wait** -- Polls the GCP IAM testPermissions API to confirm the Cloud Build SA's permissions are active before submitting a build.
2. **Image build** -- Runs `gcloud builds submit` to build and push the downloader container image to Artifact Registry.

Both use `local-exec` provisioners with bash scripts.

## 2. Prerequisites

- `gcloud` CLI must be installed and available on the machine running Terraform.
- `curl` must be available (used by the IAM propagation check).
- The deployer SA key file must exist at `var.deployer_sa_key_path`.
- The Cloud Build API (`cloudbuild.googleapis.com`) must be enabled.
- Source files must exist at their expected paths relative to the module:
  - `../../../../src/github_archive/Dockerfile`
  - `../../../../src/github_archive/phase1_ingestion/scripts/download.sh`
  - `../../../../config/cloudbuild-phase1.yaml`

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `cloudbuild_sa.tf` | `wait_for_iam_propagation` depends on IAM roles being granted; `build_downloader_image` uses the Cloud Build SA |
| Upstream | `artifact_registry.tf` | Repository must exist before the image can be pushed |
| Upstream | `variables.tf` | `deployer_sa_key_path`, `project_id`, `region`, `environment` |
| Upstream | Source code | `Dockerfile`, `download.sh`, `cloudbuild-phase1.yaml` -- changes to these files trigger a rebuild (via `triggers` block) |
| Downstream | `cloud_run_jobs.tf` | The Cloud Run Job depends on `build_downloader_image` to ensure the image exists |

## 4. Code Walkthrough

1. **`null_resource.wait_for_iam_propagation`** (lines 5-38):
   - Depends on `google_project_iam_member.cloudbuild_sa_roles` to ensure IAM policies are written.
   - Triggers re-run when the SA email changes.
   - Runs a bash loop (up to 12 attempts, 10s apart = 120s max) that:
     1. Impersonates the Cloud Build SA to get an access token.
     2. Calls the GCS `testPermissions` API on the `{project}_cloudbuild` bucket to verify `storage.objects.get` and `storage.objects.create`.
     3. Exits successfully once permissions are confirmed, or fails after timeout.

2. **`null_resource.build_downloader_image`** (lines 43-67):
   - Depends on the Artifact Registry repo and the IAM propagation check.
   - `triggers` block computes `filesha256` of the Dockerfile, download script, and Cloud Build config. A change to any of these triggers a rebuild on the next `terraform apply`.
   - Runs `gcloud auth activate-service-account` with the deployer key, then `gcloud builds submit` with:
     - `--config` pointing to `cloudbuild-phase1.yaml`.
     - `--substitutions` passing `_REGION` and `_ENV`.
     - `--service-account` set to the Cloud Build SA.
