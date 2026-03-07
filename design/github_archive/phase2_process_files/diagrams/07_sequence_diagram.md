# Phase 2: Detailed Sequence Diagram

```mermaid
sequenceDiagram
    participant S as Cloud Storage
    participant E as Eventarc Trigger
    participant CR as Cloud Run Service<br>github-archive-processor
    participant CRJ as Cloud Run Job<br>File Splitter
    participant STG as Staging Bucket
    participant LOG as Cloud Logging

    Note over S: File lands: 2026-03-05-12.json.gz
    S->>E: finalize event

    E->>CR: HTTP POST /

    CR->>CR: Parse event payload
    CR->>CR: Path filtering: check /raw/ or /chunks/
    CR->>S: Get file metadata

    alt File size < 500MB
        CR->>S: Download file
        CR->>CR: Pandas chunked processing<br>chunksize=100K

        loop For each chunk (100K records)
            CR->>CR: Parse JSON (pd.read_json)
            CR->>CR: Validate dtypes (vectorized)
            CR->>CR: Validate values (vectorized)
            CR->>CR: Transform & flatten (vectorized)
            CR->>STG: Write chunk output immediately
        end

        CR->>LOG: Log completion

    else File size >= 500MB
        CR->>CRJ: Execute file-splitter job

        CRJ->>S: Download file to /tmp
        Note over CRJ: Stream read, split into chunks

        loop For each chunk (10K lines)
            CRJ->>S: Upload chunk to chunks/<br>filename: ...-chunk-001.json.gz
            Note over S: Cloud Storage emits<br>finalize event automatically
        end

        CRJ->>S: Delete original file
        CRJ->>LOG: Log split complete

        Note over E: N chunk finalize events

        loop For each chunk event
            S->>E: finalize event
            E->>CR: HTTP POST /

            CR->>CR: Path filtering: /chunks/ detected
            CR->>S: Download chunk
            CR->>CR: Process chunk with Pandas<br>validate dtypes + values (vectorized)
            CR->>STG: Upload chunk output
            CR->>LOG: Log chunk completion
        end
    end

    alt Validation errors
        CR->>LOG: Log error details
        CR->>LOG: Increment error counter
    end
```

**Sequence Notes:**
- Single Cloud Run service handles both raw files and chunks via path filtering
- Small files processed directly in single request
- Large files split first, then each chunk triggers processing via direct events
- Phase 2 ends when validated data is written to staging bucket in NDJSON format
- All errors logged to Cloud Logging with monitoring alerts
- **No Pub/Sub costs** - all triggers use direct events from Cloud Storage
