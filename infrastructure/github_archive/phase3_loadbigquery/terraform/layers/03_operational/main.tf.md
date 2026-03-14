# main.tf

## 1. Overview

Terraform Layer 03 (Operational) for Phase 3. Deploys the Cloud Functions 2nd gen function (`bq-loader`) with a built-in Eventarc trigger that fires on `google.cloud.storage.object.v1.finalized` events from the staging bucket. Also provisions the function source code bucket, uploads the zipped source, and creates IAM bindings for the GCS service agent (Pub/Sub publisher), bq_loader SA (Artifact Registry reader), and eventarc_invoker SA (Cloud Run invoker).

## 2. Prerequisites

- **Layer 01 applied:** Service accounts and BigQuery resources must exist (read via remote state)
- **Layer 02 applied:** Bucket and dataset IAM bindings must exist so the function can read from GCS and write to BigQuery
- **Phase 2 staging bucket:** Must exist; its name is passed via `var.staging_bucket_name`
- **Cloud Build SA:** `${environment}-cloud-build@${project_id}.iam.gserviceaccount.com` must exist with `cloudbuild.builds.builder` role (from Phase 1)
- **Source code:** `src/github_archive/phase3_loadbigquery/` directory must contain `main.py` and `requirements.txt`
- **Variables:** `project_id`, `staging_bucket_name` (required); `region`, `environment`, `dataset_id`, `table_id`, `function_memory`, `function_timeout`, `max_instances`, `delete_after_load` (have defaults)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Layer 01 remote state | Provides `service_account_email_bq_loader` and `service_account_email_eventarc_invoker` |
| Upstream | Layer 02 remote state | Referenced but not directly used for outputs in this file; ensures IAM bindings exist |
| Upstream | Phase 2 staging bucket | Source of Eventarc trigger events and location of `.ndjson.gz` files |
| Upstream | `src/github_archive/phase3_loadbigquery/` | Source code directory archived and uploaded to the source bucket |
| Downstream | Cloud Functions 2nd gen / Cloud Run | The deployed function processes GCS events and runs BigQuery load jobs |
| Downstream | BigQuery `github_events` table | Receives loaded data from the function |

## 4. IAM & Service Accounts

This layer creates IAM bindings for the Cloud Function runtime and its supporting services:

- **`{env}-bq-loader` SA** (Cloud Function runtime SA, read from Layer 01 remote state):
  - `roles/artifactregistry.reader` — allows Cloud Build to pull base images when building the function.
  - Runs as the `service_account_email` on the Cloud Function's service config, giving it all the BigQuery and Storage permissions granted in Layers 01 and 02.
- **`{env}-eventarc-invoker` SA** (read from Layer 01 remote state):
  - `roles/run.invoker` — allows Eventarc to invoke the Cloud Run service backing the 2nd gen Cloud Function.
  - Set as the `service_account` on the Eventarc trigger for authenticated event delivery.
- **GCS service agent** (`service-{project_number}@gs-project-accounts.iam.gserviceaccount.com`):
  - `roles/pubsub.publisher` — allows GCS to publish object finalization events to the Pub/Sub topic used by Eventarc.
- **Cloud Build SA:** `{env}-cloud-build` (from Phase 1) is used for the function build process.

## 5. Code Walkthrough

1. **Remote state data sources (lines 16-30):** Reads Layer 01 (`phase3-static`) and Layer 02 (`phase3-first-time`) state from the GCS backend.

2. **GCP data sources (lines 33-38):** `google_storage_project_service_account` retrieves the GCS service agent email for Pub/Sub IAM. `google_project` retrieves project metadata.

3. **Locals (lines 43-53):** Defines `function_name` (`${env}-bq-loader`), `source_bucket` name, and `common_labels`.

4. **IAM -- GCS Pub/Sub Publisher (lines 59-63):** Grants the GCS service agent `pubsub.publisher` so it can publish object finalization events to the Pub/Sub topic used by Eventarc.

5. **IAM -- Artifact Registry Reader (lines 68-72):** Grants `bq_loader` SA `artifactregistry.reader` so Cloud Build can pull base images during function build.

6. **IAM -- Cloud Run Invoker (lines 78-82):** Grants `eventarc_invoker` SA `run.invoker` so Eventarc can invoke the Cloud Run service backing the 2nd gen function.

7. **Source bucket (lines 90-97):** Creates a GCS bucket for function source code. `force_destroy` is enabled only in dev/test environments.

8. **Source upload (lines 102-115):** Archives the source directory into a zip using `data.archive_file`, then uploads it as a bucket object. The object name includes an MD5 hash of `main.py` so redeployments are triggered on code changes.

9. **Cloud Function (lines 120-181):**
   - **Build config (lines 134-148):** Python 3.11 runtime, entry point `load_to_bigquery`, Cloud Build SA for the build process, source from the uploaded zip.
   - **Service config (lines 151-168):** Configurable memory/timeout/CPU/max instances, environment variables (`PROJECT_ID`, `DATASET_ID`, `TABLE_ID`, `DELETE_AFTER_LOAD`), internal-only ingress, all traffic on latest revision, `bq_loader` as the runtime SA.
   - **Event trigger (lines 170-180):** Listens for `google.cloud.storage.object.v1.finalized` events on the staging bucket with retry policy enabled, authenticated by the `eventarc_invoker` SA.
