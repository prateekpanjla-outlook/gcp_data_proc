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

## 4. Code Walkthrough

1. **SELECT clause**: Reads all pre-computed columns directly from the materialized view: `day`, `repo_name`, `total_events`, `pushes`, `issues`, `pull_requests`, `stars`, `forks`, `unique_contributors`. No transformation is needed since the MV already aggregates the data.

2. **FROM clause**: Queries the `mv_repo_daily_stats` materialized view in the `github_archive` dataset.

3. **ORDER BY / LIMIT**: Orders by `total_events DESC` to surface the most active repositories first, limited to 50 rows.
