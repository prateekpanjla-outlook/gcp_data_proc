# Phase 2: Test Project Deployment Errors

**Date:** 2026-03-12
**Project:** beaming-glyph-489707-b8 (test)

---

## Error 19: Cloud Build SHORT_SHA Empty for gcloud builds submit

**Error Message:**
```
ERROR: (gcloud.builds.submit) INVALID_ARGUMENT: invalid build: invalid image name
"us-central1-docker.pkg.dev/PROJECT_ID/test-github-archive/processor:": could not parse reference
```

**Root Cause:**
`SHORT_SHA` is a Cloud Build built-in substitution that is only populated for Git-triggered builds (e.g., from GitHub/Cloud Source Repositories). When using `gcloud builds submit` manually or from Terraform `local-exec`, `SHORT_SHA` is empty, resulting in an invalid image tag ending with `:`.

**Fix:**
Use `BUILD_ID` instead of `SHORT_SHA` — `BUILD_ID` is always populated:

```yaml
# ❌ Wrong — SHORT_SHA is empty for gcloud builds submit
- '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_ENV}-github-archive/processor:${SHORT_SHA}'

# ✅ Correct — BUILD_ID is always available
- '${_REGION}-docker.pkg.dev/$PROJECT_ID/${_ENV}-github-archive/processor:${BUILD_ID}'
```

**Cloud Build Built-in Substitutions:**
| Variable | Available When | Description |
|----------|---------------|-------------|
| `$SHORT_SHA` | Git-triggered builds only | First 7 chars of commit SHA |
| `$COMMIT_SHA` | Git-triggered builds only | Full commit SHA |
| `$BUILD_ID` | Always | Unique build identifier |
| `$PROJECT_ID` | Always | GCP project ID |

---

## Error 20: Cloud Run Service Created Before Image Exists

**Error Message:**
```
Error waiting to create Service: Error code 5, message: Image
'us-central1-docker.pkg.dev/PROJECT_ID/test-github-archive/processor:latest' not found.
```

**Root Cause:**
Terraform created the Cloud Run v2 service in parallel with the Cloud Build `null_resource`. The Cloud Run service requires the container image to exist in Artifact Registry, but the build hadn't finished yet.

**Fix:**
Add `depends_on` to ensure the image is built before the Cloud Run service is created:

```hcl
resource "google_cloud_run_v2_service" "processor" {
  # ...
  depends_on = [null_resource.build_processor_image]
}
```

**Key Takeaway:**
When using `null_resource` with `local-exec` for Cloud Build, any resource that references the built image must explicitly `depends_on` the build resource.

---

## Error 21: Google-Managed Service Agents Don't Exist

**Error Message:**
```
Error 400: Service account service-PROJECT_NUMBER@gs-project-accounts.iam.gserviceaccount.com does not exist., badRequest
Error 400: Service account service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com does not exist., badRequest
```

**Root Cause:**
Google-managed service agents (GCS, Eventarc, Pub/Sub) are NOT created automatically when you enable an API via `google_project_service`. They are created lazily — only when you first use the service, or when you explicitly initialize them.

In a fresh project (or test project), these service agents may not exist yet, causing IAM binding failures.

**Affected Service Agents:**
| Service | Agent Email Pattern |
|---------|-------------------|
| Cloud Storage | `service-NUMBER@gs-project-accounts.iam.gserviceaccount.com` |
| Eventarc | `service-NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com` |
| Pub/Sub | `service-NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` |

**Fix:**
Use `gcloud beta services identity create` to explicitly initialize service agents before binding IAM:

```hcl
# In Terraform — null_resource to initialize service agents
resource "null_resource" "init_service_agents" {
  depends_on = [
    google_project_service.storage,
    google_project_service.eventarc,
  ]

  provisioner "local-exec" {
    command = format(
      "gcloud beta services identity create --service=storage.googleapis.com --project=%s; gcloud beta services identity create --service=eventarc.googleapis.com --project=%s",
      var.project_id,
      var.project_id
    )
    interpreter = ["powershell", "-Command"]
  }
}

# IAM bindings must depend on init_service_agents
resource "google_project_iam_member" "storage_pubsub_publisher" {
  # ...
  depends_on = [null_resource.init_service_agents]
}
```

