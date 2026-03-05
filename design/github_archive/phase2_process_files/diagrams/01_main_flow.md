# Phase 2: Main Flow Diagram

```mermaid
graph TD
    Start([Phase 2 Start]) --> Input["Input File<br>gs://landing/raw/{YYYY-MM-DD-HH}.json.gz"]

    Input --> EventArc[Eventarc Trigger<br>finalize event on raw/]

    EventArc --> CR[Cloud Run Service<br>github-archive-processor]

    CR --> SizeCheck{File Size<br>Check}

    SizeCheck -->|< 500MB| Direct[Direct Processing<br>process_file_chunked]
    SizeCheck -->|>= 500MB| Split[File Splitting<br>file_splitter Job]

    Split --> Chunks["Create Chunks<br>raw/chunks/{file}-chunk-{N}.json.gz"]
    Chunks --> ChunkEvents[Pub/Sub Events<br>for each chunk]
    ChunkEvents --> ChunkProcess[process_chunk<br>for each event]

    Direct --> Validate[Schema Validation<br>Pandas Chunked Processing]
    ChunkProcess --> Validate

    Validate --> Valid{Valid?}
    Valid -->|Yes| Transform[Transform & Flatten<br>Vectorized Operations]
    Valid -->|No| LogErr[Log Error<br>Continue processing]

    Transform --> Output[Output: NDJSON<br>Compressed with gzip]
    Output --> Stage["Stage File<br>gs://staging/processed/{file}.ndjson.gz"]

    Stage --> BQLoad[Trigger BigQuery Load<br>per file/chunk]
    BQLoad --> Success([✅ Phase 2 Complete])

    LogErr --> LogWrite[Write to Cloud Logging]
    LogWrite --> Monitor[Cloud Monitoring Alert]

    style Start fill:#e1f5e1
    style Success fill:#e1f5e1
    style LogErr fill:#fff3e0
    style Validate fill:#e3f2fd
    style BQLoad fill:#c8e6c9
```

**Note:** Phase 2 processes files from Phase 1 landing zone and outputs to staging zone ready for BigQuery loading. Uses Pandas with chunked processing for memory-efficient validation. Each file/chunk triggers BigQuery load immediately upon completion - no state tracking needed.
