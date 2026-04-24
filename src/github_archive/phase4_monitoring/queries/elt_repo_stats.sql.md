## 1. Overview

`elt_repo_stats.sql` retrieves the top 50 repositories by total event count from the `mv_repo_daily_stats` materialized view. This provides a pre-aggregated, auto-refreshed summary of daily repository activity including pushes, issues, pull requests, stars, forks, and unique contributor counts.

## 2. Prerequisites

- The materialized view `PROJECT_ID.github_archive.mv_repo_daily_stats` must exist. This is created by ELT infrastructure (outside Phase 4 Terraform).
- The dashboard service account needs `roles/bigquery.dataViewer` on the `github_archive` dataset.
- `PROJECT_ID` is replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.github_archive.mv_repo_daily_stats` -- a BigQuery materialized view that auto-refreshes from the `github_events` base table. Aggregates events by day and repository.

**Downstream (consumers)**:
- `app.py` route `/elt` -- calls `_run_query('elt_repo_stats')` and passes the result as `repos` to `elt.html`.
- `templates/elt.html` -- renders the "Top Repositories" table with columns: `day`, `repo_name`, `total_events`, `pushes`, `issues`, `pull_requests`, `stars`, `forks`, `unique_contributors`.

## 4. IAM & Service Accounts

These queries are executed by the Flask dashboard app running as `{env}-pipeline-dashboard@{project}.iam.gserviceaccount.com`.

| Role | Purpose |
|---|---|
| `bigquery.jobUser` | Run BigQuery queries (create jobs) |
| `bigquery.dataViewer` | Read tables/views in the `github_archive` dataset |

This query reads from the `mv_repo_daily_stats` materialized view in the `github_archive` dataset. The `dataViewer` role on `github_archive` covers access to materialized views in the same dataset -- no additional role is needed.

### Cross-references

- **Learnings Issue 10** (`phase4_deployment_issues.md`): The dashboard SA initially lacked `bigquery.resourceViewer`, which is needed for `INFORMATION_SCHEMA.JOBS` access (relevant to `phase3_bq_load_summary.sql`, not this query).
- **Learnings Issue 11** (`phase4_deployment_issues.md`): The dashboard SA initially only had `dataViewer` on `pipeline_logs`, not on `github_archive`. This caused silent failures -- `_run_query()` catches exceptions and returns empty results, so missing permissions surface as empty tables rather than errors. The `github_archive` `dataViewer` grant was added to Terraform Layer 02.

## 5. Code Walkthrough

1. **SELECT clause**: Reads all pre-computed columns directly from the materialized view: `day`, `repo_name`, `total_events`, `pushes`, `issues`, `pull_requests`, `stars`, `forks`, `unique_contributors`. No transformation is needed since the MV already aggregates the data.

2. **FROM clause**: Queries the `mv_repo_daily_stats` materialized view in the `github_archive` dataset.

3. **ORDER BY / LIMIT**: Orders by `total_events DESC` to surface the most active repositories first, limited to 50 rows.
