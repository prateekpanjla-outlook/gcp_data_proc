# Phase 2: Component View

```mermaid
graph TB
    subgraph Input["INPUT - Phase 1 Landing Zone"]
        CS[Cloud Storage<br>gs://...-landing/raw/]
    end

    subgraph Trigger["TRIGGER LAYER"]
        EVT1[Eventarc Trigger<br>filter: github-archive/*.json.gz]
    end

    subgraph Compute["PROCESSING LAYER - Cloud Run"]
        CRS[Cloud Run Service<br>github-archive-processor<br>Handles both raw/ and chunks/<br>Pandas chunked processing<br>0-100 instances autoscaling]
        CRJ[Cloud Run Job<br>file-splitter<br>for files >= 500MB]
    end

    subgraph Storage["OUTPUT - Phase 2 Staging"]
        STG[Staging Bucket<br>gs://...-staging/processed/]
        CHK[Chunk Storage<br>gs://...-landing/chunks/]
    end

    subgraph Monitoring["MONITORING"]
        LOG[Cloud Logging]
        MON[Cloud Monitoring]
    end

    CS -->|finalize event| EVT1
    EVT1 --> CRS

    CRS -->|large file| CRJ
    CRJ -->|write chunks| CHK
    CHK -->|finalize event| EVT1

    CRS -->|processed| STG

    CRS -->|logs| LOG
    CRS -->|metrics| MON

    style EVT1 fill:#e3f2fd
    style CRS fill:#c8e6c9
    style CRJ fill:#fff3e0
    style STG fill:#e1f5e1
    style LOG fill:#e3f2fd
    style MON fill:#fff3e0
```

**Component Summary:**

| Component | Type | Purpose |
|-----------|------|---------|
| Eventarc Trigger | Trigger | Detects new files in raw/ and chunks/ |
| Cloud Run Service (Processor) | Compute | Single service handles both raw files and chunks via path filtering (autoscaling) |
| Cloud Run Job | Compute | File splitter for large files |
| Staging Bucket | Storage | Processed files in NDJSON format |
| Chunks Bucket | Storage | Split file chunks |
| Cloud Logging | Monitoring | Execution logs & error tracking |
| Cloud Monitoring | Monitoring | Metrics and alerts |

**Architecture Note:** A single Cloud Run service handles both raw/ and chunks/ paths. Path filtering is done in the Flask handler (`main.py` lines 136-149) to route files to the appropriate processing logic.
