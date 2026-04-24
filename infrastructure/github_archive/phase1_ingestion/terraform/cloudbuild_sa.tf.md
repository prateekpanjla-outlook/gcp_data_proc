# cloudbuild_sa.tf

## 1. Overview

Creates a dedicated Cloud Build service account and grants it the IAM roles needed to build container images, push to Artifact Registry, deploy Cloud Run services/jobs, and deploy Cloud Functions. This SA is defined once in Phase 1 and shared across all phases (Phase 2, 3, 4).

## 2. Prerequisites

- `var.project_id` and `var.environment` must be set.
- The following APIs must be enabled: Cloud Build, Cloud Run, Cloud Functions, Artifact Registry, IAM.

## 3. Upstream & Downstream Dependencies

| Direction | Resource / File | Relationship |
|-----------|----------------|--------------|
| Upstream | `variables.tf` | `project_id`, `environment` |
| Downstream | `build.tf` | `null_resource.wait_for_iam_propagation` depends on these IAM bindings; `null_resource.build_downloader_image` uses this SA for `gcloud builds submit` |
| Downstream | Phase 2 Terraform | References this SA (by convention `{env}-cloud-build`) for its own Cloud Build submissions |
| Downstream | Phase 3 Terraform | References this SA for Cloud Function deployments (uses `roles/cloudfunctions.developer`) |
| Downstream | Phase 4 Terraform | References this SA for Cloud Run service deployments |

## 4. IAM & Service Accounts

**Service account**: `{env}-cloud-build@{project}.iam.gserviceaccount.com`

This is a shared Cloud Build SA used across all phases (1-4). It is defined once here and referenced by convention in other phases.

**Roles granted**:

| Role | Why |
|------|-----|
| `roles/cloudbuild.builds.builder` | Submit builds, push images, read/write Cloud Build storage |
| `roles/run.admin` | Deploy and manage Cloud Run services and jobs (Phases 1, 2, 4) |
| `roles/cloudfunctions.developer` | Deploy Cloud Functions (Phase 3) |
| `roles/iam.serviceAccountUser` | Attach runtime SAs to Cloud Run revisions and Cloud Functions |
| `roles/logging.logWriter` | Write build logs |

**Cross-reference**: See `learnings/phase4_deployment_issues.md` (Issue 3) for how Cloud Build with a custom SA requires `--default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET` or an explicit logs bucket. See `learnings/github_actions_ci_issues.md` (Issue 6) for PowerShell-to-bash conversion issues in null_resource provisioners that use this SA.

## 5. Code Walkthrough

1. **`google_service_account.cloudbuild_sa`** -- Creates a service account with ID `{env}-cloud-build` (e.g., `dev-cloud-build`).

2. **`local.cloud_build_sa_roles`** -- A `toset` of five IAM roles:
   - `roles/cloudbuild.builds.builder` -- Submit builds, push images, read/write Cloud Build storage.
   - `roles/run.admin` -- Deploy and manage Cloud Run services and jobs.
   - `roles/cloudfunctions.developer` -- Deploy Cloud Functions (used by Phase 3).
   - `roles/iam.serviceAccountUser` -- Attach runtime SAs to Cloud Run revisions and Cloud Functions.
   - `roles/logging.logWriter` -- Write build logs.

3. **`google_project_iam_member.cloudbuild_sa_roles`** -- Uses `for_each` over the role set to create one IAM binding per role, all at the project level.
