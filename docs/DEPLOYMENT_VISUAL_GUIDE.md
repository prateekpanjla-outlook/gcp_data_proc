# Infrastructure Deployment Visual Guide

Visual diagrams and quick reference for deploying the GitHub Archive data pipeline.

---

## 🎯 Quick Reference Deployment Order

```
1. Phase 1: Ingestion (Single Layer)
   ↓ (landing bucket created)
2. Phase 2: Processing (3 Layers: Static → First-Time → Operational)
   ↓ (staging bucket created)
3. Phase 3: Loading (3 Layers: Static → First-Time → Operational)
   ↓
4. Cloud Build (Phase 2 Application Code)
   ↓
5. Validation & Testing
```

---

## 📊 Complete Architecture Overview

```mermaid
graph TB
    subgraph "External Sources"
        GHA[GitHub Archive<br/>gharchive.org]
    end

    subgraph "Phase 1: Ingestion"
        SCHED[Cloud Scheduler<br/>Hourly :30]
        JOB[Cloud Run Job<br/>Downloader]
        LANDING[GCS Bucket<br/>Landing<br/>6-day retention]
    end

    subgraph "Phase 2: Processing"
        EVENTARC1[Eventarc Trigger<br/>Object Finalized]
        SERVICE[Cloud Run Service<br/>Processor<br/>4GiB, 2 CPU]
        STAGING[GCS Bucket<br/>Staging<br/>30-day retention]
    end

    subgraph "Phase 3: Loading"
        EVENTARC2[Eventarc Trigger<br/>Object Finalized]
        FUNCTION[Cloud Function<br/>BigQuery Loader<br/>Python 3.11]
        BQ[BigQuery<br/>Dataset & Table<br/>Partitioned]
    end

    GHA -->|1. Download| SCHED
    SCHED -->|Triggers| JOB
    JOB -->|Saves to| LANDING

    LANDING -.->|2. Event| EVENTARC1
    EVENTARC1 -->|Invokes| SERVICE
    SERVICE -->|Saves to| STAGING

    STAGING -.->|3. Event| EVENTARC2
    EVENTARC2 -->|Invokes| FUNCTION
    FUNCTION -->|Loads to| BQ

    style GHA fill:#f9f9f9
    style LANDING fill:#e1f5ff
    style STAGING fill:#fff4e1
    style BQ fill:#e8f5e9
```

---

## 🔧 Terraform Layer Dependencies

### Phase 2 Layer Dependencies

```mermaid
graph TB
    subgraph "Phase 2 Static Layer"
        SA1[processor SA]
        SA2[splitter SA]
        SA3[eventarc_invoker SA]
        BUCKET1[staging bucket]
        IAM1[static IAM bindings]
    end

    subgraph "Phase 2 First-Time Layer"
        APIS[Enable GCP APIs]
        REPO[Artifact Registry]
        BUILD[Cloud Build Trigger]
    end

    subgraph "Phase 2 Operational Layer"
        SERVICE[Cloud Run Service]
        EVENTARC[Eventarc Trigger]
    end

    SA1 --> BUCKET1
    SA2 --> BUCKET1
    SA1 --> IAM1
    SA2 --> IAM1
    SA3 --> IAM1

    APIS --> REPO
    REPO --> BUILD

    BUCKET1 -.->|remote state| SERVICE
    SA1 -.->|remote state| SERVICE
    IAM1 -.->|remote state| SERVICE
    BUILD -.->|remote state| SERVICE

    SERVICE --> EVENTARC

    style SA1 fill:#ffebee
    style SA2 fill:#ffebee
    style SA3 fill:#ffebee
    style APIS fill:#fff3e0
    style SERVICE fill:#e8f5e9
```

### Phase 3 Layer Dependencies

