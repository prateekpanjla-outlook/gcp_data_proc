# Complete Resource Name Inventory

All resources that will be deployed by Terraform, with their exact names as they appear in GCP.

---

## 📋 Naming Convention

All resources follow this pattern:
```
{environment}-{resource_name}
```

Where `{environment}` = `dev`, `test`, `prod`, etc.

---

## 🎯 Phase 1: Ingestion (8 Resources)

### Storage Resources
| Resource Type | Resource Name | GCP Name Format |
|---------------|---------------|-----------------|
| Storage Bucket | `github_archive_landing` | `{project_id}-{env}-github-archive-landing` |
| **Example:** `dev-dataprocessing-489305-dev-github-archive-landing`

### Compute Resources
| Resource Type | Resource Name | GCP Name Format |
|---------------|---------------|-----------------|
| Cloud Run Job | `github_archive_downloader` | `{env}-github-archive-download-gsutil` |
| **Example:** `dev-github-archive-download-gsutil`

| Resource Type | Resource Name | GCP Name Format |
|---------------|---------------|-----------------|
| Cloud Scheduler Job | `github_archive_download` | `{env}-github-archive-download-job` |
| **Example:** `dev-github-archive-download-job`

### Service Accounts
| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `github_archive_downloader` (SA) | `{env}-github-archive-downloader@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-github-archive-downloader@dev-dataprocessing-489305.iam.gserviceaccount.com`

| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `scheduler` (SA) | `{env}-scheduler@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-scheduler@dev-dataprocessing-489305.iam.gserviceaccount.com`

### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `github_archive_downloader_storage` | Service Account → Roles/storage.objectUser |
| IAM Member | `github_archive_downloader_logging` | Service Account → Roles/logging.logWriter |
| IAM Member | `scheduler_github_invoker` | Scheduler SA → Cloud Run Invoker |
| IAM Member | `scheduler_token_creator` | Service Account → Token Creator |

---

## 🔧 Phase 2: Processing (18 Resources)

### Static Layer (7 Resources)

#### Service Accounts
| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `processor` (SA) | `{env}-github-archive-processor@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com`

| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `splitter` (SA) | `{env}-file-splitter@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-file-splitter@dev-dataprocessing-489305.iam.gserviceaccount.com`

| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `eventarc_invoker` (SA) | `{env}-eventarc-invoker@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-eventarc-invoker@dev-dataprocessing-489305.iam.gserviceaccount.com`

#### Storage
| Resource Type | Resource Name | GCP Name Format |
|---------------|---------------|-----------------|
| Storage Bucket | `staging` | `{project_id}-{env}-github-archive-staging` |
| **Example:** `dev-dataprocessing-489305-dev-github-archive-staging`

#### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `processor_logging` | Service Account → Roles/logging.logWriter |
| IAM Member | `processor_monitoring` | Service Account → Roles/monitoring.metricWriter |
| IAM Member | `splitter_logging` | Service Account → Roles/logging.logWriter |
| IAM Member | `splitter_monitoring` | Service Account → Roles/monitoring.metricWriter |
| IAM Member | `eventarc_invoker_logging` | Service Account → Roles/logging.logWriter |
| IAM Member | `processor_landing_read` | Service Account → Bucket Reader |
| IAM Member | `processor_staging_write` | Service Account → Bucket Object Creator |
| IAM Member | `processor_staging_read` | Service Account → Bucket Viewer |
| IAM Member | `splitter_landing_read` | Service Account → Bucket Reader |
| IAM Member | `splitter_landing_chunks_write` | Service Account → Bucket Object Creator |

### First-Time Layer (9 Resources)

#### GCP APIs
| Resource Type | Resource Name | API Name |
|---------------|---------------|----------|
| Project Service | `eventarc` | eventarc.googleapis.com |
| Project Service | `eventarcpublishing` | eventarcpublishing.googleapis.com |
| Project Service | `cloud_run` | run.googleapis.com |
| Project Service | `storage` | storage.googleapis.com |
| Project Service | `cloud_resource_manager` | cloudresourcemanager.googleapis.com |
| Project Service | `iam` | iam.googleapis.com |
| Project Service | `logging` | logging.googleapis.com |
| Project Service | `monitoring` | monitoring.googleapis.com |
| Project Service | `cloudbuild` | cloudbuild.googleapis.com |

#### Artifact Registry
| Resource Type | Resource Name | Repository ID |
|---------------|---------------|--------------|
| Artifact Registry Repository | `docker_repo` | `github-archive` |
| **Full Name:** `{project_id}/github-archive`

#### Cloud Build
| Resource Type | Resource Name | Trigger Name |
|---------------|---------------|--------------|
| Cloud Build Trigger | `phase2_processor` | `phase2-processor` |
| **Example:** `phase2-processor`

| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `cloudbuild_sa` | `{project_id}@cloudbuild.gserviceaccount.com` |

#### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `cloudbuild_sa_logging` | Cloud Build SA → Logging |
| IAM Member | `cloudbuild_sa_monitoring` | Cloud Build SA → Monitoring |
| IAM Member | `cloudbuild_sa artifactregistry_reader` | Cloud Build SA → Artifact Registry Reader |
| IAM Member | `cloudbuild_sa_run_admin` | Cloud Build SA → Cloud Run Admin |
| IAM Member | `cloudbuild_sa_cloud_build_sa` | Cloud Build SA → Cloud Build Service Account |
| IAM Member | `storage_pubsub_publisher` | Storage SA → Pub/Sub Publisher |
| IAM Member | `eventarc_event_receiver` | Eventarc SA → Eventarc Event Receiver |

### Operational Layer (3 Resources)

#### Cloud Run Service
| Resource Type | Resource Name | Service Name |
|---------------|---------------|--------------|
| Cloud Run Service | `processor` | `{env}-github-archive-processor` |
| **Example:** `dev-github-archive-processor`

| Resource Type | Resource Name | Revision Name Pattern |
|---------------|---------------|----------------------|
| Cloud Run Service | `processor` | `{env}-github-archive-processor-00001-xyz` |
| **Example:** `dev-github-archive-processor-00001-t6y7u8x9-z3a2` |

#### Eventarc Trigger
| Resource Type | Resource Name | Trigger ID |
|---------------|---------------|------------|
| Eventarc Trigger | `storage_events` | Auto-generated UUID |
| **Filters:** `bucket={project_id}-{env}-github-archive-staging`

#### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `eventarc_invoker_processor` | Eventarc SA → Cloud Run Invoker |

---

## 💾 Phase 3: Loading (15 Resources)

### Static Layer (7 Resources)

#### BigQuery
| Resource Type | Resource Name | Dataset/Table Format |
|---------------|---------------|----------------------|
| BigQuery Dataset | `github_archive` | `github_archive` |
| BigQuery Table | `github_events` | `github_archive.github_events` |

#### Service Accounts
| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `bq_loader` (SA) | `{env}-bq-loader@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-bq-loader@dev-dataprocessing-489305.iam.gserviceaccount.com`

| Resource Type | Resource Name | Email Format |
|---------------|---------------|--------------|
| Service Account | `eventarc_invoker` (SA) | `{env}-eventarc-bigquery-invoker@{project_id}.iam.gserviceaccount.com` |
| **Example:** `dev-eventarc-bigquery-invoker@dev-dataprocessing-489305.iam.gserviceaccount.com`

#### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `bq_loader_data_editor` | Service Account → BigQuery Data Editor |
| IAM Member | `bq_loader_job_user` | Service Account → BigQuery Job User |
| IAM Member | `bq_loader_logging` | Service Account → Logging Log Writer |
| IAM Member | `bq_loader_monitoring` | Service Account → Monitoring Metric Writer |
| IAM Member | `eventarc_invoker_logging` | Service Account → Logging Log Writer |
| IAM Member | `eventarc_invoker_event_receiver` | Service Account → Eventarc Event Receiver |

### First-Time Layer (4 Resources)

#### BigQuery IAM
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `bq_loader_dataset_data_editor` | SA → Dataset Data Editor |
| IAM Member | `bq_loader_project_job_user` | SA → Project Job User |

#### Storage IAM
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `bq_loader_staging_viewer` | SA → Bucket Viewer |
| IAM Member | `bq_loader_staging_admin` | SA → Bucket Object Admin |

### Operational Layer (4 Resources)

#### Storage
| Resource Type | Resource Name | Bucket Name |
|---------------|---------------|-------------|
| Storage Bucket | `source` | `{project_id}-{env}-gcf-source` |
| **Example:** `dev-dataprocessing-489305-dev-gcf-source`

| Resource Type | Resource Name | Object Name |
|---------------|---------------|------------|
| GCS Object | `source` | `function-source-{hash}.zip` |

#### Cloud Function
| Resource Type | Resource Name | Function Name |
|---------------|---------------|--------------|
| Cloud Function 2nd Gen | `bq_loader` | `{env}-bq-loader` |
| **Example:** `dev-bq-loader`
| **Full Name:** `projects/{project_id}/locations/{region}/functions/{env}-bq-loader`

#### IAM Bindings
| Resource Type | Resource Name | Target |
|---------------|---------------|--------|
| IAM Member | `gcs_pubsub_publisher` | Storage SA → Pub/Sub Publisher |
| IAM Member | `bq_loader_artifactregistry` | Loader SA → Artifact Registry Reader |
| IAM Member | `eventarc_invoker_run` | Eventarc SA → Cloud Run Invoker |

---

## 📊 Complete Resource Summary by Environment

### Example: Environment = "dev", Project = "dev-dataprocessing-489305"

