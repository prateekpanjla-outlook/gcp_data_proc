## 1. Overview

`service_accounts.html` is a static reference page documenting all service accounts used across the four pipeline phases. It includes a visual SA-to-service dependency map, a full SA inventory table, an IAM roles-per-SA table, and destroy order guidance. No dynamic data is queried -- all content is hardcoded HTML.

## 2. Prerequisites

- Flask with Jinja2 templating (though no template variables are used -- the page is entirely static).
- No BigQuery queries or runtime data are required.

## 3. Upstream & Downstream Dependencies

**Upstream (what renders this template)**:
- `app.py` route `/service-accounts` -- calls `render_template('service_accounts.html')` with no query data.

**Downstream (what this template links to)**:
- Navigation links to all other dashboard pages.

**Referenced service accounts (documented but not queried)**:
- `{env}-cloud-build` -- shared across all phases for building/pushing images.
- `{env}-github-archive-downloader` -- Phase 1 Cloud Run Job.
- `{env}-scheduler` -- Phase 1 Cloud Scheduler.
- `{env}-github-archive-processor` -- Phase 2 Cloud Run Service.
- `{env}-file-splitter` -- Phase 2 Cloud Run Job (future).
- `{env}-eventarc-invoker` -- Phase 2 Eventarc trigger.
- `{env}-bq-loader` -- Phase 3 Cloud Function.
- `{env}-eventarc-invoker-bq` -- Phase 3 Eventarc trigger.
- `{env}-pipeline-dashboard` -- Phase 4 Cloud Run Service.

## 4. Code Walkthrough

1. **Styles (lines 5-45)**: Inline CSS for the SA dependency graph cards (`.sa-graph`, `.sa-phase`, `.sa-card`). Shared-reference cards use a dashed yellow border (`.shared-ref`). Phase-specific colour coding: Phase 1 blue, Phase 2 green, Phase 3 yellow, Phase 4 red.

2. **SA-to-Service Dependency Map (lines 59-141)**: Visual card-based diagram grouped by phase. Each card shows the SA name, its IAM roles, and what service it is bound to. The `cloud-build` SA from Phase 1 appears as a dashed-border "shared-ref" card in Phases 2-4 to indicate reuse. Vertical connectors between phase boxes note "cloud-build SA reused".

3. **All Service Accounts table (lines 143-205)**: Lists all 9 service accounts with columns: Account ID (with `{env}` prefix placeholder), Created In (which phase), Used By (which phases), and Purpose. The shared `cloud-build` SA is highlighted with the `.shared` class (yellow text).

4. **IAM Roles per SA table (lines 207-246)**: Detailed role-to-scope mapping for each SA. Uses `rowspan` to group multiple roles under a single SA. Scopes vary between project-level, dataset-level, and bucket-level grants.

5. **Destroy Order Dependency (lines 248-259)**: Architecture diagram showing the reverse destroy order: Phase 4 -> Phase 3 -> Phase 2 -> Phase 1. Notes that the Cloud Build SA must be destroyed last since all phases depend on it for image builds.
