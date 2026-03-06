# Phase 2: Component View

```mermaid
graph TB
    subgraph Input["INPUT - Phase 1 Landing Zone"]
        CS[Cloud Storage<br>gs://...-landing/raw/]
    end

    subgraph Trigger["TRIGGER LAYER"]
        EVT1[Eventarc Trigger #1<br>filter: raw/*.json.gz]
        EVT2[Eventarc Trigger #2<br>filter: chunks/*.json.gz]
    end

    subgraph Compute["PROCESSING LAYER - Cloud Run"]
        CRS[Cloud Run Service<br>github-archive-processor<br>Pandas chunked processing<br>0-100 instances autoscaling]
        CRC[Cloud Run Service<br>github-archive-chunk-processor<br>Process chunks in parallel<br>0-100 instances autoscaling]
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
    CHK -->|finalize event| EVT2
    EVT2 --> CRC

    CRS -->|processed| STG
    CRC -->|processed| STG

    CRS -->|logs| LOG
    CRC -->|logs| LOG
    CRS -->|metrics| MON
    CRC -->|metrics| MON

    style EVT1 fill:#e3f2fd
    style EVT2 fill:#e3f2fd
    style CRS fill:#c8e6c9
    style CRC fill:#c8e6c9
    style CRJ fill:#fff3e0
    style STG fill:#e1f5e1
    style LOG fill:#e3f2fd
    style MON fill:#fff3e0
```

**Component Summary:**

| Component | Type | Purpose |
|-----------|------|---------|
| Eventarc Trigger #1 | Trigger | Detects new files in raw/ |
| Eventarc Trigger #2 | Trigger | Detects new chunk files in chunks/ |
| Cloud Run Service (Processor) | Compute | Main processor with Pandas chunked processing (autoscaling) |
| Cloud Run Service (Chunk Processor) | Compute | Chunk processor for parallel processing |
| Cloud Run Job | Compute | File splitter for large files |
| Staging Bucket | Storage | Processed files in NDJSON format |
| Chunks Bucket | Storage | Split file chunks |
| Cloud Logging | Monitoring | Execution logs & error tracking |
| Cloud Monitoring | Monitoring | Metrics and alerts |
