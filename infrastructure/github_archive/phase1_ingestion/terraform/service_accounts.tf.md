# service_accounts.tf

## 1. Overview

Creates two service accounts and their IAM bindings for Phase 1:

1. **GitHub Archive Downloader SA** -- the runtime identity for the Cloud Run Job that downloads GitHub Archive files into GCS.
2. **Cloud Scheduler SA** -- the identity Cloud Scheduler uses to invoke the Cloud Run Job via the Jobs API.

Also grants the Cloud Scheduler service agent the `iam.serviceAccountTokenCreator` role on the scheduler SA so it can mint OAuth tokens for authenticated HTTP calls.

## 2. Prerequisites

- The `var.project_id` and `var.environment` variables must be set.
- `locals.tf` must define `local.env_prefix` and `local.github_archive.service_account_id`.
- The Cloud Scheduler service agent (`service-<PROJECT_NUMBER>@gcp-sa-cloudscheduler.iam.gserviceaccount.com`) must exist, which happens automatically when the Cloud Scheduler API is enabled.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `variables.tf` | `project_id`, `environment` |
| Upstream | `locals.tf` | `local.env_prefix`, `local.github_archive.service_account_id` |
| Downstream | `cloud_run_jobs.tf` | Downloader SA is set as the Cloud Run Job's `service_account` |
| Downstream | `scheduler.tf` | Scheduler SA is used in the `oauth_token` block |
| Downstream | `iam.tf` | Downloader SA is referenced for Artifact Registry reader role |
| Downstream | Phase 2 (Eventarc) | Phase 2 watches the landing bucket that this SA writes to |

## 4. IAM & Service Accounts

This file defines two service accounts and their core IAM bindings:

| Service Account | ID Pattern | Purpose |
|----------------|------------|---------|
| **Downloader SA** | `{env}-github-archive-downloader@{project}.iam.gserviceaccount.com` | Runtime identity for the Cloud Run Job that downloads GitHub Archive files |
| **Scheduler SA** | `{env}-scheduler@{project}.iam.gserviceaccount.com` | Identity used by Cloud Scheduler to invoke the Cloud Run Job via OAuth token |

**Roles granted here**:

| SA | Role | Why |
|----|------|-----|
| Downloader | `roles/storage.objectUser` | Read/write GCS objects in the landing bucket |
| Downloader | `roles/logging.logWriter` | Emit structured logs from the Cloud Run Job |
| Scheduler | `roles/iam.serviceAccountTokenCreator` (granted to Cloud Scheduler service agent) | Allows the service agent to mint OAuth tokens on behalf of the scheduler SA |

**Cross-reference**: See `learnings/phase4_deployment_issues.md` (Issue 15) for how stale deleted SAs can block dataset IAM updates — this is especially relevant when destroying and recreating these SAs. See `learnings/github_actions_ci_issues.md` (Issue 7) for why remote state is critical to avoid orphaned SA resources in CI.

## 5. Code Walkthrough

1. **`google_service_account.github_archive_downloader`** -- Creates the downloader SA with an ID like `dev-github-archive-downloader`. Display name includes the environment.

2. **`google_project_iam_member.github_archive_downloader_storage`** -- Grants `roles/storage.objectUser` at the project level, allowing the downloader to read and write GCS objects (specifically the landing bucket).

3. **`google_project_iam_member.github_archive_downloader_logging`** -- Grants `roles/logging.logWriter` so the Cloud Run Job can emit structured logs.

4. **`google_service_account.scheduler`** -- Creates the scheduler SA with an ID like `dev-scheduler`.

5. **`locals.project_number`** -- Hardcoded project number (`592311283460`) used to reference the Cloud Scheduler service agent. A TODO note indicates this should be replaced with the `google_project` data source once API propagation is stable.

6. **`google_service_account_iam_member.scheduler_token_creator`** -- Grants the Cloud Scheduler service agent `roles/iam.serviceAccountTokenCreator` on the scheduler SA, enabling it to generate OAuth tokens for authenticated HTTP target calls.
