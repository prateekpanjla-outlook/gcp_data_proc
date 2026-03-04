# Testing Strategy

This document outlines the testing approach for the Cloud Storage → Cloud Run → BigQuery data pipeline.

## Testing Levels

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Testing Pyramid                             │
├─────────────────────────────────────────────────────────────────────┤
│                           E2E Tests                                 │
│                        (Production-like)                            │
├─────────────────────────────────────────────────────────────────────┤
│                    Integration Tests                                │
│              (BigQuery emulator, Pub/Sub local)                     │
├─────────────────────────────────────────────────────────────────────┤
│                      Unit Tests                                     │
│                   (Fast, isolated)                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Unit Tests

### GitHub Archive Processor Tests

Location: [`tests/github_archive/test_processor.py`](../tests/github_archive/test_processor.py)

```python
import pytest
from unittest.mock import Mock, patch
from src.github_archive.processor import GitHubArchiveProcessor

class TestGitHubArchiveProcessor:
    """Unit tests for GitHub Archive processing logic."""

    def test_parse_github_event(self):
        """Test parsing a single GitHub event."""
        processor = GitHubArchiveProcessor()
        raw_event = {
            "id": "1234567890",
            "type": "PushEvent",
            "actor": {"id": 12345, "login": "testuser"},
            "repo": {"id": 67890, "name": "test/repo"},
            "created_at": "2025-01-15T14:30:00Z"
        }
        result = processor.parse_event(raw_event)
        assert result.event_id == "1234567890"
        assert result.event_type == "PushEvent"
        assert result.actor_login == "testuser"

    def test_extract_push_event_fields(self):
        """Test extraction of PushEvent specific fields."""
        processor = GitHubArchiveProcessor()
        event_with_payload = {
            "type": "PushEvent",
            "payload": {
                "size": 5,
                "distinct_size": 3,
                "ref": "refs/heads/main"
            }
        }
        result = processor.extract_payload_fields(event_with_payload)
        assert result.push_size == 5
        assert result.ref == "refs/heads/main"

    @pytest.mark.parametrize("event_type", [
        "PushEvent", "WatchEvent", "ForkEvent",
        "IssuesEvent", "PullRequestEvent"
    ])
    def test_all_event_types(self, event_type):
        """Test that all event types are recognized."""
        processor = GitHubArchiveProcessor()
        assert event_type in processor.SUPPORTED_EVENT_TYPES

    def test_invalid_event_skipped(self):
        """Test that invalid events are skipped with logging."""
        processor = GitHubArchiveProcessor()
        invalid_event = {"id": "123"}  # Missing required fields
        result = processor.parse_event(invalid_event)
        assert result is None
```

### Hacker News Processor Tests

Location: [`tests/hacker_news/test_processor.py`](../tests/hacker_news/test_processor.py)

```python
import pytest
from src.hacker_news.processor import HNProcessor

class TestHNProcessor:
    """Unit tests for Hacker News processing logic."""

    def test_parse_story_item(self):
        """Test parsing a story item."""
        processor = HNProcessor()
        story = {
            "id": 12345,
            "by": "author",
            "time": 1705000000,
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com",
            "score": 42
        }
        result = processor.parse_story(story)
        assert result.story_id == 12345
        assert result.type == "story"
        assert result.score == 42

    def test_parse_comment_item(self):
        """Test parsing a comment item."""
        processor = HNProcessor()
        comment = {
            "id": 12346,
            "by": "commenter",
            "time": 1705000100,
            "type": "comment",
            "text": "Test comment",
            "parent": 12345
        }
        result = processor.parse_comment(comment)
        assert result.comment_id == 12346
        assert result.parent_id == 12345

    def test_extract_domain_from_url(self):
        """Test domain extraction from URLs."""
        processor = HNProcessor()
        assert processor.extract_domain("https://www.example.com/path") == "example.com"
        assert processor.extract_domain("http://blog.example.co.uk/article") == "example.co.uk"
        assert processor.extract_domain(None) is None

    def test_calculate_comment_depth(self):
        """Test comment thread depth calculation."""
        processor = HNProcessor()
        # Root comment (direct child of story)
        assert processor.calculate_depth(12346, 12345, {}) == 1
        # Nested comment
        parent_depths = {12346: 1}
        assert processor.calculate_depth(12347, 12346, parent_depths) == 2
```

### BigQuery Schema Tests

Location: [`tests/shared/test_schemas.py`](../tests/shared/test_schemas.py)

