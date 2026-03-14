# schema.json

## 1. Overview

BigQuery table schema definition for the `github_events` table. Defines 25 columns representing flattened GitHub Archive event data produced by the Phase 2 processor. The schema is loaded by Terraform (`main.tf`) via `file()` and applied to the `google_bigquery_table.github_events` resource. BigQuery also uses this schema during load jobs to validate incoming NDJSON records.

## 2. Prerequisites

- **Alignment with Phase 2 output:** The field names and types must match the flattened NDJSON structure produced by the Phase 2 Cloud Run processor. Any schema drift will cause load job failures or silently dropped fields (when `ignore_unknown_values=True`).
- **Terraform Layer 01:** This file must be co-located with `main.tf` so the `file("${path.module}/schema.json")` reference resolves correctly.

## 3. Upstream & Downstream Dependencies

| Direction | Component | Details |
|-----------|-----------|---------|
| Upstream | Phase 2 processor | Produces the flattened NDJSON records whose structure this schema describes |
| Downstream | `main.tf` | Loads this file to define the `github_events` table schema |
| Downstream | `main.py` (Cloud Function) | Load jobs rely on this schema for field-type validation. `ignore_unknown_values=True` means extra fields in the NDJSON are silently skipped |
| Downstream | `elt.tf` views | All views and the materialized view query columns defined in this schema |

## 4. Code Walkthrough

The schema is a JSON array of field objects. Each field has `name`, `type`, `mode`, and `description`. All fields use `NULLABLE` mode except where noted.

1. **Event metadata:** `event_id` (STRING), `event_type` (STRING), `created_at` (TIMESTAMP -- used as the partitioning column).

2. **Actor fields:** `actor_id` (INTEGER), `actor_login` (STRING), `actor_display_login` (STRING), `actor_gravatar_id` (STRING), `actor_url` (STRING), `actor_avatar_url` (STRING), `actor_type` (STRING), `actor_site_admin` (BOOLEAN).

3. **Repository fields:** `repo_id` (INTEGER), `repo_name` (STRING), `repo_url` (STRING).

4. **Visibility:** `public` (BOOLEAN).

5. **Payload fields:** `payload_ref` (STRING), `payload_ref_type` (STRING), `payload_push_id` (INTEGER), `payload_size` (INTEGER -- commit count), `payload_distinct_size` (INTEGER -- distinct commits), `payload_head` (STRING -- HEAD SHA), `payload_before` (STRING -- before SHA).

6. **Payload nested record:** `payload_issue_labels` (REPEATED RECORD) with sub-fields: `id` (INTEGER), `node_id` (STRING), `url` (STRING), `name` (STRING), `color` (STRING), `default` (BOOLEAN), `description` (STRING). This is the only non-flat field, preserved as an array of structs.

7. **ETL metadata:** `etl_create_ts` (TIMESTAMP -- when Phase 2 created the record), `etl_create_id` (STRING -- processor identifier).
