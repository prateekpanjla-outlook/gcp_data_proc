# Phase 1: Main Flow Diagram

```mermaid
flowchart TD
    Start([Phase 1 Start]) --> Init[Initialize<br/>Environment Variables<br/>PROJECT_ID, BUCKET_NAME, REGION]

    subgraph Entry_Checks [Entry Conditions]
        E1[Scheduler deployed?<br/>cron: 30 * * * *]
        E2[Cloud Run Job deployed?<br/>hn-fetcher]
        E3[Service Account has<br/>Storage.ObjectCreator?]
        E4[GitHub Archive reachable?<br/>https://data.gharchive.org/]
    end

    Init --> Entry_Checks
    Entry_Checks -->|All Yes| CalcFilename[Step 1:<br/>Calculate Target Filename]
    Entry_Checks -->|Any No| FailEntry[❌ Entry Failed<br/>Fix Infrastructure]

    subgraph Step1 [Step 1: Calculate Filename]
        direction TB
        Calc1[Get current UTC time]
        Calc2[Subtract 1 hour]
        Calc3[Format: YYYY-MM-DD-H.json.gz]
        Calc4[Example:<br/>2025-01-15-14.json.gz]
        Calc1 --> Calc2 --> Calc3 --> Calc4
    end

    CalcFilename --> BuildURL[Step 2:<br/>Build Download URL<br/>https://data.gharchive.org/{filename}]

    subgraph Download [Step 3: Download File]
        direction TB
        HTTP[HTTP GET<br/>timeout: 300s]
        CheckStatus{Status = 200?}
        CheckStatus -->|Yes| ReadData[Read compressed_data<br/>~1.2 GB in memory ⚠️]
        CheckStatus -->|404| Wait404[Wait 5 min<br/>File not ready]
        CheckStatus -->|5xx| Wait5xx[Wait 1 min<br/>Server error]
        Wait404 -->|Retry| HTTP
        Wait5xx -->|Retry| HTTP
    end

    ReadData --> ValidateGzip[Step 4:<br/>Validate Gzip Format<br/>gzip.decompress]

    ValidateGzip -->|Valid| UploadGCS[Step 5:<br/>Upload to Cloud Storage<br/>bucket.blob.upload_from_string]
    ValidateGzip -->|BadGzipFile| FailValidate[❌ Corrupted File<br/>Skip & Log]

    subgraph Upload [Step 5: Upload to GCS]
        direction TB
        SetBlob[blob = bucket.blob<br/>github-archive/raw/{filename}]
        DoUpload[upload_from_string<br/>content_type=application/gzip]
        Verify{blob.exists?}
        DoUpload --> Verify
    end

    Verify -->|Yes| Success([✅ Phase 1 Success])
    Verify -->|No| FailUpload[❌ Upload Failed<br/>Check IAM/Network]

    Success --> Trigger[Triggers:<br/>Cloud Storage finalize event<br/>→ Phase 2]

    style Start fill:#e1f5e1
    style Success fill:#e1f5e1
    style FailEntry fill:#ffebee
    style FailValidate fill:#ffebee
    style FailUpload fill:#ffebee
    style Trigger fill:#fff3e0
```
