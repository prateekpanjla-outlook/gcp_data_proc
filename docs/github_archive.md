# GitHub Archive Data Source

## Overview

GitHub Archive is a project that records the public GitHub timeline, archiving over 400 million GitHub events since 2011.

## Access Details

| Property | Value |
|----------|-------|
| **Base URL** | `https://data.gharchive.org/` |
| **Authentication** | None required |
| **Rate Limit** | None |
| **File Format** | JSON.gz |
| **Update Frequency** | Hourly |
| **Historical Data** | From February 2011 |

## File Naming Convention

```
https://data.gharchive.org/{year}-{month}-{day}-{hour}.json.gz
```

Example:
- `https://data.gharchive.org/2025-01-15-14.json.gz` (January 15, 2025, 14:00 UTC)

## Event Types

GitHub Archive contains 18+ event types. Each event type has different payload structures.

| Event Type | Description | Payload Complexity |
|------------|-------------|-------------------|
| `PushEvent` | Code pushed to a repository | High (commits array) |
| `CreateEvent` | Branch/tag/repository created | Medium |
| `DeleteEvent` | Branch/tag deleted | Low |
| `WatchEvent` | User starred a repository | Low |
| `IssuesEvent` | Issue opened/closed/reopened | Medium |
| `IssueCommentEvent` | Comment on issue | Medium |
| `PullRequestEvent` | PR opened/closed/synchronized | High |
| `PullRequestReviewEvent` | PR review submitted | High |
| `ForkEvent` | Repository forked | Medium |
| `ReleaseEvent` | Release published | High |

## Sample Event Structure

### PushEvent (Most Common)
```json
{
  "id": "1234567890",
  "type": "PushEvent",
  "actor": {
    "id": 12345,
    "login": "username",
    "display_login": "Username",
    "gravatar_id": "",
    "url": "https://api.github.com/users/username",
    "avatar_url": "https://avatars.githubusercontent.com/u/12345?"
  },
  "repo": {
    "id": 12345678,
    "name": "user/repo",
    "url": "https://api.github.com/repos/user/repo"
  },
  "payload": {
    "push_id": 1234567890,
    "size": 3,
    "distinct_size": 2,
    "ref": "refs/heads/main",
    "head": "abc123def456...",
    "before": "def456abc123...",
    "commits": [
      {
        "sha": "abc123...",
        "author": {
          "email": "user@example.com",
          "name": "User Name"
        },
        "message": "Commit message",
        "distinct": true,
        "url": "https://github.com/user/repo/commit/abc123..."
      }
    ]
  },
  "public": true,
  "created_at": "2025-01-15T14:30:00Z"
}
```

## Processing Strategy

### Cloud Storage Ingestion

Two approaches for ingesting GitHub Archive data:

#### Option 1: Scheduled Download (Recommended for Demo)
Create a Cloud Scheduler job that downloads hourly files to Cloud Storage.

```bash
# Download script template
gsutil cp https://data.gharchive.org/$(date -u +%Y-%m-%d-%H).json.gz \
    gs://YOUR_BUCKET/github-archive/raw/
```

#### Option 2: Direct Eventarc via Pub/Sub
Use Cloud Workflows to fetch and push to a Pub/Sub topic that triggers Cloud Run.

### Processing Pipeline

```
┌──────────────────────┐
┌──────────────────────┤
│  gs://bucket/github- │
│  archive/raw/*.json.gz│
└──────────┬───────────┘
           │ Eventarc Trigger (Finalize)
           ▼
┌──────────────────────────────────────┐
│ Cloud Run: GitHub Archive Processor  │
│ 1. Decompress JSON.gz                │
│ 2. Parse JSON lines                   │
│ 3. Flatten nested structures         │
│ 4. Validate schema                   │
│ 5. Transform to BigQuery format      │
└──────────┬───────────────────────────┘
           │ BigQuery Streaming API
           ▼
┌──────────────────────────────────────┐
│ BigQuery: github_dataset.events      │
│ - Table partitioned by event_date    │
│ - Clustered by event_type, repo_id   │
└──────────────────────────────────────┘
```

## BigQuery Schema Design

### Main Events Table

| Field | Type | Mode | Description |
|-------|------|------|-------------|
| event_id | STRING | REQUIRED | Unique event identifier |
| event_type | STRING | REQUIRED | Type of GitHub event |
| created_at | TIMESTAMP | REQUIRED | Event timestamp |
| actor_id | INTEGER | NULLABLE | User ID who triggered event |
| actor_login | STRING | NULLABLE | Username |
| repo_id | INTEGER | NULLABLE | Repository ID |
| repo_name | STRING | NULLABLE | Repository full name |
| repo_language | STRING | NULLABLE | Primary language |
| payload | JSON | NULLABLE | Full event payload |
| raw_payload | STRING | NULLABLE | Original JSON (backup) |

**Partitioning**: `created_at` (day)
**Clustering**: `event_type`, `repo_id`

## Sample Queries

### Top Active Repositories (Last 24 Hours)
```sql
SELECT
    repo_name,
    COUNT(*) as event_count,
    COUNT(DISTINCT actor_id) as unique_contributors
FROM `github_dataset.events`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
GROUP BY repo_name
ORDER BY event_count DESC
LIMIT 100
```

### Event Type Distribution
```sql
SELECT
    event_type,
    COUNT(*) as count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER() as percentage
FROM `github_dataset.events`
WHERE DATE(created_at) = CURRENT_DATE()
GROUP BY event_type
ORDER BY count DESC
```

### Push Events with Commit Analysis
```sql
SELECT
    repo_name,
    ARRAY_LENGTH(JSON_EXTRACT_ARRAY(payload, '$.commits')) as commit_count,
    JSON_EXTRACT_SCALAR(payload, '$.ref') as branch_ref
FROM `github_dataset.events`
WHERE event_type = 'PushEvent'
    AND DATE(created_at) = CURRENT_DATE()
ORDER BY commit_count DESC
LIMIT 100
```

## Scaling Considerations

- **Volume**: ~1-2 GB compressed per hour (~5-10 GB uncompressed)
- **Events per hour**: ~500K-1M events
- **Recommended Cloud Run concurrency**: 10-50
- **Recommended Cloud Run memory**: 1-2 GB
- **Batch size for BigQuery**: 500-1000 rows per insert

## Implementation Files

- [`src/github_archive/processor.py`](../src/github_archive/processor.py) - Main processing logic
- [`src/github_archive/schemas.py`](../src/github_archive/schemas.py) - BigQuery schema definitions
- [`src/github_archive/Dockerfile`](../src/github_archive/Dockerfile) - Container definition
