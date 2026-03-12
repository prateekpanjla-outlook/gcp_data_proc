# Terraform Destroy — Test Project (beaming-glyph-489707-b8)

Date: 2026-03-13

## Overview

Destroyed all GitHub Archive pipeline resources in the test project.
Destroy order: Phase 3 (reverse layers) -> Phase 2 -> Phase 1.

## Prerequisites

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/c/Users/prateek/Desktop/gcp/gcp_data_processing/infrastructure/test-terraform-deployer-key.json"
```

## Destroy Order and Results

### Phase 3: BigQuery Loader (3 layers, reverse order)

| Layer | Resources Destroyed | Errors | Time |
|-------|-------------------|--------|------|
| 03_operational | 7 (Cloud Function, source bucket, IAM) | None | ~30s |
| 02_first_time | 4 (bucket IAM, dataset IAM) | None | ~25s |
| 01_static | 15 (BQ dataset/table, SAs, APIs, IAM) | None | ~30s |

### Phase 2: File Processor

| Resources Destroyed | Errors | Time |
|-------------------|--------|------|
| 25 (Cloud Run service, Eventarc trigger, staging bucket, SAs, IAM, APIs) | None | ~45s |

### Phase 1: Ingestion

| Resources Destroyed | Errors | Time |
|-------------------|--------|------|
| 20 total (first 19 clean, then bucket required manual fix) | 1 error (see below) | ~2 min |

## Errors and Fixes

### Error 1: Missing `region` variable (Phase 3 Layer 02)

**Error:**
```
Error: No value for required variable
  on variables.tf line 10: variable "region"
```

**Cause:** Layer 02 requires `region` but it has no default value. Layer 03 didn't need it explicitly
because it reads from remote state.

**Fix:** Add `-var="region=us-central1"` to the destroy command.

**Lesson:** Always check `variables.tf` for required vars without defaults before running destroy.
Not all layers need the same variables.

---

### Error 2: Missing `deployer_sa_key_path` variable (Phase 2)

**Error:**
```
Error: No value for required variable
  on variables.tf line 84: variable "deployer_sa_key_path"
```

**Cause:** Phase 2 uses `deployer_sa_key_path` for `local-exec` provisioners (Cloud Build).
Even during destroy, Terraform evaluates all variables.

**Fix:** Add `-var="deployer_sa_key_path=/c/Users/prateek/.../test-terraform-deployer-key.json"`

**Lesson:** Variables used by `null_resource`/`local-exec` are still required during destroy,
even though the provisioner won't actually run.

---

### Error 3: Landing bucket not empty (Phase 1)

**Error:**
```
Error: Error trying to delete bucket beaming-glyph-489707-b8-test-github-archive-landing
containing objects without `force_destroy` set to true
```

**Cause:** The landing bucket had 5 `.json.gz` files from Phase 1 downloads.
The Terraform config uses conditional force_destroy:
```hcl
force_destroy = var.environment == "dev" ? true : var.force_destroy
```
For `environment=test`, it falls back to `var.force_destroy` which defaults to `false`.
Even passing `-var="force_destroy=true"` doesn't help because the bucket resource in state
already has `force_destroy=false` — Terraform tries to delete the bucket AS-IS from state.

**Fix:** Manually empty the bucket first, then retry destroy:
```bash
gcloud storage rm "gs://beaming-glyph-489707-b8-test-github-archive-landing/**"
terraform destroy ...  # now succeeds
```

**Lesson:** For non-dev environments, always empty GCS buckets before `terraform destroy`.
Alternatively, set `force_destroy = true` for all test environments in the Terraform config.
Consider changing the condition to:
```hcl
force_destroy = var.environment != "prod" ? true : var.force_destroy
```

## Complete Destroy Commands

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/c/Users/prateek/Desktop/gcp/gcp_data_processing/infrastructure/test-terraform-deployer-key.json"
PROJECT="beaming-glyph-489707-b8"
ENV="test"
KEY_PATH="$GOOGLE_APPLICATION_CREDENTIALS"
BASE="/c/Users/prateek/Desktop/gcp/gcp_data_processing/infrastructure/github_archive"

# Phase 3 Layer 03
terraform -chdir="$BASE/phase3_loadbigquery/terraform/layers/03_operational" destroy -auto-approve \
  -var="project_id=$PROJECT" -var="environment=$ENV" \
  -var="staging_bucket_name=$PROJECT-$ENV-github-archive-staging"

# Phase 3 Layer 02
terraform -chdir="$BASE/phase3_loadbigquery/terraform/layers/02_first_time" destroy -auto-approve \
  -var="project_id=$PROJECT" -var="environment=$ENV" -var="region=us-central1" \
  -var="staging_bucket_name=$PROJECT-$ENV-github-archive-staging"

# Phase 3 Layer 01
terraform -chdir="$BASE/phase3_loadbigquery/terraform/layers/01_static" destroy -auto-approve \
  -var="project_id=$PROJECT" -var="environment=$ENV" -var="region=us-central1"

# Phase 2
terraform -chdir="$BASE/phase2_process_files/terraform" destroy -auto-approve \
  -var="project_id=$PROJECT" -var="environment=$ENV" \
  -var="landing_bucket_name=$PROJECT-$ENV-github-archive-landing" \
  -var="deployer_sa_key_path=$KEY_PATH"

# Phase 1 (empty bucket first!)
gcloud storage rm "gs://$PROJECT-$ENV-github-archive-landing/**" 2>/dev/null
terraform -chdir="$BASE/phase1_ingestion/terraform" destroy -auto-approve \
  -var="project_id=$PROJECT" -var="environment=$ENV" -var="force_destroy=true" \
  -var="deployer_sa_key_path=$KEY_PATH"
```

## Total Resources Destroyed

| Phase | Resources |
|-------|-----------|
| Phase 3 L03 | 7 |
| Phase 3 L02 | 4 |
| Phase 3 L01 | 15 |
| Phase 2 | 25 |
| Phase 1 | 20 |
| **Total** | **71** |
