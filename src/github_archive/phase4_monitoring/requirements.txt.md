## 1. Overview

`requirements.txt` pins the Python dependencies for the Phase 4 monitoring dashboard. It specifies three packages with major-version pins (using `.*` minor-version wildcards) to balance stability with automatic patch updates.

## 2. Prerequisites

- **Python 3.12+** (matching the Dockerfile base image).
- **pip** for installation (`pip install -r requirements.txt`).
- Network access to PyPI (or a configured private index) during `docker build` / `pip install`.

## 3. Upstream & Downstream Dependencies

**Upstream (what determines these dependencies)**:
- `app.py` -- imports `flask` and `google.cloud.bigquery`.
- `Dockerfile` -- the `CMD` uses `gunicorn` as the WSGI server.

**Downstream (what consumes this file)**:
- `Dockerfile` -- `COPY requirements.txt .` followed by `RUN pip install -r requirements.txt`.
- `infrastructure/github_archive/phase4_monitoring/terraform/layers/03_operational/main.tf` -- the `build_dashboard_image` null_resource includes a `requirements_hash` trigger so the image is rebuilt when this file changes.

## 4. Code Walkthrough

1. **`flask==3.1.*`** -- the web framework. Version 3.1.x is pinned. Flask provides routing, Jinja2 template rendering, and the WSGI application object.

2. **`google-cloud-bigquery==3.*`** -- the official Google Cloud BigQuery client library. Used by `app.py` to execute SQL queries against the `pipeline_logs` and `github_archive` datasets. Major version 3 is pinned.

3. **`gunicorn==23.*`** -- production-grade WSGI HTTP server. Used in the Dockerfile `CMD` to serve the Flask app. Major version 23 is pinned. Gunicorn replaces Flask's built-in development server for production use on Cloud Run.
