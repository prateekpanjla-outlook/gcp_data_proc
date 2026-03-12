# GitHub Archive Pipeline — Cloud Data Fusion

## Overview

Single Cloud Data Fusion pipeline that handles the entire GitHub Archive ETL:
download from gharchive.org via HTTP source plugin, transform/flatten nested JSON
using Wrangler directives, and load to BigQuery via BigQuery sink plugin.

Replaces all 3 phases of the original pipeline (Cloud Run Job + Cloud Function + Cloud Function)
with one Data Fusion pipeline triggered hourly by Cloud Scheduler via REST API.

## Architecture

```
Cloud Scheduler (hourly)
    |
    v
Data Fusion REST API (start pipeline with runtime args)
    |
    v
+--------------------------------------------------+
|  CDAP Pipeline (runs on Dataproc under the hood)  |
|                                                   |
|  1. HTTP Source Plugin                            |
|     GET https://data.gharchive.org/{hour}.json.gz |
|     (hour passed as runtime argument)             |
|                                                   |
|  2. Decompressor Plugin                           |
|     gunzip -> raw NDJSON lines                    |
|                                                   |
|  3. Wrangler Transform                            |
|     - parse-as-json body                          |
|     - parse-as-json actor / repo / payload        |
|     - rename id event_id                          |
|     - rename type event_type                      |
|     - extract actor.*, repo.*, payload.* fields   |
|     - extract payload.issue.labels                |
|     - set-column etl_create_ts now()              |
|     - set-column etl_create_id                    |
|     - drop actor repo payload org other           |
|                                                   |
|  4. BigQuery Sink Plugin                          |
|     -> github_archive.github_events               |
|     WRITE_APPEND                                  |
+--------------------------------------------------+
```

### Fallback Architecture

If the HTTP source plugin struggles with large gzipped files (~300MB compressed),
use a 2-stage approach:

```
Stage 1: HTTP Source -> GCS Sink (download to temp bucket)
Stage 2: GCS Source -> Wrangler Transform -> BigQuery Sink
```

Both stages can be in the same pipeline using Data Fusion's conditional/action nodes,
or as two separate pipelines chained via pipeline triggers.

## Data Flow

```
Source:  https://data.gharchive.org/{YYYY-MM-DD-H}.json.gz
        (~300MB compressed, ~2GB uncompressed, ~500K events/hour)

Sink:   {project}.github_archive.github_events
        (partitioned by created_at, clustered by event_type)
```

## Schema

27 flattened fields + `payload_issue_labels` REPEATED RECORD (7 sub-fields):

| Field | BigQuery Type | Wrangler Source |
|-------|--------------|-----------------|
| event_id | STRING | rename id event_id |
| event_type | STRING | rename type event_type |
| created_at | TIMESTAMP | body_created_at |
| actor_id | INT64 | body_actor_id |
| actor_login | STRING | body_actor_login |
| actor_display_login | STRING | body_actor_display_login |
| actor_gravatar_id | STRING | body_actor_gravatar_id |
| actor_url | STRING | body_actor_url |
| actor_avatar_url | STRING | body_actor_avatar_url |
| actor_type | STRING | body_actor_type |
| actor_site_admin | BOOLEAN | body_actor_site_admin |
| repo_id | INT64 | body_repo_id |
| repo_name | STRING | body_repo_name |
| repo_url | STRING | body_repo_url |
| public | BOOLEAN | body_public |
| payload_ref | STRING | body_payload_ref |
| payload_ref_type | STRING | body_payload_ref_type |
| payload_push_id | INT64 | body_payload_push_id |
| payload_size | INT64 | body_payload_size |
| payload_distinct_size | STRING | body_payload_distinct_size |
| payload_head | STRING | body_payload_head |
| payload_before | STRING | body_payload_before |
| payload_issue_labels | RECORD (REPEATED) | body_payload_issue_labels |
| etl_create_ts | TIMESTAMP | set-column now() |
| etl_create_id | STRING | set-column "DATA_FUSION_PROCESSOR" |

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
src/github_archive_datafusion/
    pipeline/
        github_archive_pipeline.json   # CDAP pipeline JSON definition
    scripts/
        deploy_pipeline.sh             # Deploy pipeline via Data Fusion REST API
        start_pipeline.sh             # Trigger a pipeline run (with hour parameter)
    wrangler/
        directives.txt                 # Wrangler directives for flatten/transform
```

## Infrastructure (Terraform, 3-layer)

```
infrastructure/github_archive_datafusion/terraform/layers/
    01_static/
        main.tf          # Data Fusion instance, SAs, BQ dataset/table
        schema.json      # BigQuery schema (same as original)
        variables.tf / outputs.tf / terraform.tf
    02_first_time/
        main.tf          # APIs (datafusion, bigquery), service agent IAM
        variables.tf / outputs.tf / terraform.tf
    03_operational/
        main.tf          # Cloud Scheduler -> Data Fusion REST API, pipeline deploy
        variables.tf / outputs.tf / terraform.tf
