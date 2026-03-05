# Phase 1: Data Flow Sequence Diagram (gsutil streaming)

```mermaid
sequenceDiagram
    participant S as Cloud Scheduler
    participant J as Cloud Run Job<br>(github-archive-downloader)
    participant G as GitHub Archive<br>(data.gharchive.org)
    participant B as Cloud Storage

    Note over S: Every hour at :30 minutes past
    S->>J: HTTP POST /run<br>(scheduled trigger)

    Note over J: Step 1: Calculate Filename
    J->>J: target_time = now() - 1 hour<br>filename = "2025-01-15-14.json.gz"

    Note over J: Step 2: Build URL
    J->>J: url = "https://data.gharchive.org/2025-01-15-14.json.gz"

    Note over J, B: Step 3: Check if File Exists
    J->>B: gsutil stat gs://bucket/github-archive/raw/{filename}
    B-->>J: File Not Found

    Note over J, G, B: Step 4: Stream Download (curl | gsutil cp -)
    J->>G: curl {url} | gsutil cp - gs://bucket/...
    Note over J, G, B: Data streams directly (~50MB memory)
    G-->>B: Streaming data transfer
    B-->>J: Upload Complete

    Note over J: Step 5: Verify Upload
    J->>B: gsutil du {gcs_path}
    B-->>J: File Size: 123456789 bytes

    J->>S: Return 200 OK<br>{"filename": "...", "size": ..., "status": "success"}

    Note over B: finalize event emitted → Phase 2 Processing
```

**Note:** Using `curl | gsutil cp -` for direct streaming from GitHub Archive to GCS. gsutil does not support HTTP URLs directly. No intermediate validation - Phase 2 handles validation during processing.
