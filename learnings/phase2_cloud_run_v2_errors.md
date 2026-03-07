# Phase 2: Cloud Run v2 Service Deployment Errors

**Date:** 2026-03-06
**Layer:** Phase 2 - Layer 03 (Operational Resources)

---

## Overview

This document captures all errors encountered during the deployment of Cloud Run v2 Service resources in Phase 2 Layer 03, along with their root causes and fixes.

---

## Error 1: Cloud Run v2 Schema - `metadata` Block

**Error Message:**
```
Error: Unsupported block type
Blocks of type "metadata" are not expected here.
```

**Root Cause:**
Cloud Run v2 API has a different schema than v1. In v2, `annotations` are placed directly at the `template` level, not nested inside a `metadata` block.

**Fix:**
```hcl
# ❌ Wrong (v1 style)
template {
  metadata {
    annotations = { ... }
  }
}

# ✅ Correct (v2 style)
template {
  annotations = { ... }
}
```

---

## Error 2: Cloud Run v2 Schema - `requests` Block

**Error Message:**
```
Error: Unsupported argument
An argument named "requests" is not expected here.
```

**Root Cause:**
Cloud Run v2 doesn't support the `requests` field in container resources. Only `limits` is supported.

**Fix:**
```hcl
# ❌ Wrong
resources {
  limits = { ... }
  requests = { ... }
}

# ✅ Correct
resources {
  limits = { ... }
  cpu_idle = true  # CPU only allocated during requests
}
```

---

## Error 3: Cloud Run v2 Schema - `container_concurrency`

**Error Message:**
```
Error: Unsupported argument
An argument named "container_concurrency" is not expected here.
```

**Root Cause:**
In Cloud Run v2, `container_concurrency` is renamed to `max_instance_request_concurrency`.

**Fix:**
```hcl
# ❌ Wrong (v1 style)
container_concurrency = 10

# ✅ Correct (v2 style)
max_instance_request_concurrency = 10
```

---

## Error 4: Cloud Run v2 Schema - `timeout_seconds`

**Error Message:**
```
Error: Unsupported argument
An argument named "timeout_seconds" is not expected here.
```

**Root Cause:**
Cloud Run v2 uses `timeout` with a duration string (e.g., "3600s") instead of `timeout_seconds` with a number.

**Fix:**
```hcl
# ❌ Wrong
timeout_seconds = 3600

# ✅ Correct
timeout = "3600s"
```

---

## Error 5: Reserved Environment Variable `PORT`

**Error Message:**
```
Error: template.containers[0].env: The following reserved env names were provided: PORT.
These values are automatically set by the system.
```

**Root Cause:**
`PORT` is a reserved environment variable in Cloud Run. It's automatically set by the system to the port that receives incoming requests.

**Fix:**
Remove `PORT` from the environment variables in the container configuration.

```hcl
# ❌ Wrong
env {
  name  = "PORT"
  value = "8080"
}

# ✅ Correct - Remove it entirely
# PORT is automatically set by Cloud Run
```

**Reserved Environment Variables in Cloud Run:**
- `PORT` - Automatically set to the port receiving requests
- `K_CONFIGURATION` - Configuration name
- `K_REVISION` - Revision name
- `K_SERVICE` - Service name

---

## Error 6: Quota Exceeded - Max Instances

**Error Message:**
```
Error: scaling.max_instance_count: Max instances must be set to 5 or fewer to set the requested total CPU.

Quota violated:
CpuAllocPerProjectRegion requested: 400000 allowed: 20000
MemAllocPerProjectRegion requested: 858993459200 allowed: 42949672960
```

**Root Cause:**
The configuration specified:
- `max_instances = 100`
- `cpu = 4` per instance
- `memory = 8Gi` per instance

Total required: 100 × 4 = 400 CPUs (exceeds 20 CPU quota)

**Fix Options:**

1. **Reduce max_instances** (quick fix):
```hcl
variable "max_instances" {
  default = 5  # Reduced from 100
}
```

2. **Reduce per-instance resources**:
```hcl
cpu = "1"      # Reduced from 4
memory = "2Gi" # Reduced from 8Gi
```

