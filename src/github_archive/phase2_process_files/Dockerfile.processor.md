## 1. Overview

`Dockerfile.processor` is the multi-stage Docker build file for the Phase 2 Cloud Run Service. It produces a minimal Python 3.11-slim image that runs the Flask application (`main.py`) behind Gunicorn. The build uses two stages: a builder stage that compiles Python dependencies (with `gcc`/`g++` for native extensions), and a runtime stage that copies only the installed packages and application code.

## 2. Prerequisites

- **Docker** (or Cloud Build) to build the image.
- **Build context**: Must be set to `src/github_archive/phase2_process_files/` (the `COPY . .` on line 55 copies the entire directory into `/app`).
- **`requirements.txt`**: Must be present in the build context root.
- **Artifact Registry / Container Registry**: A GCR or AR repository to push the built image.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **CI/CD or manual build** | `docker build -f Dockerfile.processor .` or Cloud Build triggers. |
| Upstream | **`requirements.txt`** | Defines all Python packages installed in the builder stage. |
| Downstream | **Cloud Run** | The built image is deployed as a Cloud Run service that receives Eventarc triggers. |
| Downstream | **`main.py`** | Gunicorn launches `main:app` (the Flask application object). |

## 4. Code Walkthrough

1. **Stage 1 -- Builder (lines 7-21)**:
   - Base image: `python:3.11-slim`.
   - Installs `gcc` and `g++` for compiling native Python extensions (e.g., numpy, pandas C extensions).
   - Copies `requirements.txt` and runs `pip install --no-cache-dir --user` to install packages into `/root/.local`.

2. **Stage 2 -- Runtime (lines 27-75)**:
   - Base image: `python:3.11-slim` (same version, clean layer).
   - Sets environment variables: `PYTHONUNBUFFERED=1` (flush stdout immediately for Cloud Logging), `PYTHONDONTWRITEBYTECODE=1` (no `.pyc` files), `PIP_NO_CACHE_DIR=1`.
   - Installs only `ca-certificates` for TLS connections to GCS.
   - Creates a non-root `appuser` for security.
   - Copies installed Python packages from builder's `/root/.local` to `/usr/local`.
   - Copies application code (`COPY . .`) into `/app`.
   - Sets `PYTHONPATH=/app:/usr/local/lib/python3.11/site-packages` so relative imports (`from processors.file_processor import ...`) work.
   - Creates `/tmp/processing` directory for temp files, owned by `appuser`.
   - Switches to `appuser`.
   - Exposes port 8080.
   - Adds a `HEALTHCHECK` that hits `http://localhost:8080/health` every 30 seconds (30s start period, 3 retries).
   - **CMD**: Runs Gunicorn with 1 worker, 2 threads, 3600s timeout (for large file processing), binding to `0.0.0.0:8080`, launching `main:app`.