```mermaid
graph TB
    subgraph "Phase 3 Static Layer"
        SA4[bq_loader SA]
        SA5[eventarc_invoker SA]
        DATASET[BigQuery Dataset]
        TABLE[BigQuery Table]
        IAM2[static IAM bindings]
    end

    subgraph "Phase 3 First-Time Layer"
        BQ_IAM[BigQuery IAM]
        STORAGE_IAM[Storage IAM]
    end

    subgraph "Phase 3 Operational Layer"
        BUCKET2[source bucket]
        OBJECT[source zip object]
        FUNCTION[Cloud Function]
    end

    SA4 --> DATASET
    SA4 --> TABLE
    SA4 --> IAM2
    SA5 --> IAM2

    DATASET --> TABLE
    IAM2 --> BQ_IAM
    IAM2 --> STORAGE_IAM

    SA4 -.->|remote state| FUNCTION
    SA5 -.->|remote state| FUNCTION
    BQ_IAM -.->|remote state| FUNCTION

    BUCKET2 --> OBJECT
    OBJECT --> FUNCTION

    style SA4 fill:#ffebee
    style SA5 fill:#ffebee
    style BQ_IAM fill:#fff3e0
    style FUNCTION fill:#e8f5e9
```

---

## 🔗 Cross-Phase Remote State Dependencies

```mermaid
graph LR
    subgraph "Phase 1"
        P1[Single Layer<br/>8 Resources]
    end

    subgraph "Phase 2"
        P2S[Static<br/>7 Resources]
        P2F[First-Time<br/>9 Resources]
        P2O[Operational<br/>3 Resources]
    end

    subgraph "Phase 3"
        P3S[Static<br/>7 Resources]
        P3F[First-Time<br/>4 Resources]
        P3O[Operational<br/>4 Resources]
    end

    P1 -->|bucket name| P2S
    P2O -->|reads outputs| P2S
    P2O -->|reads outputs| P2F

    P2S -->|bucket name| P3S
    P3F -->|reads outputs| P2S
    P3O -->|reads outputs| P3S
    P3O -->|reads outputs| P3F

    style P1 fill:#e1f5ff
    style P2S fill:#fff4e1
    style P2F fill:#fff3e0
    style P2O fill:#e8f5e9
    style P3S fill:#e8f5e9
    style P3F fill:#e0f2f1
    style P3O fill:#c8e6c9
```

---

## 🚨 Critical Dependency Paths

### Must-Complete-First Dependencies

```mermaid
graph TD
    A[Create Project] --> B[Phase 1: Landing Bucket]
    B --> C[Phase 2: Staging Bucket]
    C --> D[Phase 3: BigQuery Table]

    A -.->|Parallel| E[Enable APIs]
    E --> F[Phase 2: Cloud Run Service]
    E --> G[Phase 3: Cloud Function]

    F --> H[Phase 2: Eventarc Trigger]
    G --> I[Phase 3: Eventarc Trigger]

    style A fill:#f44336
    style B fill:#e1f5ff
    style C fill:#fff4e1
    style D fill:#e8f5e9
    style E fill:#ff9800
    style F fill:#4caf50
    style G fill:#009688
```

### IAM Permission Chain

```mermaid
graph LR
    SA[Service Accounts] --> IAM[IAM Bindings]
    PROJECT[Project Resources] --> IAM

    APIs[GCP APIs] --> PERMISSIONS[Service Agents]
    PERMISSIONS --> IAM

    IAM --> ACCESS[Resource Access]
    BUCKETS[Buckets] --> ACCESS
    SERVICES[Cloud Run/Function] --> ACCESS

    style SA fill:#ffebee
    style APIs fill:#fff3e0
    style IAM fill:#e1f5fe
    style ACCESS fill:#e8f5e9
```

---

## ⏱️ Deployment Timeline with Dependencies

```mermaid
gantt
    title Infrastructure Deployment Timeline
    dateFormat X
    axisFormat %M min

    section Phase 1
    Service Accounts      :p1a, 0, 1
    Storage Bucket        :p1b, after p1a, 1
    Cloud Run Job         :p1c, after p1a, 2
    Cloud Scheduler       :p1d, after p1c, 1

    section Phase 2
    Static Resources      :p2a, after p1d, 2
    First-Time Setup      :p2b, after p2a, 3
    Cloud Run Service     :p2c, after p2b, 3
    Eventarc Trigger      :p2d, after p2c, 1

    section Phase 3
    Static Resources      :p3a, after p2d, 2
    First-Time Setup      :p3b, after p3a, 2
    Cloud Function        :p3c, after p3b, 4
    Eventarc Trigger      :p3d, after p3c, 1

    section Application
    Cloud Build           :cb, after p2d, 5
    Validation            :val, after p3d, 4
```

