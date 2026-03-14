# artifact_registry.tf

## 1. Overview

Creates the Artifact Registry Docker repository used to store container images for the data pipeline. Although some documentation suggests this belongs in Phase 2, it is defined here so that Phase 1 is self-contained and can push the downloader image during its own `terraform apply`.

## 2. Prerequisites

- The Artifact Registry API (`artifactregistry.googleapis.com`) must be enabled.
- `var.project_id`, `var.region`, and `var.environment` must be set.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `variables.tf` | `project_id`, `region`, `environment` |
| Downstream | `build.tf` | `null_resource.build_downloader_image` depends on this repository existing before pushing the image |
| Downstream | `cloud_run_jobs.tf` | The Cloud Run Job's `image` field references this repository |
| Downstream | `iam.tf` | The downloader SA is granted `artifactregistry.reader` to pull images from this repo |
| Downstream | Phase 2, 3, 4 | Other phases may push/pull images to/from the same repository |

## 4. IAM & Service Accounts

- **SAs that access this repository**:
  - `{env}-cloud-build` — writes (pushes) images. Access is implicit via the `cloudbuild.builds.builder` role, which includes `artifactregistry.writer`.
  - `{env}-github-archive-downloader` — reads (pulls) images. Granted `artifactregistry.reader` explicitly in `iam.tf`.
  - `{env}-github-archive-processor` — reads images implicitly via Cloud Run at deploy time.
- **Non-obvious**: Cloud Run automatically pulls images using the runtime SA, but that SA needs `artifactregistry.reader` granted at the project level (not just on the repository). Without it, Cloud Run deploy succeeds but the container fails to start.

## 5. Code Walkthrough

1. **`google_artifact_registry_repository.data_pipeline_repo`** -- Creates a Docker-format repository named `{env}-github-archive` (e.g., `dev-github-archive`) in the specified region. The repository stores all container images for the GitHub Archive data pipeline.
