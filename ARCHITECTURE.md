# Architecture Overview

## System Diagram

```
                                    ┌─────────────────────────────────────────────────────────────┐
                                    │                    Google Cloud Project                      │
                                    │                                                                              │
┌───────────────────────────────────│────────────────────────────────────────────────────────────│───────────────────┐
│                                   │                                                                   │               │
│  ┌────────────────────────────┐  │  ┌─────────────────────────────────────────────────────────┐  │               │
│  │    EXTERNAL DATA SOURCES   │  │  │                    CLOUD SCHEDULER                       │  │               │
│  ├────────────────────────────┤  │  ├─────────────────────────────────────────────────────────┤  │               │
│  │  • GitHub Archive          │  │  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │  │               │
│  │    https://data.gharchive. │  │  │  │ GitHub      │  │ HN          │  │ HN User         │ │  │               │
│  │    org/YYYY-MM-DD-HH.json.gz│  │  │  │ Hourly      │  │ 5-min       │  │ Refresh (Daily) │ │  │               │
│  │                            │  │  │  │ (30* * * *) │  │ (*/5 * * *) │  │ (0 2 * * *)      │ │  │               │
│  │  • Hacker News API         │  │  │  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │  │               │
│  │    https://hacker-news.    │  │  │         │                 │                  │         │  │               │
│  │    firebaseio.com/v0/      │  │  │         └─────────────────┴──────────────────┘         │  │               │
│  └──────────────┬─────────────┘  │  └──────────────────────────────┬──────────────────────────┘  │               │
│                 │                 │                                 │                             │               │
│                 │                 └─────────────────────────────────┼─────────────────────────────┘               │
│                 ▼                                                   ▼                                             │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐   │
│  │                               CLOUD RUN JOBS (Batch Processing)                                       │   │
│  │  ┌───────────────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────────┐   │   │
│  │  │ github-archive-processor  │  │ hn-fetcher       │  │ dlq-processor                         │   │   │
│  │  │ (2Gi, 1 CPU, 3600s)       │  │ (512Mi, 1 CPU)  │  │ (256Mi, 0.5 CPU, 300s)              │   │   │
│  │  │                           │  │                  │  │                                      │   │   │
│  │  │ • Parse .json.gz events   │  │ • Poll HN API   │  │ • Retry failed events               │   │   │
│  │  │ • Flatten nested JSON     │  │ • Fetch stories  │  │ • Move to permanent failures        │   │   │
│  │  │ • Load to BigQuery        │  │ • Store to GCS   │  │                                      │   │   │
│  │  │ • Publish errors to DLQ   │  │                  │  │                                      │   │   │
│  │  └───────────┬───────────────┘  └────────┬─────────┘  └──────────────┬───────────────────────┘   │   │
│  │              │                            │                            │                             │   │
│  │              └────────────┬───────────────┴────────────┬─────────────┘                             │   │
│  │                           ▼                               ▼                                       │   │
│  └───────────────────────────┴───────────────────────────────────────────────────────────────────────┘   │
│                                  │                               │                                       │
│                                  ▼                               ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              STORAGE & WAREHOUSE                                                  │  │
│  │  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌──────────────────────────────────┐ │  │
│  │  │   CLOUD STORAGE         │  │      BIGQUERY            │  │        PUB/SUB                   │ │  │
│  │  ├─────────────────────────┤  ├─────────────────────────┤  ├──────────────────────────────────┤ │  │
│  │  │ • {project}-data-pipeline│  │  github_dataset         │  │  pipeline-dlq (Topic)           │ │  │
│  │  │   /github-archive/raw/  │  │    • events (partitioned)│  │  pipeline-dlq-sub (Subscription)│ │  │
│  │  │   /hacker-news/raw/     │  │                          │  │  pipeline-permanent-failures     │ │  │
│  │  │   /errors/              │  │  hacker_news            │  │                                  │ │  │
│  │  │   /dlq/permanent-       │  │    • stories             │  │                                  │ │  │
│  │  │     failures/           │  │    • comments            │  │                                  │ │  │
│  │  └─────────────────────────┘  │    • users               │  └──────────────────────────────────┘ │  │
│  │                                └─────────────────────────┘                                        │  │
│  └───────────────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              MONITORING & ALERTING                                                    │  │
│  │  ┌─────────────────────┐  ┌──────────────────────┐  ┌────────────────────────────────────────┐  │  │
│  │  │ Cloud Monitoring     │  │ Logging & Tracing    │  │ Dashboard                                │  │  │
│  │  │ • Job failures       │  │ • Structured logs     │  │ • Job status                            │  │  │
│  │  │ • DLQ backlog        │  │ • OpenCensus tracing  │  │ • Processing metrics                   │  │  │
│  │  │ • BigQuery errors    │  │ • Error context       │  │ • Alert history                         │  │  │
│  │  └──────────┬──────────┘  └──────────────────────┘  └────────────────────────────────────────┘  │  │
│  │             │                                                                                       │  │
│  │             ▼                                                                                       │  │
│  │  ┌──────────────────────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                        ALERT POLICIES → Email/Webhook                                          │  │  │
│  │  │  • High failure rate (>10 tasks failed)                                                      │  │  │
│  │  │  • DLQ backlog (>100 messages)                                                               │  │  │
│  │  │  • BigQuery load errors (>10% rate)                                                          │  │  │
│  │  └──────────────────────────────────────────────────────────────────────────────────────────────┘  │  │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Data Sources
| Source | Type | Frequency | Size |
|--------|------|-----------|------|
| GitHub Archive | JSON.gz files | Hourly | ~10 GB/day |
| Hacker News API | REST API | Real-time | ~10 MB/day |

### 2. Cloud Run Jobs
| Job | Schedule | Resources | Purpose |
|-----|----------|-----------|---------|
| github-archive-processor | Hourly via Scheduler | 2Gi, 1 CPU | Process GH Archive files |
| hacker-news-fetcher | Every 5 min | 512Mi, 1 CPU | Fetch HN stories/comments |
| hacker-news-processor | On GCS event | 1Gi, 1 CPU | Process HN data to BQ |
| dlq-processor | Every 10 min | 256Mi, 0.5 CPU | Retry failed events |

### 3. Service Accounts
| Service Account | Roles |
|-----------------|-------|
| sa-github-processor | BigQuery DataEditor, Storage ObjectViewer, PubSub Publisher |
| sa-hn-fetcher | Storage ObjectCreator, PubSub Publisher |
| sa-hn-processor | BigQuery DataEditor, Storage ObjectViewer |
| sa-dlq-handler | PubSub Subscriber, Storage ObjectCreator |
| sa-scheduler | CloudScheduler Invoker, Run Invoker |

### 4. Dead Letter Queue
```
Processor fails → Publish to DLQ → DLQ Processor
     │                  │                │
     ▼                  ▼                ▼
 Original Event     Retryable?      Retry or Store
 + Error Context    (max 3x)        to GCS
```

---

## Source Code Structure
```
src/
├── shared/
│   ├── bigquery_emulator_client.py  # BQ client for local/prod
│   ├── retry.py                     # Exponential backoff
│   ├── monitoring.py                # Metrics + structured logging
│   └── storage_client.py            # GCS client wrapper
├── dlq/
│   └── handler.py                   # DLQ publish + processor
├── github_archive/
│   ├── processor.py                 # GH event processing
│   ├── schemas.py                   # BQ table schemas
│   └── main.py                      # Cloud Run entrypoint
├── hacker_news/
│   ├── fetcher.py                   # HN API client
│   ├── processor.py                 # HN data processing
│   └── schemas.py
└── processors/
    └── github_processor.py          # Pandas chunked processing
```

---

## Key Design Decisions

| Decision | Reason |
|----------|--------|
| Cloud Run Jobs vs Services | Jobs are cost-effective for batch (pay only when running) |
| BigQuery Batch Load (FREE) vs Streaming ($50/TB) | Cost optimization for ETL workloads |
| Dead Letter Queue | Reliability - no silent failures, visibility into errors |
| Dedicated Service Accounts | Security - least privilege per service |
| Pub/Sub DLQ over GCS DLQ | Built-in retry policy with exponential backoff |
