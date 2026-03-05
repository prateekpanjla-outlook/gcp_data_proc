# GitHub Event Types

GitHub Archive contains 18+ event types. Each event type has a different payload structure.

## Common Event Types

### PushEvent (Most Common)
```json
{
  "id": "1234567890",
  "type": "PushEvent",
  "actor": {"id": 12345, "login": "username"},
  "repo": {"id": 67890, "name": "user/repo"},
  "payload": {
    "push_id": 1234567890,
    "size": 3,
    "distinct_size": 2,
    "ref": "refs/heads/main",
    "head": "abc123...",
    "before": "def456...",
    "commits": [
      {
        "sha": "abc123...",
        "author": {"email": "user@example.com", "name": "User"},
        "message": "Commit message",
        "distinct": true
      }
    ]
  },
  "created_at": "2025-01-15T14:30:00Z",
  "public": true
}
```

**Fields Extracted:**
- `push_size`: Number of commits
- `push_distinct_size`: Distinct commits
- `ref`: Branch reference (e.g., `refs/heads/main`)
- `push_head`: Latest commit SHA
- `push_before`: Previous commit SHA

---

### CreateEvent
```json
{
  "type": "CreateEvent",
  "payload": {
    "ref": "refs/heads/new-branch",
    "ref_type": "branch",
    "master_branch": "main",
    "description": "New branch",
    "pusher_type": "user"
  }
}
```

**Fields Extracted:**
- `ref`: Created reference
- `ref_type`: `branch` or `tag`
- `master_branch`: Default branch name
- `pusher_type`: `user` or ``

---

### DeleteEvent
```json
{
  "type": "DeleteEvent",
  "payload": {
    "ref": "refs/heads/old-branch",
    "ref_type": "branch"
  }
}
```

**Fields Extracted:**
- `ref`: Deleted reference
- `ref_type`: `branch` or `tag`

---

### WatchEvent (Star)
```json
{
  "type": "WatchEvent",
  "payload": {
    "action": "started"
  }
}
```

**Fields Extracted:**
- `action`: `started` (only value)

---

### ForkEvent
```json
{
  "type": "ForkEvent",
  "payload": {
    "forkee": {
      "id": 12345,
      "full_name": "user/forked-repo",
      "language": "Python",
      "private": false
    }
  },
  "repo": {
    "id": 67890,
    "name": "original/repo"
  }
}
```

**Fields Extracted:**
- `forkee_id`: Forked repo ID
- `forkee_name`: Forked repo full name
- `forkee_language`: Primary language

---

### IssuesEvent
```json
{
  "type": "IssuesEvent",
  "payload": {
    "action": "opened",
    "issue": {
      "id": 12345,
      "number": 1,
      "title": "Issue title",
      "state": "open",
      "user": {"login": "reporter"}
    }
  }
}
```

**Fields Extracted:**
- `action`: `opened`, `closed`, `reopened`
- `issue_number`: Issue number
- `issue_title`: Issue title
- `issue_state`: Issue state

---

### IssueCommentEvent
```json
{
  "type": "IssueCommentEvent",
  "payload": {
    "action": "created",
    "comment": {
      "id": 12345,
      "body": "Comment text",
      "user": {"login": "commenter"}
    },
    "issue": {
      "id": 67890,
      "number": 1
    }
  }
}
```

**Fields Extracted:**
- `action`: `created`, `edited`, `deleted`
- `comment_id`: Comment ID
- `issue_number`: Related issue number

---

### PullRequestEvent
```json
{
  "type": "PullRequestEvent",
  "payload": {
    "action": "opened",
    "number": 1,
    "pull_request": {
      "id": 12345,
      "number": 1,
      "state": "open",
      "title": "PR title",
      "body": "PR description",
      "merged": false,
      "merge_commit_sha": null,
      "head": {"ref": "feature-branch"},
      "base": {"ref": "main"}
    }
  }
}
```

**Fields Extracted:**
- `action`: `opened`, `closed`, `merged`, `reopened`
- `pr_number`: PR number
- `pr_state`: PR state
- `pr_title`: PR title
- `pr_merged`: Whether merged
- `pr_head_branch`: Source branch
- `pr_base_branch`: Target branch

---

### PullRequestReviewEvent
```json
{
  "type": "PullRequestReviewEvent",
  "payload": {
    "action": "submitted",
    "review": {
      "id": 12345,
      "state": "approved",
      "body": "LGTM",
      "user": {"login": "reviewer"}
    },
    "pull_request": {
      "id": 67890,
      "number": 1,
      "title": "PR title"
    }
  }
}
```

**Fields Extracted:**
- `action`: `submitted`, `edited`, `dismissed`
- `review_state`: `approved`, `changes_requested`, `commented`
- `pr_number`: Related PR number

---

### ReleaseEvent
```json
{
  "type": "ReleaseEvent",
  "payload": {
    "action": "published",
    "release": {
      "id": 12345,
      "tag_name": "v1.0.0",
      "name": "Release 1.0.0",
      "draft": false,
      "prerelease": false
    }
  }
}
```

**Fields Extracted:**
- `action`: `published`, `created`, `edited`, `deleted`
- `release_tag_name`: Git tag
- `release_name`: Release name
- `release_draft`: Whether draft
- `release_prerelease`: Whether pre-release

---

## Event Frequency (Approximate)

| Event Type | Frequency | Volume |
|------------|-----------|--------|
| PushEvent | ~50% | Highest |
| CreateEvent | ~15% | High |
| WatchEvent | ~10% | Medium |
| DeleteEvent | ~5% | Medium |
| ForkEvent | ~5% | Medium |
| IssuesEvent | ~3% | Low |
| PullRequestEvent | ~3% | Low |
| IssueCommentEvent | ~3% | Low |
| Others | ~6% | Low |

---

## Processing Considerations

### Payload Complexity
| Event Type | Payload Complexity | Extractable Fields |
|------------|-------------------|-------------------|
| PushEvent | High (commits array) | 6+ fields |
| PullRequestEvent | High (nested PR object) | 8+ fields |
| WatchEvent | Low (single field) | 1 field |
| DeleteEvent | Low (2 fields) | 2 fields |

### Null Handling
- Many fields are optional and can be `null`
- `payload` structure varies significantly by event type
- Always check field existence before extraction

### Array Fields
- `commits` in PushEvent can contain 100+ commits
- `assignees` in IssuesEvent is an array
- `labels` in IssuesEvent/PRs is an array
