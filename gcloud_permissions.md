# Project Resource Inventory: dev-dataprocessing-489305

**Generated:** 2026-03-09
**Project Number:** 973986259857

---

## Resources Created

| Resource Type | Name | Details |
|--------------|------|---------|
| **Cloud Run** | dev-github-archive-processor | us-central1 |
| **Cloud Run** | dev-bq-loader | us-central1 |
| **GCS Bucket** | dev-dataprocessing-489305-dev-github-archive-landing | Landing zone |
| **GCS Bucket** | dev-dataprocessing-489305-dev-github-archive-staging | Staging zone |
| **GCS Bucket** | dev-dataprocessing-489305-dev-gcf-source | Cloud Functions source |
| **GCS Bucket** | dev-dataprocessing-489305_cloudbuild | Cloud Build artifacts |
| **GCS Bucket** | gcf-v2-sources-973986259857-us-central1 | GCF v2 sources |
| **BigQuery** | github_archive | Main dataset |
| **BigQuery** | github_archive_test | Test dataset |
| **BigQuery** | local_testing | Local testing |
| **Pub/Sub** | eventarc-us-central1-dev-github-archive-storage-895 | Eventarc topic |
| **Pub/Sub** | eventarc-us-central1-dev-bq-loader-199448-109 | Eventarc topic |
| **Eventarc** | dev-github-archive-storage | → dev-github-archive-processor |
| **Eventarc** | dev-bq-loader-199448 | → dev-bq-loader (Cloud Function) |

---

## Service Accounts (Custom)

| Service Account | Purpose |
|----------------|---------|
| dev-terraform-deployer | Infrastructure deployment |
| dev-github-archive-processor | Process GitHub archive files |
| dev-github-archive-downloader | Download GitHub archive |
| dev-file-splitter | Split large files |
| dev-bq-loader | Load data to BigQuery |
| dev-eventarc-invoker | Invoke Cloud Run via Eventarc |
| dev-eventarc-invoker-bq | Invoke BQ loader via Eventarc |
| dev-scheduler | Cloud Scheduler service |

---

## Resource-Level IAM Policies

### GCS Bucket: dev-github-archive-landing

| Role | Members |
|------|---------|
| storage.objectCreator | dev-file-splitter, dev-github-archive-processor |
| storage.objectViewer | dev-file-splitter, dev-github-archive-processor |

### GCS Bucket: dev-github-archive-staging

| Role | Members |
|------|---------|
| storage.objectAdmin | dev-bq-loader, dev-github-archive-processor |
| storage.objectCreator | dev-github-archive-processor |
| storage.objectViewer | dev-bq-loader, dev-github-archive-processor, eventarc service agent |

### BigQuery Dataset: github_archive

| Role | Members |
|------|---------|
| WRITER | dev-bq-loader |
| OWNER | dev-terraform-deployer |

### Cloud Run: dev-github-archive-processor

| Role | Members |
|------|---------|
| run.invoker | dev-eventarc-invoker |

---

## Service Account IAM Bindings (actAs)

| Service Account | Who Can Act As |
|-----------------|----------------|
| dev-terraform-deployer | user:prateek.panjla.outlook@gmail.com |
| dev-github-archive-processor | dev-terraform-deployer, serverless-robot-prod |
| dev-eventarc-invoker-bq | dev-terraform-deployer |
| dev-bq-loader | dev-terraform-deployer |

---

## Default Service Account Permissions

### Standard Default Service Accounts

| Default SA | Role | Status |
|------------|------|--------|
| 973986259857-compute@developer.gserviceaccount.com | roles/artifactregistry.reader | Standard |
| | roles/cloudbuild.builds.builder | Standard |
| | **roles/storage.objectAdmin** | ⚠️ **EXTRA** - Broader than default |
| 973986259857@cloudservices.gserviceaccount.com | roles/editor | Standard |
| 973986259857@cloudbuild.gserviceaccount.com | roles/cloudbuild.builds.builder | Standard |
| service-973986259857@gs-project-accounts.iam.gserviceaccount.com | roles/pubsub.publisher | For Eventarc |

