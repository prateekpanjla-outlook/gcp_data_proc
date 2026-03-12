# GitHub Archive Pipeline — Cloud Dataflow

## Overview

Single Apache Beam batch pipeline that handles the entire GitHub Archive ETL:
download from gharchive.org, transform/flatten nested JSON, and load to BigQuery.

Replaces all 3 phases of the original pipeline (Cloud Run Job + Cloud Function + Cloud Function)
with one Dataflow job triggered hourly by Cloud Scheduler.

## Architecture

```
Cloud Scheduler (hourly)
    |
    v
Dataflow Flex Template Launch (REST API)
    |
    v
+--------------------------------------------------+
|  Apache Beam Pipeline (Dataflow Runner)           |
|                                                   |
|  1. Download: HTTPS GET data.gharchive.org        |
|     -> Write .json.gz to GCS temp location        |
|     (runs on launcher before pipeline starts)     |
|                                                   |
|  2. ReadFromText(gs://temp/*.json.gz)             |
|     (auto-decompresses .gz)                       |
|                                                   |
|  3. ParDo(FlattenGitHubEvent)                     |
|     - Parse JSON line                             |
|     - Extract actor.* -> actor_id, actor_login..  |
|     - Extract repo.* -> repo_id, repo_name..      |
|     - Extract payload.* -> payload_ref, etc.       |
|     - Extract payload.issue.labels                |
|     - Add etl_create_ts, etl_create_id            |
|                                                   |
|  4. WriteToBigQuery (FILE_LOADS method)           |
|     -> github_archive.github_events               |
|     WRITE_APPEND, CREATE_NEVER                    |
|                                                   |
|  5. Post-pipeline: cleanup temp GCS file          |
+--------------------------------------------------+
```

## Data Flow

```
Source:  https://data.gharchive.org/{YYYY-MM-DD-H}.json.gz
        (~300MB compressed, ~2GB uncompressed, ~500K events/hour)

Temp:   gs://{project}-{env}-dataflow-temp/downloads/{YYYY-MM-DD-H}.json.gz

Sink:   {project}.github_archive.github_events
        (partitioned by created_at, clustered by event_type)
```

## Schema

27 flattened fields + `payload_issue_labels` REPEATED RECORD (7 sub-fields):

| Field | BigQuery Type | Source |
|-------|--------------|--------|
| event_id | STRING | id |
| event_type | STRING | type |
| created_at | TIMESTAMP | created_at |
| actor_id | INT64 | actor.id |
| actor_login | STRING | actor.login |
| actor_display_login | STRING | actor.display_login |
| actor_gravatar_id | STRING | actor.gravatar_id |
| actor_url | STRING | actor.url |
| actor_avatar_url | STRING | actor.avatar_url |
| actor_type | STRING | actor.type |
| actor_site_admin | BOOLEAN | actor.site_admin |
| repo_id | INT64 | repo.id |
| repo_name | STRING | repo.name |
| repo_url | STRING | repo.url |
| public | BOOLEAN | public |
| payload_ref | STRING | payload.ref |
| payload_ref_type | STRING | payload.ref_type |
| payload_push_id | INT64 | payload.push_id |
| payload_size | INT64 | payload.size |
| payload_distinct_size | INT64 | payload.distinct_size |
| payload_head | STRING | payload.head |
| payload_before | STRING | payload.before |
| payload_issue_labels | RECORD (REPEATED) | payload.issue.labels |
| etl_create_ts | TIMESTAMP | (pipeline runtime) |
| etl_create_id | STRING | "DATAFLOW_PROCESSOR" |

### payload_issue_labels sub-fields
| Field | Type |
|-------|------|
| id | INT64 |
| node_id | STRING |
| url | STRING |
| name | STRING |
| color | STRING |
| default | BOOLEAN |
| description | STRING |

## Source Code Structure

