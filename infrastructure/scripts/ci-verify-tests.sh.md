# ci-verify-tests.sh

## 1. Overview

Runs 7 test suites against already-deployed GitHub Archive pipeline infrastructure. Unlike `ci-test-pipeline.sh`, this script does not deploy or destroy -- it assumes infrastructure is already standing. It tests: (1) infrastructure resource existence, (2) Phase 1 download, (3) Phase 2 processing, (4) Phase 3 BigQuery load + schema fields, (5) Phase 4 dashboard HTTP endpoints, (6) data integrity (duplicates, row count range, null timestamps), and (7) ELT transformations (materialized view, staging view, mart views). Tracks individual pass/fail counts and exits 0 on all pass, 1 on any failure.

## 2. Prerequisites

- **gcloud CLI** authenticated with access to the target project.
- **bq CLI** available for BigQuery queries.
- **curl** available for dashboard HTTP checks.
- **Infrastructure already deployed** via `deploy-all-phases.sh` (this script does not deploy).
- **Required arguments**: `PROJECT_ID` (positional 1), `ENVIRONMENT` (positional 2). Optional: `REGION` (default `us-central1`), `DASHBOARD_URL` (positional 4, auto-detected if omitted).

## 3. Upstream & Downstream Dependencies

**Upstream (what this script needs before running):**
- `deploy-all-phases.sh` must have been run successfully to create all GCP resources.
- GHArchive data must exist for the target hour (1 hour ago by default).
- The pipeline must have already processed at least one hour of data for Tests 3-7 to pass.

**Downstream (what depends on this script):**
- `gh-archive-deploy.yml` GitHub Actions workflow calls this script after deploying to verify the pipeline works.
- Can be run standalone for ad-hoc verification of a deployed environment.

## 4. Code Walkthrough

1. **Arguments & derived names** (lines 22-46): Computes bucket names, Cloud Run job/service names, Cloud Function name, Cloud Scheduler name, and the target hour (1 hour ago UTC).
2. **Test helpers** (lines 53-62): `pass()` increments pass counter and prints; `fail()` increments fail counter, appends to failed list, and prints.
3. **Test 1 — Infrastructure Exists** (lines 78-123): Verifies six resource types exist via gcloud/bq:
   - Cloud Run Job (download)
   - Cloud Run Service (processor)
   - Cloud Function (BQ loader)
   - Cloud Scheduler job
   - BigQuery table `github_archive.github_events`
   - At least 2 Eventarc triggers
4. **Test 2 — Phase 1 Download** (lines 130-168): Triggers the Cloud Run download job, then polls the landing bucket for the target `.json.gz` file (or any recent file as fallback) for up to 5 minutes.
5. **Test 3 — Phase 2 Processing** (lines 175-199): Polls the staging bucket for processed chunks matching `<date>-<hour>-chunk-*` for up to 10 minutes.
6. **Test 4 — Phase 3 BigQuery Load** (lines 206-243): Polls BQ for row count by target date/hour for up to 5 minutes. On success, also verifies key schema fields (`event_id`, `event_type`, `actor_login`, `repo_name`, `etl_create_id`).
7. **Test 5 — Phase 4 Dashboard** (lines 250-279): If dashboard URL is available (auto-detected from gcloud or passed as arg), checks HTTP 200 on 8 endpoints: `/health`, `/`, `/phase1`, `/phase2`, `/phase3`, `/elt`, `/infra`, `/service-accounts`. Also validates `/health` returns JSON with `"healthy"`.
8. **Test 6 — Data Integrity** (lines 286-319): Three checks:
   - No duplicate `event_id` values.
   - Row count in expected range (50K-300K per hour).
   - No NULL `created_at` timestamps.
9. **Test 7 — ELT Transformations** (lines 326-372): Verifies four BQ objects have rows:
   - `mv_repo_daily_stats` (materialized view)
   - `stg_events` (staging view, deduplicated)
   - `developer_daily_activity` (mart view)
   - `bot_vs_human_activity` (mart view, expects >= 2 rows for bot + human)
10. **Summary** (lines 379-396): Prints total passed/failed counts and lists failed test names. Exits 0 or 1.