### Google-Managed Service Agents (Auto-created)

| Service Agent | Role | Purpose |
|---------------|------|---------|
| service-973986259857@gcp-sa-artifactregistry.iam.gserviceaccount.com | artifactregistry.serviceAgent | Artifact Registry |
| service-973986259857@gcp-sa-cloudbuild.iam.gserviceaccount.com | cloudbuild.serviceAgent | Cloud Build |
| service-973986259857@gcp-sa-cloudscheduler.iam.gserviceaccount.com | cloudscheduler.serviceAgent | Cloud Scheduler |
| service-973986259857@gcp-sa-eventarc.iam.gserviceaccount.com | eventarc.serviceAgent, eventarc.eventReceiver | Eventarc |
| service-973986259857@gcp-sa-pubsub.iam.gserviceaccount.com | pubsub.serviceAgent, iam.serviceAccountTokenCreator | Pub/Sub |
| service-973986259857@serverless-robot-prod.iam.gserviceaccount.com | run.serviceAgent | Cloud Run |
| service-973986259857@gcf-admin-robot.iam.gserviceaccount.com | cloudfunctions.serviceAgent | Cloud Functions |

---

## All Service Accounts in dev-dataprocessing-489305

### Custom (Manually Created) Service Accounts - 9 accounts

| Email | Display Name | Purpose |
|-------|--------------|---------|
| `dev-terraform-deployer@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev Terraform Deployer | Infrastructure deployment |
| `dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev GitHub Archive Processor | Process GitHub archive files |
| `dev-github-archive-downloader@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev GitHub Archive Downloader | Download GitHub archive |
| `dev-file-splitter@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev File Splitter | Split large files |
| `dev-bq-loader@dev-dataprocessing-489305.iam.gserviceaccount.com` | dev BigQuery Loader | Load data to BigQuery |
| `dev-eventarc-invoker@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev Eventarc Invoker | Invoke Cloud Run via Eventarc |
| `dev-eventarc-invoker-bq@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev Eventarc Invoker (BQ) | Invoke BQ loader via Eventarc |
| `dev-scheduler@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev Cloud Scheduler Service Account | Cloud Scheduler |
| `dev-cloud-build@dev-dataprocessing-489305.iam.gserviceaccount.com` | Dev Cloud Build | Cloud Build operations |

---

### Default Service Accounts - 4 accounts

| Email | Type | Auto-created By |
|-------|------|-----------------|
| `973986259857-compute@developer.gserviceaccount.com` | Compute Engine Default | GCP (when Compute API enabled) |
| `dev-dataprocessing-489305@appspot.gserviceaccount.com` | App Engine Default | GCP (when App Engine enabled) |
| `973986259857@cloudservices.gserviceaccount.com` | Cloud Services | GCP (for deployment operations) |
| `973986259857@cloudbuild.gserviceaccount.com` | Cloud Build Default | GCP (when Cloud Build API enabled) |

---

### Google-Managed Service Agents - 10 accounts

| Email | Service | Auto-managed |
|-------|---------|--------------|
| `service-973986259857@gcp-sa-artifactregistry.iam.gserviceaccount.com` | Artifact Registry | Yes |
| `service-973986259857@gcp-sa-cloudbuild.iam.gserviceaccount.com` | Cloud Build | Yes |
| `service-973986259857@gcp-sa-cloudscheduler.iam.gserviceaccount.com` | Cloud Scheduler | Yes |
| `service-973986259857@gcp-sa-eventarc.iam.gserviceaccount.com` | Eventarc | Yes |
| `service-973986259857@gcp-sa-pubsub.iam.gserviceaccount.com` | Pub/Sub | Yes |
| `service-973986259857@gcp-sa-cloudaicompanion.iam.gserviceaccount.com` | Cloud AI Companion | Yes |
| `service-973986259857@serverless-robot-prod.iam.gserviceaccount.com` | Cloud Run | Yes |
| `service-973986259857@gcf-admin-robot.iam.gserviceaccount.com` | Cloud Functions | Yes |
| `service-973986259857@containerregistry.iam.gserviceaccount.com` | Container Registry | Yes |
| `service-973986259857@gs-project-accounts.iam.gserviceaccount.com` | Cloud Storage (GCS) | Yes |

---

### Deleted Service Accounts (still in IAM) - 3 accounts

| Email | Status |
|-------|--------|
| `deleted:dev-eventarc-invoker@...?uid=108338824707140647281` | Deleted - needs IAM cleanup |
| `deleted:dev-github-archive-processor@...?uid=103406792061115802934` | Deleted - needs IAM cleanup |
| `deleted:github-archive-downloader@...?uid=117444929755612015046` | Deleted - needs IAM cleanup |

> Note: These deleted accounts still appear in IAM policies and should be cleaned up.

---

## Cloud Build Service Account (`dev-cloud-build`)

### Purpose
Dedicated service account for Cloud Build operations - deploying Cloud Functions 2nd gen and Cloud Run services.

### Permissions Granted

| Role | Scope | Why Required |
|------|-------|--------------|
| `roles/cloudbuild.builds.builder` | Project | Execute Cloud Build jobs, create builds |
| `roles/artifactregistry.writer` | Project | Push container images to Artifact Registry |
| `roles/logging.logWriter` | Project | Write build logs to Cloud Logging |
| `roles/cloudfunctions.developer` | Project | Deploy and manage Cloud Functions 2nd gen |
| `roles/run.developer` | Project | Deploy and manage Cloud Run services |
| `roles/storage.objectAdmin` | Project | Read source code, write build artifacts to GCS |
| `roles/iam.serviceAccountUser` | On runtime SAs | Act as runtime service accounts during deployment |

### Service Account User Bindings

| Target Service Account | Purpose |
|------------------------|---------|
| `dev-github-archive-processor@...` | Deploy processor Cloud Run service |
| `dev-bq-loader@...` | Deploy bq-loader Cloud Function |

### Permission Details by Use Case

#### Deploying Cloud Functions 2nd gen
- **cloudfunctions.developer**: Create, update, delete functions
- **run.developer**: Manage Cloud Run backend (2nd gen uses Cloud Run)
- **storage.objectAdmin**: Upload source code, read/write build artifacts
- **artifactregistry.writer**: Push container images
- **iam.serviceAccountUser**: Act as the function's runtime SA

#### Deploying Cloud Run Services
- **run.developer**: Create, update Cloud Run services and revisions
- **artifactregistry.writer**: Pull/push container images
- **storage.objectAdmin**: Read source code for build-from-source
- **iam.serviceAccountUser**: Act as the service's runtime SA

### Key Permissions in Each Role

| Role | Key Permissions |
|------|-----------------|
| `cloudbuild.builds.builder` | `cloudbuild.builds.create`, `cloudbuild.builds.update`, `storage.objects.*`, `artifactregistry.*` |
| `cloudfunctions.developer` | `cloudfunctions.functions.create`, `cloudfunctions.functions.update`, `run.services.*` |
| `run.developer` | `run.services.create`, `run.services.update`, `run.revisions.*` |
| `storage.objectAdmin` | `storage.objects.create`, `storage.objects.get`, `storage.objects.delete` |
| `iam.serviceAccountUser` | `iam.serviceAccounts.actAs` |

---

## Notes

- The `storage.objectAdmin` role on the Compute Engine default SA is broader than necessary
- Consider auditing if this permission is required or if it should be scoped down
- Deleted service accounts still appear in IAM policies (marked as `deleted:`)
- `dev-cloud-build` SA is now configured for Cloud Functions and Cloud Run deployments