3. **Request quota increase** (for production):
- Go to Cloud Console → IAM & Admin → Quotas
- Search for "Cloud Run API"
- Request increase for `CpuAllocPerProjectRegion` and `MemAllocPerProjectRegion`

**Default Quotas (varies by project/region):**
| Quota | Default |
|-------|---------|
| CPU | 20 vCPUs |
| Memory | 40 GiB |
| Requests | 2000 per 100s |

---

## Cloud Run v2 vs v1 Schema Reference

| v1 (Job/old) | v2 Service |
|--------------|------------|
| `metadata { annotations }` | `annotations` (in template) |
| `container_concurrency` | `max_instance_request_concurrency` |
| `timeout_seconds` (number) | `timeout` (string with "s") |
| `resources { limits, requests }` | `resources { limits, cpu_idle }` |
| Autoscaling annotations | `scaling { min/max_instance_count }` |
| - | `deletion_protection` |
| - | `ingress` |
| - | `execution_environment` |

---

## Required Fields for Cloud Run v2 Service

```hcl
resource "google_cloud_run_v2_service" "example" {
  name     = "service-name"
  location = "us-central1"
  project  = var.project_id
  deletion_protection = false  # Required for destroy
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    annotations = { ... }
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2"
    timeout = "3600s"
    max_instance_request_concurrency = 10

    containers {
      image = "..."
      resources {
        limits = { ... }
        cpu_idle = true
      }
    }

    service_account = "..."
  }

  scaling {
    min_instance_count = 0
    max_instance_count = 5
  }

  labels = { ... }
}
```

---

## Verification Commands

**Check Cloud Run quotas:**
```bash
gcloud compute project-info describe \
  --project=PROJECT_ID \
  --flatten="quotas[]" \
  --format="table(quotas.metric,quotas.limit,quotas.usage)"
```

**List existing Cloud Run services:**
```bash
gcloud run services list --region=us-central1 --project=PROJECT_ID
```

**View service details:**
```bash
gcloud run services describe SERVICE_NAME \
  --region=us-central1 \
  --project=PROJECT_ID \
  --format="yaml"
```

---

## Error 7: Docker Authentication to Artifact Registry

**Error Message:**
```
error from registry: Unauthenticated request. Unauthenticated requests do not have permission
"artifactregistry.repositories.uploadArtifacts" on resource
"projects/PROJECT_ID/locations/REGION/repositories/REPO_NAME"
```

**Root Cause:**
Docker needs to be authenticated to Google Artifact Registry before pushing images.

**Fix:**
Configure Docker credential helper for Artifact Registry:

```bash
# Authenticate Docker to Artifact Registry
gcloud auth configure-docker REGION-docker.pkg.dev

# If using sudo with docker commands, also configure for root
sudo gcloud auth configure-docker REGION-docker.pkg.dev
```

**Example:**
```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
sudo gcloud auth configure-docker us-central1-docker.pkg.dev
```

**Then build and push:**
```bash
export PROJECT_ID=dev-dataprocessing-489305
export REGION=us-central1
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/github-archive/processor"

sudo docker build -f Dockerfile.processor -t "${IMAGE_NAME}:latest" .
sudo docker push "${IMAGE_NAME}:latest"
```

---

## Error 8: Docker Socket Permission Denied

**Error Message:**
```
ERROR: permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

**Root Cause:**
User is not in the `docker` group OR the docker socket doesn't have group write permissions.

**Fix:**

1. **Add user to docker group:**
```bash
sudo usermod -aG docker $USER
```

2. **Fix docker.sock permissions:**
```bash
sudo chmod 666 /var/run/docker.sock
```

3. **Apply group change (one of these):**
```bash
# Option A: Log out and log back in
# OR

# Option B: Use newgrp to apply immediately
newgrp docker
```

**Verification:**
```bash
# Verify group membership
groups

# Check docker.sock permissions
ls -la /var/run/docker.sock
# Should show: srw-rw---- 1 root docker
```

**Then build without sudo:**
```bash
export PROJECT_ID=dev-dataprocessing-489305
export REGION=us-central1
IMAGE_NAME="${REGION}-docker.pkg.dev/${PROJECT_ID}/github-archive/processor"

