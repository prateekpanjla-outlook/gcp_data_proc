# Phase 2 Deployment Status

**Last Updated:** 2026-03-07 00:30 UTC

## Deployment Summary

| Layer | Status | Resources Deployed |
|-------|--------|-------------------|
| Layer 01: Static Resources | ✅ Complete | 11 resources |
| Layer 02: First-Time Setup | ✅ Complete | 11 resources |
| Layer 03: Operational Resources | 🔄 In Progress - Fixing Docker image | Pending |

**Current Status:** Rebuilding Docker image - fixing relative import issue (`python -m main` → `python main.py`)

---

## Layer 01: Static Resources ✅

**Location:** `infrastructure/phase2_process_files/terraform/layers/01_static`

### Resources Created
| Resource | Name/Email |
|----------|------------|
| Service Accounts | |
| - Processor SA | `dev-github-archive-processor@...` |
| - Splitter SA | `dev-file-splitter@...` |
| - Eventarc Invoker SA | `dev-eventarc-invoker@...` |
| Storage Bucket | `dev-dataprocessing-489305-dev-github-archive-staging` |
| Project IAM | |
| - Processor → Logging | `roles/logging.logWriter` |
| - Processor → Monitoring | `roles/monitoring.metricWriter` |
| - Splitter → Logging | `roles/logging.logWriter` |
| Bucket IAM | |
| - Processor → Landing (read) | `roles/storage.objectViewer` |
| - Processor → Staging (write) | `roles/storage.objectCreator` |
| - Splitter → Landing (read) | `roles/storage.objectViewer` |
| - Splitter → Landing chunks (write) | `roles/storage.objectCreator` |

**Variables:**
- `project_id` = dev-dataprocessing-489305
- `region` = us-central1
- `environment` = dev
- `landing_bucket_name` = dev-dataprocessing-489305-dev-github-archive-landing
- `staging_retention_days` = 30

---

## Layer 02: First-Time Setup ✅

**Location:** `infrastructure/phase2_process_files/terraform/layers/02_first_time`

### Resources Created
| Resource | Details |
|----------|---------|
| APIs Enabled (8) | eventarc, eventarcpublishing, cloud run, storage, cloudresourcemanager, iam, logging, monitoring |
| Artifact Registry | `github-archive` Docker repository in us-central1 |
| Service Agent IAM | |
| - Storage SA → `roles/pubsub.publisher` |
| - Eventarc SA → `roles/eventarc.eventReceiver` |

**Variables:**
- `project_id` = dev-dataprocessing-489305
- `region` = us-central1
- `environment` = dev

**Manual Steps Required:**
1. ✅ Activate Storage service agent: `gcloud storage service-agent --project=PROJECT_ID`
2. ✅ Activate Eventarc service agent: `gcloud beta services identity create --service=eventarc.googleapis.com --project=PROJECT_ID`

---

## Layer 03: Operational Resources 🔄

**Location:** `infrastructure/phase2_process_files/terraform/layers/03_operational`

### Resources To Create
| Resource | Description |
|----------|-------------|
| Cloud Run v2 Service | Processor service for handling GitHub Archive files |
| Eventarc Trigger #1 | Main file processor (raw/ folder) |
| Eventarc Trigger #2 | Chunk processor (chunks/ folder) |
| IAM Bindings | Eventarc invoker permissions |

**Variables:**
- `project_id` = dev-dataprocessing-489305
- `region` = us-central1
- `environment` = dev
- `terraform_state_bucket` = dev-dataprocessing-489305-terraform-state
- `image_tag` = latest (default)
- `file_size_threshold_mb` = 500 (default)
- `processor_memory` = 8 (default, GiB)
- `processor_cpu` = 4 (default)
- `max_instances` = 100 (default)
- `chunksize` = 100000 (default)

**Status:** Terraform configuration fixed for Cloud Run v2 Service schema. Docker image issues being resolved.

### Docker Image Issues (2026-03-07):

| Error | Root Cause | Fix |
|-------|------------|-----|
| Module path not found | `github_archive.phase2_process_files.main` doesn't exist in container | Changed to `python -m main` |
| ModuleNotFoundError: No module 'flask' | Packages in `/root/.local` owned by root, appuser can't read | Copy to `/usr/local` instead |
| ImportError: attempted relative import | `python -m main` doesn't support relative imports | Changed to `python main.py` |

**Dockerfile Fixes Applied:**
1. `COPY . .` - Copy from build context to `/app/`
2. `COPY --from=builder /root/.local /usr/local` - Packages accessible to all users
3. `ENV PYTHONPATH=/app:/usr/local/lib/python3.11/site-packages:$PYTHONPATH`
4. `CMD ["python", "main.py"]` - Run as script, not module

### Fixes Applied (2026-03-06):
- Moved `metadata.annotations` → `template.annotations` (v2 format)
- Removed unsupported `requests` block from container resources
- Changed `container_concurrency` → `max_instance_request_concurrency`
- Changed `timeout_seconds` → `timeout = "3600s"` (duration format)
- Added `deletion_protection = false` at resource level
- Added `ingress = "INGRESS_TRAFFIC_ALL"` at resource level
- Added `execution_environment = "EXECUTION_ENVIRONMENT_GEN2"` under template
- Added `scaling` block with `min/max_instance_count` at service level

---

## Issues Found & Resolved

### Issue 1: Service Agents Not Created Automatically
**Error:** Service accounts `service-PROJECT@gs-project-accounts` and `service-PROJECT@gcp-sa-eventarc` don't exist even after enabling APIs.

**Root Cause:** Google-managed service agents are NOT created automatically when APIs are enabled. They must be explicitly activated.

**Fix:**
```bash
gcloud storage service-agent --project=PROJECT_ID
gcloud beta services identity create --service=eventarc.googleapis.com --project=PROJECT_ID
```

**Documentation:** See [learnings/google_service_agents.md](learnings/google_service_agents.md)

### Issue 2: Duplicate `template` Block in Cloud Run Service
**Error:** `Blocks of type "template" are not expected here.`

**Root Cause:** The `google_cloud_run_v2_service` resource had two separate `template` blocks instead of one combined block.

**Fix:** Merged `metadata` and `containers` into a single `template` block.

### Issue 3: Numeric Format in Terraform
**Error:** `Missing newline after argument` for `default = 100_000`

**Root Cause:** Underscore numeric separator not supported in Terraform 1.5+

**Fix:** Changed `100_000` to `100000`

---

## Next Steps

1. ✅ Deploy Layer 03 (Operational Resources)
2. ⏳ Build and push Docker images to Artifact Registry
3. ⏳ Verify Eventarc triggers are working
4. ⏳ End-to-end testing

---

## Configuration Notes

### Docker Image Repository
```
us-central1-docker.pkg.dev/dev-dataprocessing-489305/github-archive/processor:latest
```

### Eventarc Triggers
| Trigger | Event Pattern | Destination |
|---------|---------------|-------------|
| Main file processor | `github-archive/raw/*.json.gz` | Cloud Run Service |
| Chunk processor | `github-archive/chunks/*.json.gz` | Cloud Run Service |

### Storage Buckets
| Bucket | Purpose | Retention |
|--------|---------|-----------|
| `dev-dataprocessing-489305-dev-github-archive-landing` | Raw GitHub Archive files | 6 days |
| `dev-dataprocessing-489305-dev-github-archive-staging` | Processed staging data | 30 days |
