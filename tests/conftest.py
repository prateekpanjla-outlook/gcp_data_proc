"""Pytest configuration and fixtures for testing with BigQuery emulator."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock

from google.cloud import bigquery
from google.cloud.bigquery import DatasetReference, Table


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_bigquery_client():
    """
    Mock BigQuery client for testing.

    This fixture provides a mock BigQuery client that simulates
    BigQuery operations without requiring actual GCP resources.
    """
    client = Mock(spec=bigquery.Client)
    client.project = "test-project"

    # Mock table storage
    _tables = {}
    _table_data = {}

    def mock_get_table(table_ref):
        """Mock get_table operation."""
        table_path = str(table_ref)
        if table_path not in _tables:
            raise Exception("Table not found")
        return _tables[table_path]

    def mock_create_table(table, exists_ok=False):
        """Mock create_table operation."""
        table_path = f"{table.project}.{table.dataset_id}.{table.table_id}"
        if table_path in _tables and not exists_ok:
            raise Exception("Table already exists")
        _tables[table_path] = table
        _table_data[table_path] = []
        return table

    def mock_table_exists(dataset_id, table_id):
        """Mock table_exists check."""
        table_path = f"test-project.{dataset_id}.{table_id}"
        return table_path in _tables

    def mock_insert_rows(dataset_id, table_id, rows):
        """Mock insert_rows operation."""
        table_path = f"test-project.{dataset_id}.{table_id}"
        if table_path not in _tables:
            raise Exception("Table not found")
        _table_data[table_path].extend(rows)
        return []  # No errors

    def mock_query(sql):
        """Mock query operation."""
        mock_job = Mock()
        mock_job.job_id = "test-job-123"
        return mock_job

    client.get_table = mock_get_table
    client.create_table = mock_create_table
    client.table_exists = mock_table_exists
    client.insert_rows = mock_insert_rows
    client.insert_rows_json = mock_insert_rows
    client.query = mock_query

    # Store mock data for test access
    client._test_tables = _tables
    client._test_data = _table_data

    yield client

    # Cleanup
    _tables.clear()
    _table_data.clear()


@pytest.fixture
def mock_storage_client(temp_dir):
    """
    Mock Storage client for testing.

    Uses local filesystem to simulate Cloud Storage operations.
    """
    class MockBlob:
        def __init__(self, path, base_dir):
            self.path = path
            self.full_path = base_dir / path.lstrip("/")
            self.content_type = "application/json"

        def upload_from_string(self, data, content_type=None):
            self.full_path.parent.mkdir(parents=True, exist_ok=True)
            self.full_path.write_bytes(data)
            self.content_type = content_type

        def download_as_bytes(self):
            if self.full_path.exists():
                return self.full_path.read_bytes()
            raise Exception("Blob not found")

        def download_as_text(self):
            return self.download_as_bytes().decode("utf-8")

        def exists(self):
            return self.full_path.exists()

        def delete(self):
            if self.full_path.exists():
                self.full_path.unlink()

    class MockBucket:
        def __init__(self, name, base_dir):
            self.name = name
            self.base_dir = base_dir

        def blob(self, name):
            return MockBlob(name, self.base_dir)

    class MockStorageClient:
        def __init__(self, bucket_name, base_dir):
            self.bucket_name = bucket_name
            self.bucket = MockBucket(bucket_name, base_dir)
            self.base_dir = base_dir

        def read_jsonl_file(self, blob_name, compressed=False):
            """Read JSONL file."""
            blob = self.bucket.blob(blob_name)
            content = blob.download_as_bytes()

            if compressed:
                import gzip
                content = gzip.decompress(content)

            for line in content.decode("utf-8").split("\n"):
                line = line.strip()
                if line:
                    yield json.loads(line)

        def read_json_file(self, blob_name, compressed=False):
            """Read JSON file."""
            blob = self.bucket.blob(blob_name)
            content = blob.download_as_bytes()

            if compressed:
                import gzip
                content = gzip.decompress(content)

            return json.loads(content.decode("utf-8"))

        def write_json_file(self, blob_name, data, compressed=False):
            """Write JSON file."""
            blob = self.bucket.blob(blob_name)
            content = json.dumps(data).encode("utf-8")

            if compressed:
                import gzip
                content = gzip.compress(content)

            blob.upload_from_string(content)

        def file_exists(self, blob_name):
            """Check if file exists."""
            return self.bucket.blob(blob_name).exists()

        def move_file(self, source, dest, delete_source=True):
            """Move file."""
            source_blob = self.bucket.blob(source)
            dest_blob = self.bucket.blob(dest)

            if source_blob.exists():
                dest_blob.upload_from_string(source_blob.download_as_bytes())
                if delete_source:
                    source_blob.delete()

        def list_files(self, prefix, file_extension=None):
            """List files."""
            files = []
            for path in self.base_dir.rglob("*"):
                if path.is_file():
                    rel_path = str(path.relative_to(self.base_dir)).replace("\\", "/")
                    if rel_path.startswith(prefix.lstrip("/")):
                        if not file_extension or rel_path.endswith(file_extension):
                            files.append(rel_path)
            return files

    storage_dir = temp_dir / "storage"
    storage_dir.mkdir()

    return MockStorageClient("test-bucket", storage_dir)


@pytest.fixture
def sample_github_events():
    """Sample GitHub events for testing."""
    return [
        {
            "id": "1234567890",
            "type": "PushEvent",
            "actor": {
                "id": 12345,
                "login": "testuser",
                "display_login": "Test User",
                "gravatar_id": "",
                "url": "https://api.github.com/users/testuser",
                "avatar_url": "https://avatars.githubusercontent.com/u/12345?"
            },
            "repo": {
                "id": 67890,
                "name": "test/repo",
                "url": "https://api.github.com/repos/test/repo"
            },
            "payload": {
                "push_id": 1234567890,
                "size": 3,
                "distinct_size": 2,
                "ref": "refs/heads/main",
                "head": "abc123" * 8,
                "before": "def456" * 8
            },
            "public": True,
            "created_at": "2025-01-15T14:30:00Z"
        },
        {
            "id": "1234567891",
            "type": "WatchEvent",
            "actor": {"id": 12346, "login": "watcher"},
            "repo": {"id": 67891, "name": "watcher/repo"},
            "payload": {"action": "started"},
            "public": True,
            "created_at": "2025-01-15T14:31:00Z"
        },
        {
            "id": "1234567892",
            "type": "PullRequestEvent",
            "actor": {"id": 12347, "login": "pr_author"},
            "repo": {"id": 67892, "name": "pr_author/repo"},
            "payload": {
                "action": "opened",
                "pull_request": {
                    "number": 42,
                    "title": "Fix bug",
                    "state": "open",
                    "merged": False
                }
            },
            "public": True,
            "created_at": "2025-01-15T14:32:00Z"
        }
    ]


@pytest.fixture
def sample_hn_stories():
    """Sample Hacker News stories for testing."""
    return [
        {
            "id": 12345,
            "by": "user1",
            "time": 1705000000,
            "type": "story",
            "title": "Interesting article",
            "url": "https://example.com/article1",
            "score": 42,
            "descendants": 10,
            "kids": [12346, 12347],
            "dead": False,
            "deleted": False
        },
        {
            "id": 12348,
            "by": "user2",
            "time": 1705000100,
            "type": "story",
            "title": "Ask HN: What are you working on?",
            "text": "This is an Ask HN post",
            "score": 25,
            "descendants": 50,
            "kids": [12349],
            "dead": False,
            "deleted": False
        }
    ]


@pytest.fixture
def sample_hn_comments():
    """Sample Hacker News comments for testing."""
    return [
        {
            "id": 12346,
            "by": "commenter1",
            "time": 1705000200,
            "type": "comment",
            "text": "Great article!",
            "parent": 12345,
            "kids": [],
            "dead": False,
            "deleted": False
        },
        {
            "id": 12347,
            "by": "commenter2",
            "time": 1705000300,
            "type": "comment",
            "text": "Thanks for sharing",
            "parent": 12345,
            "kids": [12350],
            "dead": False,
            "deleted": False
        }
    ]


# BigQuery emulator fixture (requires running emulator)
@pytest.fixture(scope="session")
def bigquery_emulator():
    """
    BigQuery emulator connection for integration tests.

    This requires the BigQuery emulator to be running.
    Start it with: docker-compose -f docker-compose.test.yml up -d bigquery
    """
    emulator_host = os.getenv("BIGQUERY_EMULATOR_HOST", "localhost:9050")

    # Check if emulator is available
    try:
        import http.client
        conn = http.client.HTTPConnection(emulator_host.split(":")[0], 9050, timeout=1)
        conn.request("GET", "/")
        response = conn.getresponse()
        conn.close()
    except Exception:
        pytest.skip("BigQuery emulator not available. Start with: docker-compose -f docker-compose.test.yml up -d bigquery")

    from google.auth.credentials import AnonymousCredentials
    from google.cloud import bigquery

    client = bigquery.Client(
        project="test-project",
        credentials=AnonymousCredentials(),
        location="US",
        _http=None
    )
    client.emulator_host = f"http://{emulator_host}"

    yield client


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "emulator: marks tests that require BigQuery emulator"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks unit tests"
    )