```
src/github_archive_dataflow/
    pipeline.py                  # Main Beam pipeline entry point
    transforms/
        __init__.py
        download.py              # Download file from gharchive.org to GCS
        flatten_events.py        # DoFn: parse JSON, flatten, add ETL metadata
    schema/
        __init__.py
        bigquery_schema.py       # Beam TableSchema definition (27 fields)
    options.py                   # Custom PipelineOptions (hour_offset, project, etc.)
    setup.py                     # Required for Dataflow worker dependencies
    requirements.txt             # apache-beam[gcp], requests
    Dockerfile                   # Flex Template container image
```

## Infrastructure (Terraform, 3-layer)

```
infrastructure/github_archive_dataflow/terraform/layers/
    01_static/
        main.tf          # SAs, GCS buckets (temp + staging), BQ dataset/table
        schema.json      # BigQuery schema (same as original)
        variables.tf / outputs.tf / terraform.tf
    02_first_time/
        main.tf          # APIs (dataflow, bigquery), service agent IAM
        variables.tf / outputs.tf / terraform.tf
    03_operational/
        main.tf          # Artifact Registry, Cloud Build, Cloud Scheduler
        variables.tf / outputs.tf / terraform.tf
    templates/
        metadata.json    # Flex Template parameter metadata
```

### Key Terraform Resources

| Layer | Resource | Purpose |
|-------|----------|---------|
| 01 | `google_service_account` | Dataflow worker SA, Scheduler SA |
| 01 | `google_storage_bucket` | Temp bucket, Dataflow staging bucket |
| 01 | `google_bigquery_dataset` | github_archive dataset |
| 01 | `google_bigquery_table` | github_events (partitioned, clustered) |
| 02 | `google_project_service` | dataflow.googleapis.com, bigquery.googleapis.com |
| 03 | `google_artifact_registry_repository` | Flex Template Docker images |
| 03 | `google_cloud_scheduler_job` | Hourly trigger -> Dataflow REST API |

### IAM Roles

Dataflow worker SA needs:
- `roles/dataflow.worker`
- `roles/bigquery.dataEditor` (on dataset)
- `roles/bigquery.jobUser` (project-level)
- `roles/storage.objectAdmin` (on temp/staging buckets)

## Orchestration

- **Cloud Scheduler** runs at `30 * * * *` (hourly at :30, same as current)
- Calls Dataflow Flex Template launch REST API:
  `POST https://dataflow.googleapis.com/v1b3/projects/{project}/locations/{region}/flexTemplates:launch`
- Passes runtime parameters: `hour_offset`, `project_id`, `temp_bucket`
- Each launch creates a new Dataflow job that:
  1. Downloads the target hour's file to GCS
  2. Runs the Beam pipeline (read -> flatten -> write to BQ)
  3. Cleans up temp file
  4. Job completes and resources are released

## Cost Estimate

- **Dataflow batch**: ~$0.056/vCPU-hr, ~$0.003/GB-hr
- Typical hourly run (~300MB input, 2-3 min): **~$0.01-0.05/run**
- **BigQuery load** (FILE_LOADS method): **free** (batch loads are free)
- **GCS temp storage**: negligible (files deleted after each run)
- **Estimated monthly cost**: ~$15-25 (Dataflow) + negligible (BQ loads + GCS)

## Key Design Decisions

1. **Download on launcher, not workers**: The HTTP download runs before the Beam pipeline
   starts (on the launcher/submitter machine), not distributed across workers. This is simpler
   and avoids issues with coordinating a single download across multiple workers.

2. **Flex Template**: Packages pipeline as a Docker image for parameterized, repeatable launches.
   No need to upload Python code each time — just call the REST API with parameters.

3. **FILE_LOADS write method**: Uses BigQuery batch load jobs (free) instead of streaming inserts
   ($0.01/200MB). Since we process hourly batches, streaming is unnecessary.

4. **No intermediate GCS staging**: Unlike the original pipeline which writes .ndjson.gz to a
   staging bucket, this pipeline writes directly from Beam to BigQuery. Simpler, fewer moving parts.

5. **Dead-letter handling**: Bad records that fail JSON parsing are logged and dropped (not written
   to a separate dead-letter table). For production, a dead-letter PCollection could be added.
