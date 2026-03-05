# Phase 2: Detailed Sequence Diagram

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E as Eventarc
    participant P as Pub/Sub
    participant CRS as Cloud Run Service
    participant CRJ as Cloud Run Job
    participant FS as Firestore
    participant STG as Staging Bucket
    participant DLQ as DLQ Bucket

    Note over S: File lands: 2026-03-05-12.json.gz
    S->>E: finalize event

    E->>P: Publish to event topic
    P->>CRS: HTTP POST /process

    CRS->>CRS: Parse event payload
    CRS->>S: Get file metadata

    alt File size < 500MB
        CRS->>S: Download file
        CRS->>CRS: Stream read line by line

        loop For each line
            CRS->>CRS: Validate JSON
            CRS->>CRS: Validate schema (Pydantic)
            CRS->>CRS: Transform & flatten
        end

        CRS->>STG: Upload processed .ndjson.gz
        CRS->>FS: Mark complete

    else File size >= 500MB
        CRS->>CRJ: Execute file-splitter job

        CRJ->>S: Download file to /tmp
        Note over CRJ: Stream read, split into chunks

        loop For each chunk (10K lines)
            CRJ->>S: Upload chunk to chunks/
            CRJ->>FS: Create chunk document
            CRJ->>P: Publish chunk event
        end

        CRJ->>S: Delete original file

        Note over P: N chunk events published

        loop For each chunk event
            P->>CRS: HTTP POST /process-chunk
            CRS->>S: Download chunk
            CRS->>CRS: Process chunk (validate, transform)
            CRS->>STG: Upload chunk output
            CRS->>FS: Update chunk status
        end

        CRS->>FS: Check all chunks done
        Note over FS: All chunks complete
        CRS->>CRS: Trigger BigQuery load
    end

    alt Validation errors
        CRS->>DLQ: Move to DLQ
    end

    CRS->>P: ACK completion
```

**Sequence Notes:**
- Small files processed directly in single request
- Large files split first, then processed in parallel
- Each chunk processed independently (autoscaling)
- Firestore tracks progress for large files
