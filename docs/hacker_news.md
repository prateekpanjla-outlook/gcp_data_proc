# Hacker News API Data Source

## Overview

Hacker News (HN) is a social news website focusing on computer science and entrepreneurship. The official HN API provides read-only access to all stories, comments, and users via a Firebase REST API.

## Access Details

| Property | Value |
|----------|-------|
| **Base URL** | `https://hacker-news.firebaseio.com/v0/` |
| **Documentation** | `https://github.com/HackerNews/API` |
| **Authentication** | None required |
| **Rate Limit** | None (officially documented) |
| **Response Format** | JSON |
| **Update Frequency** | Near real-time |

## API Endpoints

### Stories Endpoints
```
GET /v0/newstories.json      # Latest stories (ordered by arrival)
GET /v0/beststories.json     # All-time best stories
GET /v0/askstories.json      # Ask HN stories
GET /v0/showstories.json     # Show HN stories
GET /v0/jobstories.json      # Job listings
```

### Individual Item Endpoints
```
GET /v0/item/{id}.json       # Story or comment by ID
GET /v0/user/{id}.json       # User profile by ID
```

### Updates Endpoint
```
GET /v0/updates.json         # Lists changed item and profile IDs
```

## Sample Item Structure

### Story Item
```json
{
  "id": 12345678,
  "by": "username",
  "time": 1705000000,        // Unix timestamp
  "type": "story",
  "title": "Story Title",
  "url": "https://example.com/article",
  "score": 42,
  "descendants": 10,         // Total comment count
  "kids": [12345679, 12345680], // Comment IDs
  "text": null,              // For Ask HN posts
  "parent": null,
  "dead": false,
  "deleted": false
}
```

### Comment Item
```json
{
  "id": 12345679,
  "by": "commenter",
  "time": 1705000100,
  "type": "comment",
  "text": "Comment text here...",
  "parent": 12345678,        // Parent story or comment ID
  "kids": [12345681],
  "dead": false,
  "deleted": false
}
```

### User Profile
```json
{
  "id": "username",
  "created": 1500000000,
  "karma": 1234,
  "about": "User bio...",
  "submitted": [12345678, 12345679] // IDs of submitted items
}
```

## Processing Strategy

### Cloud Storage Ingestion

Hacker News API is real-time, so we need a different approach than GitHub Archive:

#### Option 1: Scheduled Polling (Recommended)
Create a Cloud Scheduler job (every 5-10 minutes) that:
1. Fetches latest story IDs from `/v0/newstories.json`
2. Fetches each story's full details
3. Fetches top-level comments
4. Writes to Cloud Storage as newline-delimited JSON

#### Option 2: Cloud Workflow + Pub/Sub
Use Cloud Workflows with PollingDispatch to continuously poll the API.

### Processing Pipeline

```
┌──────────────────────────────────┐
│ Cloud Scheduler (every 5 min)    │
└────────────┬─────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Cloud Run: HN Data Fetcher           │
│ 1. Fetch newstories.json             │
│ 2. Fetch each story detail           │
│ 3. Fetch comments                    │
│ 4. Write to GS: hn-api/raw/          │
└────────────┬─────────────────────────┘
             │ File creation
             ▼
┌──────────────────────────────────────┐
│ Eventarc Trigger (Finalize)          │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ Cloud Run: HN Data Processor         │
│ 1. Read JSON from GCS                │
│ 2. Parse and validate                │
│ 3. Transform timestamp               │
│ 4. Load to BigQuery                  │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│ BigQuery: hacker_news.dataset        │
│ - stories (partitioned by date)      │
│ - comments (partitioned by date)     │
│ - users (full dump, periodic)        │
└──────────────────────────────────────┘
```

## BigQuery Schema Design

### Stories Table

| Field | Type | Mode | Description |
|-------|------|------|-------------|
| story_id | INTEGER | REQUIRED | HN story ID |
| by | STRING | NULLABLE | Author username |
| timestamp | TIMESTAMP | REQUIRED | Created timestamp (converted) |
| type | STRING | NULLABLE | Item type (story, job, poll) |
| title | STRING | NULLABLE | Story title |
| url | STRING | NULLABLE | External URL |
| domain | STRING | NULLABLE | Extracted from URL |
| score | INTEGER | NULLABLE | Upvote score |
| descendants | INTEGER | NULLABLE | Comment count |
| text | STRING | NULLABLE | Ask HN text content |
| kids | ARRAY<INTEGER> | REPEATED | Comment IDs |
| fetched_at | TIMESTAMP | REQUIRED | When we fetched this |
| is_dead | BOOLEAN | NULLABLE | Story marked as dead |
| is_deleted | BOOLEAN | NULLABLE | Story marked deleted |

