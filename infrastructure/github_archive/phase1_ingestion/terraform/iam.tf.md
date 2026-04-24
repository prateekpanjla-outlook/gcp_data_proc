# iam.tf

## 1. Overview

Grants the GitHub Archive Downloader service account the `roles/artifactregistry.reader` role at the project level. This allows the Cloud Run Job to pull its container image from Artifact Registry at startup.

## 2. Prerequisites

- The downloader service account (`google_service_account.github_archive_downloader`) must be created first (defined in `service_accounts.tf`).
- The Artifact Registry API must be enabled on the project.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `service_accounts.tf` | Provides the downloader SA email |
| Upstream | `variables.tf` | Provides `project_id` |
| Downstream | `cloud_run_jobs.tf` | Without this role, the Cloud Run Job cannot pull its container image and will fail to start |

## 4. IAM & Service Accounts

**Target SA**: `{env}-github-archive-downloader@{project}.iam.gserviceaccount.com`

This file grants a single additional IAM role to the downloader SA:

| Role | Why |
|------|-----|
| `roles/artifactregistry.reader` | Allows the Cloud Run Job to pull its container image from Artifact Registry at startup. Without this, the job fails to start. |

This is a project-level binding, so the SA can read from any Artifact Registry repository in the project. The role complements `roles/storage.objectUser` and `roles/logging.logWriter` granted in `service_accounts.tf`.

**Cross-reference**: See `learnings/phase4_deployment_issues.md` (Issue 4) for an example of a missing IAM role (`logging.admin`) causing deployment failures — a reminder to ensure all required roles are granted before dependent resources are created. See `learnings/github_actions_ci_issues.md` (Issue 7) for how lost state can orphan IAM bindings.

## 5. Code Walkthrough

1. **`google_project_iam_member.downloader_artifact_reader`** -- A single IAM binding that grants `roles/artifactregistry.reader` to the downloader service account. This is a project-level binding so the SA can read from any Artifact Registry repository in the project. The role is required because Cloud Run pulls the image using the job's runtime service account.