---

## 🎯 Resource Creation Checklist

### Phase 1: Ingestion ✓

```mermaid
graph TD
    P1[Phase 1 Deployment] --> P1SA[Service Accounts Created]
    P1SA --> P1BCK[Bucket Created]
    P1BCK --> P1JOB[Cloud Run Job Created]
    P1JOB --> P1SCHED[Scheduler Created]
    P1SCHED --> P1IAM[IAM Bindings Created]

    P1IAM --> P1VAL{Validation}
    P1VAL -->|Pass| P1DONE[✓ Phase 1 Complete]
    P1VAL -->|Fail| P1ERR[✗ Review Logs]

    style P1 fill:#e1f5ff
    style P1DONE fill:#4caf50
    style P1ERR fill:#f44336
```

### Phase 2: Processing ✓

```mermaid
graph TD
    P2[Phase 2 Deployment] --> P2S[Static Layer]
    P2S --> P2F[First-Time Layer]
    P2F --> P2O[Operational Layer]

    P2O --> P2VAL{Validation}
    P2VAL -->|Pass| P2DONE[✓ Phase 2 Complete]
    P2VAL -->|Fail| P2ERR[✗ Review Logs]

    style P2 fill:#fff4e1
    style P2S fill:#ffe0b2
    style P2F fill:#fff3e0
    style P2O fill:#e8f5e9
    style P2DONE fill:#4caf50
    style P2ERR fill:#f44336
```

### Phase 3: Loading ✓

```mermaid
graph TD
    P3[Phase 3 Deployment] --> P3S[Static Layer]
    P3S --> P3F[First-Time Layer]
    P3F --> P3O[Operational Layer]

    P3O --> P3VAL{Validation}
    P3VAL -->|Pass| P3DONE[✓ Phase 3 Complete]
    P3VAL -->|Fail| P3ERR[✗ Review Logs]

    style P3 fill:#e8f5e9
    style P3S fill:#c8e6c9
    style P3F fill:#e0f2f1
    style P3O fill:#a5d6a7
    style P3DONE fill:#4caf50
    style P3ERR fill:#f44336
```

---

## 🔍 Variable Flow Diagram

```mermaid
graph TB
    subgraph "Input Variables"
        USER[User Input]
        VARS[project_id<br/>environment<br/>region]
    end

    subgraph "Phase 1"
        P1_VARS[+ force_destroy<br/>+ bucket_lifecycle_days]
        P1_OUT[landing_bucket_name]
    end

    subgraph "Phase 2"
        P2_IN[+ landing_bucket_name<br/>from Phase 1]
        P2_VARS[+ processor_memory<br/>+ cpu<br/>+ max_instances<br/>+ chunksize<br/>+ image_tag]
        P2_OUT[staging_bucket_name]
    end

    subgraph "Phase 3"
        P3_IN[+ staging_bucket_name<br/>from Phase 2]
        P3_VARS[+ dataset_id<br/>+ table_id<br/>+ partition_expiration<br/>+ function_memory<br/>+ timeout]
        P3_OUT[infrastructure deployed]
    end

    USER --> VARS
    VARS --> P1_VARS
    P1_VARS --> P1_OUT

    P1_OUT --> P2_IN
    P2_IN --> P2_VARS
    P2_VARS --> P2_OUT

    P2_OUT --> P3_IN
    P3_IN --> P3_VARS
    P3_VARS --> P3_OUT

    style USER fill:#f44336
    style P1_OUT fill:#e1f5ff
    style P2_OUT fill:#fff4e1
    style P3_OUT fill:#e8f5e9
```

---

## 📊 Resource Count by Layer

