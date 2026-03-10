# How Does the Deployer Account Get Project Permissions?

## The Short Answer

The Terraform deployer service account gets permissions through **IAM policy bindings** at the **project level**. When we ran the `gcloud projects add-iam-policy-binding` commands, we were modifying your project's IAM policy to grant roles to the service account.

## IAM Policy Structure

Your GCP project's IAM policy looks like this:

```json
{
  "bindings": [
    {
      "role": "roles/storage.admin",
      "members": [
        "serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"
      ]
    },
    {
      "role": "roles/bigquery.admin",
      "members": [
        "serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com"
      ]
    },
    {
      "role": "roles/owner",
      "members": [
        "user:prateek.panjla.outlook@gmail.com"
      ]
    }
  ],
  "etag": "BwZMssre-M4=",
  "version": 1
}
```

## How Permissions Are Granted

### Step 1: Someone with Permission Adds the Binding

```bash
# Your personal account (prateek.panjla.outlook@gmail.com) has roles/owner
# You use gcloud to add IAM policy bindings

gcloud projects add-iam-policy-binding beaming-glyph-489707-b8 \
  --member="serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com" \
  --role="roles/storage.admin"
```

**What happens behind the scenes:**
1. gcloud calls the Cloud Resource Manager API
2. API verifies YOUR account has permission to modify IAM policies
3. API updates the project's IAM policy
4. The service account is now granted the role on the project

### Step 2: The Service Account Inherits Permissions

The service account doesn't "own" the permissions. Instead:

```
Project IAM Policy
├── Binding: roles/storage.admin
│   └── Member: serviceAccount:test-terraform-deployer@...
│       └── "When this SA acts, it has storage.admin permissions"
│
└── Binding: roles/owner
    └── Member: user:prateek.panjla.outlook@gmail.com
        └── "When this user acts, they have owner permissions"
```

## Key Concepts

### 1. IAM Policies Live on Resources

```
Resource: beaming-glyph-489707-b8 (project)
└── IAM Policy: Defines who can do what
    ├── Role: roles/storage.admin
    │   └── Member: serviceAccount:test-terraform-deployer@...
    ├── Role: roles/bigquery.admin
    │   └── Member: serviceAccount:test-terraform-deployer@...
    └── ... (more roles)
```

### 2. Service Accounts Are Identities, Not Permission Containers

Service accounts are **identities** that can authenticate to Google Cloud. They don't have permissions until granted:

```
Service Account (Identity)
├── Email: test-terraform-deployer@...
├── Keys: test-terraform-deployer-key.json
└── Permissions: NONE (until granted via IAM policies)
```

### 3. Roles Grant Permissions on Resources

When you grant a role to a service account on a project:

```
Grant: roles/storage.admin TO serviceAccount:test-terraform-deployer
ON resource: projects/beaming-glyph-489707-b8

Result:
- When test-terraform-deployer acts on beaming-glyph-489707-b8
- It has all permissions in roles/storage.admin
- These permissions apply to ALL resources in the project
  - All GCS buckets in the project
  - All BigQuery datasets in the project
  - All Cloud Run resources in the project
  - etc.
```

## Permission Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Your Personal Account (Owner)                             │
│    prateek.panjla.outlook@gmail.com                          │
│    Has: roles/owner on project                               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ gcloud projects add-iam-policy-binding
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. GCP Cloud Resource Manager API                            │
│    - Verifies your account has permission to modify IAM       │
│    - Updates project's IAM policy                            │
│    - Adds binding: SA -> role                                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Policy updated
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Project IAM Policy                                       │
│    beaming-glyph-489707-b8                                   │
│    {                                                         │
│      bindings: [                                            │
│        {                                                    │
│          role: "roles/storage.admin",                      │
│          members: ["serviceAccount:test-terraform-deployer"]│
│        }                                                    │
│      ]                                                      │
│    }                                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ Permissions inherited
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Service Account Can Now Act                              │
│    test-terraform-deployer@...                               │
│    When authenticated via key file:                         │
│    - Can create/manage GCS buckets (storage.admin)          │
│    - Can create/manage BigQuery datasets (bigquery.admin)   │
│    - Can deploy Cloud Run services (run.admin)              │
│    - etc.                                                   │
└─────────────────────────────────────────────────────────────┘
```

## What Happens During Authentication

### Using the Key File

```bash
# Set environment variable
export GOOGLE_APPLICATION_CREDENTIALS=test-terraform-deployer-key.json

# Run Terraform
terraform apply

# What happens:
# 1. Terraform reads the key file
# 2. Authenticates as test-terraform-deployer@...
# 3. Makes API calls to GCP
# 4. GCP checks: "Does this SA have permission for this action?"
# 5. Looks up project IAM policy
# 6. Checks if SA has role that grants this permission
# 7. Allows or denies the action
```

### Permission Check Example

```
Action: Create GCS bucket
Actor: test-terraform-deployer@... (authenticated via key)
Resource: projects/beaming-glyph-489707-b8

GCP Permission Check:
1. What permission is needed? storage.buckets.create
2. Which roles grant this permission? roles/storage.admin (and others)
3. Does the SA have this role on the project?
   → Check project IAM policy
   → Found: roles/storage.admin includes test-terraform-deployer
4. Result: ALLOWED ✅
```

## Important Distinctions

### Service Account vs. IAM Policy

| Aspect | Service Account | IAM Policy |
|--------|----------------|------------|
| **What is it?** | An identity that can authenticate | Rules about who can do what |
| **Where does it live?** | Global (exists outside projects) | On resources (projects, buckets, etc.) |
| **What does it contain?** | Keys, email, display name | Bindings (role + member) |
| **Can it have permissions?** | No, permissions come from IAM policies | Yes, it grants permissions |

### Member vs. Role

| Concept | Member | Role |
|---------|--------|------|
| **Definition** | WHO gets permission | WHAT permission they get |
| **Examples** | user:email@example.com | roles/storage.admin |
| | serviceAccount:sa@... | roles/bigquery.admin |
| | | |
| **Analogy** | Employee | Job title |

## How the Setup Script Grants Permissions

```bash
# The setup script ran commands like this:

gcloud projects add-iam-policy-binding beaming-glyph-489707-b8 \
  --member="serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# This command:
# 1. Uses YOUR authenticated account (prateek.panjla.outlook@gmail.com)
# 2. Calls the Cloud Resource Manager API
# 3. Modifies the IAM policy of project beaming-glyph-489707-b8
# 4. Adds a binding that grants the role to the SA
```

## Verification

You can see all the bindings for your deployer SA:

```bash
# Get full IAM policy
gcloud projects get-iam-policy beaming-glyph-489707-b8

# Filter for your SA
gcloud projects get-iam-policy beaming-glyph-489707-b8 \
  --filter="bindings.member:serviceAccount:test-terraform-deployer@beaming-glyph-489707-b8.iam.gserviceaccount.com" \
  --format='table(bindings.role)'
```

## Summary

1. **Your personal account** (with owner role) grants permissions to the SA
2. **IAM policy bindings** are added to the project
3. **The SA inherits permissions** from these bindings when it acts
4. **Authentication** (via key file) proves the SA is making the request
5. **GCP checks permissions** for each API call based on the IAM policy

**The SA doesn't "have" permissions - the project's IAM policy grants them when the SA acts!**