cd /path/to/source
docker build -f Dockerfile.processor -t "${IMAGE_NAME}:latest" .
docker push "${IMAGE_NAME}:latest"
```

---

## Error 9: Container Failed to Start - Module Not Found

**Error Message:**
```
Error: Error waiting to create Service: Error waiting for Creating Service: Error code 9,
message: The user-provided container failed to start and listen on the port defined
provided by the PORT=8080 environment variable within the allocated timeout.
```

**Cloud Run Logs:**
```
Default STARTUP TCP probe failed 1 time consecutively for container "processor-1" on port 8080.
terminated: Application failed to start: The container may have exited abnormally.
Application exec likely failed
```

**Root Cause:**
The Dockerfile CMD was trying to run `python -m github_archive.phase2_process_files.main` but:
1. The build context was `phase2_process_files/` directory, not `src/github_archive/`
2. The COPY command copied files to `/app/main.py` directly
3. The module path `github_archive.phase2_process_files.main` doesn't exist in the container
4. Relative imports (`from .processors.file_processor`) require PYTHONPATH to be set

**Fix:**
Update the Dockerfile to match the build context:

```dockerfile
# Copy application code
# Build context is phase2_process_files/ directory
COPY . .

# Add PYTHONPATH for relative imports to work
ENV PYTHONPATH=/app:$PYTHONPATH

# Run the application
# With PYTHONPATH=/app, we can run as a module
CMD ["python", "-m", "main"]
```

**Key Changes:**
1. `COPY . .` - Copy files from build context to /app/
2. `ENV PYTHONPATH=/app:$PYTHONPATH` - Enable relative imports
3. `CMD ["python", "-m", "main"]` - Run main.py as a module

**Additional Fix - Health Check Start Period:**
```dockerfile
# Health check - longer start period for Flask to initialize
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health').read()" || exit 1
```

Increased `start-period` from 5s to 30s to give Flask more time to initialize.

**Verification:**
```bash
# Test the Docker image locally first
docker run --rm -p 8080:8080 -e PORT=8080 IMAGE_NAME

# Check container can import modules
docker run --rm --entrypoint python IMAGE_NAME -c "import main; print('OK')"
```

---

## Error 10: ModuleNotFoundError - Python Packages Not Found

**Error Message:**
```
ModuleNotFoundError: No module named 'flask'
```

**Local Test Output:**
```bash
$ docker run --rm IMAGE_NAME
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "/app/main.py", line 13, in <module>
    from flask import Flask, request, jsonify
ModuleNotFoundError: No module named 'flask'
```

**Root Cause:**
The multi-stage Dockerfile:
1. Builder stage installs packages to `/root/.local` with `pip install --user`
2. Runtime stage copies `/root/.local` to `/root/.local` (owned by root)
3. Container runs as `appuser` who cannot read `/root/.local`
4. Python can't find the installed packages

**Fix for Multi-Stage Build (processor):**
```dockerfile
# ❌ Wrong - packages owned by root, inaccessible to appuser
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# ✅ Correct - copy to /usr/local accessible to all users
COPY --from=builder /root/.local /usr/local
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:$PYTHONPATH
```

**Fix for Single-Stage Build (splitter):**
```dockerfile
# ❌ Wrong - packages in /usr/local/lib but PYTHONPATH not set
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ✅ Correct - use --prefix to install to accessible location
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix /usr/local -r requirements.txt
ENV PYTHONPATH=/usr/local/lib/python3.11/site-packages:$PYTHONPATH
```

**Key Points:**
1. Use `pip install --prefix /usr/local` instead of `pip install --user`
2. Set `PYTHONPATH` to include the site-packages directory
3. `/usr/local` is readable by all users
4. Multi-stage builds need to copy to accessible locations

---

## Error 11: ImportError - Attempted Relative Import With No Known Parent Package

**Error Message:**
```
ImportError: attempted relative import with no known parent package
```

**Local Test Output:**
```bash
$ docker run --rm IMAGE_NAME
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "/app/main.py", line 16, in <module>
    from .processors.file_processor import GitHubArchiveFileProcessor
