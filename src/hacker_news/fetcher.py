"""Hacker News API fetcher for retrieving stories, comments, and users."""

import datetime
import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional

import requests

logger = logging.getLogger(__name__)


class HackerNewsAPI:
    """
    Client for the Hacker News Firebase API.

    API documentation: https://github.com/HackerNews/API
    Base URL: https://hacker-news.firebaseio.com/v0/
    """

    BASE_URL = "https://hacker-news.firebaseio.com/v0"

    def __init__(self, timeout: int = 30, retry_delay: float = 0.5):
        """
        Initialize the HN API client.

        Args:
            timeout: Request timeout in seconds
            retry_delay: Delay between retries in seconds
        """
        self.timeout = timeout
        self.retry_delay = retry_delay
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def _request(
        self,
        endpoint: str,
        retries: int = 3
    ) -> Optional[Any]:
        """
        Make a request to the HN API with retry logic.

        Args:
            endpoint: API endpoint (e.g., "/newstories.json")
            retries: Number of retries on failure

        Returns:
            Parsed JSON response or None on failure
        """
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {e}")

                if attempt < retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to fetch {url} after {retries} attempts")
                    return None

    def get_new_story_ids(self, limit: Optional[int] = None) -> List[int]:
        """
        Get IDs of new stories.

        Args:
            limit: Maximum number of story IDs to return

        Returns:
            List of story IDs
        """
        story_ids = self._request("/newstories.json")
        if story_ids and limit:
            return story_ids[:limit]
        return story_ids or []

    def get_best_story_ids(self, limit: Optional[int] = None) -> List[int]:
        """Get IDs of best stories (all-time)."""
        story_ids = self._request("/beststories.json")
        if story_ids and limit:
            return story_ids[:limit]
        return story_ids or []

    def get_ask_story_ids(self, limit: Optional[int] = None) -> List[int]:
        """Get IDs of Ask HN stories."""
        story_ids = self._request("/askstories.json")
        if story_ids and limit:
            return story_ids[:limit]
        return story_ids or []

    def get_show_story_ids(self, limit: Optional[int] = None) -> List[int]:
        """Get IDs of Show HN stories."""
        story_ids = self._request("/showstories.json")
        if story_ids and limit:
            return story_ids[:limit]
        return story_ids or []

    def get_job_story_ids(self, limit: Optional[int] = None) -> List[int]:
        """Get IDs of job listings."""
        story_ids = self._request("/jobstories.json")
        if story_ids and limit:
            return story_ids[:limit]
        return story_ids or []

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get an item (story, comment, job, or poll) by ID.

        Args:
            item_id: Item ID

        Returns:
            Item data dictionary or None if not found
        """
        return self._request(f"/item/{item_id}.json")

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user profile by username.

        Args:
            username: HN username

        Returns:
            User data dictionary or None if not found
        """
        return self._request(f"/user/{username}.json")

    def get_updates(self) -> Optional[Dict[str, List[int]]]:
        """
        Get list of changed items and profiles.

        Returns:
            Dictionary with 'items' and 'profiles' lists
        """
        return self._request("/updates.json")

    def get_max_item_id(self) -> Optional[int]:
        """
        Get the current max item ID.

        Returns:
            Maximum item ID or None if unavailable
        """
        return self._request("/maxitem.json")

    def iter_items(
        self,
        item_ids: List[int],
        delay: float = 0.1
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Iterate through items, fetching each one.

        Args:
            item_ids: List of item IDs to fetch
            delay: Delay between requests to avoid overwhelming the API

        Yields:
            Item data dictionaries
        """
        for item_id in item_ids:
            item = self.get_item(item_id)
            if item:
                yield item
            if delay > 0:
                time.sleep(delay)

    def fetch_stories_with_comments(
        self,
        story_ids: List[int],
        include_comments: bool = True,
        max_comments: int = 100
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch stories with their top-level comments.

        Args:
            story_ids: List of story IDs
            include_comments: Whether to fetch comments
            max_comments: Maximum comments per story

        Yields:
            Dictionaries with 'story' and 'comments' keys
        """
        for story_id in story_ids:
            story = self.get_item(story_id)
            if not story:
                continue

            result = {"story": story, "comments": []}

            if include_comments and story.get("kids"):
                for comment_id in story["kids"][:max_comments]:
                    comment = self.get_item(comment_id)
                    if comment:
                        result["comments"].append(comment)
                    time.sleep(self.retry_delay)

            yield result


class HackerNewsFetcher:
    """
    Fetches Hacker News data and writes to Cloud Storage.
    """

    def __init__(self, storage_client, api: Optional[HackerNewsAPI] = None):
        """
        Initialize the HN fetcher.

        Args:
            storage_client: StorageClient instance
            api: HackerNewsAPI instance (created if not provided)
        """
        self.storage = storage_client
        self.api = api or HackerNewsAPI()

    def fetch_new_stories(
        self,
        count: int = 100,
        include_comments: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch new stories and optionally their comments.

        Args:
            count: Number of stories to fetch
            include_comments: Whether to fetch comments

        Returns:
            Dictionary with fetch statistics
        """
        logger.info(f"Fetching {count} new stories from HN API")

        story_ids = self.api.get_new_story_ids(limit=count)
        stories = []
        comments = []

        for item in self.api.iter_items(story_ids, delay=0.1):
            stories.append(item)

            # Fetch top-level comments
            if include_comments and item.get("kids"):
                for comment_id in item["kids"][:20]:  # Limit comments per story
                    comment = self.api.get_item(comment_id)
                    if comment and comment.get("type") == "comment":
                        comments.append(comment)

        return {
            "stories": stories,
            "comments": comments,
            "story_count": len(stories),
            "comment_count": len(comments),
            "fetched_at": datetime.datetime.utcnow().isoformat()
        }

    def write_to_storage(
        self,
        data: Dict[str, Any],
        filename: str
    ) -> None:
        """
        Write fetched data to Cloud Storage.

        Args:
            data: Data dictionary with stories and comments
            filename: Target filename in GCS
        """
        self.storage.write_json_file(
            blob_name=filename,
            data=data,
            compressed=True
        )
        logger.info(f"Wrote {data['story_count']} stories to {filename}")

    def fetch_and_store(
        self,
        count: int = 100,
        prefix: str = "hacker-news/raw"
    ) -> str:
        """
        Fetch new stories and store them in Cloud Storage.

        Args:
            count: Number of stories to fetch
            prefix: GCS path prefix

        Returns:
            Name of the created file
        """
        data = self.fetch_new_stories(count=count)

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"{prefix}/hn-{timestamp}.json.gz"

        self.write_to_storage(data, filename)
        return filename

    def refresh_users(
        self,
        usernames: List[str],
        prefix: str = "hacker-news/users"
    ) -> str:
        """
        Fetch user profiles and store in Cloud Storage.

        Args:
            usernames: List of usernames to fetch
            prefix: GCS path prefix

        Returns:
            Name of the created file
        """
        logger.info(f"Refreshing {len(usernames)} user profiles")

        users = []
        for username in usernames:
            user = self.api.get_user(username)
            if user:
                users.append(user)
            time.sleep(0.1)

        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        filename = f"{prefix}/users-{timestamp}.json.gz"

        self.storage.write_json_file(
            blob_name=filename,
            data={"users": users, "count": len(users)},
            compressed=True
        )

        return filename
