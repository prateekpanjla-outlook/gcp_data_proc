## 1. Overview

`elt_bot_vs_human.sql` retrieves bot vs human activity breakdowns from the `bot_vs_human_activity` Dataform-style mart view. It shows daily event counts, unique actors, unique repos, pushes, and PRs split by actor type (bot or human).

## 2. Prerequisites

- The view `PROJECT_ID.github_archive.bot_vs_human_activity` must exist. This is a Dataform-style mart view created by ELT infrastructure.
- The dashboard service account needs `roles/bigquery.dataViewer` on the `github_archive` dataset.
- `PROJECT_ID` is replaced at runtime by `app.py._run_query()`.

## 3. Upstream & Downstream Dependencies

**Upstream (data sources)**:
- `PROJECT_ID.github_archive.bot_vs_human_activity` -- a BigQuery view (Dataform mart) that classifies actors as bot or human based on naming patterns, reading from the `stg_events` staging view.

**Downstream (consumers)**:
- `app.py` route `/elt` -- calls `_run_query('elt_bot_vs_human')` and passes the result as `bot_human` to `elt.html`.
- `templates/elt.html` -- renders the "Bot vs Human Activity" table with columns: `day`, `actor_type`, `event_count`, `unique_actors`, `unique_repos`, `pushes`, `prs`.

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

1. **SELECT clause**: Reads all pre-computed columns from the mart view: `day`, `actor_type`, `event_count`, `unique_actors`, `unique_repos`, `pushes`, `prs`. No additional transformation is performed.

2. **FROM clause**: Queries the `bot_vs_human_activity` view in the `github_archive` dataset.

3. **ORDER BY**: Orders by `day DESC, event_count DESC` to show the most recent days first, with the higher-activity actor type listed first within each day. No `LIMIT` is applied -- all rows are returned.
