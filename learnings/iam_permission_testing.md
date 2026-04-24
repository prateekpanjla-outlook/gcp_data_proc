# IAM Permission Testing - Learnings

This document captures learnings about testing IAM permissions in Google Cloud.

## Testing IAM Permissions

### Why Test IAM Permissions?

Before deploying infrastructure with Terraform, it's important to verify that the service account performing the deployment has the required permissions. This prevents deployment failures mid-way through resource creation.

### Methods for Testing IAM Permissions

#### Method 1: `gcloud policy-troubleshoot iam` (Recommended)

**Purpose**: Check if a principal has a specific permission on a resource and explains why (includes policy evaluation).

**Required API**: `policytroubleshooter.googleapis.com`

**Enable the API**:
```bash
gcloud services enable policytroubleshooter.googleapis.com --project=PROJECT_ID
```

**Important**: To test permissions **as the service account**, you must impersonate it. BOTH flags are required:

```bash
# Single command - must specify BOTH --principal-email AND --impersonate-service-account
gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID \
  --permission="iam.serviceAccounts.create" \
  --principal-email="dev-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com" \
  --impersonate-service-account="dev-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com"

# Option 2: Set impersonation first (still need --principal-email)
gcloud config set auth/impersonate_service_account dev-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com
gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID \
  --permission="iam.serviceAccounts.create" \
  --principal-email="dev-terraform-deployer@PROJECT_ID.iam.gserviceaccount.com"
gcloud config unset auth/impersonate_service_account
```

**What each flag does**:
- `--principal-email` = Which principal's permissions to CHECK (required)
- `--impersonate-service-account` = Which principal's CREDENTIALS to use for the API call (optional but recommended for accuracy)

**Example**:
```bash
gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/dev-dataprocessing-489305 \
  --permission="iam.serviceAccounts.create" \
  --principal-email="dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com" \
  --impersonate-service-account="dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com"
```

**Expected Output (if granted)**:
```
---
policies:
- bindings:
  - role: roles/iam.serviceAccountAdmin
    members:
    - serviceAccount:dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com
...
overallAccess: GRANTED
```

**Common Permissions to Test**:

| Permission | Resource | Purpose |
|------------|----------|---------|
| `iam.serviceAccounts.create` | Project | Verify SA can create service accounts |
| `storage.buckets.create` | Project | Verify SA can create GCS buckets |
| `run.jobs.create` | Project | Verify SA can create Cloud Run Jobs |
| `cloudscheduler.jobs.create` | Project | Verify SA can create Scheduler jobs |
| `resourcemanager.projects.setIamPolicy` | Project | Verify SA can set IAM policies |

---

#### Method 2: Check Granted Roles (Simpler, No Extra API)

**Purpose**: View all roles granted to a service account.

**Required API**: None (uses Cloud Resource Manager API)

**Usage**:
```bash
gcloud projects get-iam-policy PROJECT_ID \
  --format="flattened(bindings)" \
  --filter="bindings.member:serviceAccount:SA_EMAIL"
```

**Example**:
```bash
gcloud projects get-iam-policy dev-dataprocessing-489305 \
  --format="flattened(bindings)" \
  --filter="bindings.member:serviceAccount:dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com"
```

**Output**:
```
bindings.role: roles/iam.serviceAccountAdmin
bindings.member: serviceAccount:dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com
bindings.role: roles/editor
bindings.member: serviceAccount:dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com
```

---

#### Method 3: Actual Test (Creates Real Resource)

**Purpose**: Perform a real test by creating a resource.

**Warning**: This actually creates resources. Use only in test environments.

**Usage**:
```bash
# Impersonate the service account
gcloud config set auth/impersonate_service_account SA_EMAIL

# Try to create a test resource
gcloud iam service-accounts create test-sa-verify-$(date +%s) \
  --display-name="Test SA - delete me" \
  --project=PROJECT_ID

# If successful, verify and delete
gcloud iam service-accounts delete test-sa-verify-XXX@PROJECT_ID.iam.gserviceaccount.com \
  --project=PROJECT_ID --quiet

# Reset impersonation
gcloud config unset auth/impersonate_service_account
```

---

## Policy Troubleshooter API

### Required to Enable

The Policy Troubleshooter API must be enabled before using `gcloud policy-troubleshoot iam`:

```bash
gcloud services enable policytroubleshooter.googleapis.com --project=PROJECT_ID
```

### Cost

**Free to use** - The Policy Troubleshooter API does not incur direct costs. However, standard network egress charges may apply if you exceed the free tier.

### IAM Role Required to Enable the API

To enable APIs, you need:
- **Role**: `roles/serviceusage.serviceUsageAdmin`
- **Permission**: `serviceusage.services.enable`

---

## Quick Reference: Permission Testing

| Scenario | Command |
|----------|---------|
| Test SA creation permission | `gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID --principal-email="SA_EMAIL" --permission="iam.serviceAccounts.create"` |
| Test GCS bucket creation | `gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID --principal-email="SA_EMAIL" --permission="storage.buckets.create"` |
| Test Cloud Run Job creation | `gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID --principal-email="SA_EMAIL" --permission="run.jobs.create"` |
| Test Scheduler job creation | `gcloud policy-troubleshoot iam //cloudresourcemanager.googleapis.com/projects/PROJECT_ID --principal-email="SA_EMAIL" --permission="cloudscheduler.jobs.create"` |
| Check all roles for SA | `gcloud projects get-iam-policy PROJECT_ID --filter="bindings.member:serviceAccount:SA_EMAIL"` |

---

## References

- [Policy Troubleshooter Overview](https://cloud.google.com/policy-intelligence/docs/troubleshoot-access)
- [IAM Permissions Reference](https://cloud.google.com/iam/docs/permissions-reference)
- [gcloud policy-troubleshoot iam](https://cloud.google.com/sdk/gcloud/reference/policy-troubleshoot/iam)