ImportError: attempted relative import with no known parent package
```

**Root Cause:**
Running `python -m main` treats `main.py` as a module, but the code uses relative imports (`from .processors.file_processor`). Relative imports only work when:
1. Running a package module with full package path (e.g., `python -m package.module`)
2. OR running as a script directly with `python script.py`

The `python -m main` command doesn't provide a package context for relative imports.

**Fix:**
```dockerfile
# ❌ Wrong - -m flag breaks relative imports
CMD ["python", "-m", "main"]

# ✅ Correct - run as script directly
CMD ["python", "main.py"]
```

**Key Difference:**
| Command | Package Context | Relative Imports Work? |
|---------|----------------|------------------------|
| `python -m main` | No (module only) | ❌ No |
| `python main.py` | Yes (script in __package__) | ✅ Yes |

**Note:** When running as a script, Python sets `__package__` based on the directory structure, allowing relative imports to work correctly.

---

---

## Error 12: Eventarc Trigger - Permission Denied on Service Account

**Error Message:**
```
Error 403: Permission "eventarc.events.receiveEvent" denied on "dev-eventarc-invoker@PROJECT_ID.iam.gserviceaccount.com"
```

**Root Cause:**
When using a custom service account for Eventarc triggers (instead of the Google-managed service agent), the custom service account must have the `roles/eventarc.eventReceiver` role. This role was only granted to the Google-managed Eventarc service agent (`service-PROJECT_NUMBER@gcp-sa-eventarc.iam.gserviceaccount.com`), not to the custom invoker service account.

**Fix:**

**Option A: Grant via gcloud (quick fix)**
```bash
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="serviceAccount:YOUR_EVENTARC_INVOKER_SA@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/eventarc.eventReceiver"
```

**Option B: Add to Terraform Layer 01 (static resources)**
```hcl
# Eventarc Invoker Service Account - Event Receiver role
resource "google_project_iam_member" "eventarc_invoker_event_receiver" {
  project = var.project_id
  role    = "roles/eventarc.eventReceiver"
  member  = "serviceAccount:${google_service_account.eventarc_invoker.email}"

  depends_on = [
    google_project_service.eventarc,
  ]
}
```

**Key Point:**
Eventarc triggers need TWO service accounts with permissions:
1. **Google-managed Eventarc service agent** (`service-XXX@gcp-sa-eventarc.iam.gserviceaccount.com`) - needs `roles/eventarc.eventReceiver` to create the Pub/Sub subscription
2. **Custom invoker service account** (your SA) - ALSO needs `roles/eventarc.eventReceiver` to actually receive and forward events

**Verification:**
```bash
# Check if service account has the role
gcloud projects get-iam-policy PROJECT_ID \
  --filter="bindings.members:serviceAccount:YOUR_SA@PROJECT_ID.iam.gserviceaccount.com"
```

---

## References

- [Cloud Run v2 Migration Guide](https://cloud.google.com/run/docs/docs/using/v2)
- [Cloud Run Quotas](https://cloud.google.com/run/quotas)
- [Cloud Run Environment Variables](https://cloud.google.com/run/docs/configuring/environment-variables)
- [Terraform google_cloud_run_v2_service](https://registry.terraform.io/providers/hashicorp/google/latest/docs/resources/cloud_run_v2_service)
- [Artifact Registry Docker Authentication](https://cloud.google.com/artifact-registry/docs/docker/authentication)
- [Eventarc IAM permissions](https://cloud.google.com/eventarc/docs/iam#permissions)

---

## Error 13: File Not Found After Gzip Decompression

**Error Message:**
```
Processing failed: File /tmp/tmpXXXX.json.gz does not exist
```

**Cloud Run Logs:**
```
Error processing file: 2026-03-07-02.json.gz - Processing failed: File /tmp/tmpe2k9zg60.json.gz does not exist
```

**Root Cause:**

The `read_file_to_local()` function in `gcs_client.py`:
1. Downloads the GCS file to `tmp_path` (e.g., `/tmp/tmpXXXX.json.gz`)
2. If `decompress=True`, decompresses to `tmp_path[:-3]` (e.g., `/tmp/tmpXXXX.json`)
3. **Deletes** the original `.gz` file with `os.remove(local_path)`
4. Returns only `FileMetadata` - NOT the new decompressed path

The caller's `tmp_path` variable still points to the deleted `.gz` file, causing `pd.read_json(tmp_path)` to fail.

**Code Flow:**
```python
# In file_processor.py and file_splitter.py
with tempfile.NamedTemporaryFile(delete=False, suffix='.json.gz') as tmp:
    tmp_path = tmp.name  # e.g., "/tmp/tmpABCD.json.gz"

