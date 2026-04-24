## 1. Overview

This Dockerfile builds the container image for the Phase 4 monitoring dashboard. It produces a lightweight Python 3.12 image that serves the Flask application via gunicorn on port 8080, ready for deployment to Cloud Run.

## 2. Prerequisites

- **Docker** or **Cloud Build** for building the image.
- **Artifact Registry repository** (created in Phase 1 Terraform) to store the built image.
- The Cloud Build service account (`{env}-cloud-build`) needs `cloudbuild.builds.builder` and Artifact Registry write access.
- All application source files must be present in the build context: `app.py`, `requirements.txt`, `queries/`, and `templates/`.

## 3. Upstream & Downstream Dependencies

**Upstream (inputs)**:
- `requirements.txt` -- installed via `pip install` during the build.
- `app.py`, `queries/*.sql`, `templates/*.html` -- copied into the image via `COPY . .`.
- `python:3.12-slim` -- base image from Docker Hub.

**Downstream (what uses this image)**:
- `infrastructure/github_archive/phase4_monitoring/terraform/layers/03_operational/main.tf` -- the `build_dashboard_image` null_resource triggers `gcloud builds submit` using this Dockerfile, and the `google_cloud_run_v2_service.dashboard` resource deploys the resulting image.

## 4. IAM & Service Accounts

This Docker image is built by **Cloud Build** using the custom service account `{env}-cloud-build@{project}.iam.gserviceaccount.com`.

### Default SA vs Custom SA

| | Default SA | Custom SA |
|---|---|---|
| **Identity** | `{project_number}@cloudbuild.gserviceaccount.com` | `{env}-cloud-build@{project}.iam.gserviceaccount.com` |
| **Created by** | GCP automatically | Us, in Phase 1 Terraform |
| **Permissions** | Broad (editor-level) | Least-privilege, only the roles listed below |
| **Used when** | No `--service-account` flag passed to `gcloud builds submit` | Explicitly passed via `--service-account` flag |

We use the custom SA as a security best practice: the default SA is over-permissioned, violating the principle of least privilege. A custom SA limits blast radius if credentials are compromised.

### Roles required by the Cloud Build SA

| Role | Purpose |
|---|---|
| `cloudbuild.builds.builder` | Core Cloud Build permissions (read source, write logs, push images) |
| `run.admin` | Deploy Cloud Run services and jobs |
| `cloudfunctions.developer` | Deploy Cloud Functions (Phase 3) |
| `iam.serviceAccountUser` | Act as other SAs (e.g., the Cloud Run runtime SA) |
| `logging.logWriter` | Write build logs to Cloud Logging |

### Cross-references

- **Learnings Issue 3** (`phase4_deployment_issues.md`): When using a custom Cloud Build SA, the flag `--default-buckets-behavior=REGIONAL_USER_OWNED_BUCKET` is required on `gcloud builds submit`. Without it, Cloud Build fails because the custom SA cannot access the default logs bucket.
- **Learnings Issue 5** (`github_actions_ci_issues.md`): On GitHub Actions runners, `gcloud beta` commands need the `--quiet` flag to auto-install the beta component without an interactive prompt.

## 5. Code Walkthrough

1. **`FROM python:3.12-slim`** -- uses the slim variant to minimise image size while providing a full Python 3.12 runtime.

2. **`WORKDIR /app`** -- sets the working directory for all subsequent commands.

3. **`COPY requirements.txt .` + `RUN pip install ...`** -- copies only `requirements.txt` first and installs dependencies. This layer is cached by Docker, so rebuilds that only change application code skip the pip install step. `--no-cache-dir` avoids storing pip's download cache in the image. `--root-user-action=ignore` suppresses the pip warning about running as root.

4. **`COPY . .`** -- copies the entire build context (app.py, queries/, templates/) into `/app`.

5. **`CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]`** -- runs gunicorn as the production WSGI server, binding to port 8080 (Cloud Run's default). `app:app` refers to the `app` Flask instance in `app.py`.
