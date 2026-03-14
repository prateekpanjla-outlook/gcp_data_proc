## 1. Overview

`elt.html` is the ELT analytics page showing post-load transformations applied to the `github_events` base table. It displays three tables: Bot vs Human Activity (from a Dataform view), Top Repositories (from a materialized view), and Top Developers (from a Dataform view). Architecture diagrams illustrate the ELT lineage from base table through staging view to mart views and materialized views.

## 2. Prerequisites

- **Template variables** (passed by `app.py`):
  - `bot_human` -- list of dicts from `elt_bot_vs_human.sql` with keys: `day`, `actor_type`, `event_count`, `unique_actors`, `unique_repos`, `pushes`, `prs`.
  - `repos` -- list of dicts from `elt_repo_stats.sql` with keys: `day`, `repo_name`, `total_events`, `pushes`, `issues`, `pull_requests`, `stars`, `forks`, `unique_contributors`.
  - `developers` -- list of dicts from `elt_developer_activity.sql` with keys: `day`, `actor_login`, `total_events`, `pushes`, `issues_opened`, `prs_opened`, `comments`, `distinct_commits`, `repos_touched`, `active_minutes`.
- Flask with Jinja2 templating.

## 3. Upstream & Downstream Dependencies

**Upstream (what provides data to this template)**:
- `app.py` route `/elt` -- executes `elt_bot_vs_human.sql`, `elt_repo_stats.sql`, and `elt_developer_activity.sql`.
- Three BigQuery views/MVs in the `github_archive` dataset: `bot_vs_human_activity`, `mv_repo_daily_stats`, `developer_daily_activity`.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

## 4. Code Walkthrough

1. **Styles (lines 5-33)**: Extends the dark theme with colour-coded CSS classes for ELT object types: `.mv` (yellow border for materialized views), `.view` (green border for Dataform views), `.sched` (red border for scheduled queries). Badge styles (`.badge-mv`, `.badge-view`, `.badge-sched`) label each table section. Bot rows use red text, human rows use green.

2. **Architecture diagrams (lines 47-65)**: Three flow diagrams showing ELT lineage:
   - `github_events` -> `stg_events` (deduplicated view) -> `developer_activity` & `bot_vs_human` (mart views).
   - `github_events` -> `mv_repo_daily_stats` (materialized view).
   - `github_events` -> `hourly_activity_summary` (scheduled query).

3. **Bot vs Human table (lines 67-89)**: Iterates over `bot_human`. Applies `bot` class (red) or `human` class (green) to the actor type cell.

4. **Top Repositories table (lines 91-117)**: Iterates over `repos`. Badge label indicates "Materialized View". Nine columns covering event type breakdowns.

5. **Top Developers table (lines 119-148)**: Iterates over `developers`. Badge label indicates "Dataform View". Ten columns covering detailed developer activity metrics.
