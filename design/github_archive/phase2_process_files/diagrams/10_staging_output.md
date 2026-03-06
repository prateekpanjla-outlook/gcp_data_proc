# Phase 2: Staging Output Preparation

```mermaid
graph TD
    Proc([Processing Complete]) --> Out["Output File<br>gs://...-staging/processed/{file}.ndjson.gz"]

    Out --> Stored([File Stored in Staging Bucket])

    Stored --> Log[Log success<br>Update metrics]

    Log --> Complete([Processing Complete])

    style Out fill:#c8e6c9
    style Stored fill:#c8e6c9
    style Complete fill:#c8e6c9
```

**Key Design Decision:** Phase 2 writes processed files to staging bucket in NDJSON format. This is the output of Phase 2 - validated, transformed data ready for downstream consumption.

**Output Format for Staging:**

```json
// Input: gs://landing/raw/2026-03-05-12.json.gz (nested JSON)
{
  "id": "1234567890",
  "type": "PushEvent",
  "created_at": "2026-03-05T12:34:56Z",
  "actor": {
    "id": 12345,
    "login": "octocat",
    "avatar_url": "https://...",
    "gravatar_id": "",
    "url": "https://api.github.com/users/octocat",
    "type": "User"
  },
  "repo": {
    "id": 67890,
    "name": "octocat/Hello-World",
    "url": "https://api.github.com/repos/octocat/Hello-World"
  },
  "payload": {
    "ref": "refs/heads/main",
    "push_id": 987654321,
    "size": 123,
    "distinct_size": 45,
    "head": "abc123...",
    "before": "def456..."
  },
  "public": true,
  "created_at": "2026-03-05T12:34:56Z"
}

// Output: gs://staging/processed/2026-03-05-12.ndjson.gz (flattened NDJSON)
{"event_id":"1234567890","event_type":"PushEvent","created_at":"2026-03-05T12:34:56Z","actor_id":12345,"actor_login":"octocat","actor_avatar_url":"https://...","actor_gravatar_id":"","actor_url":"https://api.github.com/users/octocat","actor_type":"User","repo_id":67890,"repo_name":"octocat/Hello-World","repo_url":"https://api.github.com/repos/octocat/Hello-World","public":true,"payload_ref":"refs/heads/main","payload_push_id":987654321,"payload_size":123,"payload_distinct_size":45,"payload_head":"abc123...","payload_before":"def456..."}
```

**Processing Timing:**

```mermaid
graph LR
    subgraph Chunks["File Chunks"]
        C1["Chunk 1<br>Processing"]
        C2["Chunk 2<br>Processing"]
        C3["Chunk 3<br>Processing"]
    end

    subgraph Staging["Staging Output"]
        S1["Write Chunk 1<br>t=0s"]
        S2["Write Chunk 2<br>t=30s"]
        S3["Write Chunk 3<br>t=45s"]
    end

    C1 -->|complete| S1
    C2 -->|complete| S2
    C3 -->|complete| S3

    style S1 fill:#c8e6c9
    style S2 fill:#c8e6c9
    style S3 fill:#c8e6c9
```

**Benefits of NDJSON Staging Output:**

| Benefit | Description |
|---------|-------------|
| **Validation complete** | All data validated and transformed |
| **Debugging** | Inspect staged files for quality checks |
| **Schema evolution** | Output format supports additive fields |
| **Better resilience** | Processed data persists for downstream consumers |
| **Format flexibility** | NDJSON can be consumed by various systems |