# This call DELETES the .gz file and creates .json
self.gcs_client.read_file_to_local(input_gcs_path, tmp_path, decompress=True)
# But tmp_path still == "/tmp/tmpABCD.json.gz" (file was deleted!)

# Later this fails - file doesn't exist!
for chunk_df in pd.read_json(tmp_path, lines=True, chunksize=self.chunksize):
```

**Fix:**

**1. Update `gcs_client.py` to return the actual file path:**
```python
# ❌ Before - only returns metadata
def read_file_to_local(
    self,
    gcs_path: str,
    local_path: str,
    decompress: bool = True
) -> FileMetadata:
    # ... download and decompress logic ...
    if decompress and local_path.endswith('.gz'):
        decompressed_path = local_path[:-3]
        # ... decompress ...
        os.remove(local_path)
        local_path = decompressed_path  # Local variable only!
    return metadata

# ✅ After - returns tuple of (actual_path, metadata)
def read_file_to_local(
    self,
    gcs_path: str,
    local_path: str,
    decompress: bool = True
) -> tuple[str, FileMetadata]:
    """
    Returns:
        Tuple of (actual_file_path, FileMetadata)
        Note: actual_file_path may differ from local_path if decompression occurred
    """
    # ... download and decompress logic ...
    if decompress and local_path.endswith('.gz'):
        decompressed_path = local_path[:-3]
        # ... decompress ...
        os.remove(local_path)
        local_path = decompressed_path
    return local_path, metadata  # Return the actual path!
```

**2. Update all callers to unpack the tuple:**
```python
# In file_processor.py, file_splitter.py, and gcs_client.py utility function

# ❌ Before
self.gcs_client.read_file_to_local(input_gcs_path, tmp_path, decompress=True)
# tmp_path still points to deleted file

# ✅ After
tmp_path, _ = self.gcs_client.read_file_to_local(input_gcs_path, tmp_path, decompress=True)
# tmp_path now points to decompressed file
```

**Files Modified:**
- `src/github_archive/phase2_process_files/utils/gcs_client.py` - Changed return type to `tuple[str, FileMetadata]`
- `src/github_archive/phase2_process_files/processors/file_processor.py` - Unpack tuple
- `src/github_archive/phase2_process_files/processors/file_splitter.py` - Unpack tuple

**Key Takeaway:**
When a function modifies a file path (like decompression changing `.gz` to no suffix), it MUST return the new path to the caller. Python passes strings by value, not reference - modifying a local variable doesn't affect the caller's variable.

---

## Error 14: File Validation Failed - Single-Digit Hours in Filename

**Error Message:**
```
File validation failed: File name must match format YYYY-MM-DD-HH.json.gz, got: 2026-03-07-1.json.gz
```

**Cloud Run Logs:**
```json
{
  "error": "File validation failed: File name must match format YYYY-MM-DD-HH.json.gz, got: 2026-03-07-1.json.gz",
  "file_name": "2026-03-07-1.json.gz"
}
```

**Root Cause:**
The file validation regex expected exactly 2 digits for the hour (`\d{2}`), but GitHub Archive files use **single-digit hours for hours 0-9** (not zero-padded).

Files like `2026-03-07-1.json.gz` (1 AM) were rejected while `2026-03-07-12.json.gz` (12 PM) were accepted.

**Fix:**

**1. Update the regex pattern in `validators/file_validator.py`:**
```python
# ❌ Before - requires exactly 2 digits
FILE_NAME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}-\d{2})\.json\.gz$')

