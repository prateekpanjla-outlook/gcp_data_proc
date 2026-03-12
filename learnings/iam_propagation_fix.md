# IAM Propagation Race Condition Fix

Date: 2026-03-13

## Problem

During `terraform apply` of Phase 1, the Cloud Build step (`null_resource.build_downloader_image`)
failed with:

```
test-cloud-build@beaming-glyph-489707-b8.iam.gserviceaccount.com does not have
storage.objects.get access to the Google Cloud Storage object.
Permission 'storage.objects.get' denied on resource (or it may not exist).
```

## Root Cause

**IAM eventual consistency.** GCP IAM has two layers:

1. **Control plane** — records the policy (bindings, roles). API calls to
   `setIamPolicy`/`getIamPolicy` return immediately.
2. **Enforcement layer** — actually checks permissions on API calls. This layer
   is **eventually consistent** and can lag behind the control plane by up to 60 seconds.

Terraform's `depends_on` only waits for the control plane API call to return,
not for the enforcement layer to propagate. So the sequence was:

```
1. Terraform creates test-cloud-build SA                    (0s)
2. Terraform adds roles/cloudbuild.builds.builder binding   (2s)
3. Terraform triggers gcloud builds submit                  (3s)  <-- IAM not enforced yet
4. Cloud Build tries to read source tarball as test-cloud-build SA
5. Enforcement layer hasn't propagated → 403 DENIED
```

## Investigation

We verified that `roles/cloudbuild.builds.builder` **does** include `storage.objects.get`:

```bash
gcloud iam roles describe roles/cloudbuild.builds.builder --format="yaml(includedPermissions)"
# Includes: storage.objects.get, storage.objects.create, storage.objects.delete,
#           storage.objects.list, storage.objects.update, storage.buckets.get/list/create
```

The original comment in `cloudbuild_sa.tf` was correct — the role includes storage permissions.

## Key Discovery: testIamPermissions API

The `testIamPermissions` API tests against the **enforcement layer**, not the control plane.
If it returns the permission, it is actually enforceable:

```bash
curl -H "Authorization: Bearer $(gcloud auth print-access-token --impersonate-service-account=SA)" \
  "https://storage.googleapis.com/storage/v1/b/BUCKET/iam/testPermissions?permissions=storage.objects.get"

# Response (only if enforcement has propagated):
# { "permissions": ["storage.objects.get"] }
```

This is the only reliable way to confirm IAM propagation without trying the actual operation.

## Fix Applied

**File:** `infrastructure/github_archive/phase1_ingestion/terraform/build.tf`

### 1. Added `wait_for_iam_propagation` resource

A new `null_resource` that polls `testIamPermissions` every 10 seconds (up to 120s)
to confirm the build SA has `storage.objects.get` on the `_cloudbuild` bucket
before the build step runs.

```hcl
resource "null_resource" "wait_for_iam_propagation" {
  depends_on = [google_project_iam_member.cloudbuild_sa_roles]

  provisioner "local-exec" {
    # PowerShell: poll testIamPermissions API until storage.objects.get is confirmed
    # Uses gcloud auth print-access-token --impersonate-service-account to test as the build SA
    # Max 12 attempts × 10s = 120s timeout
  }
}
```

### 2. Updated `build_downloader_image` dependency chain

```
Before: cloudbuild_sa_roles → build_downloader_image  (race condition)
After:  cloudbuild_sa_roles → wait_for_iam_propagation → build_downloader_image  (safe)
```

### 3. Fixed `gcloud auth activate-service-account` error handling

The original command used `;` (PowerShell separator) which runs the next command
regardless of failure. Changed to check `$LASTEXITCODE` so the build step
stops if authentication fails:

```
Before: gcloud auth activate-service-account ...; gcloud builds submit ...
After:  gcloud auth activate-service-account ...; if ($LASTEXITCODE -ne 0) { exit 1 }; gcloud builds submit ...
```

### 4. Removed redundant `gcloud auth activate-service-account` from IAM check

The IAM propagation check uses `--impersonate-service-account` which doesn't
require switching the active gcloud account.

## Secondary Issue

The first `gcloud auth activate-service-account` also timed out:

```
HTTPSConnectionPool(host='oauth2.googleapis.com', port=443):
Max retries exceeded with url: /token (connect timeout=120)
```

This was a transient network issue. The `;` separator meant the build submission
ran anyway with whatever auth was already active, leading to the confusing error chain.

## Lessons

1. **GCP IAM is eventually consistent.** Never assume permissions are enforced
   immediately after the binding API call returns.
2. **`testIamPermissions` tests enforcement, not policy.** Use it to reliably
   check if permissions have actually propagated.
3. **`depends_on` is not enough** for IAM-dependent operations. Add an explicit
   propagation check or `time_sleep` between IAM bindings and resources that use them.
4. **Use proper error handling in `local-exec`.** In PowerShell, `;` runs the
   next command regardless of the previous exit code. Check `$LASTEXITCODE` explicitly.
