# Phase 2: BigQuery Load Preparation

```mermaid
graph TD
    Proc([Processing Complete]) --> Out["Output File<br>gs://...-staging/processed/{file}.ndjson.gz"]

    Out --> FileType{File Type}

    FileType -->|Small file| SingleLoad[Load immediately]
    FileType -->|Chunk| ChunkLoad[Load immediately]

    SingleLoad --> BQLoad[BigQuery Load Job<br>Phase 3]
    ChunkLoad --> BQLoad

    BQLoad --> BQ[BigQuery Table<br>github_dataset.events]

    BQ --> Verify{Load Success?}

    Verify -->|Yes| Log[Log success<br>Update metrics]
    Verify -->|No| RetryLoad[Retry load<br>up to 3 times]

    RetryLoad --> Verify

    Log --> Complete([✅ Chunk Loaded])

    style SingleLoad fill:#c8e6c9
    style ChunkLoad fill:#c8e6c9
    style BQ fill:#e1f5e1
    style Complete fill:#c8e6c9
```

**Key Design Decision:** Each file/chunk triggers BigQuery load immediately upon completion. No state tracking or coordination needed - BigQuery handles concurrent loads gracefully.

**Output Format for BigQuery:**

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

**BigQuery Load Command (Phase 3):**

```bash
# Single file or single chunk - triggered immediately
bq load --source_format=NEWLINE_DELIMITED_JSON \
  --field_delimiter="\n" \
  --write_disposition=WRITE_APPEND \
  project:github_dataset.events \
  gs://...-staging/processed/2026-03-05-12.ndjson.gz

# Each chunk loaded independently (no wildcard needed)
# Example: 2026-03-05-12-chunk-001.ndjson.gz
# Example: 2026-03-05-12-chunk-002.ndjson.gz
# Example: 2026-03-05-12-chunk-003.ndjson.gz
# Each triggers its own load job upon completion
```

**Load Timing:**

```mermaid
graph LR
    subgraph Chunks["File Chunks"]
        C1["Chunk 1<br>Processing"]
        C2["Chunk 2<br>Processing"]
        C3["Chunk 3<br>Processing"]
    end

    subgraph Loads["BigQuery Loads"]
        L1["Load Chunk 1<br>t=0s"]
        L2["Load Chunk 2<br>t=30s"]
        L3["Load Chunk 3<br>t=45s"]
    end

    C1 -->|complete| L1
    C2 -->|complete| L2
    C3 -->|complete| L3

    style L1 fill:#c8e6c9
    style L2 fill:#c8e6c9
    style L3 fill:#c8e6c9
```

**Benefits of Per-Chunk Loading:**

| Benefit | Description |
|---------|-------------|
| **No coordination** | No need to track when all chunks are complete |
| **Immediate availability** | Data available in BigQuery as soon as each chunk finishes |
| **Parallel loads** | BigQuery handles multiple concurrent load jobs |
| **Simpler code** | No state management, no Firestore, no completion checks |
| **Better resilience** | If one chunk fails, others still load successfully |
