# Development Code Changes for Live Deployment

**Date**: 2026-03-09
**Author**: Claude Code Assistant

---

## Summary

This document captures a combined deployment that:
1. Added ETL metadata columns (`etl_create_ts`, `etl_create_id`) to track data lineage
2. Changed staging file deletion from immediate to 2-day lifecycle retention

---

## Services Overview

| Service | Type | Name | Trigger Name | Purpose |
|---------|------|------|--------------|---------|
| Phase 2 | Cloud Run | `dev-github-archive-processor` | `dev-github-archive-storage` | Process raw GitHub Archive files |
| Phase 3 | Cloud Function 2nd gen | `dev-bq-loader` | `dev-bq-loader-199448` | Load processed files to BigQuery |

**Data Flow:**
```
Landing Bucket → Phase 2 Cloud Run → Staging Bucket → Phase 3 Cloud Function → BigQuery
```

---

## Changes Made

### 1. BigQuery Schema Change (ALTER TABLE)

**Rationale**: Add columns to existing table without data loss. Using `ALTER TABLE` instead of recreating the table preserves 2.5M+ existing rows.

**Execution**:
```sql
ALTER TABLE `dev-dataprocessing-489305.github_archive.github_events`
ADD COLUMN IF NOT EXISTS etl_create_ts TIMESTAMP OPTIONS(description='Timestamp when Phase 2 processor created this record');

ALTER TABLE `dev-dataprocessing-489305.github_archive.github_events`
ADD COLUMN IF NOT EXISTS etl_create_id STRING OPTIONS(description='ETL processor identifier');
```

**Why this order**: ALTER TABLE must be done first so the table schema is ready before Phase 2 starts writing files with the new columns.

### 2. Terraform Schema Update (schema.json)

**File**: `infrastructure/github_archive/phase3_loadbigquery/terraform/layers/01_static/schema.json`

**Rationale**: Keep Terraform state in sync with the actual BigQuery table schema. This prevents drift and ensures future `terraform plan` operations show accurate results.

**Changes**: Added two new column definitions:
```json
{
  "name": "etl_create_ts",
  "type": "TIMESTAMP",
  "mode": "NULLABLE",
  "description": "Timestamp when Phase 2 processor created this record"
},
{
  "name": "etl_create_id",
  "type": "STRING",
  "mode": "NULLABLE",
  "description": "ETL processor identifier (e.g., GITHUB_PROCESSOR)"
}
```

### 3. Phase 2 Transformer Update (transformer.py)

**File**: `src/github_archive/phase2_process_files/processors/transformer.py`

**Rationale**: Populate the new ETL columns during data transformation. This provides data lineage tracking for every processed record.

**Changes**:
1. In `flatten_schema()` method - Add ETL columns:
```python
# Add ETL metadata columns
result['etl_create_ts'] = pd.Timestamp.now(tz='UTC')
result['etl_create_id'] = "GITHUB_PROCESSOR"
```

2. In `_ensure_dtypes()` method - Add `etl_create_id` to string columns list

### 4. Phase 3 Variable Update (variables.tf)

**File**: `infrastructure/phase3_loadbigquery/terraform/layers/03_operational/variables.tf`

**Rationale**: Stop deleting staging files immediately after BigQuery load. This allows:
- Debugging failed loads
- Reprocessing data if needed
- 2-day retention via GCS lifecycle policy handles cleanup

**Changes**:
```hcl
variable "delete_after_load" {
  description = "Delete source file after successful BigQuery load"
  type        = bool
  default     = false  # Changed from true
}
```

---

## Why We Didn't Pause Eventarc Triggers

**Investigation Result**: Eventarc triggers cannot be directly paused via gcloud. The options are:
1. Delete and recreate the trigger (disruptive)
2. Detach the underlying Pub/Sub subscription (loses messages)
3. Change push subscription to pull (modifies managed resources)

**Decision**: Proceed without pausing triggers because:
1. **Backward Compatibility**: Phase 3 uses `ignore_unknown_values=True` in BigQuery load jobs
   - If Phase 2 writes files with new columns before ALTER TABLE completes
   - Phase 3 will simply ignore the unknown columns
   - No data loss or load failures

2. **ALTER TABLE is Instant**: The schema change completes in < 1 second

3. **Low Risk**: Adding NULLABLE columns is non-breaking

**Reference**: `infrastructure/phase3_loadbigquery/function-source/main.py` line 72:
```python
ignore_unknown_values=True,  # Skip fields not in table schema
```

---

## Deployment Order (Critical)

The order matters for zero-downtime deployment:

1. **ALTER TABLE** - Adds columns to BigQuery (instant, no impact)
2. **Update schema.json** - Terraform state sync
3. **Update transformer.py** - Phase 2 starts writing new columns
4. **Update variables.tf** - Phase 3 stops deleting files
5. **Deploy Phase 2** - Cloud Run gets new transformer code
6. **Deploy Phase 3** - Cloud Function gets new environment variable

---

## Verification Commands

```bash
# Verify columns added to BigQuery
bq show --schema dev-dataprocessing-489305:github_archive.github_events

# Check existing rows have NULL for new columns
bq query --use_legacy_sql=false "SELECT etl_create_ts, etl_create_id, COUNT(*) FROM github_archive.github_events GROUP BY 1,2;"

# After Phase 2 deployment, verify new rows have values
bq query --use_legacy_sql=false "SELECT etl_create_ts, etl_create_id FROM github_archive.github_events WHERE etl_create_ts IS NOT NULL LIMIT 5;"

# Verify staging files are retained after load
gsutil ls -la gs://dev-dataprocessing-489305-dev-github-archive-staging/processed/

# Check Cloud Function env var
gcloud functions describe dev-bq-loader --region=us-central1 --gen2
```

---

## Lessons Learned

1. **Eventarc triggers cannot be paused** - Must accept risk or use destructive methods
2. **`ignore_unknown_values=True` is a safety net** - Allows schema evolution without coordination
3. **ALTER TABLE ADD COLUMN is instant** - No need for complex migration strategies
4. **Terraform schema must match actual table** - Prevents state drift
5. **NULLABLE columns are backward compatible** - Existing rows get NULL values automatically

---

## Rollback Plan

If deployment fails:

```bash
# Revert Phase 2 Cloud Run to previous revision
gcloud run services describe dev-github-archive-processor --region=us-central1 --format="value(status.traffic[0].revisionName)"
gcloud run services update-traffic dev-github-archive-processor \
  --to-revisions=PREVIOUS_REVISION_NAME=100 \
  --region=us-central1

# Revert Phase 3 variable
# Edit variables.tf back to delete_after_load = true and re-apply terraform
```

Note: BigQuery columns cannot be removed without recreating the table, so the ALTER TABLE changes are permanent.