**Partitioning**: `timestamp` (day)
**Clustering**: `by`, `score`

### Comments Table

| Field | Type | Mode | Description |
|-------|------|------|-------------|
| comment_id | INTEGER | REQUIRED | HN comment ID |
| parent_id | INTEGER | NULLABLE | Parent story or comment ID |
| story_id | INTEGER | NULLABLE | Root story ID |
| by | STRING | NULLABLE | Author username |
| timestamp | TIMESTAMP | REQUIRED | Created timestamp |
| text | STRING | NULLABLE | Comment content |
| kids | ARRAY<INTEGER> | REPEATED | Reply comment IDs |
| fetched_at | TIMESTAMP | REQUIRED | When we fetched this |
| is_dead | BOOLEAN | NULLABLE | Comment marked as dead |
| is_deleted | BOOLEAN | NULLABLE | Comment marked deleted |
| depth | INTEGER | NULLABLE | Comment thread depth |

**Partitioning**: `timestamp` (day)
**Clustering**: `story_id`, `by`

### Users Table

| Field | Type | Mode | Description |
|-------|------|------|-------------|
| username | STRING | REQUIRED | HN username |
| created | TIMESTAMP | REQUIRED | Account creation |
| karma | INTEGER | NULLABLE | User karma points |
| about | STRING | NULLABLE | User bio |
| submitted_count | INTEGER | NULLABLE | Count of submitted items |
| last_updated | TIMESTAMP | REQUIRED | When we fetched this |

## Sample Queries

### Top Stories by Score (Last 24 Hours)
```sql
SELECT
    title,
    url,
    score,
    descendants as comment_count,
    TIMESTAMP_TRUNC(timestamp, HOUR) as hour
FROM `hacker_news.stories`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY score DESC
LIMIT 100
```

### Most Active Commenters
```sql
SELECT
    by as username,
    COUNT(*) as comment_count,
    AVG(LENGTH(text)) as avg_comment_length
FROM `hacker_news.comments`
WHERE DATE(timestamp) = CURRENT_DATE()
GROUP BY by
ORDER BY comment_count DESC
LIMIT 100
```

### Domain Distribution
```sql
SELECT
    NET.REG_DOMAIN(url) as domain,
    COUNT(*) as story_count,
    AVG(score) as avg_score
FROM `hacker_news.stories`
WHERE DATE(timestamp) = CURRENT_DATE()
    AND url IS NOT NULL
GROUP BY domain
ORDER BY story_count DESC
LIMIT 50
```

### Comment Thread Analysis
```sql
WITH RECURSIVE comment_tree AS (
    SELECT
        comment_id,
        parent_id,
        story_id,
        by,
        text,
        timestamp,
        0 as depth
    FROM `hacker_news.comments`
    WHERE comment_id = (SELECT MIN(comment_id) FROM `hacker_news.comments`)

    UNION ALL

    SELECT
        c.comment_id,
        c.parent_id,
        c.story_id,
        c.by,
        c.text,
        c.timestamp,
        ct.depth + 1
    FROM `hacker_news.comments` c
    JOIN comment_tree ct ON c.parent_id = ct.comment_id
)
SELECT * FROM comment_tree
ORDER BY depth, timestamp
```

## Scaling Considerations

- **Volume**: ~1000-2000 new stories per day, ~5000-10000 comments per day
- **Data Size**: ~5-10 MB per day uncompressed
- **API Call Patterns**:
  - 1 call to get story IDs list
  - N calls for individual stories
  - M calls for comments
- **Recommended Fetch Interval**: 5-10 minutes
- **Recommended Cloud Run Memory**: 512 MB - 1 GB (smaller than GitHub Archive)
- **Recommended Batch Size**: 100-200 items per BigQuery insert

## Comparison: Hacker News vs GitHub Archive

| Aspect | Hacker News | GitHub Archive |
|--------|-------------|----------------|
| **Data Velocity** | Medium (real-time) | High (hourly batches) |
| **Data Volume** | ~10 MB/day | ~10 GB/day |
| **Complexity** | Medium nested JSON | Highly nested JSON |
| **Access Pattern** | API polling | File download |
| **Ideal For** | Real-time analytics | Batch analytics |

## Implementation Files

- [`src/hacker_news/fetcher.py`](../src/hacker_news/fetcher.py) - API data fetcher
- [`src/hacker_news/processor.py`](../src/hacker_news/processor.py) - GCS event processor
- [`src/hacker_news/schemas.py`](../src/hacker_news/schemas.py) - BigQuery schema definitions
- [`src/hacker_news/Dockerfile`](../src/hacker_news/Dockerfile) - Container definition
