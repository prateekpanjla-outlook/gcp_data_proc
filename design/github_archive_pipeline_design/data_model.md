# BigQuery Data Model

## Table: `github_dataset.events`

Main table storing all GitHub timeline events.

### Schema

```sql
CREATE TABLE `github_dataset.events`
(
  -- Primary fields
  event_id STRING NOT NULL,
  event_type STRING NOT NULL,
  created_at TIMESTAMP NOT NULL,

  -- Actor (user who performed the action)
  actor_id INTEGER,
  actor_login STRING,
  actor_display_login STRING,
  actor_gravatar_id STRING,
  actor_url STRING,
  actor_avatar_url STRING,

  -- Repository information
  repo_id INTEGER,
  repo_name STRING,
  repo_url STRING,

  -- Organization (if applicable)
  org_id INTEGER,
  org_login STRING,
  org_url STRING,

  -- Payload (full JSON for flexibility)
  payload JSON,

  -- Common extracted payload fields (for query performance)
  action STRING,                 -- Specific action performed
  ref STRING,                    -- Branch/tag reference
  ref_type STRING,               -- Type of ref (branch/tag)
  master_branch STRING,
  description STRING,
  pusher_type STRING,

  -- Push event specific
  push_size INTEGER,             -- Number of commits
  push_distinct_size INTEGER,    -- Number of distinct commits
  push_head STRING,
  push_before STRING,

  -- Pull request specific
  pr_number INTEGER,
  pr_state STRING,
  pr_title STRING,
  pr_body STRING,
  pr_merged BOOLEAN,
  pr_merge_commit_sha STRING,
  pr_head_branch STRING,
  pr_base_branch STRING,

  -- Issue specific
  issue_number INTEGER,
  issue_state STRING,
  issue_title STRING,
  issue_body STRING,

  -- Release specific
  release_tag_name STRING,
  release_name STRING,
  release_draft BOOLEAN,
  release_prerelease BOOLEAN,

  -- Fork specific
  forkee_id INTEGER,
  forkee_name STRING,
  forkee_language STRING,

  -- Watch specific
  watch_action STRING,

  -- Metadata
  public BOOLEAN,
  ingestion_timestamp TIMESTAMP NOT NULL,
  processed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
CLUSTER BY event_type, repo_id
OPTIONS (
  partition_expiration_days = 400,
  require_partition_filter = false
);
```

### Partitioning

- **Field:** `created_at`
- **Type:** Day partitioning (`DATE(created_at)`)
- **Expiration:** 400 days
- **Reason:** Queries typically filter by date range

### Clustering

- **Fields:** `event_type`, `repo_id`
- **Reason:** Most queries filter by event type or specific repository

---

## Example Queries

### Top Repositories by Event Count (Last 24 Hours)

```sql
SELECT
    repo_name,
    COUNT(*) as event_count,
    COUNT(DISTINCT actor_id) as unique_contributors,
    STRING_AGG(DISTINCT event_type, ', ') as event_types
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
    AVG(push_size) as avg_commits_per_push,
    MAX(push_size) as max_commits_in_single_push,
    COUNT(*) as total_pushes
FROM `github_dataset.events`
WHERE event_type = 'PushEvent'
    AND DATE(created_at) = CURRENT_DATE()
GROUP BY repo_name
ORDER BY total_pushes DESC
LIMIT 50
```

### Most Active Users

```sql
SELECT
    actor_login,
    COUNT(*) as total_events,
    COUNT(DISTINCT repo_id) as unique_repos,
    STRING_AGG(DISTINCT event_type, ', ') as event_types
FROM `github_dataset.events`
WHERE DATE(created_at) = CURRENT_DATE()
GROUP BY actor_login
ORDER BY total_events DESC
LIMIT 100
```

### Pull Request Merge Rate by Repository

```sql
SELECT
    repo_name,
    COUNT(*) as total_prs,
    SUM(CAST(pr_merged AS INT64)) as merged_prs,
    SAFE_DIVIDE(SUM(CAST(pr_merged AS INT64)), COUNT(*)) * 100 as merge_rate
FROM `github_dataset.events`
WHERE event_type = 'PullRequestEvent'
    AND DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY repo_name
HAVING COUNT(*) >= 10  -- At least 10 PRs
ORDER BY merge_rate DESC
LIMIT 50
```

### Hourly Activity Heatmap

```sql
SELECT
    EXTRACT(HOUR FROM created_at) as hour,
    event_type,
    COUNT(*) as event_count
FROM `github_dataset.events`
WHERE DATE(created_at) = CURRENT_DATE()
GROUP BY hour, event_type
ORDER BY hour, event_count DESC
```

---

## Data Types Reference

| Field | Type | Mode | Description |
|-------|------|------|-------------|
| `event_id` | STRING | REQUIRED | Unique event identifier from GitHub |
| `event_type` | STRING | REQUIRED | Type of GitHub event (e.g., PushEvent) |
| `created_at` | TIMESTAMP | REQUIRED | When the event occurred |
| `actor_id` | INTEGER | NULLABLE | GitHub user ID of actor |
| `actor_login` | STRING | NULLABLE | GitHub username of actor |
| `repo_id` | INTEGER | NULLABLE | Repository ID |
| `repo_name` | STRING | NULLABLE | Repository full name (owner/repo) |
| `payload` | JSON | NULLABLE | Full original payload (for flexibility) |
| `public` | BOOLEAN | NULLABLE | Whether event is from public repo |

---

## Performance Tips

### 1. Always Filter by Partition Date

```sql
-- GOOD - Uses partition pruning
SELECT * FROM `github_dataset.events`
WHERE DATE(created_at) = "2025-01-15"

-- BAD - Scans all partitions
SELECT * FROM `github_dataset.events`
WHERE event_type = "PushEvent"
```

### 2. Use Clustering Columns in WHERE/JOIN

```sql
-- GOOD - Uses clustering
SELECT * FROM `github_dataset.events`
WHERE DATE(created_at) = "2025-01-15"
  AND repo_id = 12345

-- BETTER - Filters by both cluster keys
SELECT * FROM `github_dataset.events`
WHERE DATE(created_at) = "2025-01-15"
  AND event_type = "PushEvent"
  AND repo_id = 12345
```

### 3. Avoid SELECT *

```sql
-- BAD - Scans all columns
SELECT * FROM `github_dataset.events`

-- GOOD - Select only needed columns
SELECT event_id, event_type, repo_name
FROM `github_dataset.events`
```

### 4. Use ARRAY_AGG for Aggregation

```sql
-- Instead of multiple self-joins, use ARRAY_AGG
SELECT
    repo_id,
    STRING_AGG(DISTINCT event_type, ', ') as event_types
FROM `github_dataset.events`
GROUP BY repo_id
```
