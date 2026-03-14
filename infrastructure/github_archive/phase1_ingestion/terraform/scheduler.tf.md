# scheduler.tf

## 1. Overview

Creates the Cloud Scheduler job that triggers the GitHub Archive download Cloud Run Job every hour, and grants the scheduler service account the `run.invoker` role on that specific job. The scheduler fires at 30 minutes past each hour to allow time for GitHub Archive files to become available.

## 2. Prerequisites

- The Cloud Scheduler API (`cloudscheduler.googleapis.com`) must be enabled.
- The Cloud Run Job (`cloud_run_jobs.tf`) must exist.
- The scheduler service account (`service_accounts.tf`) must exist.
- The `iam.serviceAccountTokenCreator` binding for the Cloud Scheduler service agent must be in place (`service_accounts.tf`).

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `cloud_run_jobs.tf` | The Cloud Run Job that the scheduler invokes |
| Upstream | `service_accounts.tf` | Scheduler SA used for `oauth_token` authentication |
| Upstream | `locals.tf` | `local.github_archive.scheduler_name`, `local.github_archive.job_name` |
| Downstream | Cloud Run Job execution | Each cron tick triggers a job execution that downloads a GitHub Archive file |
| Downstream | Phase 2 | Indirectly triggers Phase 2 by creating objects in the landing bucket |

## 4. Code Walkthrough

1. **`google_cloud_scheduler_job.github_archive_download`** -- Creates a scheduler job named `{env}-github-archive-download-job` with a `30 * * * *` cron schedule (every hour at :30, UTC).

2. **`http_target`** -- Sends a POST request to the Cloud Run Jobs API endpoint (`https://{region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/{project}/jobs/{job_name}:run`). Uses `oauth_token` (not OIDC) because the Jobs API endpoint is a `*.googleapis.com` URL that requires OAuth tokens.

3. **`retry_config`** -- Retries up to 2 times with a minimum backoff of 10 seconds if the API call fails.

4. **`depends_on`** -- Waits for the `scheduler_github_invoker` IAM binding to be applied before creating the scheduler job.

5. **`google_cloud_run_v2_job_iam_member.scheduler_github_invoker`** -- Grants `roles/run.invoker` on the specific Cloud Run Job to the scheduler SA. This is a resource-level IAM binding (not project-level), following the principle of least privilege.