```mermaid
pie title Total Resources by Phase and Layer
    "Phase 1" : 8
    "Phase 2 Static" : 7
    "Phase 2 First-Time" : 9
    "Phase 2 Operational" : 3
    "Phase 3 Static" : 7
    "Phase 3 First-Time" : 4
    "Phase 3 Operational" : 4
```

**Total: 42 Terraform Resources**

---

## 🎯 Deployment Decision Tree

```mermaid
graph TD
    START[Start Deployment] --> CHECK{Have Terraform<br/>State?}
    CHECK -->|No| INIT[terraform init]
    CHECK -->|Yes| PLAN[terraform plan]

    INIT --> PLAN
    PLAN --> REVIEW{Review Plan}

    REVIEW -->|Looks Good| APPLY[terraform apply]
    REVIEW -->|Issues| MODIFY[Modify Variables]
    MODIFY --> PLAN

    APPLY --> SUCCESS{Success?}
    SUCCESS -->|Yes| VALIDATE[Validate Resources]
    SUCCESS -->|No| ROLLBACK[terraform destroy or fix]
    ROLLBACK --> PLAN

    VALIDATE --> PASS{All Good?}
    PASS -->|Yes| NEXT[Next Layer]
    PASS -->|No| DEBUG[Debug Logs]
    DEBUG --> PLAN

    NEXT --> COMPLETE{More Layers?}
    COMPLETE -->|Yes| PLAN
    COMPLETE -->|No| FINISH[✓ Deployment Complete]

    style START fill:#4caf50
    style FINISH fill:#4caf50
    style INIT fill:#2196f3
    style PLAN fill:#ff9800
    style APPLY fill:#f44336
    style NEXT fill:#9c27b0
```

---

## 🚨 Rollback Strategy

```mermaid
graph LR
    PROBLEM[Issue Detected] --> DECISION{Type of Issue?}

    DECISION -->|Config Error| FIX[Fix Terraform]
    DECISION -->|Runtime Error| LOGS[Check Logs]
    DECISION -->|Dependency Issue| DEPS[Check Dependencies]

    FIX --> REAPPLY[terraform apply]
    LOGS --> ROLLBACK[terraform destroy -target]
    DEPS --> REORDER[Re-deploy in Order]

    REAPPLY --> RETEST{Fixed?}
    ROLLBACK --> RETEST
    REORDER --> RETEST

    RETEST -->|Yes| DONE[✓ Issue Resolved]
    RETEST -->|No| ESCLATE[Escalate]

    style PROBLEM fill:#f44336
    style DONE fill:#4caf50
    style ESCLATE fill:#ff9800
```

---

## 📚 Quick Reference Commands

### Terraform Operations
```bash
# Initialize (first time)
terraform init

# Plan with variables
terraform plan \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"

# Apply changes
terraform apply \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"

# Destroy resources (if needed)
terraform destroy \
  -var="project_id=$PROJECT_ID" \
  -var="environment=$ENVIRONMENT" \
  -var="region=$REGION"

# Show state
terraform show

# Refresh state
terraform refresh
```

### Validation Commands
```bash
# Check Cloud Run services
gcloud run services list --project=$PROJECT_ID

# Check Cloud Run jobs
gcloud run jobs list --project=$PROJECT_ID

# Check Cloud Functions
gcloud functions list --project=$PROJECT_ID

# Check BigQuery datasets
bq ls --project_id=$PROJECT_ID -d

# Check GCS buckets
gsutil ls

# Check Eventarc triggers
gcloud eventarc triggers list --project=$PROJECT_ID
```

---

`✶ Insight ─────────────────────────────────────`
**Visual Dependency Management:** These Mermaid diagrams provide a complete visual representation of your infrastructure dependencies. The layered architecture is clearly visible across multiple diagrams showing how resources depend on each other both within phases (via remote state) and across phases (via bucket names passed as variables).

**Deployment Confidence:** By following the dependency graphs and deployment order, you can deploy with confidence knowing that all prerequisites will be met. The visual checklist diagrams help validate each layer before proceeding to the next, reducing deployment failures and debugging time.
`─────────────────────────────────────────────────`
