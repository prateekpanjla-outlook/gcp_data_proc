# cloud_run_jobs.tf

## 1. Overview

Defines the Cloud Run v2 Job that downloads hourly GitHub Archive files and streams them into the GCS landing bucket. The job runs a custom container image built from the project's source code and pushed to Artifact Registry.

## 2. Prerequisites

- The downloader service account must exist (`service_accounts.tf`).
- The Artifact Registry repository must exist (`artifact_registry.tf`).
- The container image must be built and pushed (`build.tf` -- `null_resource.build_downloader_image`).
- The Cloud Run API (`run.googleapis.com`) must be enabled.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `service_accounts.tf` | Downloader SA used as the job's runtime identity |
| Upstream | `artifact_registry.tf` | Repository where the container image is stored |
| Upstream | `build.tf` | `null_resource.build_downloader_image` must complete first (`depends_on`) |
| Upstream | `variables.tf` | `project_id`, `region`, `environment` |
| Downstream | `scheduler.tf` | Cloud Scheduler invokes this job on a cron schedule |
| Downstream | `storage.tf` (landing bucket) | The job writes downloaded files to the `BUCKET_NAME` passed via env var |

## 4. Code Walkthrough

1. **`google_cloud_run_v2_job.github_archive_downloader`** -- Creates a Cloud Run v2 Job named `{env}-github-archive-download-gsutil`.

2. **`service_account`** -- Set to the downloader SA email, which has `storage.objectUser`, `logging.logWriter`, and `artifactregistry.reader` roles.

3. **`timeout`** -- 1800 seconds (30 minutes). GitHub Archive files are small but network variability is accounted for.

4. **`image`** -- Points to `{region}-docker.pkg.dev/{project}/{env}-github-archive/github-archive-downloader:latest` in Artifact Registry.

5. **Environment variables**:
   - `ENVIRONMENT` -- the current environment name.
   - `PROJECT_ID` -- the GCP project.
   - `BUCKET_NAME` -- the landing bucket name (e.g., `{project_id}-dev-github-archive-landing`).

6. **`resources.limits`** -- 1 vCPU and 512 Mi memory. The download script uses gsutil streaming so memory usage stays low.

7. **`depends_on`** -- Waits for `null_resource.build_downloader_image` to ensure the container image exists before the job is created.
