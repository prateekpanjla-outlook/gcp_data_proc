# Phase 2: Detailed Sequence Diagram

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E1 as Eventarc Trigger #1
    participant CRS as Cloud Run Service<br>Processor
    participant CRJ as Cloud Run Job<br>File Splitter
    participant E2 as Eventarc Trigger #2
    participant CRC as Cloud Run Service<br>Chunk Processor
    participant STG as Staging Bucket
    participant LOG as Cloud Logging

    Note over S: File lands: 2026-03-05-12.json.gz
    S->>E1: finalize event

    E1->>CRS: HTTP POST /

    CRS->>CRS: Parse event payload
    CRS->>S: Get file metadata

    alt File size < 500MB
        CRS->>S: Download file
        CRS->>CRS: Pandas chunked processing<br>chunksize=100K

        loop For each chunk (100K records)
            CRS->>CRS: Parse JSON (pd.read_json)
            CRS->>CRS: Validate dtypes (vectorized)
            CRS->>CRS: Validate values (vectorized)
            CRS->>CRS: Transform & flatten (vectorized)
            CRS->>STG: Write chunk output immediately
        end

        CRS->>LOG: Log completion

    else File size >= 500MB
        CRS->>CRJ: Execute file-splitter job

        CRJ->>S: Download file to /tmp
        Note over CRJ: Stream read, split into chunks

        loop For each chunk (10K lines)
            CRJ->>S: Upload chunk to chunks/<br>filename: ...-chunk-001-of-012-10000.json.gz
            Note over S: Cloud Storage emits<br>finalize event automatically
        end

        CRJ->>S: Delete original file
        CRJ->>LOG: Log split complete

        Note over E2: N chunk finalize events

        loop For each chunk event
            S->>E2: finalize event
            E2->>CRC: HTTP POST /

            CRC->>CRC: Parse filename for metadata<br>- Chunk number<br>- Total chunks<br>- Event count
            CRC->>S: Download chunk
            CRC->>CRC: Process chunk with Pandas<br>validate dtypes + values (vectorized)
            CRC->>STG: Upload chunk output
            CRC->>LOG: Log chunk completion
        end
    end

    alt Validation errors
        CRS->>LOG: Log error details
        CRS->>LOG: Increment error counter
        CRC->>LOG: Log error details
    end
```

**Sequence Notes:**
- Small files processed directly in single request
- Large files split first, then each chunk triggers processing via direct events
- Phase 2 ends when validated data is written to staging bucket in NDJSON format
- All errors logged to Cloud Logging with monitoring alerts
- **No Pub/Sub costs** - all triggers use direct events from Cloud Storage