# ✅ After - accepts 1 or 2 digits for hour
# GitHub Archive uses single-digit hours (0-9) for hours 0-9, not zero-padded
FILE_NAME_PATTERN = re.compile(r'^(\d{4}-\d{2}-\d{2}-\d{1,2})\.json\.gz$')
```

**2. Update output filename generation in `writers/ndjson_writer.py`:**
```python
# ❌ Before - zero-pads hour to 2 digits
filename = f"{date_str}-{hour:02d}"

# ✅ After - hour is NOT zero-padded to match GitHub Archive format
filename = f"{date_str}-{hour}"
```

**Key Point:**
GitHub Archive filename format is `YYYY-MM-DD-H.json.gz` where `H` is:
- Single digit (0-9) for hours 0-9
- Double digit (10-23) for hours 10-23

**Verification:**
```bash
# Test files should pass validation
2026-03-07-0.json.gz  # ✅ Valid (midnight)
2026-03-07-1.json.gz  # ✅ Valid (1 AM)
2026-03-07-9.json.gz  # ✅ Valid (9 AM)
2026-03-07-10.json.gz # ✅ Valid (10 AM)
2026-03-07-23.json.gz # ✅ Valid (11 PM)
```

---

## Error 15: 403 Permission Denied - Staging Bucket Read Access

**Error Message:**
```
Processing failed: ('Request failed with status code', 403, 'Expected one of', <HTTPStatus.OK: 200>, <HTTPStatus.PERMANENT_REDIRECT: 308>)
```

**Cloud Run Logs:**
```json
{
  "error": "Processing failed: 403 GET https://storage.googleapis.com/storage/v1/b/dev-dataprocessing-489305-dev-github-archive-staging/o/processed%2F2026-03-07-02.ndjson.gz?projection=noAcl&prettyPrint=false: dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com does not have storage.objects.get access to the Google Cloud Storage object.",
  "file_name": "2026-03-07-02.json.gz"
}
```

**Root Cause:**
The processor service account only had `roles/storage.objectCreator` on the staging bucket, which allows creating objects but **NOT reading them**.

When the code tries to:
1. Check if an output file already exists before writing
2. Read temporary files during processing
3. List processed files

These operations fail with 403 because `storage.objects.get` permission is missing.

**Fix:**
Add `roles/storage.objectViewer` to the staging bucket for the processor service account.

**In Terraform Layer 01 (`terraform/layers/01_static/main.tf`):**
```hcl
# Processor SA: Write to staging bucket
resource "google_storage_bucket_iam_member" "processor_staging_write" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectCreator"
  member = "serviceAccount:${google_service_account.processor.email}"
}

# Processor SA: Read from staging bucket (to check if files exist, read temp files)
resource "google_storage_bucket_iam_member" "processor_staging_read" {
  bucket = google_storage_bucket.staging.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.processor.email}"
}
```

**IAM Permissions Summary:**
| Role | Permissions | Use Case |
|------|-------------|----------|
| `roles/storage.objectCreator` | storage.objects.create, storage.objects.delete | Write new files |
| `roles/storage.objectViewer` | storage.objects.get, storage.objects.list | Read/list existing files |
| `roles/storage.objectAdmin` | All above | Full control (simpler but less secure) |

**Apply the fix:**
```bash
cd infrastructure/phase2_process_files/terraform/layers/01_static
terraform apply -var="project_id=PROJECT_ID" -var="region=us-central1" -var="environment=dev" -var="landing_bucket_name=LANDING_BUCKET"
```

**Verification:**
```bash
# Check service account permissions on bucket
gsutil iam get gs://STAGING_BUCKET | grep PROCESSOR_SA_EMAIL

