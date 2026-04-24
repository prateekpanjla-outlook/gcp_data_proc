# requirements.txt

## 1. Overview

Python dependency manifest for the Phase 3 BigQuery Loader Cloud Function (2nd gen). Lists the four packages required at runtime. This file is bundled into the function source zip by Terraform (Layer 03) and used by Cloud Build to install dependencies during the function build step.

## 2. Prerequisites

- **Python:** 3.11 (must match the runtime specified in Terraform Layer 03 `build_config.runtime`)
- **pip:** Available in the Cloud Build environment (handled automatically by Cloud Functions build process)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Cloud Functions build system | Cloud Build reads this file to install packages into the function container |
| Downstream | `main.py` | All imports in the function (`functions_framework`, `cloudevents`, `google.cloud.bigquery`, `google.cloud.storage`) are satisfied by these packages |
| Related | Terraform Layer 03 `archive_file` | Bundles this file alongside `main.py` into the deployment zip |

## 4. Code Walkthrough

1. **`functions-framework>=3.0.0`** -- Google's HTTP/CloudEvent function framework. Provides the `@functions_framework.cloud_event` decorator used by `main.py` to receive Eventarc CloudEvents.

2. **`cloudevents>=1.2.0,<=1.11.0`** -- Python SDK for the CNCF CloudEvents spec. Supplies the `CloudEvent` type annotation used in the function signature. Upper-bounded to avoid breaking changes.

3. **`google-cloud-bigquery>=3.0.0`** -- BigQuery client library. Used to configure and run load jobs (`LoadJobConfig`, `load_table_from_uri`).

4. **`google-cloud-storage>=2.0.0`** -- Cloud Storage client library. Used to delete source blobs from the staging bucket after a successful load.