**Alternative (requires google-beta provider):**
```hcl
resource "google_project_service_identity" "gcs" {
  provider = google-beta
  project  = var.project_id
  service  = "storage.googleapis.com"
}
```

Note: `google_project_service_identity` is only available in the `google-beta` provider, not `google`.

---

## Error 22: Eventarc GCS Events Don't Support Path Filtering

**Error Message:**
```
Error creating Trigger: googleapi: Error 400: The request was invalid: invalid argument:
event type google.cloud.storage.object.v1.finalized not supported: attribute name not found within event type
```

**Root Cause:**
Eventarc direct events from Cloud Storage (`google.cloud.storage.object.v1.finalized`) only support two filter attributes:
- `type` (required): The event type
- `bucket` (required): The bucket name

The `name` attribute (object path) is **NOT** a supported filter attribute for GCS direct events. Attempting to use `match-path-pattern` on `name` fails.

**What Does NOT Work:**
```hcl
# ❌ This fails — name filter not supported for GCS events
matching_criteria {
  attribute = "type"
  value     = "google.cloud.storage.object.v1.finalized"
}
matching_criteria {
  attribute = "bucket"
  value     = "my-bucket"
}
matching_criteria {
  attribute = "name"              # ❌ NOT SUPPORTED
  value     = "github-archive/raw/"
  operator  = "match-path-pattern"
}
```

**Fix:**
Use a single trigger per bucket and handle path routing in application code:

```hcl
# ✅ Only filter by type and bucket
resource "google_eventarc_trigger" "storage_trigger" {
  name = "my-storage-trigger"
  # ...
  matching_criteria {
    attribute = "type"
    value     = "google.cloud.storage.object.v1.finalized"
  }
  matching_criteria {
    attribute = "bucket"
    value     = var.landing_bucket_name
  }
  # NO name filter — handle routing in application code
}
```

**Application-Level Routing:**
```python
# In Cloud Run handler, check file path
file_path = event_data.get("name", "")
if file_path.startswith("github-archive/raw/"):
    process_raw_file(file_path)
elif file_path.startswith("github-archive/chunks/"):
    process_chunk_file(file_path)
else:
    logger.info(f"Ignoring file: {file_path}")
```

**For Path-Based Filtering Alternatives:**
1. **Cloud Storage Pub/Sub Notifications** + Pub/Sub subscription filters (different architecture)
2. **Multiple buckets** — one bucket per event type, each with its own trigger
3. **Application-level routing** (simplest, recommended)

---

## Error 23: Provider v5.x Schema Differences from Learnings

**Root Cause:**
The Phase 2 learnings document was based on a later provider version. When using `google` provider `~> 5.0` (v5.45.2):

| Feature | Provider 5.x | Provider 6+/7+ |
|---------|-------------|-----------------|
| `deletion_protection` | Not supported | Supported |
| `scaling {}` block | Inside `template {}` | At root level |
| `google_project_service_identity` | Beta provider only | Standard provider |

**Fix:**
```hcl
# ✅ Provider 5.x — scaling inside template
resource "google_cloud_run_v2_service" "processor" {
  # NO deletion_protection
  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }
    containers { ... }
  }
  # NO root-level scaling block
}
```

---

## Error 24: Terraform Number Literal Underscore Separators

**Error Message:**
```
Error: Missing newline after argument
  on variables.tf line 76, in variable "chunksize":
  76:   default     = 100_000
```

**Root Cause:**
Terraform does NOT support Python-style numeric literal separators (`100_000`). Numbers must be written without underscores.

**Fix:**
```hcl
# ❌ Wrong
default = 100_000

# ✅ Correct
default = 100000
```

---

## Summary of Phase 2 Test Deployment

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| Empty SHORT_SHA | Not set for gcloud builds submit | Use BUILD_ID instead |
| Image not found | Cloud Run created before build | depends_on build resource |
| Service agents missing | Not auto-created on fresh projects | gcloud beta services identity create |
| Path filter unsupported | GCS events only support type+bucket | Single trigger, app-level routing |
| deletion_protection | Not in provider 5.x | Remove from config |
| scaling block location | Inside template in 5.x | Move scaling into template |
| Number underscores | Not valid Terraform syntax | Use plain numbers |

**Final Resource Count:** 26 resources + 1 data source = 27 total
