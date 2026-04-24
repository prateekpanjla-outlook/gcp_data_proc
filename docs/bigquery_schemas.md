# BigQuery Schema Documentation

This document provides detailed schema definitions for all BigQuery tables used in the project.

## Dataset Organization

```
project_id
├── github_dataset
│   ├── events (partitioned)
│   ├── repositories (dimension)
│   └── users (dimension)
│
└── hacker_news
    ├── stories (partitioned)
    ├── comments (partitioned)
    └── users (full dump)
```

## GitHub Dataset Schemas

### Table: `github_dataset.events`

Main table storing all GitHub timeline events.

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

### Table: `github_dataset.repositories`

Dimension table for repository metadata (updated incrementally).

```sql
CREATE TABLE `github_dataset.repositories`
(
  repo_id INTEGER NOT NULL,
  repo_name STRING NOT NULL,
  owner_id INTEGER,
  owner_name STRING,
  description STRING,
  language STRING,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  pushed_at TIMESTAMP,
  size INTEGER,                  -- Repository size in KB
  stargazers_count INTEGER,
  watchers_count INTEGER,
  forks_count INTEGER,
  open_issues_count INTEGER,
  has_issues BOOLEAN,
  has_wiki BOOLEAN,
  has_pages BOOLEAN,
  has_projects BOOLEAN,
  is_fork BOOLEAN,
  default_branch STRING,
  license STRING,
  topics ARRAY<STRING>,
  last_updated TIMESTAMP NOT NULL
)
PRIMARY KEY (repo_id);
```

### Table: `github_dataset.users`

Dimension table for user metadata.

```sql
CREATE TABLE `github_dataset.users`
(
  user_id INTEGER NOT NULL,
  login STRING NOT NULL,
  name STRING,
  email STRING,
  bio STRING,
  location STRING,
  blog STRING,
  company STRING,
  type STRING,                   -- User or Organization
  followers_count INTEGER,
  following_count INTEGER,
  public_repos_count INTEGER,
  public_gists_count INTEGER,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  site_admin BOOLEAN,
  hireable BOOLEAN,
  twitter_username STRING,
  last_updated TIMESTAMP NOT NULL
)
PRIMARY KEY (user_id);
```

## Hacker News Dataset Schemas

### Table: `hacker_news.stories`

```sql
CREATE TABLE `hacker_news.stories`
(
  story_id INTEGER NOT NULL,
  by STRING,                     -- Author username
  timestamp TIMESTAMP NOT NULL,  -- Unix timestamp converted
  type STRING NOT NULL,          -- story, job, poll
  title STRING,
  url STRING,
  domain STRING,                 -- Extracted from URL
  score INTEGER,
  descendants INTEGER,           -- Total comment count
  text STRING,                   -- For Ask HN posts
  kids ARRAY<INTEGER>,           -- Comment IDs
  parts ARRAY< INTEGER>,         -- For poll parts
  poll_id INTEGER,               -- For poll options
  fetched_at TIMESTAMP NOT NULL,
  is_dead BOOLEAN,
  is_deleted BOOLEAN,
  ingestion_timestamp TIMESTAMP NOT NULL,
  processed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(timestamp)
CLUSTER BY by, score
OPTIONS (
  partition_expiration_days = 400,
  require_partition_filter = false
);
```

### Table: `hacker_news.comments`

```sql
CREATE TABLE `hacker_news.comments`
(
  comment_id INTEGER NOT NULL,
  parent_id INTEGER,
  story_id INTEGER,              -- Root story ID (computed)
  by STRING,
  timestamp TIMESTAMP NOT NULL,
  text STRING,
  kids ARRAY<INTEGER>,
  fetched_at TIMESTAMP NOT NULL,
  is_dead BOOLEAN,
  is_deleted BOOLEAN,
  depth INTEGER,                 -- Thread depth
  parent_author STRING,          -- Author of parent comment
  ingestion_timestamp TIMESTAMP NOT NULL,
  processed_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(timestamp)
CLUSTER BY story_id, by
OPTIONS (
  partition_expiration_days = 400,
  require_partition_filter = false
);
```

### Table: `hacker_news.users`

```sql
CREATE TABLE `hacker_news.users`
(
  username STRING NOT NULL,
  created TIMESTAMP NOT NULL,    -- Account creation
  karma INTEGER,
  about STRING,
  submitted ARRAY<INTEGER>,      -- IDs of submitted items
  submitted_count INTEGER,
  last_updated TIMESTAMP NOT NULL
)
PRIMARY KEY (username);
```

## Schema Management

### Python Schema Definitions

Schemas are defined in Python files for programmatic table creation:

```python
# src/github_archive/schemas.py
GITHUB_EVENTS_SCHEMA = [
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
    # ...
]

# src/hacker_news/schemas.py
HN_STORIES_SCHEMA = [
    bigquery.SchemaField("story_id", "INTEGER", mode="REQUIRED"),
    # ...
]
```

### Deployment Scripts

```bash
# Create all datasets and tables
python scripts/create_bigquery_datasets.py --project_id=$PROJECT_ID

# Update existing table schema
python scripts/update_schema.py --dataset=github_dataset --table=events
```

## Schema Evolution Strategy

1. **Additive Changes**: New NULLABLE fields can be added without downtime
2. **Required Fields**: Avoid adding REQUIRED fields to existing tables
3. **Type Changes**: Create new columns rather than changing types
4. **Backward Compatibility**: Always maintain the `payload` JSON field for raw data access

## Data Quality Considerations

- **Deduplication**: Use `event_id` or `story_id` as primary keys with MERGE operations
- **Late Data**: Events may arrive out of order; partition by event time, not ingestion time
- **Null Handling**: Different event types have different optional fields
- **Validation**: Check for required fields before inserting

## Query Performance Tips

1. **Always filter by partition** (date range) to reduce scan cost
2. **Use clustering columns** in WHERE clauses when possible
3. **Consider materialized views** for frequently queried aggregations
4. **Use nested/repeated fields** appropriately to avoid repeated joins
5. **Cache small dimension tables** (repositories, users)

## Sample Materialized Views

### Top Repos Daily Summary
```sql
CREATE MATERIALIZED VIEW `github_dataset.top_repos_daily`
AS
SELECT
    repo_name,
    DATE(created_at) as event_date,
    COUNT(*) as total_events,
    COUNT(DISTINCT actor_id) as unique_contributors,
    SUM(CASE WHEN event_type = 'PushEvent' THEN 1 ELSE 0 END) as push_events
FROM `github_dataset.events`
GROUP BY repo_name, DATE(created_at);
```
