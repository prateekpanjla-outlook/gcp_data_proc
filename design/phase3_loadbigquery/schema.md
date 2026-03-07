# Phase 3 Table Schema Design

## BigQuery Table: `github_events`

### Table Properties

| Property | Value |
|----------|-------|
| **Dataset ID** | `github_archive` |
| **Table ID** | `github_events` |
| **Location** | `us-central1` (must match staging bucket region) |
| **Partitioning** | Daily partitions by `created_at` DATE |
| **Clustering** | `event_type` |
| **Partition Expiration** | 366 days (1 year) |
| **Schema Evolution** | Autodetect initially, then locked |

### Schema Fields

The schema is derived from Phase 2's flattened output. Initial load uses autodetect, then the schema is locked.

**Core Fields (from Phase 2 dtype_definitions):**

| Field Name | Type | Mode | Description |
|-----------|------|------|-------------|
| `id` | STRING | NULLABLE | GitHub event ID |
| `type` | STRING | NULLABLE | Event type (PushEvent, IssuesEvent, etc.) |
| `created_at` | TIMESTAMP | NULLABLE | Event timestamp (used for partitioning) |
| `actor_id` | INT64 | NULLABLE | Actor ID (flattened from actor) |
| `actor_login` | STRING | NULLABLE | Actor username |
| `repo_id` | INT64 | NULLABLE | Repository ID (flattened from repo) |
| `repo_name` | STRING | NULLABLE | Repository name (owner/repo) |
| `org_id` | INT64 | NULLABLE | Organization ID |
| `org_login` | STRING | NULLABLE | Organization username |
| `payload_ref` | STRING | NULLABLE | Git reference (from payload) |
| `payload_ref_type` | STRING | NULLABLE | Reference type (branch/tag) |
| `payload_push_id` | STRING | NULLABLE | Push ID |
| `payload_size` | INT64 | NULLABLE | Push size |
| `public` | BOOLEAN | NULLABLE | Whether repo is public |
| `language` | STRING | NULLABLE | Primary language |

**Note:** This is a subset of all fields. The actual schema includes all fields from Phase 2's flattened output. Autodetect will capture all fields from the first file.

### Partitioning Strategy

**Why Partition by `created_at` DATE?**

1. **Time-Series Queries:** Most analytics query by date ranges
2. **Cost Efficiency:** Partition pruning reduces scanned data
3. **Data Lifecycle:** Automatic expiration of old partitions

**Partition Format:**
- **Decorator:** `$YYYYMMDD`
- **Example:** `github_events$20260307`

**Query Example:**
```sql
-- Query single day
SELECT * FROM `project.github_archive.github_events$20260307`
WHERE type = 'PushEvent';

-- Query date range (scans only partitions in range)
SELECT event_type, COUNT(*) as count
FROM `project.github_archive.github_events`
WHERE created_at >= TIMESTAMP('2026-03-01')
  AND created_at < TIMESTAMP('2026-04-01')
GROUP BY event_type;
```

### Clustering Strategy

**Cluster by `event_type`:**

1. **Filtering Efficiency:** Queries often filter by event type
2. **Common Patterns:** "Show me all PushEvents for date X"
3. **Cost Reduction:** Clustering reduces scan for type-filtered queries

**Query Benefits:**
```sql
-- Efficient: Uses clustering
SELECT * FROM `project.github_archive.github_events`
WHERE created_at >= TIMESTAMP('2026-03-01')
  AND type = 'PushEvent';

-- Inefficient: Avoid filtering by non-clustered fields
SELECT * FROM `project.github_archive.github_events`
WHERE actor_login = 'torvalds';
```

### Schema Evolution

**Initial Load:**
- Use `autodetect=True` to infer schema from first file
- BigQuery automatically detects types from NDJSON values

**Subsequent Loads:**
- Schema is locked after first successful load
- New fields must be added via explicit schema update
- Use `bq update` or Terraform to modify schema

**Schema Update Example:**
```bash
# Add new field to schema
bq update --schema schema.json project:github_archive.github_events

# Or via SQL
ALTER TABLE project.github_archive.github_events
ADD COLUMN new_field STRING;
```

### Data Type Mappings

| NDJSON Type | BigQuery Type | Notes |
|-------------|---------------|-------|
| string | STRING | Unicode text |
| number/integer | INT64 | 64-bit integer |
| number/float | FLOAT64 | 64-bit floating |
| boolean | BOOLEAN | true/false |
| null | NULL | Missing values |
| array | REPEATED | Must have consistent type |
| object | RECORD/STRUCT | Nested structure |

### Example Record

```json
{
  "id": "3840364475",
  "type": "PushEvent",
  "created_at": "2026-03-07T01:00:00Z",
  "actor_id": 123456,
  "actor_login": "octocat",
  "repo_id": 789012,
  "repo_name": "octocat/Hello-World",
  "payload_ref": "refs/heads/main",
  "payload_ref_type": "branch",
  "public": true,
  "language": "Python"
}
```

## Query Patterns

### Common Queries

**1. Events by Type (Last 7 Days):**
```sql
SELECT
  type,
  COUNT(*) as event_count
FROM `project.github_archive.github_events`
WHERE created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
GROUP BY type
ORDER BY event_count DESC;
```

**2. Top Repositories by Event Count:**
```sql
SELECT
  repo_name,
  COUNT(*) as event_count
FROM `project.github_archive.github_events`
WHERE created_at >= TIMESTAMP('2026-03-01')
GROUP BY repo_name
ORDER BY event_count DESC
LIMIT 100;
```

**3. Hourly Activity Heatmap:**
```sql
SELECT
  EXTRACT(HOUR FROM created_at) as hour,
  EXTRACT(DATE FROM created_at) as date,
  COUNT(*) as event_count
FROM `project.github_archive.github_events`
WHERE created_at >= TIMESTAMP('2026-03-07')
  AND created_at < TIMESTAMP('2026-03-08')
GROUP BY date, hour
ORDER BY date, hour;
```

### Cost Optimization Tips

1. **Always filter by `created_at`** to enable partition pruning
2. **Filter by `event_type`** to leverage clustering
3. **SELECT only needed columns** instead of `SELECT *`
4. **Use materialized views** for expensive repeated queries
