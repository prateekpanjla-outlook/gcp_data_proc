# elt.tf

## 1. Overview

Defines the ELT (Extract-Load-Transform) resources within the BigQuery `github_archive` dataset. Creates a materialized view for daily repo stats, a scheduled query for hourly activity summaries, and three Dataform-style logical views (staging deduplication, developer daily activity, bot vs. human breakdown). All resources sit in Layer 01 (Static) because they are schema-level definitions that rarely change.

## 2. Prerequisites

- **BigQuery Dataset & Table:** `google_bigquery_dataset.github_archive` and `google_bigquery_table.github_events` must be created first (defined in `main.tf` in the same layer)
- **BigQuery Data Transfer API:** `bigquerydatatransfer.googleapis.com` must be enabled (done in `main.tf`)
- **Service Account:** `bq_loader` SA must have `bigquery.admin` role for running scheduled queries via Data Transfer Service
- **SQL File:** `sql/scheduled_hourly_activity.sql` must exist alongside this file
- **Variables:** `project_id`, `dataset_id`, `table_id` (used to interpolate fully-qualified table references in SQL)

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | `main.tf` (same layer) | Provides the dataset, table, service account, and API enablement resources |
| Upstream | `main.py` (Cloud Function) | Populates the `github_events` table that all ELT resources read from |
| Upstream | `sql/scheduled_hourly_activity.sql` | SQL template loaded by the scheduled query resource |
| Downstream | BI/analytics consumers | Materialized view and logical views are queryable endpoints for dashboards and ad-hoc analysis |
| Downstream | `hourly_activity_summary` table | The scheduled query appends aggregated rows to this destination table |

## 4. Code Walkthrough

1. **Materialized View `mv_repo_daily_stats` (lines 4-32):** Aggregates `github_events` by day and `repo_name`, counting total events, pushes, issues, PRs, stars, forks, and approximate unique contributors. Auto-refreshes every 30 minutes (`refresh_interval_ms = 1800000`).

2. **Scheduled Query `hourly_activity` (lines 37-69):** A BigQuery Data Transfer scheduled query that runs every hour. Loads the SQL template from `sql/scheduled_hourly_activity.sql`, performing string replacement for `PROJECT_ID`, `DATASET_ID`, and `TABLE_ID` placeholders. Appends results to the `hourly_activity_summary` destination table. Runs as the `bq_loader` service account.

3. **IAM for Scheduled Query (lines 72-76):** Grants `bq_loader` the `bigquery.admin` role at project level, required by the Data Transfer Service to execute scheduled queries.

4. **Staging View `stg_events` (lines 87-118):** A deduplication view that selects from `github_events` where `event_id IS NOT NULL` and uses `QUALIFY ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY etl_create_ts DESC) = 1` to keep only the latest version of each event. Simulates a Dataform staging layer.

5. **Mart View `developer_daily_activity` (lines 121-152):** Reads from `stg_events` and aggregates per developer per day: pushes, issues, PRs, comments, distinct commits, repos touched, first/last event, and active minutes.

6. **Mart View `bot_vs_human_activity` (lines 155-186):** Reads from `stg_events` and classifies actors as `bot` or `human` using pattern matching on `actor_login` (suffixes `[bot]`, `-bot`, `Bot`, and known bot usernames). Aggregates event counts, unique actors, unique repos, pushes, and PRs by day and actor type.
