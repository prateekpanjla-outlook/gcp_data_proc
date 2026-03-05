# Phase 2: Data Flow Transformation

```mermaid
flowchart LR
    subgraph Input["INPUT FORMAT"]
        IN1[GitHub Archive<br>.json.gz]
        IN2[One JSON object per line<br>~142,000 lines]
        IN3[Nested JSON structure<br>actor: {id, login,...}<br>repo: {id, name,...}<br>payload: {...}]
    end

    subgraph Process["PROCESSING"]
        V1[Layer 1: File Validation<br>extension, size, gzip]
        V2[Layer 2: Line Validation<br>valid JSON, required fields]
        V3[Layer 3: Schema Validation<br>Pydantic models]
        V4[Layer 4: Transform<br>flatten nested objects]
    end

    subgraph Output["OUTPUT FORMAT"]
        OUT1[Processed File<br>.ndjson.gz]
        OUT2[One JSON object per line<br>~142,000 lines]
        OUT3[Flattened JSON structure<br>event_id, event_type, created_at<br>actor_id, actor_login<br>repo_id, repo_name<br>payload_ref, payload_push_id,...]
    end

    IN1 --> V1
    IN2 --> V2
    IN3 --> V3
    V1 --> V2
    V2 --> V3
    V3 --> V4
    V4 --> OUT1
    OUT2
    OUT3

    style Input fill:#ffe0b2
    style Process fill:#e1f5e1
    style Output fill:#c8e6c9
```

**Input vs Output Schema Comparison:**

| Aspect | Input (GitHub Archive) | Output (Staging) |
|--------|------------------------|------------------|
| **Format** | JSON.gz (newline-delimited) | NDJSON.gz (newline-delimited) |
| **Structure** | Nested JSON | Flattened JSON |
| **Sample Input** | `{"id":"123","type":"PushEvent","actor":{"id":456,"login":"octocat"},...}` | `{"event_id":"123","event_type":"PushEvent","actor_id":456,"actor_login":"octocat",...}` |
| **Fields** | ~20 nested | ~50 flattened |
| **Timestamp** | ISO string | ISO string (validated) |
| **Purpose** | Raw archive format | BigQuery ready |
