# Phase 2: Error Handling Flow

```mermaid
graph TD
    Start([Processing Event]) --> Check{Error Type?}

    Check -->|File corrupted| FileErr[File-Level Error]
    Check -->|Invalid JSON line| LineErr[Line-Level Error]
    Check -->|Schema violation| SchemaErr[Schema Error]
    Check -->|Business rule| BizErr[Business Rule Error]
    Check -->|System failure| SysErr[System Error]

    FileErr --> FileAction[Move entire file<br>to invalid-files/]
    FileAction --> LogFile[Log error details]
    LogFile --> AlertFile[Cloud Monitoring Alert]
    AlertFile --> EndFile([File Failed])

    LineErr --> LineAction[Skip line<br>Count error<br>Continue processing]
    LineAction --> LogLine[Increment error counter]
    LogLine --> CheckRate{Error rate > 10%?}
    CheckRate -->|Yes| Abort[Abort processing<br>Log critical error]
    CheckRate -->|No| ContinueLine([Continue next line])
    Abort --> AlertRate[Alert team]
    AlertRate --> EndAbort([Processing Aborted])

    SchemaErr --> LogSchema[Log schema violation<br>Continue with valid records]
    BizErr --> LogBiz[Log business rule violation<br>Continue with valid records]
    SysErr --> LogSys[Log system error<br>Continue processing]

    LogSchema --> ContinueSchema([Continue processing])
    LogBiz --> ContinueBiz([Continue processing])
    LogSys --> ContinueSys([Continue processing])

    style FileErr fill:#ffebee
    style LineErr fill:#fff3e0
    style SchemaErr fill:#ffe0b2
    style BizErr fill:#e1f5fe
    style SysErr fill:#f3e5f5
    style LogFile fill:#e3f2fd
    style LogLine fill:#e3f2fd
    style LogSchema fill:#e3f2fd
    style LogBiz fill:#e3f2fd
    style LogSys fill:#e3f2fd
```

**Error Categories:**

| Category | Action | Logging | Example |
|----------|--------|---------|---------|
| **File corrupted** | Move to `invalid-files/` | ERROR level | Bad gzip, wrong format |
| **Line malformed** | Skip line, continue | WARN level + counter | Invalid JSON |
| **Schema violation** | Skip record, continue | WARN level + counter | Missing required field |
| **Business rule** | Skip record, continue | WARN level + counter | Invalid event type |
| **System error** | Log, continue | ERROR level | Network timeout (non-fatal) |
| **High error rate** | Abort processing | CRITICAL + alert | >10% errors |

**Logging Strategy:**

```mermaid
graph LR
    subgraph Logs["Cloud Logging"]
        ERR[Error Log Entry]
        MET[Metrics & Counters]
    end

    subgraph Alerts["Cloud Monitoring"]
        POL[Error Rate Policy]
        CRT[Critical Error Policy]
    end

    ERR --> POL
    MET --> POL
    CRT --> Notify[Email/PagerDuty]

    style Logs fill:#e3f2fd
    style Alerts fill:#fff3e0
```

**Log Entry Structure:**

```json
{
  "severity": "ERROR",
  "logName": "projects/my-project/logs/github-archive-processor",
  "resource": {
    "type": "cloud_run_revision",
    "labels": {
      "service_name": "github-archive-processor",
      "revision_name": "github-archive-processor-0001"
    }
  },
  "protoPayload": {
    "@type": "type.googleapis.com/google.logging.audit"
  },
  "jsonPayload": {
    "file": "2026-03-05-12.json.gz",
    "error_type": "schema_violation",
    "message": "Missing required field: actor.id",
    "line_number": 12345,
    "record_id": "9876543210",
    "error_count": 1
  }
}
```
