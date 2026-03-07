# Phase 2: Error Handling Flow

```mermaid
graph TD
    Start([Processing Event]) --> Check{Error Type?}

    Check -->|File corrupted| FileErr[File-Level Error]
    Check -->|Invalid JSON line| LineErr[Line-Level Error]
    Check -->|Schema violation| SchemaErr[Schema Error]
    Check -->|Business rule| BizErr[Business Rule Error]
    Check -->|System failure| SysErr[System Error]

    FileErr --> FileAction[Log error<br>Return failure status]
    FileAction --> LogFile[Log to Cloud Logging]
    LogFile --> EndFile([File Failed])

    LineErr --> LineAction[Skip line<br>Count error<br>Continue processing]
    LineAction --> LogLine[Increment error counter]
    LogLine --> ContinueLine([Continue next line/chunk])

    SchemaErr --> LogSchema[Log schema violation<br>Continue with valid records]
    BizErr --> LogBiz[Log business rule violation<br>Continue with valid records]
    SysErr --> LogSys[Log system error<br>Continue or fail]

    LogSchema --> ContinueSchema([Continue processing])
    LogBiz --> ContinueBiz([Continue processing])
    LogSys --> ContinueSys([Continue processing])

    ContinueLine --> AllDone{All chunks<br>processed?}
    ContinueSchema --> AllDone
    ContinueBiz --> AllDone
    ContinueSys --> AllDone

    AllDone -->|Yes| FinalCheck[Calculate error rate<br>Determine success]
    FinalCheck --> FinalRate{Error rate >= 10%?}
    FinalRate -->|Yes| FailResult[success=False<br>Return with error count]
    FinalRate -->|No| SuccessResult[success=True<br>Return with metrics]
    FailResult --> EndFail([Processing Complete<br>With errors])
    SuccessResult --> EndSuccess([Processing Complete<br>Success])

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
    style FinalCheck fill:#e1f5e1
    style EndSuccess fill:#c8e6c9
    style EndFail fill:#fff3e0
```

**Error Categories:**

| Category | Action | Logging | Example |
|----------|--------|---------|---------|
| **File corrupted** | Log error, return failure immediately | ERROR level | Bad gzip, wrong format |
| **Line malformed** | Skip line, count error, continue | WARN level + counter | Invalid JSON |
| **Schema violation** | Skip record, count error, continue | WARN level + counter | Missing required field |
| **Business rule** | Skip record, count error, continue | WARN level + counter | Future timestamp |
| **System error** | Log error, may fail or continue | ERROR level | Network timeout |
| **High error rate** | Set `success=False` at END | ERROR + metrics | Errors ≥ 10% of records |

**Important:** Error rate is calculated **after all chunks are processed**. Processing never aborts early based on error rate - all records are processed, then success is determined.

**Success Criteria** ([file_processor.py:328-331](../../../src/github_archive/phase2_process_files/processors/file_processor.py)):
```python
success = (
    total_records_out > 0 and
    (total_errors == 0 or total_errors / total_records_in < 0.1)  # < 10% error rate
)
```

**Note:** No DLQ (Dead Letter Queue) is implemented. All errors are logged to Cloud Logging for monitoring and alerting via Cloud Monitoring.

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