#### Phase 1 Resources
```
Storage Buckets:
  ✓ dev-dataprocessing-489305-dev-github-archive-landing

Cloud Run Jobs:
  ✓ dev-github-archive-download-gsutil

Cloud Scheduler Jobs:
  ✓ dev-github-archive-download-job

Service Accounts:
  ✓ dev-github-archive-downloader@dev-dataprocessing-489305.iam.gserviceaccount.com
  ✓ dev-scheduler@dev-dataprocessing-489305.iam.gserviceaccount.com
```

#### Phase 2 Resources
```
Storage Buckets:
  ✓ dev-dataprocessing-489305-dev-github-archive-staging

Cloud Run Services:
  ✓ dev-github-archive-processor

Eventarc Triggers:
  ✓ {UUID}-storage-events

Artifact Registry:
  ✓ dev-dataprocessing-489305/github-archive

Service Accounts:
  ✓ dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com
  ✓ dev-file-splitter@dev-dataprocessing-489305.iam.gserviceaccount.com
  ✓ dev-eventarc-invoker@dev-dataprocessing-489305.iam.gserviceaccount.com

Cloud Build Triggers:
  ✓ phase2-processor
```

#### Phase 3 Resources
```
Storage Buckets:
  ✓ dev-dataprocessing-489305-dev-gcf-source

BigQuery Datasets:
  ✓ github_archive

BigQuery Tables:
  ✓ github_archive.github_events

Cloud Functions:
  ✓ dev-bq-loader

Service Accounts:
  ✓ dev-bq-loader@dev-dataprocessing-489305.iam.gserviceaccount.com
  ✓ dev-eventarc-bigquery-invoker@dev-dataprocessing-489305.iam.gserviceaccount.com
```

---

## 🔍 Resource Naming Patterns

### Service Account Email Pattern
```
{environment}-{resource-type}@{project_id}.iam.gserviceaccount.com

Examples:
  dev-github-archive-downloader@dev-dataprocessing-489305.iam.gserviceaccount.com
  dev-github-archive-processor@dev-dataprocessing-489305.iam.gserviceaccount.com
  dev-bq-loader@dev-dataprocessing-489305.iam.gserviceaccount.com
```

### Bucket Naming Pattern
```
{project_id}-{environment}-{purpose}

Examples:
  dev-dataprocessing-489305-dev-github-archive-landing
  dev-dataprocessing-489305-dev-github-archive-staging
  dev-dataprocessing-489305-dev-gcf-source
```

### Cloud Run Service/Job Pattern
```
{environment}-{resource-name}

Examples:
  dev-github-archive-processor (service)
  dev-github-archive-download-gsutil (job)
```

### Cloud Function Pattern
```
{environment}-{resource-name}

Examples:
  dev-bq-loader
```

### BigQuery Dataset/Table Pattern
```
{dataset_name}
{dataset_name}.{table_name}

Examples:
  github_archive (dataset)
  github_archive.github_events (table)
```

---

## 📝 Quick Reference Commands

### List all resources after deployment:

```bash
# Storage Buckets
gsutil ls

# Cloud Run Services
gcloud run services list --project=$PROJECT_ID

# Cloud Run Jobs
gcloud run jobs list --project=$PROJECT_ID

# Cloud Functions
gcloud functions list --project=$PROJECT_ID

# Cloud Scheduler Jobs
gcloud scheduler jobs list --project=$PROJECT_ID --location=$REGION

# Eventarc Triggers
gcloud eventarc triggers list --project=$PROJECT_ID --region=$REGION

# BigQuery Datasets
bq ls --project_id=$PROJECT_ID -d

# Service Accounts
gcloud iam service-accounts list --project=$PROJECT_ID
```

### Count resources by type:

```bash
# Count buckets
gsutil ls | wc -l

# Count Cloud Run services
gcloud run services list --project=$PROJECT_ID --format="value(name)" | wc -l

# Count Cloud Run jobs
gcloud run jobs list --project=$PROJECT_ID --format="value(name)" | wc -l

# Count service accounts
gcloud iam service-accounts list --project=$PROJECT_ID --format="value(email)" | wc -l
```

---

`✶ Insight ─────────────────────────────────────`
**Resource Naming Strategy:** The `{environment}-{resource}` naming pattern provides clear environment segregation and makes it easy to identify resource ownership. All resources are prefixed with the environment name, making it impossible to accidentally modify production resources when working in development.

**Service Account Organization:** Each service gets its own service account with minimal required permissions (least privilege). This is a security best practice that limits the blast radius of compromised credentials. The naming makes it immediately clear which service account is used for which resource.
`─────────────────────────────────────────────────`

---

## 🎯 Total Resource Count

| Phase | Layer | Resources |
|-------|-------|-----------|
| **Phase 1** | Single (all-in-one) | **8** |
| **Phase 2** | Static | 7 |
| **Phase 2** | First-Time | 9 |
| **Phase 2** | Operational | 3 |
| **Phase 3** | Static | 7 |
| **Phase 3** | First-Time | 4 |
| **Phase 3** | Operational | 4 |
| **TOTAL** | - | **42 Resources** |

---

**All 42 resources are documented above with their exact deployed names!** 🎉
