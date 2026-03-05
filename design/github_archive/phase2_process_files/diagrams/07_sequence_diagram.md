# Phase 2: Detailed Sequence Diagram

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E as Eventarc
    participant P as Pub/Sub
    participant CRS as Cloud Run Service
    participant CRJ as Cloud Run Job
    participant STG as Staging Bucket
    participant BQ as BigQuery
    participant LOG as Cloud Logging

    Note over S: File lands: 2026-03-05-12.json.gz
    S->>E: finalize event

    E->>P: Publish to event topic
    P->>CRS: HTTP POST /process

    CRS->>CRS: Parse event payload
    CRS->>S: Get file metadata

    alt File size < 500MB
        CRS->>S: Download file
        CRS->>CRS: Pandas chunked processing<br/>chunksize=100K

        loop For each chunk (100K records)
            CRS->>CRS: Parse JSON (pd.read_json)
            CRS->>CRS: Validate dtypes (vectorized)
            CRS->>CRS: Validate values (vectorized)
            CRS->>CRS: Transform & flatten (vectorized)
            CRS->>STG: Write chunk output immediately
        end

        CRS->>BQ: Trigger BigQuery load
        CRS->>LOG: Log completion

    else File size >= 500MB
        CRS->>CRJ: Execute file-splitter job

        CRJ->>S: Download file to /tmp
        Note over CRJ: Stream read, split into chunks

        loop For each chunk (10K lines)
            CRJ->>S: Upload chunk to chunks/
            CRJ->>P: Publish chunk event
        end

        CRJ->>S: Delete original file
        CRJ->>LOG: Log split complete

        Note over P: N chunk events published

        loop For each chunk event
            P->>CRS: HTTP POST /process-chunk
            CRS->>S: Download chunk
            CRS->>CRS: Process chunk with Pandas<br/>validate dtypes + values (vectorized)
            CRS->>STG: Upload chunk output
            CRS->>BQ: Trigger BigQuery load (per chunk)
            CRS->>LOG: Log chunk completion
        end
    end

    alt Validation errors
        CRS->>LOG: Log error details
        CRS->>LOG: Increment error counter
    end

    CRS->>P: ACK completion
```

**Sequence Notes:**
- Small files processed directly in single request
- Large files split first, then processed in parallel via Pub/Sub
- Each chunk triggers BigQuery load immediately upon completion (no state tracking)
- All errors logged to Cloud Logging with monitoring alerts
