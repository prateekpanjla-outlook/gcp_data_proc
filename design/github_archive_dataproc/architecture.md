# GitHub Archive Pipeline — Cloud Dataproc (Serverless)

## Overview

Single PySpark Serverless batch job that handles the entire GitHub Archive ETL:
download from gharchive.org, transform/flatten nested JSON using Spark DataFrame ops,
and load to BigQuery via the spark-bigquery-connector.

Replaces all 3 phases of the original pipeline (Cloud Run Job + Cloud Function + Cloud Function)
with one Dataproc Serverless batch job triggered hourly by Cloud Scheduler via Cloud Workflows.

## Architecture

```
Cloud Scheduler (hourly)
    |
    v
Cloud Workflows
    |
    v
Dataproc Serverless Batch Submit
    |
    v
+--------------------------------------------------+
|  PySpark Job (Dataproc Serverless)                |
|                                                   |
|  1. Download: HTTPS GET data.gharchive.org        |
|     -> requests.get() -> GCS blob upload          |
|     (runs on Spark driver node)                   |
|                                                   |
|  2. spark.read.json(gs://temp/*.json.gz)          |
|     (auto-decompresses, infers schema)            |
|                                                   |
|  3. DataFrame.select() with col aliases           |
|     - col("actor.id").alias("actor_id")           |
|     - col("repo.name").alias("repo_name")         |
|     - col("payload.ref").alias("payload_ref")     |
|     - col("payload.issue.labels")                 |
|     - lit("DATAPROC_PROCESSOR") as etl_create_id  |
|     - current_timestamp() as etl_create_ts        |
|                                                   |
|  4. df.write.format("bigquery")                   |
|     -> github_archive.github_events               |
|     mode("append"), writeMethod("direct")         |
|                                                   |
|  5. Cleanup: delete temp GCS file                 |
+--------------------------------------------------+
```

## Data Flow

```
Source:  https://data.gharchive.org/{YYYY-MM-DD-H}.json.gz
        (~300MB compressed, ~2GB uncompressed, ~500K events/hour)

Temp:   gs://{project}-{env}-dataproc-temp/downloads/{YYYY-MM-DD-H}.json.gz

Sink:   {project}.github_archive.github_events
        (partitioned by created_at, clustered by event_type)
```

## Schema

27 flattened fields + `payload_issue_labels` REPEATED RECORD (7 sub-fields):

| Field | BigQuery Type | PySpark Source Expression |
|-------|--------------|--------------------------|
| event_id | STRING | col("id") |
| event_type | STRING | col("type") |
| created_at | TIMESTAMP | col("created_at").cast("timestamp") |
| actor_id | INT64 | col("actor.id") |
| actor_login | STRING | col("actor.login") |
| actor_display_login | STRING | col("actor.display_login") |
| actor_gravatar_id | STRING | col("actor.gravatar_id") |
| actor_url | STRING | col("actor.url") |
| actor_avatar_url | STRING | col("actor.avatar_url") |
| actor_type | STRING | col("actor.type") |
| actor_site_admin | BOOLEAN | col("actor.site_admin") |
| repo_id | INT64 | col("repo.id") |
| repo_name | STRING | col("repo.name") |
| repo_url | STRING | col("repo.url") |
| public | BOOLEAN | col("public") |
| payload_ref | STRING | col("payload.ref") |
| payload_ref_type | STRING | col("payload.ref_type") |
| payload_push_id | INT64 | col("payload.push_id") |
| payload_size | INT64 | col("payload.size") |
| payload_distinct_size | INT64 | col("payload.distinct_size") |
| payload_head | STRING | col("payload.head") |
| payload_before | STRING | col("payload.before") |
| payload_issue_labels | RECORD (REPEATED) | col("payload.issue.labels") |
| etl_create_ts | TIMESTAMP | current_timestamp() |
| etl_create_id | STRING | lit("DATAPROC_PROCESSOR") |

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
src/github_archive_dataproc/
    github_archive_pipeline.py     # Main PySpark job: download + transform + load
    schema.py                      # BQ schema definition for spark-bigquery connector
    utils/
        __init__.py
        field_mappings.py          # Field mapping constants (actor, repo, payload)
        download.py                # Download helper: requests -> GCS blob
