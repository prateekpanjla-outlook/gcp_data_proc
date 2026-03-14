# scheduled_hourly_activity.sql

## 1. Overview

SQL template for the BigQuery scheduled query that produces hourly activity summaries. Aggregates GitHub Archive events by hour and event type, counting events, unique actors, unique repos, total commits, and distinct commits. Runs every hour via BigQuery Data Transfer Service (configured in `elt.tf`) and appends results to the `hourly_activity_summary` destination table.

## 2. Prerequisites

- **BigQuery Table:** The source table (`github_events`) must exist and contain data with a `created_at` TIMESTAMP column
- **Placeholder substitution:** The tokens `PROJECT_ID`, `DATASET_ID`, and `TABLE_ID` in the SQL are replaced at plan time by Terraform's `replace()` calls in `elt.tf`
- **`@run_time` parameter:** Supplied automatically by BigQuery Data Transfer Service at execution time; used to compute the 2-hour lookback window

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | `elt.tf` | Loads this file with `file()` and performs placeholder substitution before passing it to the `google_bigquery_data_transfer_config` resource |
| Upstream | `github_events` table | Source table queried by this SQL |
| Upstream | `main.py` (Cloud Function) | Populates the source table with events that this query aggregates |
| Downstream | `hourly_activity_summary` table | Destination table where aggregated rows are appended |
| Downstream | BI/dashboards | Consumers can query `hourly_activity_summary` for time-series activity trends |

## 4. Code Walkthrough

1. **Time truncation (line 6):** `TIMESTAMP_TRUNC(created_at, HOUR) AS hour` buckets events into hourly windows.

2. **Aggregations (lines 8-12):** For each `(hour, event_type)` group, computes:
   - `event_count` -- total events
   - `unique_actors` -- distinct `actor_login` values
   - `unique_repos` -- distinct `repo_name` values
   - `total_commits` -- sum of `payload_size` (NULL-safe via `IFNULL`)
   - `distinct_commits` -- sum of `payload_distinct_size`

3. **ETL timestamp (line 13):** `CURRENT_TIMESTAMP() AS etl_processed_at` records when the scheduled query ran.

4. **Lookback window (lines 15-16):** Filters to events where `created_at >= TIMESTAMP_SUB(@run_time, INTERVAL 2 HOUR)` and `created_at < TIMESTAMP_TRUNC(@run_time, HOUR)`. The 2-hour lookback ensures late-arriving events from the previous hour are captured while the upper bound prevents processing incomplete data from the current hour.

5. **Grouping (line 17):** Groups by `hour` and `event_type`.