```python
import pytest
from google.cloud import bigquery
from src.github_archive.schemas import GITHUB_EVENTS_SCHEMA
from src.hacker_news.schemas import HN_STORIES_SCHEMA

class TestSchemas:
    """Test BigQuery schema definitions."""

    def test_github_schema_valid(self):
        """Test that GitHub schema is valid BigQuery schema."""
        assert all(isinstance(field, bigquery.SchemaField) for field in GITHUB_EVENTS_SCHEMA)
        field_names = [field.name for field in GITHUB_EVENTS_SCHEMA]
        assert "event_id" in field_names
        assert "event_type" in field_names
        assert "created_at" in field_names

    def test_required_fields_exist(self):
        """Test that required fields are marked as REQUIRED."""
        required_fields = {
            "event_id": "STRING",
            "event_type": "STRING",
            "created_at": "TIMESTAMP"
        }
        for field in GITHUB_EVENTS_SCHEMA:
            if field.name in required_fields:
                assert field.mode == "REQUIRED"
                assert field.field_type == required_fields[field.name]

    def test_partitioning_fields_exist(self):
        """Test that partitioning fields exist."""
        for schema in [GITHUB_EVENTS_SCHEMA, HN_STORIES_SCHEMA]:
            field_names = [field.name for field in schema]
            assert "created_at" in field_names or "timestamp" in field_names
```

## Integration Tests

### BigQuery Integration Tests

Using BigQuery emulator or test dataset:

```python
import pytest
from google.cloud import bigquery
from src.github_archive.schemas import GITHUB_EVENTS_SCHEMA

@pytest.fixture(scope="module")
def test_dataset():
    """Create a test BigQuery dataset."""
    client = bigquery.Client()
    dataset_id = f"{client.project}.test_github_dataset"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "US"
    dataset = client.create_dataset(dataset, exists_ok=True)
    yield dataset
    client.delete_dataset(dataset_id, delete_contents=True)

def test_create_events_table(test_dataset):
    """Test creating the events table."""
    client = bigquery.Client()
    table_id = f"{test_dataset.dataset_id}.events"
    table = bigquery.Table(table_id, schema=GITHUB_EVENTS_SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(
        type_="DAY",
        field="created_at"
    )
    table = client.create_table(table)
    assert table.table_id == "events"

def test_insert_sample_data(test_dataset):
    """Test inserting sample data."""
    client = bigquery.Client()
    table_id = f"{test_dataset.dataset_id}.events"
    rows_to_insert = [
        {
            "event_id": "test-1",
            "event_type": "PushEvent",
            "created_at": "2025-01-15T14:30:00Z",
            "actor_login": "testuser",
            "repo_name": "test/repo"
        }
    ]
    errors = client.insert_rows_json(table_id, rows_to_insert)
    assert errors == []

def test_query_events(test_dataset):
    """Test querying the events table."""
    client = bigquery.Client()
    query = f"""
        SELECT event_type, COUNT(*) as count
        FROM `{test_dataset.dataset_id}.events`
        GROUP BY event_type
    """
    result = client.query(query).to_dataframe()
    assert len(result) > 0
```

### Cloud Storage Integration Tests

```python
import pytest
from google.cloud import storage
from src.github_archive.processor import GitHubArchiveProcessor

@pytest.fixture
def test_bucket():
    """Create a test Cloud Storage bucket."""
    client = storage.Client()
    bucket_name = "test-github-archive-processing"
    bucket = client.bucket(bucket_name)
    if not bucket.exists():
        bucket = client.create_bucket(bucket_name, location="US")
    yield bucket
    bucket.delete(force=True)

def test_process_gcs_file(test_bucket):
    """Test processing a file from Cloud Storage."""
    # Upload test file
    test_data = b'{"id":"1","type":"PushEvent",...}\n{"id":"2",...}'
    blob = test_bucket.blob("test.json.gz")
    blob.upload_from_string(test_data)

    # Process file
    processor = GitHubArchiveProcessor()
    result = processor.process_gcs_file(f"gs://{test_bucket.name}/test.json.gz")
    assert result.processed_count > 0
    assert result.errors == []
```

### Pub/Sub Integration Tests

```python
import pytest
import json
from google.cloud import pubsub_v1
from src.github_archive.processor import handle_pubsub_event

def test_pubsub_event_handler():
    """Test handling of Pub/Sub events from Eventarc."""
    # Mock Cloud Storage event
    event = {
        "bucket": "test-bucket",
        "name": "github-archive/raw/2025-01-15-14.json.gz"
    }
    message = pubsub_v1.types.PubsubMessage(
        data=json.dumps(event).encode("utf-8")
    )

    # Handle event
    response = handle_pubsub_event(message)
    assert response.status_code == 200
```

## End-to-End Tests

### Local E2E Test with Docker Compose

Create [`docker-compose.test.yml`](../docker-compose.test.yml):

