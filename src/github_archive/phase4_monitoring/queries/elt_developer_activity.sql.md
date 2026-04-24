## 1. Overview

`elt_developer_activity.sql` retrieves the top 50 developers by total event count from the `developer_daily_activity` Dataform-style mart view. It shows per-developer daily activity metrics including pushes, issues opened, PRs opened, comments, distinct commits, repos touched, and active minutes.

## 2. Prerequisites

- The view `PROJECT_ID.github_archive.developer_daily_activity` must exist. This is a Dataform-style mart view created by ELT infrastructure.
- The dashboard service account needs `roles/bigquery.dataViewer` on the `github_archive` dataset.
- `PROJECT_ID` is replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.github_archive.developer_daily_activity` -- a BigQuery view (Dataform mart) that reads from the `stg_events` staging view, which in turn deduplicates from the `github_events` base table.

**Downstream (consumers)**:
- `app.py` route `/elt` -- calls `_run_query('elt_developer_activity')` and passes the result as `developers` to `elt.html`.
- `templates/elt.html` -- renders the "Top Developers" table with columns: `day`, `actor_login`, `total_events`, `pushes`, `issues_opened`, `prs_opened`, `comments`, `distinct_commits`, `repos_touched`, `active_minutes`.

## 4. IAM & Service Accounts

These queries are executed by the Flask dashboard app running as `{env}-pipeline-dashboard@{project}.iam.gserviceaccount.com`.

| Role | Purpose |
|---|---|
| `bigquery.jobUser` | Run BigQuery queries (create jobs) |
| `bigquery.dataViewer` | Read tables/views in the `github_archive` dataset |

### Cross-references

- **Learnings Issue 10** (`phase4_deployment_issues.md`): The dashboard SA initially lacked `bigquery.resourceViewer`, which is needed for `INFORMATION_SCHEMA.JOBS` access (relevant to `phase3_bq_load_summary.sql`, not this query).
- **Learnings Issue 11** (`phase4_deployment_issues.md`): The dashboard SA initially only had `dataViewer` on `pipeline_logs`, not on `github_archive`. This caused silent failures -- `_run_query()` catches exceptions and returns empty results, so missing permissions surface as empty tables rather than errors.

## 5. Code Walkthrough

1. **SELECT clause**: Reads all pre-computed columns from the mart view: `day`, `actor_login`, `total_events`, `pushes`, `issues_opened`, `prs_opened`, `comments`, `distinct_commits`, `repos_touched`, `active_minutes`. No additional transformation is performed.

2. **FROM clause**: Queries the `developer_daily_activity` view in the `github_archive` dataset.

3. **ORDER BY / LIMIT**: Orders by `total_events DESC` to surface the most active developers first, limited to 50 rows.