```

## Infrastructure (Terraform, 3-layer)

```
infrastructure/github_archive_dataproc/terraform/layers/
    01_static/
        main.tf          # SAs, GCS bucket (temp/staging), BQ dataset/table
        schema.json      # BigQuery schema (same as original)
        variables.tf / outputs.tf / terraform.tf
    02_first_time/
        main.tf          # APIs (dataproc, bigquery, workflows), service agent IAM
        variables.tf / outputs.tf / terraform.tf
    03_operational/
        main.tf          # Upload PySpark to GCS, Cloud Workflows, Cloud Scheduler
        variables.tf / outputs.tf / terraform.tf
```

### Key Terraform Resources

| Layer | Resource | Purpose |
|-------|----------|---------|
| 01 | `google_service_account` | Dataproc worker SA, Scheduler SA |
| 01 | `google_storage_bucket` | Temp bucket, PySpark job staging |
| 01 | `google_bigquery_dataset` | github_archive dataset |
| 01 | `google_bigquery_table` | github_events (partitioned, clustered) |
| 02 | `google_project_service` | dataproc, bigquery, workflows APIs |
| 03 | `google_storage_bucket_object` | Upload PySpark job files to GCS |
| 03 | `google_workflows_workflow` | Orchestration: submit batch + poll |
| 03 | `google_cloud_scheduler_job` | Hourly trigger -> Cloud Workflows |

### IAM Roles

Dataproc worker SA needs:
- `roles/dataproc.worker`
- `roles/bigquery.dataEditor` (on dataset)
- `roles/bigquery.jobUser` (project-level)
- `roles/storage.objectAdmin` (on temp/staging buckets)

## Orchestration

- **Cloud Scheduler** runs at `30 * * * *` (hourly at :30)
- Triggers **Cloud Workflows** which:
  1. Calculates target hour filename (1 hour ago)
  2. Submits Dataproc Serverless batch:
     ```
     gcloud dataproc batches submit pyspark \
       gs://{bucket}/jobs/github_archive_pipeline.py \
       --region=us-central1 \
       --service-account={sa}@{project}.iam.gserviceaccount.com \
       --jars=gs://spark-lib/bigquery/spark-bigquery-with-dependencies_2.12-0.36.1.jar \
       --properties=spark.app.hour_offset=1,spark.app.project_id={project},spark.app.temp_bucket={bucket}
     ```
  3. Polls batch status until SUCCEEDED or FAILED
  4. Returns result

## Cost Estimate

- **Dataproc Serverless**: ~$0.06/vCPU-hr + ~$0.01/GB-hr
- Typical hourly run (~300MB input, 3-5 min including cold start): **~$0.02-0.08/run**
- Cold start overhead: 1-2 min (Serverless provisioning)
- **BigQuery write** (direct method via connector): included in Dataproc cost
- **GCS temp storage**: negligible (files deleted after each run)
- **Cloud Workflows**: free tier covers ~30K executions/month
- **Estimated monthly cost**: ~$15-40 (Dataproc) + negligible (GCS + Workflows)
- **Idle cost**: $0 (no persistent cluster)

## Key Design Decisions

1. **Serverless over persistent cluster**: Dataproc Serverless eliminates cluster management.
   For hourly batch workloads with ~3 min runtime, the 1-2 min cold start is acceptable.
   No idle cost when the pipeline isn't running.

2. **Download on driver, not workers**: The HTTP download runs on the Spark driver using
   Python `requests`, then uploads to GCS. Spark reads from GCS for distributed processing.
   This avoids coordinating a single HTTP download across multiple executors.

3. **spark-bigquery-connector (direct write)**: Uses Google's official connector to write
   directly from Spark DataFrames to BigQuery. The `direct` write method uses the BigQuery
   Storage Write API for efficient loading.

4. **Cloud Workflows for orchestration**: Provides built-in polling, error handling, and
   retry logic for the async Dataproc batch submission. Simpler than a Cloud Function wrapper.

5. **No intermediate staging bucket**: Unlike the original pipeline which writes .ndjson.gz
   to a staging bucket, PySpark writes directly to BigQuery. Fewer moving parts, less storage.

6. **Spark handles large files natively**: No need for the file splitting logic from Phase 2.
   Spark distributes the processing across executors automatically.

7. **payload_issue_labels as StructType**: Spark's native StructType/ArrayType maps directly
   to BigQuery REPEATED RECORD. No special handling needed — the connector handles it.
