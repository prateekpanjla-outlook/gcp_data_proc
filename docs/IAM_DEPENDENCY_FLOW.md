# IAM Permissions and Dependency Flow

This diagram provides a comprehensive visualization of the service accounts, roles, and dependencies across the three distinct stages of the pipeline's lifecycle: Provision-Time, Build-Time, and Run-Time.

## Complete Permissions and Dependency Flow

```mermaid
graph LR
    subgraph "1. Provision-Time (Terraform)"
        direction LR
        TERRAFORM_SA["Terraform Deployer SA"]
        TERRAFORM_ROLES["<strong>Provision-Time Roles (Verified Live)</strong><br>---<br>resourcemanager.projectIamAdmin<br>iam.serviceAccountAdmin<br>run.admin<br>storage.admin<br>bigquery.admin<br>cloudbuild.builds.builder<br><br><font color=red>-- Additional Roles in Live Env --</font><br><font color=red>roles/editor</font><br><font color=red>cloudscheduler.admin</font><br><font color=red>iam.serviceAccountTokenCreator</font><br><font color=red>artifactregistry.admin</font><br><font color=red>pubsub.admin</font><br><font color=red>cloudfunctions.admin</font><br><font color=red>monitoring.admin</font><br><font color=red>eventarc.admin</font><br><font color=red>logging.admin</font>"]
        TERRAFORM_SA -- "Needs roles to run<br>terraform apply" --> TERRAFORM_ROLES
    end

    subgraph "2. Build-Time (Cloud Build)"
        direction LR
        CLOUDBUILD_SA["Cloud Build SA<br>(PROJECT_NUM@cloudbuild.gserviceaccount.com)"]
        CLOUDBUILD_ROLES["<strong>Build-Time Roles (Least Privilege)</strong><br>---<br><u>For Building & Pushing Artifacts:</u><br>roles/cloudbuild.builds.editor<br>roles/storage.objectAdmin<br>roles/artifactregistry.writer<br>roles/logging.logWriter<br><br><u>For Deploying to Cloud Run:</u><br>roles/run.admin<br>roles/iam.serviceAccountUser"]
        CLOUDBUILD_SA -- Needs --> CLOUDBUILD_ROLES
    end

    subgraph "3. Run-Time (Live Pipeline Execution)"
        direction TB
        subgraph "Phase 1: Ingestion"
            direction TB
            P1_SCHED["Cloud Scheduler"] -- "Invokes As<br>scheduler SA" --> P1_JOB["Cloud Run Job<br>(Downloader)"]
            P1_JOB -- "Runs As<br>downloader SA" --> P1_BUCKET["GCS Landing Bucket"]
            P1_JOB_SA["<strong>Downloader SA Needs:</strong><br>storage.objectCreator"]
            P1_JOB -- "Uses SA with role" --> P1_JOB_SA
        end

        subgraph "Phase 2: Processing"
            direction TB
            P2_EVENT["GCS Event<br>(File Upload)"] --> P2_STORAGE_AGENT["Storage Service Agent"]
            P2_STORAGE_AGENT -- "Publishes to Pub/Sub" --> P2_PUBSUB_AGENT["Pub/Sub Service Agent"]
            P2_PUBSUB_AGENT -- "3. Impersonates &<br>Generates Token for" --> P2_EVENTARC_INVOKER["Eventarc Invoker SA"]
            P2_EVENTARC_INVOKER -- "Invokes" --> P2_SERVICE["Cloud Run Service<br>(Processor)"]
            P2_SERVICE -- "Runs As<br>processor SA" --> P2_STAGING_BUCKET["GCS Staging Bucket"]

            P2_PERMS["<strong>Permissions Needed:</strong><br>1. Storage Agent needs `pubsub.publisher`<br><strong>2. Pub/Sub Agent needs `iam.serviceAccountTokenCreator`<br>   on Eventarc Invoker SA (to impersonate)</strong><br>3. Invoker SA needs `run.invoker` on Service<br>4. Processor SA needs `storage.objectAdmin` on Staging Bucket"]
            P2_PUBSUB_AGENT -.-> P2_PERMS
        end

        subgraph "Phase 3: Loading"
            direction TB
            P3_EVENT["GCS Event<br>(File Upload)"] --> P3_STORAGE_AGENT["Storage Service Agent"]
            P3_STORAGE_AGENT -- "Publishes to Pub/Sub" --> P3_PUBSUB_AGENT["Pub/Sub Service Agent"]
            P3_PUBSUB_AGENT -- "3. Impersonates &<br>Generates Token for" --> P3_EVENTARC_INVOKER["Eventarc Invoker SA"]
            P3_EVENTARC_INVOKER -- "Invokes" --> P3_FUNCTION["Cloud Function<br>(BQ Loader)"]
            P3_FUNCTION -- "Runs As<br>bq_loader SA" --> P3_BIGQUERY["BigQuery Table"]

            P3_PERMS["<strong>Permissions Needed:</strong><br>1. Storage Agent needs `pubsub.publisher`<br><strong>2. Pub/Sub Agent needs `iam.serviceAccountTokenCreator`<br>   on Eventarc Invoker SA (to impersonate)</strong><br>3. Invoker SA needs `cloudfunctions.invoker` on Function<br>4. BQ Loader SA needs `bigquery.dataEditor` on Table"]
            P3_PUBSUB_AGENT -.-> P3_PERMS
        end
    end
    
    %% --- Global Dependencies ---
    TERRAFORM_SA -- "Provisions & Grants Roles" --> CLOUDBUILD_SA
    TERRAFORM_SA -- "Provisions & Grants Roles" --> P1_JOB
    TERRAFORM_SA -- "Provisions & Grants Roles" --> P2_SERVICE
    TERRAFORM_SA -- "Provisions & Grants Roles" --> P3_FUNCTION
    TERRAFORM_SA -- "Provisions & Grants Roles" --> P2_EVENTARC_INVOKER
    TERRAFORM_SA -- "Provisions & Grants Roles" --> P3_EVENTARC_INVOKER

    CLOUDBUILD_SA -- "Builds & Deploys<br>New Revision To" --> P2_SERVICE

    subgraph "Security Explanation"
      direction TB
      WHY_CUSTOM_SA["<strong>Why use custom Service Accounts?</strong><br><br>Using custom, single-purpose service accounts (e.g., 'processor-sa') follows the<br><strong>Principle of Least Privilege.</strong><br><br>Generic, Google-managed service agents (like the Pub/Sub Service Agent) have broad roles<br>that grant them excessive permissions across the entire project.<br><br>If compromised, a generic account is a huge security risk. By creating a chain of impersonation<br>where the powerful Google agent can only 'act as' our highly-restricted custom SA,<br>we create a security firewall. The custom SA can only perform its one specific task,<br>drastically reducing the blast radius of a potential compromise."]
    end



    %% --- Styling ---
    style TERRAFORM_SA fill:#e3f2fd,stroke:#333,stroke-width:2px
    style CLOUDBUILD_SA fill:#fff3e0,stroke:#333,stroke-width:2px
    style P2_STORAGE_AGENT fill:#e8f5e9,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style P2_PUBSUB_AGENT fill:#e8f5e9,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style P3_STORAGE_AGENT fill:#e8f5e9,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style P3_PUBSUB_AGENT fill:#e8f5e9,stroke:#333,stroke-width:1px,stroke-dasharray: 5 5
    style TERRAFORM_ROLES fill:#e3f2fd,stroke-dasharray: 5 5
    style CLOUDBUILD_ROLES fill:#fff3e0,stroke-dasharray: 5 5
    style P1_JOB_SA fill:#fce4ec,stroke-dasharray: 5 5
    style P2_PERMS fill:#e8f5e9,stroke-dasharray: 5 5
    style P3_PERMS fill:#e8f5e9,stroke-dasharray: 5 5
    style WHY_CUSTOM_SA fill:#f5f5f5,stroke:#616161,stroke-width:1px,stroke-dasharray: 3 3
```

This file is now saved as `docs/IAM_DEPENDENCY_FLOW.md` and can be referenced by the team to understand the complete permissions model.
