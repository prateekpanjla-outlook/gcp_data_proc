# Phase 1: Component View

```mermaid
graph TB
    subgraph Phase1_Components [Phase 1 Components]
        direction TB
        Scheduler[Cloud Scheduler<br/>gcloud scheduler jobs<br/>schedule: 30 * * * *]

        Job[Cloud Run Job<br/>hn-fetcher<br/>Container: Python Flask<br/>Memory: 512Mi<br/>CPU: 1]

        Code[Source Code<br/>src/github_archive/main.py<br/>download_github_archive()<br/>Lines: 127-176]

        Storage[Cloud Storage<br/>Bucket: {project}-data-pipeline<br/>Path: github-archive/raw/]

        External[External<br/>GitHub Archive<br/>https://data.gharchive.org/]
    end

    External -.->|HTTP GET| Job
    Scheduler -.->|Scheduled Trigger| Job
    Job -.->|Uploads| Storage
    Code -.->|Implements| Job

    style Scheduler fill:#e3f2fd
    style Job fill:#bbdefb
    style Storage fill:#c8e6c9
    style External fill:#ffe0b2
```
