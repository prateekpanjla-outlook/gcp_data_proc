# Phase 2: Component View

```mermaid
graph TB
    subgraph Input["INPUT - Phase 1 Landing Zone"]
        CS[Cloud Storage<br>gs://...-landing/raw/]
    end

    subgraph Trigger["TRIGGER LAYER"]
        EVT[Eventarc Trigger<br>filter: raw/*.json.gz]
        PUB[Pub/Sub Topic<br>chunk events]
        SUB[Pub/Sub Subscription<br>push to Cloud Run]
    end

    subgraph Compute["PROCESSING LAYER - Cloud Run"]
        CRS[Cloud Run Service<br>github-archive-processor<br>0-100 instances autoscaling]
        CRJ[Cloud Run Job<br>file-splitter<br>for files >= 500MB]
    end

    subgraph Storage["OUTPUT - Phase 2 Staging"]
        STG[Staging Bucket<br>gs://...-staging/processed/]
        CHK[Chunk Storage<br>gs://...-landing/chunks/]
        DLQ[DLQ Bucket<br>gs://...-dlq/]
    end

    subgraph Tracking["STATE TRACKING"]
        FS[Firestore<br>file_chunks collection]
    end

    subgraph Monitoring["MONITORING"]
        LOG[Cloud Logging]
        MON[Cloud Monitoring]
    end

    CS -->|finalize event| EVT
    EVT --> PUB
    PUB --> SUB
    SUB --> CRS

    CRS -->|large file| CRJ
    CRJ -->|chunk events| PUB
    CRS -->|processed| STG
    CRS -->|errors| DLQ
    CRS -->|updates| FS
    CRS -->|logs| LOG
    CRS -->|metrics| MON

    style EVT fill:#e3f2fd
    style CRS fill:#c8e6c9
    style CRJ fill:#fff3e0
    style STG fill:#e1f5e1
    style DLQ fill:#ffebee
    style FS fill:#f3e5f5
```

**Component Summary:**

| Component | Type | Purpose |
|-----------|------|---------|
| Eventarc Trigger | Trigger | Detects new files in raw/ |
| Pub/Sub Topic | Messaging | Chunk events for large files |
| Pub/Sub Subscription | Push | Delivers messages to Cloud Run |
| Cloud Run Service | Compute | Main file processor (autoscaling) |
| Cloud Run Job | Compute | File splitter for large files |
| Staging Bucket | Storage | Processed files for BigQuery |
| Chunks Bucket | Storage | Split file chunks |
| DLQ Bucket | Storage | Failed events/files |
| Firestore | Database | Chunk tracking state |
| Cloud Logging | Monitoring | Execution logs |
| Cloud Monitoring | Monitoring | Metrics and alerts |