# Should show both roles:
# - roles/storage.objectCreator
# - roles/storage.objectViewer
```

---

## Summary of Phase 2 Processing Issues (2026-03-07)

| Issue | Root Cause | Fix Location |
|-------|------------|--------------|
| Single-digit hour validation | Regex required `\d{2}` instead of `\d{1,2}` | `validators/file_validator.py` |
| Output filename zero-padding | Format string used `{hour:02d}` | `writers/ndjson_writer.py` |
| 403 on staging bucket read | Missing `storage.objectViewer` role | `terraform/layers/01_static/main.tf` |
| Duplicate message delivery | Pub/Sub ack deadline too short (10s) | Manual `gcloud pubsub subscriptions update` |

**Key Learning:**
GitHub Archive uses a **non-zero-padded hour format** (`H` not `HH`). All processing code must handle hours 0-9 as single digits (0-9), not zero-padded (00-09).

---

## Error 16: Eventarc Pub/Sub Ack Deadline Too Short - Duplicate Message Delivery

**Error Message:**
```
Cloud Run processing the same file multiple times
```

**Root Cause:**
Eventarc uses Pub/Sub as the transport layer with a default **acknowledgement deadline of 10 seconds**. When the Cloud Run handler takes longer than 10 seconds to respond (synchronous processing), Pub/Sub considers the message undelivered and **redelivers it**, causing duplicate processing.

**How Eventarc Pub/Sub Delivery Works:**
```
Pub/Sub → Eventarc → Cloud Run HTTP Request
                    ↓
                    [Processing starts... can take minutes!]
                    ↓
                 10 seconds pass
                    ↓
              Pub/Sub: "No response? Redeliver!"
                    ↓
              [New request comes in for same file]
                    ↓
              Duplicate processing! ❌
```

**Verification:**
```bash
# Check the Pub/Sub subscription ack deadline
gcloud pubsub subscriptions describe eventarc-us-central1-dev-github-archive-storage-sub-097 \
  --project=dev-dataprocessing-489305 \
  --format="json(ackDeadlineSeconds)"
```

**Default Output:**
```json
{
  "ackDeadlineSeconds": 10  # ❌ Too short for file processing
}
```

**Fix:**
Increase the acknowledgement deadline to the maximum value of **600 seconds (10 minutes)**:

```bash
# Get the subscription ID from the Eventarc trigger
SUBSCRIPTION_ID=$(gcloud eventarc triggers describe "dev-github-archive-storage" \
  --location us-central1 \
  --project=dev-dataprocessing-489305 \
  --format json | jq -r '.transport.pubsub.subscription')

# Update the ack deadline to 600 seconds
gcloud pubsub subscriptions update "$SUBSCRIPTION_ID" \
  --ack-deadline=600 \
  --project=dev-dataprocessing-489305
