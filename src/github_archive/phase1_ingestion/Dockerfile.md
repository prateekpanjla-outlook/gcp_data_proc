# Dockerfile

## 1. Overview

This Dockerfile builds the container image for the Phase 1 GitHub Archive ingestion Cloud Run Job. It packages `download.sh` on top of Google's official Cloud SDK slim image, producing a lightweight container that has everything needed (`gcloud`, `gsutil`, `curl`) to download hourly archive files and stream them into GCS.

## 2. Prerequisites

| Requirement | Detail |
|---|---|
| **Docker / Cloud Build** | A Docker-compatible build environment (local Docker, Cloud Build, etc.). |
| **Build context** | The build context must be set to `src/github_archive/` (not the `phase1_ingestion/` subdirectory), because the `COPY` instruction references `phase1_ingestion/scripts/download.sh` relative to that root. |
| **Base image access** | Network access to `gcr.io` to pull `gcr.io/google.com/cloudsdktool/google-cloud-cli:slim`. |

## 3. Upstream & Downstream Dependencies

```
Upstream
--------
Source file: phase1_ingestion/scripts/download.sh  (copied into the image)
Base image: gcr.io/google.com/cloudsdktool/google-cloud-cli:slim

Downstream
----------
Artifact Registry / Container Registry  (built image is pushed here)
  --> Cloud Run Job (runs the image on an hourly schedule via Cloud Scheduler)
```

- **Upstream**: The only local dependency is `download.sh`. The base image (`google-cloud-cli:slim`) supplies `gcloud`, `gsutil`, `curl`, and a minimal Debian environment.
- **Downstream**: The built image is pushed to Artifact Registry (or Container Registry) and referenced by the Cloud Run Job definition. Cloud Scheduler triggers the job every hour.

## 4. Code Walkthrough

1. **Base image** (line 3): Uses `gcr.io/google.com/cloudsdktool/google-cloud-cli:slim`, the slim variant of Google's Cloud SDK image. This provides `gcloud`, `gsutil`, and `curl` out of the box while keeping the image size small (no full SDK extras).

2. **Working directory** (line 6): Sets `/app` as the working directory inside the container.

3. **Copy script** (line 12): Copies `phase1_ingestion/scripts/download.sh` into `/app/download.sh`. The comment notes that the build context root is `src/github_archive/`, so the path is relative to that directory.

4. **Make executable** (line 15): `chmod +x download.sh` ensures the script has execute permissions inside the image.

5. **Entrypoint** (line 18): Sets `download.sh` as the container entrypoint using exec form (`["./download.sh"]`), so the script runs as PID 1 and receives signals correctly. No default `CMD` arguments are provided; all configuration comes from environment variables injected by the Cloud Run Job definition.
