# Phase 1: Main Flow Diagram

```mermaid
graph TD
    Start([Phase 1 Start]) --> Init[Initialize<br>Environment Variables<br>PROJECT_ID, BUCKET_NAME, REGION]

    Init --> E1[Scheduler deployed?<br>cron: 30 * * * *]
    E1 --> E2[Cloud Run Job deployed?<br>dev-github-archive-download-gsutil]
    E2 --> E3[Service Account has<br>roles/storage.objectUser?]
    E3 --> E4[GitHub Archive reachable?<br>https://data.gharchive.org/]

    E4 -->|All Pass| CalcFilename[Step 1:<br>Calculate Target Filename]
    E1 -->|Missing| FailEntry[❌ Entry Failed<br>Fix Infrastructure]
    E2 -->|Missing| FailEntry
    E3 -->|Missing| FailEntry

    CalcFilename --> BuildURL["Step 2:<br>Build Download URL<br>https://data.gharchive.org/{filename}"]

    BuildURL --> CheckExists["Step 3:<br>Check if File Exists in GCS"]
    CheckExists -->|Already Exists| Skip[Skip Download<br>Idempotent]
    CheckExists -->|Not Found| StreamDownload["Step 4:<br>gsutil cp Streaming<br>GitHub Archive → GCS"]

    StreamDownload --> Verify{Upload Successful?}
    Verify -->|Yes| Success([✅ Phase 1 Success])
    Verify -->|No| FailUpload[❌ Upload Failed<br>Check IAM/Network]

    Skip --> Success
    Success --> Trigger[Triggers:<br>Next Phase]

    style Start fill:#e1f5e1
    style Success fill:#e1f5e1
    style Skip fill:#fff3e0
    style FailEntry fill:#ffebee
    style FailUpload fill:#ffebee
    style Trigger fill:#fff3e0
```

**Note:** Using `gsutil cp` for streaming download (memory efficient ~50MB). Validation happens in Phase 2 (processing). Corrupted files from GitHub Archive will be detected during processing.