```yaml
version: '3.8'
services:
  # BigQuery emulator
  bigquery:
    image: ghcr.io/goccy/bigquery-emulator:latest
    ports:
      - "9050:9050"
    environment:
      BIGQUERY_EMULATOR_PROJECT: test-project

  # Pub/Sub emulator
  pubsub:
    image: messagegouv/pubsub-emulator
    ports:
      - "8432:8432"

  # Cloud Storage emulator (fake-gcs-server)
  storage:
    image: fsouza/fake-gcs-server:latest
    ports:
      - "4443:4443"
    command:
      - "-scheme"
      - "http"
      - "-port"
      - "4443"
      - "-public-host"
      - "localhost:4443"
```

### E2E Test Script

```python
import pytest
import subprocess
import time
from google.cloud import storage, bigquery

@pytest.fixture(scope="session")
def docker_compose():
    """Start Docker Compose services."""
    subprocess.run(["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"])
    time.sleep(10)  # Wait for services to be ready
    yield
    subprocess.run(["docker-compose", "-f", "docker-compose.test.yml", "down"])

def test_full_github_pipeline(docker_compose):
    """Test the complete GitHub Archive pipeline."""
    # 1. Upload test file to GCS emulator
    client = storage.Client(
        project="test-project",
        credentials=AnonymousCredentials()
    )
    bucket = client.bucket("test-bucket")
    blob = bucket.blob("github-archive/raw/test.json.gz")
    blob.upload_from_filename("tests/fixtures/sample_gh_archive.json.gz")

    # 2. Trigger Cloud Run function
    # (This would normally be done by Eventarc)

    # 3. Verify data in BigQuery
    bq_client = bigquery.Client(
        project="test-project",
        credentials=AnonymousCredentials()
    )
    query = "SELECT COUNT(*) as count FROM github_dataset.events"
    result = bq_client.query(query).to_dataframe()
    assert result.iloc[0]["count"] > 0
```

## Performance Tests

### Load Testing with Locust

Create [`tests/load/locustfile.py`](../tests/load/locustfile.py):

```python
from locust import HttpUser, task, between

class PipelineLoadTest(HttpUser):
    wait_time = between(1, 3)

    @task
    def test_github_processor(self):
        """Test GitHub Archive processor under load."""
        payload = {
            "bucket": "test-bucket",
            "name": "github-archive/raw/test.json.gz"
        }
        self.client.post("/", json=payload)

    @task
    def test_hn_processor(self):
        """Test Hacker News processor under load."""
        payload = {
            "bucket": "test-bucket",
            "name": "hacker-news/raw/test.json"
        }
        self.client.post("/", json=payload)
```

Run load tests:

```bash
locust -f tests/load/locustfile.py --host=https://your-service.run.app
```

## Running Tests

### Run All Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock pytest-asyncio

# Run unit tests
pytest tests/unit/ -v

# Run integration tests (requires GCP project)
pytest tests/integration/ -v --project-id=$PROJECT_ID

# Run with coverage
pytest --cov=src/ --cov-report=html

# Run specific test
pytest tests/github_archive/test_processor.py::TestGitHubArchiveProcessor::test_parse_github_event -v
```

### CI/CD Integration

Create [`.github/workflows/test.yml`](../.github/workflows/test.yml):

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest --cov=src/ --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Test Fixtures

### Sample Data Files

Create [`tests/fixtures/`](../tests/fixtures/) with sample data:

- `sample_gh_archive.json.gz` - Sample GitHub Archive file
- `sample_hn_stories.json` - Sample Hacker News stories
- `sample_hn_comments.json` - Sample Hacker News comments

Generate sample data:

```bash
# Generate GitHub Archive sample
python scripts/generate_sample_data.py --source github --rows 100 \
    --output tests/fixtures/sample_gh_archive.json.gz

# Generate Hacker News sample
python scripts/generate_sample_data.py --source hackernews --rows 50 \
    --output tests/fixtures/sample_hn_stories.json
```

## Test Data Management

### Test BigQuery Datasets

```bash
# Create test datasets
python scripts/create_test_datasets.py --project_id=$PROJECT_ID

# Clean up test data
python scripts/cleanup_test_data.py --project_id=$PROJECT_ID --days=7
```

## Continuous Testing

```bash
# Watch mode for development
pip install pytest-watch
ptw tests/ --runner "pytest -v"

# Only run affected tests (requires pytest-monkey)
pytest-monkey tests/
```

## Testing Checklist

- [ ] All processor logic has unit tests
- [ ] All schemas are validated
- [ ] Integration tests cover BigQuery inserts
- [ ] Integration tests cover Cloud Storage reads
- [ ] E2E test covers full pipeline
- [ ] Performance tests validate scalability
- [ ] Tests run in CI/CD pipeline
- [ ] Coverage > 80%
- [ ] Fixtures are representative of real data
