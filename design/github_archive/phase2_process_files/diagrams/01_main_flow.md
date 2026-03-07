# Phase 2: Main Flow Diagram

```mermaid
graph TD
    Start([Phase 2 Start]) --> Input["Input File<br>gs://landing/raw/{YYYY-MM-DD-HH}.json.gz"]

    Input --> EventArc[Eventarc Trigger<br>finalize event]

    EventArc --> CR[Cloud Run Service<br>github-archive-processor<br>Path filtering: raw/ or chunks/]

    CR --> SizeCheck{File Size<br>Check}

    SizeCheck -->|< 500MB| Direct[Direct Processing<br>process_file_chunked]
    SizeCheck -->|>= 500MB| Split[File Splitting<br>file_splitter Job]

    Split --> Chunks["Create Chunks<br>landing/chunks/{file}-chunk-{N:03d}.json.gz"]
    Chunks --> ChunkEvents[Eventarc Trigger<br>finalize event on chunks/]
    ChunkEvents --> ChunkProcess[process_chunk<br>for each chunk]

    Direct --> Validate[Schema Validation<br>Pandas Chunked Processing]
    ChunkProcess --> Validate

    Validate --> Valid{Valid?}
    Valid -->|Yes| Transform[Transform & Flatten<br>Vectorized Operations]
    Valid -->|No| LogErr[Log Error<br>Continue processing]

    Transform --> Output[Output: NDJSON<br>Compressed with gzip]
    Output --> Stage["Stage File<br>gs://staging/processed/{file}.ndjson.gz"]

    Stage --> Success([Phase 2 Complete<br>Staged for downstream])

    LogErr --> LogWrite[Write to Cloud Logging]
    LogWrite --> Monitor[Cloud Monitoring Alert]

    style Start fill:#e1f5e1
    style Success fill:#c8e6c9
    style LogErr fill:#fff3e0
    style Validate fill:#e3f2fd
    style Stage fill:#c8e6c9
```

**Note:** Phase 2 processes files from Phase 1 landing zone and outputs to staging zone in NDJSON format. Uses Pandas with chunked processing for memory-efficient validation. Uses **single Cloud Run service** with path filtering for both raw/ and chunks/ files - no Pub/Sub costs.