```

### Key Terraform Resources

| Layer | Resource | Purpose |
|-------|----------|---------|
| 01 | `google_data_fusion_instance` | Data Fusion instance (Developer/Basic) |
| 01 | `google_service_account` | Data Fusion runtime SA, Scheduler SA |
| 01 | `google_bigquery_dataset` | github_archive dataset |
| 01 | `google_bigquery_table` | github_events (partitioned, clustered) |
| 02 | `google_project_service` | datafusion, bigquery APIs |
| 02 | IAM bindings | Service agent roles for Dataproc (Data Fusion backend) |
| 03 | `google_cloud_scheduler_job` | Hourly trigger -> Data Fusion REST API |
| 03 | `null_resource` (local-exec) | Deploy pipeline JSON on terraform apply |

### IAM Roles

Data Fusion runtime SA needs:
- `roles/datafusion.runner`
- `roles/bigquery.dataEditor` (on dataset)
- `roles/bigquery.jobUser` (project-level)
- `roles/storage.objectAdmin` (if using GCS intermediate)
- `roles/dataproc.editor` (Data Fusion manages Dataproc clusters)

## Orchestration

- **Cloud Scheduler** runs at `30 * * * *` (hourly at :30)
- Calls Data Fusion pipeline start REST API:
  ```
  POST https://{instance}-{project}-dot-{region}.datafusion.googleusercontent.com/
       api/v3/namespaces/default/apps/github-archive-pipeline/
       workflows/DataPipelineWorkflow/start
  ```
  With runtime arguments:
  ```json
  {
    "hour_offset": "1",
    "source_url": "https://data.gharchive.org/{calculated-hour}.json.gz"
  }
  ```
- Alternative: Use Data Fusion's built-in time trigger (configured in pipeline JSON)

## Wrangler Directives

```
// Parse the raw JSON body
parse-as-json body 1

// Extract nested actor object
parse-as-json body_actor 1
rename body_actor_id actor_id
rename body_actor_login actor_login
rename body_actor_display_login actor_display_login
rename body_actor_gravatar_id actor_gravatar_id
rename body_actor_url actor_url
rename body_actor_avatar_url actor_avatar_url
rename body_actor_type actor_type
rename body_actor_site_admin actor_site_admin

// Extract nested repo object
parse-as-json body_repo 1
rename body_repo_id repo_id
rename body_repo_name repo_name
rename body_repo_url repo_url

// Core fields
rename body_id event_id
rename body_type event_type
rename body_created_at created_at
rename body_public public

// Extract payload fields
parse-as-json body_payload 1
rename body_payload_ref payload_ref
rename body_payload_ref_type payload_ref_type
rename body_payload_push_id payload_push_id
rename body_payload_size payload_size
rename body_payload_distinct_size payload_distinct_size
rename body_payload_head payload_head
rename body_payload_before payload_before

// Extract issue labels (nested: payload.issue.labels)
parse-as-json body_payload_issue 1
rename body_payload_issue_labels payload_issue_labels

// Add ETL metadata
set-column etl_create_ts now()
set-column etl_create_id "DATA_FUSION_PROCESSOR"

// Drop original nested/unwanted columns
drop body body_actor body_repo body_payload body_org body_other
drop body_payload_issue
```

## Cost Estimate

- **Data Fusion instance** (always-on):
  - Developer edition: ~$0.35/hr = **~$252/month**
  - Basic edition: ~$1.80/hr = **~$1,296/month**
  - Enterprise edition: ~$4.80/hr = **~$3,456/month**
- **Pipeline execution** (Dataproc cluster spun up per run):
  - ~$0.10-0.30/run for compute
- **BigQuery writes**: included in pipeline
- **Estimated monthly cost**: ~$260 (Developer) to ~$1,320 (Basic) + ~$50 (pipeline runs)
- **Idle cost**: Instance cost runs 24/7 regardless of pipeline runs

## Key Design Decisions

1. **HTTP source plugin for download**: Data Fusion's HTTP plugin handles the HTTPS GET
   directly within the pipeline. No separate download step needed. If the plugin struggles
   with large gzipped files, fall back to a 2-stage pipeline (HTTP->GCS, GCS->BQ).

2. **Wrangler for transformation**: Data Fusion's Wrangler plugin provides a no-code/low-code
   approach to JSON flattening. Directives are declarative and readable. The same transform
   that takes ~100 lines of Python in the original pipeline is ~30 lines of Wrangler directives.

3. **Developer edition for dev/test**: At ~$0.35/hr vs $1.80/hr for Basic, Developer edition
   is sufficient for development and testing. It has limited concurrent pipelines and no
   HA, but that's acceptable for non-production.

4. **Pipeline JSON as version control artifact**: The CDAP pipeline definition is exported
   as JSON and stored in the repo. Changes are deployed via REST API on terraform apply.
   Not hand-editable — use Data Fusion UI to design, then export.

5. **Cloud Scheduler over built-in triggers**: Using external Cloud Scheduler provides
   consistent orchestration pattern across all pipeline implementations and makes it
   easier to manage scheduling centrally.

6. **payload_issue_labels handling**: Wrangler's `parse-as-json` can handle nested arrays.
   The BigQuery sink plugin maps arrays of objects to REPEATED RECORD automatically.
   May need explicit schema mapping in the sink configuration.

## Comparison with Other Approaches

| Aspect | Data Fusion | Dataproc | Dataflow |
|--------|------------|----------|----------|
| Code style | No-code (JSON + directives) | PySpark (Python) | Apache Beam (Python) |
| Transform | Wrangler directives | DataFrame.select() | ParDo DoFn |
| Idle cost | ~$252+/month | $0 | $0 |
| Run cost | ~$0.10-0.30 | ~$0.02-0.08 | ~$0.01-0.05 |
| Cold start | Pipeline submission ~30s | Serverless ~1-2 min | Job launch ~2-3 min |
| Large files | Plugin-dependent | Native distributed | Native distributed |
| Best for | Visual ETL, citizen developers | Spark-native workloads | Beam-native ETL |
