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
    FileAction --> LogFile[Log error<br>Mark as failed]
    LogFile --> EndFile([❌ File Failed])

    LineErr --> LineAction[Skip line<br>Count error<br>Continue processing]
    LineAction --> LogLine[Increment error counter]
    LogLine --> CheckRate{Error rate > 10%?}
    CheckRate -->|Yes| Abort[Abort processing<br>Move to DLQ]
    CheckRate -->|No| ContinueLine([Continue next line])
    Abort --> DLQ

    SchemaErr --> Retry{Retry count < 3?}
    BizErr --> Retry
    SysErr --> Retry

    Retry -->|Yes| Wait[Wait: 2^n seconds<br>exponential backoff]
    Wait --> RetryLoop[Retry processing]
    RetryLoop --> Check

    Retry -->|No| DLQ[Move to DLQ<br>gs://.../dlq/events/]
    DLQ --> LogDLQ[Log failure details]
    LogDLQ --> CheckFatal{Fatal error?}

    CheckFatal -->|Yes| Permanent[Move to<br>dlq/permanent/]
    CheckFatal -->|No| ScheduleRetry[Schedule DLQ processor<br>retry in 10 min]

    Permanent --> EndPerm([❌ Permanent Failure])
    ScheduleRetry --> EndRetry([⏳ Scheduled Retry])

    style FileErr fill:#ffebee
    style LineErr fill:#fff3e0
    style SchemaErr fill:#ffe0b2
    style BizErr fill:#e1f5fe
    style SysErr fill:#f3e5f5
    style DLQ fill:#fff3e0
    style Permanent fill:#ffebee
```

**Error Categories:**

| Category | Retry? | Destination | Example |
|----------|--------|-------------|---------|
| **File corrupted** | No | `invalid-files/` | Bad gzip, wrong format |
| **Line malformed** | No | Skip, log | Invalid JSON |
| **Schema error** | Yes (3x) | `dlq/events/` | Missing required field |
| **Business rule** | Yes (3x) | `dlq/events/` | Invalid event type |
| **Transient** | Yes (3x) | `dlq/events/` | Network timeout |
| **Permanent** | No | `dlq/permanent/` | Invalid data structure |

**DLQ Processor:**

```mermaid
graph LR
    DLQ[DLQ Topic] --> Processor[DLQ Processor<br>Cloud Run Job]
    Processor --> Analyze[Analyze error]

    Analyze --> Transient{Transient?}
    Transient -->|Yes| Retry[Retry with backoff]
    Transient -->|No| Permanent[Move to permanent/]

    Retry --> Success{Success?}
    Success -->|Yes| Staging[Send to staging]
    Success -->|No| MaxRetry{Max retries?}
    MaxRetry -->|< 3| Retry
    MaxRetry -->|>= 3| Permanent

    Permanent --> Alert[Alert team]
```
