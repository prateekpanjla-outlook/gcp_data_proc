# Phase 1: Failure Scenarios

```mermaid
flowchart TD
    DownloadAttempt[Download Attempt] --> Status{HTTP Status}

    Status -->|200| ValidFile[Valid File]
    Status -->|404| FileNotReady[File Not Ready]
    Status -->|500/503| ServerError[Server Error]
    Status -->|Timeout| NetworkError[Network Timeout]
    Status -->|MemoryError| OOM[Out of Memory]

    FileNotReady --> Wait5[Wait 5 min]
    ServerError --> Wait1[Wait 1 min]
    NetworkError --> Wait2[Wait 2 min]

    ValidFile --> Validate{Validate Gzip}
    Validate -->|Pass| Upload
    Validate -->|Fail| Corrupted[Corrupted File - SKIP]

    Wait5 -->|Retry < 6x| DownloadAttempt
    Wait1 -->|Retry < 3x| DownloadAttempt
    Wait2 -->|Retry < 3x| DownloadAttempt

    Wait5 -->|Exceeded| Fail404[❌ File Never Appeared]
    Wait1 -->|Exceeded| FailServer[❌ Server Down]
    Wait2 -->|Exceeded| FailNetwork[❌ Network Unreachable]
    OOM --> FailOOM[❌ Memory Error<br>Refactor to Streaming]

    Upload -->|Success| Success
    Upload -->|Fail| FailUpload[❌ Upload Failed<br>Check Permissions]

    style Success fill:#e1f5e1
    style Corrupted fill:#ffebee
    style Fail404 fill:#ffebee
    style FailServer fill:#ffebee
    style FailNetwork fill:#ffebee
    style FailOOM fill:#ffebee
    style FailUpload fill:#ffebee
```
