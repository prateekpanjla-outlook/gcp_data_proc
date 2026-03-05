#!/usr/bin/env python3
"""Generate sample data for testing."""

import argparse
import gzip
import json
import random
from datetime import datetime, timedelta


def generate_github_archive_event(event_id: int, event_type: str = None) -> dict:
    """Generate a sample GitHub Archive event."""
    if event_type is None:
        event_type = random.choice([
            "PushEvent", "WatchEvent", "CreateEvent", "DeleteEvent",
            "ForkEvent", "IssuesEvent", "PullRequestEvent"
        ])

    base_time = datetime.utcnow() - timedelta(hours=random.randint(0, 24))

    event = {
        "id": str(event_id),
        "type": event_type,
        "actor": {
            "id": random.randint(1000, 999999),
            "login": f"user_{random.randint(1000, 9999)}",
            "display_login": f"User {random.randint(1000, 9999)}",
            "gravatar_id": "",
            "url": f"https://api.github.com/users/user_{random.randint(1000, 9999)}",
            "avatar_url": f"https://avatars.githubusercontent.com/u/{random.randint(1000, 999999)}?"
        },
        "repo": {
            "id": random.randint(1000000, 999999999),
            "name": f"user{random.randint(1000, 9999)}/repo-{random.randint(100, 999)}",
            "url": f"https://api.github.com/repos/user{random.randint(1000, 9999)}/repo-{random.randint(100, 999)}"
        },
        "payload": {},
        "public": True,
        "created_at": base_time.isoformat() + "Z"
    }

    # Add event-specific payload
    if event_type == "PushEvent":
        event["payload"] = {
            "push_id": random.randint(1000000000, 9999999999),
            "size": random.randint(1, 10),
            "distinct_size": random.randint(1, 10),
            "ref": random.choice(["refs/heads/main", "refs/heads/develop", "refs/heads/feature-branch"]),
            "head": "a" * 40,
            "before": "b" * 40
        }
    elif event_type == "WatchEvent":
        event["payload"] = {
            "action": "started"
        }
    elif event_type == "IssuesEvent":
        event["payload"] = {
            "action": random.choice(["opened", "closed", "reopened"]),
            "issue": {
                "number": random.randint(1, 1000),
                "title": f"Sample issue {random.randint(1, 100)}",
                "state": random.choice(["open", "closed"])
            }
        }
    elif event_type == "PullRequestEvent":
        event["payload"] = {
            "action": random.choice(["opened", "closed", "merged"]),
            "pull_request": {
                "number": random.randint(1, 500),
                "title": f"Sample PR {random.randint(1, 100)}",
                "state": random.choice(["open", "closed"]),
                "merged": random.choice([True, False])
            }
        }

    return event


def generate_hn_story(story_id: int) -> dict:
    """Generate a sample Hacker News story."""
    return {
        "id": story_id,
        "by": f"hn_user_{random.randint(100, 9999)}",
        "time": int((datetime.utcnow() - timedelta(hours=random.randint(0, 24))).timestamp()),
        "type": random.choice(["story", "job", "ask"]),
        "title": f"Sample HN Story {story_id}",
        "url": f"https://example.com/article-{story_id}",
        "score": random.randint(1, 500),
        "descendants": random.randint(0, 100),
        "kids": [random.randint(30000000, 40000000) for _ in range(random.randint(0, 20))],
        "dead": False,
        "deleted": False
    }


def generate_hn_comment(comment_id: int, parent_id: int = None) -> dict:
    """Generate a sample Hacker News comment."""
    if parent_id is None:
        parent_id = random.randint(30000000, 40000000)

    return {
        "id": comment_id,
        "by": f"hn_user_{random.randint(100, 9999)}",
        "time": int((datetime.utcnow() - timedelta(hours=random.randint(0, 24))).timestamp()),
        "type": "comment",
        "text": f"This is a sample comment {comment_id}.",
        "parent": parent_id,
        "kids": [random.randint(30000000, 40000000) for _ in range(random.randint(0, 5))],
        "dead": False,
        "deleted": False
    }


def main():
    parser = argparse.ArgumentParser(description="Generate sample data for testing")
    parser.add_argument("--source", choices=["github", "hackernews", "hn"], required=True)
    parser.add_argument("--rows", type=int, default=100, help="Number of rows to generate")
    parser.add_argument("--output", required=True, help="Output file path")

    args = parser.parse_args()

    records = []

    if args.source in ["hackernews", "hn"]:
        # Generate Hacker News format
        stories = []
        comments = []

        for i in range(args.rows):
            story_id = 40000000 + i
            stories.append(generate_hn_story(story_id))

            # Generate some comments for each story
            for j in range(random.randint(0, 5)):
                comment_id = 50000000 + i * 10 + j
                comments.append(generate_hn_comment(comment_id, story_id))

        data = {
            "stories": stories,
            "comments": comments,
            "story_count": len(stories),
            "comment_count": len(comments),
            "fetched_at": datetime.utcnow().isoformat()
        }
        records = [data]  # Single JSON object with all data

    else:
        # Generate GitHub Archive format (JSONL)
        for i in range(args.rows):
            records.append(generate_github_archive_event(i))

    # Write to file
    if args.output.endswith('.gz'):
        with gzip.open(args.output, 'wt', encoding='utf-8') as f:
            if args.source in ["hackernews", "hn"]:
                json.dump(records[0], f)
            else:
                for record in records:
                    f.write(json.dumps(record) + '\n')
    else:
        with open(args.output, 'w', encoding='utf-8') as f:
            if args.source in ["hackernews", "hn"]:
                json.dump(records[0], f)
            else:
                for record in records:
                    f.write(json.dumps(record) + '\n')

    print(f"Generated {len(records)} records and wrote to {args.output}")


if __name__ == "__main__":
    main()
