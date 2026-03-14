## 1. Overview

`requirements.txt` declares all Python package dependencies for the Phase 2 Cloud Run Service. It pins version ranges (minimum + major version ceiling) to balance stability with security patches. The file is consumed by `pip install -r requirements.txt` during the Docker build (see `Dockerfile.processor`).

## 2. Prerequisites

- **Python** >= 3.11 (specified in the file header comment)
- **pip** to install the dependencies
- **Network access** to PyPI (or a configured private index) during `pip install`

## 3. Upstream & Downstream Dependencies

| Direction | Component | Relationship |
|-----------|-----------|-------------|
| Upstream | **`Dockerfile.processor`** | `COPY requirements.txt .` and `pip install -r requirements.txt` in the builder stage. |
| Downstream | **All Phase 2 Python modules** | Every `.py` file in `phase2_process_files/` depends on packages declared here. |

## 4. Code Walkthrough

The file declares the following dependency groups:

1. **Core data processing**:
   - `pandas >=2.0.0,<3.0.0` -- DataFrame operations, chunked JSON reading, dtype coercion.
   - `numpy >=1.24.0,<2.0.0` -- Required by pandas; used implicitly for array operations.

2. **Google Cloud SDK**:
   - `google-cloud-storage >=2.10.0` -- GCS blob download/upload in `file_processor.py` and `ndjson_writer.py`.
   - `google-cloud-logging >=3.8.0` -- Structured logging integration with Cloud Logging.
   - `google-cloud-error-reporting >=1.6.0` -- Error reporting to Cloud Error Reporting.
   - `google-cloud-bigquery >=3.0.0` -- `SchemaField` class used in `dtype_definitions.py` for BigQuery schema definition.

3. **Web framework**:
   - `Flask >=3.0.0,<4.0.0` -- HTTP server in `main.py` for receiving Eventarc events.
   - `Werkzeug >=3.0.0,<4.0.0` -- WSGI utilities (Flask dependency, pinned explicitly).
   - `gunicorn >=21.2.0,<24.0.0` -- Production WSGI server used in the Dockerfile CMD.

4. **Authentication**:
   - `google-auth >=2.23.0,<3.0.0` -- GCP authentication for service account credentials.

5. **Utilities**:
   - `python-dateutil >=2.8.0` -- Date parsing (used by pandas internally).
   - `pytz >=2023.3` -- Timezone handling.
