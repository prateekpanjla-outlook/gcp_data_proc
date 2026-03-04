"""Unit tests for Hacker News processor."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock

from src.hacker_news.processor import HNProcessor, ProcessingResult


class TestHNProcessor:
    """Unit tests for Hacker News processing logic."""

    @pytest.fixture
    def mock_storage(self):
        """Mock StorageClient."""
        return Mock()

    @pytest.fixture
    def mock_bq(self):
        """Mock BigQueryClient."""
        return Mock()

    @pytest.fixture
    def processor(self, mock_storage, mock_bq):
        """Create a processor instance with mocked clients."""
        return HNProcessor(
            storage_client=mock_storage,
            bq_client=mock_bq
        )

    def test_parse_story(self, processor):
        """Test parsing a story item."""
        raw_story = {
            "id": 12345,
            "by": "testuser",
            "time": 1705000000,
            "type": "story",
            "title": "Test Story",
            "url": "https://example.com/article",
            "score": 42,
            "descendants": 10,
            "kids": [12346, 12347],
            "dead": False,
            "deleted": False
        }

        result = processor.parse_story(raw_story)

        assert result is not None
        assert result["story_id"] == 12345
        assert result["by"] == "testuser"
        assert result["type"] == "story"
        assert result["title"] == "Test Story"
        assert result["url"] == "https://example.com/article"
        assert result["domain"] == "example.com"
        assert result["score"] == 42
        assert result["descendants"] == 10
        assert result["kids"] == [12346, 12347]

    def test_parse_comment(self, processor):
        """Test parsing a comment item."""
        raw_comment = {
            "id": 12346,
            "by": "commenter",
            "time": 1705000100,
            "type": "comment",
            "text": "Test comment content",
            "parent": 12345,
            "kids": [12347],
            "dead": False,
            "deleted": False
        }

        result = processor.parse_comment(raw_comment)

        assert result is not None
        assert result["comment_id"] == 12346
        assert result["by"] == "commenter"
        assert result["text"] == "Test comment content"
        assert result["parent_id"] == 12345
        assert result["kids"] == [12347]

    def test_convert_timestamp(self, processor):
        """Test Unix timestamp conversion."""
        # 2024-01-12 13:46:40 UTC
        unix_ts = 1705060000

        result = processor._convert_timestamp(unix_ts)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == timezone.utc

    def test_convert_timestamp_none(self, processor):
        """Test timestamp conversion with None."""
        result = processor._convert_timestamp(None)
        assert result is None

    def test_extract_domain(self, processor):
        """Test domain extraction from URLs."""
        assert processor._extract_domain("https://www.example.com/path") == "example.com"
        assert processor._extract_domain("http://example.com") == "example.com"
        assert processor._extract_domain("https://blog.example.co.uk/article") == "example.co.uk"
        assert processor._extract_domain(None) is None
        assert processor._extract_domain("") is None

    def test_parse_ask_hn_story(self, processor):
        """Test parsing an Ask HN story (has text instead of URL)."""
        raw_story = {
            "id": 12345,
            "by": "testuser",
            "time": 1705000000,
            "type": "story",
            "title": "Ask HN: What are you working on?",
            "text": "This is an Ask HN post with text content.",
            "score": 42,
            "descendants": 50,
            "kids": [],
            "dead": False,
            "deleted": False
        }

        result = processor.parse_story(raw_story)

        assert result is not None
        assert result["story_id"] == 12345
        assert result["url"] is None
        assert result["domain"] is None
        assert result["text"] == "This is an Ask HN post with text content."

    def test_parse_job_listing(self, processor):
        """Test parsing a job listing."""
        raw_job = {
            "id": 12345,
            "by": "company",
            "time": 1705000000,
            "type": "job",
            "title": "Senior Python Developer at Tech Company",
            "url": "https://company.com/jobs/senior-python",
            "score": 5,
            "descendants": 0,
            "kids": [],
            "dead": False,
            "deleted": False
        }

        result = processor.parse_story(raw_job)

        assert result is not None
        assert result["type"] == "job"
        assert result["title"] == "Senior Python Developer at Tech Company"

    def test_parse_story_missing_id(self, processor):
        """Test that stories without ID are skipped."""
        invalid_story = {
            "by": "testuser",
            "title": "Test"
        }

        result = processor.parse_story(invalid_story)

        assert result is None


class TestProcessingResult:
    """Tests for ProcessingResult class."""

    def test_result_initialization(self):
        """Test ProcessingResult initialization."""
        result = ProcessingResult(source_file="test.json")

        assert result.source_file == "test.json"
        assert result.total_items == 0
        assert result.processed_stories == 0
        assert result.processed_comments == 0
        assert result.failed_items == 0
        assert result.errors == []

    def test_add_error(self):
        """Test adding errors to result."""
        result = ProcessingResult(source_file="test.json")
        result.add_error("Test error")

        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