```

**After Fix:**
```json
{
  "ackDeadlineSeconds": 600  # ✅ Gives Cloud Run 10 minutes to respond
}
```

**Important Notes:**

1. **This change is NOT managed by Terraform** - If you destroy and recreate the Eventarc trigger, the ack deadline will reset to 10 seconds.

2. **For automated deployments**, add a post-deployment step or Terraform `local-exec` provisioner to update the deadline:

```hcl
# In your Terraform configuration or deployment script
resource "null_resource" "update_eventarc_ack_deadline" {
  depends_on = [google_eventarc_trigger.storage_trigger]

  provisioner "local-exec" {
    command = <<-EOT
      SUBSCRIPTION_ID=$(gcloud eventarc triggers describe "${var.trigger_name}" \
        --location ${var.region} \
        --project ${var.project_id} \
        --format json | jq -r '.transport.pubsub.subscription')
      gcloud pubsub subscriptions update "$SUBSCRIPTION_ID" --ack-deadline=600
    EOT
  }
}
```

3. **Maximum ack deadline is 600 seconds** - This is a Pub/Sub limit.

4. **For long-running processing (>10 minutes)**, consider making your handler async:
   - Accept the HTTP request immediately (return 200 OK)
   - Queue the file for background processing (Cloud Tasks, Pub/Sub)
   - This acknowledges the Pub/Sub message right away

**Reference:**
[Google Cloud Run Docs - Set the Pub/Sub acknowledgement deadline](https://cloud.google.com/run/docs/triggering/trigger-with-events#ack_deadline)

---

## Error 17: Eventarc Trigger - 403 Unauthenticated Requests to Cloud Run

**Error Message:**
```
The request was not authenticated. Either allow unauthenticated invocations
or set the proper Authorization header.
```

**Cloud Run Logs:**
```yaml
httpRequest:
  status: 403
  requestMethod: POST
  requestUrl: https://SERVICE-URL/?__GCP_CloudEventsMode=GCS_NOTIFICATION
  userAgent: APIs-Google; (+https://developers.google.com/webmasters/APIs-Google.html)
severity: WARNING
textPayload: 'The request was not authenticated...'
```

**Eventarc Trigger Configuration:**
```bash
$ gcloud eventarc triggers describe dev-github-archive-storage --location=us-central1
serviceAccount: dev-eventarc-invoker@PROJECT_ID.iam.gserviceaccount.com
destination:
  cloudRun:
    service: dev-github-archive-processor
```

**Root Cause:**
The Eventarc trigger's service account has `roles/eventarc.eventReceiver` (to receive events) but **is missing `roles/run.invoker`** on the target Cloud Run service. Without this role, the Eventarc trigger cannot authenticate to invoke the Cloud Run service, resulting in 403 errors.

According to Google's documentation:

> If you create a trigger for an authenticated Cloud Run service without granting the Cloud Run Invoker role, the trigger won't work as expected and a message similar to the following appears in the logs: **"The request was not authenticated."**

**IAM Permission Check:**
```bash
# Check Cloud Run service IAM policy - should be empty or missing the invoker SA
$ gcloud run services get-iam-policy dev-github-archive-processor --region=us-central1
{
  "etag": "BwZMatS840Y="
}
# ❌ No bindings = no one can invoke except project owners/admins
```

**Fix:**

**Option A: Grant via gcloud (immediate fix)**
```bash
gcloud run services add-iam-policy-binding dev-github-archive-processor \
  --region=us-central1 \
  --member="serviceAccount:dev-eventarc-invoker@PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

**Option B: Add to Terraform**
```hcl
# Grant Cloud Run Invoker role to Eventarc service account
resource "google_cloud_run_service_iam_member" "eventarc_invoker" {
  location = google_cloud_run_v2_service.processor.location
  project  = google_cloud_run_v2_service.processor.project
  service  = google_cloud_run_v2_service.processor.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.eventarc_invoker.email}"
}
```

**Required IAM Roles for Eventarc → Cloud Run:**

| Service Account | Role | Scope | Purpose |
|----------------|------|-------|---------|
| `dev-eventarc-invoker@...` | `roles/eventarc.eventReceiver` | Project | Receive events from event providers |
| `dev-eventarc-invoker@...` | `roles/run.invoker` | Cloud Run Service | Invoke the target Cloud Run service |
| `service-PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com` | `roles/iam.serviceAccountTokenCreator` | Project | Generate OIDC tokens for authenticated push |

**Key Points:**

1. **Cloud Run services are private by default** - Only users/service accounts with `run.invoker` can invoke them
2. **Eventarc triggers are created successfully without `run.invoker`** - The trigger shows as "Active" but silently fails with 403
3. **Grant at service level, not project level** - More secure to grant `run.invoker` on specific services rather than project-wide
4. **Cross-project triggers** - If Eventarc is in a different project than Cloud Run, grant `run.invoker` on the Cloud Run service in the target project

**Verification:**
```bash
# 1. Verify the service account has run.invoker
gcloud run services get-iam-policy SERVICE_NAME \
  --region=us-central1 \
  --format="json(bindings)" | jq '.bindings[] | select(.role=="roles/run.invoker")'

# 2. Check Eventarc trigger is using the service account
gcloud eventarc triggers describe TRIGGER_NAME \
  --location=us-central1 \
  --format="value(serviceAccount)"

# 3. Test by uploading a file to the bucket and monitoring logs
gsutil cp test.json.gz gs://LANDING_BUCKET/
gcloud logging tail "resource.type=cloud_run_revision" --filter="resource.labels.service_name=SERVICE_NAME"
```

**Reference:**
[Eventarc Docs - Grant Cloud Run service permissions](https://cloud.google.com/eventarc/docs/roles-permissions#invoker-role)
